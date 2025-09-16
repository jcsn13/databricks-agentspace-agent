# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This file contains the tools used by the database agent."""

import datetime
import logging
import os
import re

from ...utils.utils import get_env_var
from google.adk.tools import ToolContext
from google.genai import Client
from databricks.sdk import WorkspaceClient
from databricks import sql

from .chase_sql import chase_constants
from .oauth_utils import get_oauth_manager
from .connectivity_test import run_connectivity_test, log_connectivity_results

# Databricks environment configuration
project = os.getenv("GOOGLE_CLOUD_PROJECT", None)
location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
llm_client = Client(vertexai=True, project=project, location=location)

MAX_NUM_ROWS = 80


def get_databricks_client(tool_context: ToolContext) -> WorkspaceClient:
    """Initializes and returns a Databricks WorkspaceClient.

    This function creates a Databricks WorkspaceClient using manual OAuth M2M authentication.
    The client uses manually generated access tokens with automatic refresh.
    If connection issues occur, it runs connectivity diagnostics.

    Args:
        tool_context: The context object for the tool (not used for manual auth).

    Returns:
        A `WorkspaceClient` instance configured with manual M2M OAuth authentication.
    """
    import os

    try:
        # Use manual OAuth token generation
        oauth_manager = get_oauth_manager()
        config = oauth_manager.get_workspace_client_config()

        # Temporarily mask OAuth env vars to avoid conflicts
        original_client_id = os.environ.get("DATABRICKS_CLIENT_ID")
        original_client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")

        try:
            # Remove OAuth env vars temporarily
            if "DATABRICKS_CLIENT_ID" in os.environ:
                del os.environ["DATABRICKS_CLIENT_ID"]
            if "DATABRICKS_CLIENT_SECRET" in os.environ:
                del os.environ["DATABRICKS_CLIENT_SECRET"]

            # Create client with only token authentication
            client = WorkspaceClient(**config)

            # Verify the client works by testing a simple operation
            # This will trigger any connection issues early
            try:
                # Simple test - get workspace info (minimal API call)
                workspace_info = client.workspace.get_status("/")
                logging.info("Databricks client successfully authenticated and tested")
            except Exception as test_error:
                logging.warning(
                    f"Databricks client created but failed connectivity test: {test_error}"
                )

        finally:
            # Restore env vars
            if original_client_id is not None:
                os.environ["DATABRICKS_CLIENT_ID"] = original_client_id
            if original_client_secret is not None:
                os.environ["DATABRICKS_CLIENT_SECRET"] = original_client_secret

        return client

    except Exception as e:
        logging.error(f"Failed to create Databricks client: {e}")

        # Run connectivity diagnostics to help troubleshoot
        logging.info("Running connectivity diagnostics...")
        try:
            connectivity_results = run_connectivity_test()
            log_connectivity_results(connectivity_results)

            # Store diagnostics in tool context for debugging
            tool_context.state["last_connectivity_test"] = connectivity_results

        except Exception as diag_error:
            logging.error(f"Failed to run connectivity diagnostics: {diag_error}")

        # Re-raise the original error with enhanced context
        raise Exception(
            f"Databricks client creation failed: {e}. "
            f"This may be due to network connectivity issues. "
            f"Check the connectivity test results in the logs above."
        )


def get_database_settings(tool_context: ToolContext) -> dict:
    """Retrieves database settings, initializing them if not already present.

    This function checks if the database settings are already loaded in the tool
    context's state. If not, it calls `update_database_settings` to fetch them
    and stores them in the state for subsequent use.

    Args:
        tool_context: The context object for the tool, used for state management.

    Returns:
        A dictionary containing the database settings.
    """
    if "database_settings" not in tool_context.state:
        tool_context.state["database_settings"] = update_database_settings(tool_context)
    return tool_context.state["database_settings"]


