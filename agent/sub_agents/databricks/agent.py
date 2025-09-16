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

"""Database Agent: get data from database (Databricks) using NL2SQL."""

import os

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from . import tools
from .chase_sql import chase_db_tools
from .prompts import return_instructions_databricks

NL2SQL_METHOD = os.getenv("NL2SQL_METHOD", "BASELINE")


def setup_before_agent_call(callback_context: CallbackContext) -> None:
    """Setup the agent."""
    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = tools.get_database_settings(
            callback_context
        )

    # Run connectivity test on first setup
    if "connectivity_tested" not in callback_context.state:
        try:
            from .connectivity_test import (
                run_connectivity_test,
                log_connectivity_results,
            )
            import logging

            logger = logging.getLogger(__name__)
            logger.info("Running Databricks connectivity test...")

            results = run_connectivity_test()
            log_connectivity_results(results)

            # Store results in state
            callback_context.state["connectivity_tested"] = True
            callback_context.state["connectivity_results"] = results

            # Log critical finding about IP usage
            if "external_ip" in results.get("tests", {}):
                ip_test = results["tests"]["external_ip"]
                if ip_test.get("success"):
                    if ip_test.get("is_using_static_ip"):
                        logger.info("✅ Traffic is using our static IPs!")
                    else:
                        logger.warning(
                            f"⚠️ Traffic is NOT using our static IPs! Using: {ip_test.get('external_ip')}"
                        )
        except Exception as e:
            logger.warning(f"Connectivity test failed: {e}")
            callback_context.state["connectivity_tested"] = True


database_agent = Agent(
    model=os.getenv("DATABRICKS_AGENT_MODEL"),
    name="database_agent",
    instruction=return_instructions_databricks(),
    tools=[
        (
            chase_db_tools.initial_databricks_nl2sql
            if NL2SQL_METHOD == "CHASE"
            else tools.initial_databricks_nl2sql
        ),
        tools.run_databricks_validation,
    ],
    before_agent_callback=setup_before_agent_call,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
