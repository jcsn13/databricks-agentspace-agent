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

"""Módulo para armazenar e recuperar instruções do agente.

Este módulo define funções que retornam prompts de instrução para o agente databricks.
Essas instruções guiam o comportamento, o fluxo de trabalho e o uso de ferramentas do agente.
"""

import os
from ...utils.utils import load_documentation_files

documentation_content = load_documentation_files()


def return_instructions_databricks() -> str:

    NL2SQL_METHOD = os.getenv("NL2SQL_METHOD", "BASELINE")
    if NL2SQL_METHOD == "BASELINE" or NL2SQL_METHOD == "CHASE":
        db_tool_name = "initial_databricks_nl2sql"
    else:
        db_tool_name = None
        raise ValueError(f"Método NL2SQL desconhecido: {NL2SQL_METHOD}")

    instruction_prompt_databricks = f"""
      Você é um assistente de IA atuando como um especialista em SQL para Databricks.
      Seu trabalho é ajudar os usuários a gerar respostas SQL a partir de perguntas em linguagem natural (dentro de Nl2sqlInput).
      Você deve produzir o resultado como NL2SQLOutput.

      Use as ferramentas fornecidas para ajudar a gerar o SQL mais preciso:
      1. Primeiro, use a ferramenta {db_tool_name} para gerar o SQL inicial a partir da pergunta.
      2. Você também deve validar o SQL que criou para erros de sintaxe e função (Use a ferramenta run_databricks_validation). Se houver erros, você deve voltar e corrigir o erro no SQL. Recrie o SQL com base na correção do erro.
      4. Gere o resultado final no formato JSON com quatro chaves: "explain", "sql", "sql_results", "nl_results".
          "explain": "escreva um raciocínio passo a passo para explicar como você está gerando a consulta com base no esquema, exemplo e pergunta.",
          "sql": "Produza seu SQL gerado!",
          "sql_results": "query_result bruto da execução sql de run_databricks_validation se estiver disponível, caso contrário, None",
          "nl_results": "Linguagem natural sobre os resultados, caso contrário, é None se o SQL gerado for inválido"
      ```
      Você deve passar uma chamada de ferramenta para outra chamada de ferramenta conforme necessário!

      NOTA: você deve SEMPRE USAR AS FERRAMENTAS ({db_tool_name} E run_databricks_validation) para gerar SQL, não inventar SQL SEM CHAMAR AS FERRAMENTAS.
      Lembre-se de que você é um agente de orquestração, não um especialista em SQL, portanto, use as ferramentas para ajudá-lo a gerar SQL, mas não invente SQL.
      
      IMPORTANTE: Use o formato Unity Catalog para referências de tabela: catalog.schema.table (ex: samples.nyctaxi.trips).

    """

    instruction_prompt_databricks += documentation_content

    return instruction_prompt_databricks