def update_database_settings(tool_context: ToolContext) -> dict:
    """Fetches and updates the database settings.

    This function retrieves the latest database schema (DDL) for the configured
    Databricks catalog and combines it with other settings, such as catalog and
    schema IDs, and constants required for ChaseSQL.

    Args:
        tool_context: The context object for the tool, used to get the Databricks
          client.

    Returns:
        A dictionary containing the updated database settings.
    """
    databricks_client = get_databricks_client(tool_context)
    catalog_name = get_env_var("DATABRICKS_CATALOG")
    schema_name = get_env_var("DATABRICKS_SCHEMA")

    ddl_schema = get_databricks_schema(
        catalog_name,
        schema_name,
        client=databricks_client,
    )

    database_settings = {
        "databricks_catalog": catalog_name,
        "databricks_schema": schema_name,
        "databricks_ddl_schema": ddl_schema,
        # Include ChaseSQL-specific constants for Databricks.
        **chase_constants.chase_sql_constants_dict,
    }
    return database_settings


def get_databricks_schema(catalog_name, schema_name, client=None):
    """Retrieves schema and generates DDL with example values for a Databricks catalog/schema.

    This function inspects a Databricks catalog and schema, extracts the schema for each table,
    and generates `CREATE TABLE` DDL statements. It also includes example rows
    (up to 5) as `INSERT INTO` statements to provide context on the data.

    Args:
        catalog_name: The name of the Databricks catalog (e.g., 'samples').
        schema_name: The name of the schema within the catalog (e.g., 'nyctaxi').
        client: An optional `WorkspaceClient` instance. If not provided, a new
          one will be created.

    Returns:
        A string containing the generated DDL statements for all tables in the
        catalog/schema.
    """
    if client is None:
        oauth_manager = get_oauth_manager()
        config = oauth_manager.get_workspace_client_config()

        # Temporarily mask OAuth env vars to avoid conflicts
        original_client_id = os.environ.get("DATABRICKS_CLIENT_ID")
        original_client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")

        try:
            # Remove OAuth env vars temporarily
            if "DATABRICKS_CLIENT_ID" in os.environ:
                del os.environ["DATABRICKS_CLIENT_ID"]
            if "DATABRICKS_CLIENT_SECRET" in os.environ:
                del os.environ["DATABRICKS_CLIENT_SECRET"]

            # Create client with only token authentication
            client = WorkspaceClient(**config)

        finally:
            # Restore env vars
            if original_client_id is not None:
                os.environ["DATABRICKS_CLIENT_ID"] = original_client_id
            if original_client_secret is not None:
                os.environ["DATABRICKS_CLIENT_SECRET"] = original_client_secret

    ddl_statements = ""

    try:
        # List tables in the specified catalog and schema
        tables = client.tables.list(catalog_name=catalog_name, schema_name=schema_name)

        for table_summary in tables:
            try:
                # Get detailed table information
                full_name = f"{catalog_name}.{schema_name}.{table_summary.name}"
                table_info = client.tables.get(full_name=full_name)

                # Skip views for now, focus on tables
                if table_info.table_type == "VIEW":
                    continue

                ddl_statement = f"CREATE OR REPLACE TABLE `{full_name}` (\n"

                # Add columns
                if table_info.columns:
                    for column in table_info.columns:
                        ddl_statement += f"  `{column.name}` {column.type_text}"
                        if column.comment:
                            ddl_statement += f" COMMENT '{column.comment}'"
                        ddl_statement += ",\n"

                    ddl_statement = ddl_statement[:-2] + "\n);\n\n"
                else:
                    ddl_statement += "\n);\n\n"

                # Add example values using SQL query
                try:
                    sample_query = f"SELECT * FROM {full_name} LIMIT 5"
                    sample_data = execute_sample_query(sample_query)

                    if sample_data:
                        ddl_statement += f"-- Example values for table `{full_name}`:\n"
                        for row in sample_data:
                            ddl_statement += f"INSERT INTO `{full_name}` VALUES\n"
                            example_row_str = "("
                            for value in row.values():
                                if isinstance(value, str):
                                    example_row_str += f"'{value}',"
                                elif value is None:
                                    example_row_str += "NULL,"
                                else:
                                    example_row_str += f"{value},"
                            example_row_str = example_row_str[:-1] + ");\n\n"
                            ddl_statement += example_row_str
                except Exception as e:
                    ddl_statement += f"-- Could not retrieve sample data: {str(e)}\n\n"

                ddl_statements += ddl_statement

            except Exception as e:
                logging.warning(
                    f"Could not process table {table_summary.name}: {str(e)}"
                )
                continue

    except Exception as e:
        logging.error(
            f"Could not list tables in {catalog_name}.{schema_name}: {str(e)}"
        )
        ddl_statements = f"-- Error retrieving schema: {str(e)}\n"

    return ddl_statements


def execute_sample_query(query):
    """Helper function to execute a sample query and return results."""
    try:
        # Connect using manual M2M OAuth authentication
        oauth_manager = get_oauth_manager()
        sql_config = oauth_manager.get_sql_connection_config()

        with sql.connect(**sql_config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()[:5]  # Limit to 5 sample rows

                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    result_rows = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            if isinstance(value, datetime.date):
                                row_dict[columns[i]] = value.strftime("%Y-%m-%d")
                            else:
                                row_dict[columns[i]] = value
                        result_rows.append(row_dict)
                    return result_rows

        return []
    except Exception as e:
        logging.warning(f"Could not execute sample query: {str(e)}")
        return []


def initial_databricks_nl2sql(
    question: str,
    tool_context: ToolContext,
) -> str:
    """Generates an initial SQL query from a natural language question.

    This function uses a large language model to convert a user's natural
    language question into a Databricks SQL query. It constructs a prompt that
    includes the database schema and the user's question to guide the model in
    generating a relevant and syntactically correct query.

    Args:
        question: The natural language question from the user.
        tool_context: The tool context, used to access database settings and
          store the generated SQL query.

    Returns:
        A string containing the generated SQL query.
    """

    prompt_template = """
Você é um especialista em SQL para Databricks encarregado de responder às perguntas dos usuários sobre tabelas do Databricks, gerando consultas SQL no dialeto Spark SQL/Databricks SQL. Sua tarefa é escrever uma consulta SQL do Databricks que responda à seguinte pergunta, utilizando o contexto fornecido.

**Diretrizes:**

- **Referência de Tabela:** Use o formato catalog.schema.table. Ex: `samples.nyctaxi.trips` ou `samples.bakehouse.customers`. As tabelas devem ser referenciadas usando nomes totalmente qualificados.
- **Junções (Joins):** Junte o mínimo de tabelas possível. Ao juntar tabelas, certifique-se de que todas as colunas de junção sejam do mesmo tipo de dados. Analise o banco de dados e o esquema da tabela fornecido para entender as relações entre colunas e tabelas.
- **Agregações:** Use todas as colunas não agregadas da instrução `SELECT` na cláusula `GROUP BY`.
- **Sintaxe SQL:** Retorne SQL sintática e semanticamente correto para Databricks SQL/Spark SQL com o mapeamento de relação apropriado (catalog.schema.table). Use a instrução SQL `AS` para atribuir um novo nome temporariamente a uma coluna de tabela ou até mesmo a uma tabela, sempre que necessário. Sempre coloque subconsultas e consultas de união entre parênteses.
- **Uso de Coluna:** Use *SOMENTE* os nomes de coluna (nome_da_coluna) mencionados no Esquema da Tabela. *NÃO* use nenhum outro nome de coluna. Associe `nome_da_coluna` mencionado no Esquema da Tabela apenas ao `nome_da_tabela` especificado no Esquema da Tabela.
- **FILTROS:** Você deve escrever a consulta de forma eficaz para reduzir e minimizar o total de linhas a serem retornadas. Por exemplo, você pode usar filtros (como `WHERE`, `HAVING`, etc.) e funções de agregação (como 'COUNT', 'SUM', etc.) na consulta SQL.
- **LIMITAR LINHAS:** O número máximo de linhas retornadas deve ser inferior a {MAX_NUM_ROWS}.

**Esquema:**

A estrutura do banco de dados é definida pelos seguintes esquemas de tabela (possivelmente com linhas de exemplo):

```
{SCHEMA}
```

**Pergunta em linguagem natural:**

```
{QUESTION}
```

**Pense Passo a Passo:** Considere cuidadosamente o esquema, a pergunta, as diretrizes e as melhores práticas descritas acima para gerar o SQL correto para o Databricks.

"""

    ddl_schema = get_database_settings(tool_context)["databricks_ddl_schema"]

    prompt = prompt_template.format(
        MAX_NUM_ROWS=MAX_NUM_ROWS, SCHEMA=ddl_schema, QUESTION=question
    )

    response = llm_client.models.generate_content(
        model=os.getenv("BASELINE_NL2SQL_MODEL"),
        contents=prompt,
        config={"temperature": 0.1},
    )

    sql = response.text
    if sql:
        sql = sql.replace("```sql", "").replace("```", "").strip()

    print("\n sql:", sql)

    tool_context.state["sql_query"] = sql

    return sql


def run_databricks_validation(
    sql_string: str,
    tool_context: ToolContext,
) -> dict:
    """Validates and executes a Databricks SQL query.

    This function first cleans up the provided SQL string, then checks for any
    disallowed DML/DDL operations. It then executes the query against Databricks.
    If the query is successful, it returns the results; otherwise, it returns an
    error message.

    Args:
        sql_string: The SQL query to validate and execute.
        tool_context: The tool context, used to get authentication tokens and
          store the query results.

    Returns:
        A dictionary containing either the 'query_result' on success or an
        'error_message' on failure.
    """

    def cleanup_sql(sql_string):
        """Processes the SQL string to get a printable, valid SQL string."""

        # 1. Remove backslashes escaping double quotes
        sql_string = sql_string.replace('\\"', '"')

        # 2. Remove backslashes before newlines (the key fix for this issue)
        sql_string = sql_string.replace("\\\n", "\n")

        # 3. Replace escaped single quotes
        sql_string = sql_string.replace("\\'", "'")

        # 4. Replace escaped newlines (those not preceded by a backslash)
        sql_string = sql_string.replace("\\n", "\n")

        # 5. Add limit clause if not present
        if "limit" not in sql_string.lower():
            sql_string = sql_string + " LIMIT " + str(MAX_NUM_ROWS)

        return sql_string

    logging.info("Validating SQL: %s", sql_string)
    sql_string = cleanup_sql(sql_string)
    logging.info("Validating SQL (after cleanup): %s", sql_string)

    final_result = {"query_result": None, "error_message": None}

    # More restrictive check for Databricks - disallow DML and DDL
    if re.search(
        r"(?i)(update|delete|drop|insert|create|alter|truncate|merge)", sql_string
    ):
        final_result["error_message"] = (
            "Invalid SQL: Contains disallowed DML/DDL operations."
        )
        return final_result

    try:
        # Connect to Databricks SQL warehouse using manual M2M OAuth
        oauth_manager = get_oauth_manager()
        sql_config = oauth_manager.get_sql_connection_config()

        with sql.connect(**sql_config) as connection:

            with connection.cursor() as cursor:
                cursor.execute(sql_string)

                # Fetch results
                rows = cursor.fetchall()[:MAX_NUM_ROWS]

                if rows:
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]

                    # Convert to list of dictionaries
                    result_rows = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            # Handle date conversion
                            if isinstance(value, datetime.date):
                                row_dict[columns[i]] = value.strftime("%Y-%m-%d")
                            else:
                                row_dict[columns[i]] = value
                        result_rows.append(row_dict)

                    final_result["query_result"] = result_rows
                    tool_context.state["query_result"] = result_rows
                else:
                    final_result["error_message"] = (
                        "Valid SQL. Query executed successfully (no results)."
                    )

    except Exception as e:
        final_result["error_message"] = f"Invalid SQL: {e}"

    print("\n run_databricks_validation final_result: \n", final_result)

    return final_result
