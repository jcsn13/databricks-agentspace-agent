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

"""
Deployment script for Databricks SQL Agent to Google Cloud Agent Engine and AgentSpace.

This script:
1. Deploys the agent to Vertex AI Agent Engine using ADK
2. Creates OAuth authorization in AgentSpace
3. Registers the agent in AgentSpace for enterprise discovery
4. Saves deployment state for later undeployment

Usage:
    python deployment/deploy.py
"""

import os
import sys
import json
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv
import vertexai
from vertexai.preview import reasoning_engines
from vertexai import agent_engines
from google.cloud import storage
from google.api_core import exceptions as google_exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path for proper package imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DeploymentError(Exception):
    """Custom exception for deployment errors"""

    pass


class DatabricksAgentDeployer:
    """Handles deployment of Databricks SQL Agent to Agent Engine and AgentSpace"""

    def __init__(self, use_network_attachment: bool = False):
        """Initialize deployer with environment configuration"""
        load_dotenv()

        # Required environment variables
        self.project_id = self._get_env_var("GOOGLE_CLOUD_PROJECT")
        self.location = self._get_env_var("GOOGLE_CLOUD_LOCATION")
        self.bucket_name = self._get_env_var("GOOGLE_CLOUD_STORAGE_BUCKET")

        # Network attachment configuration for static IP
        self.use_network_attachment = use_network_attachment
        self.network_attachment_id = os.getenv("NETWORK_ATTACHMENT_ID")
        self.static_ips = (
            os.getenv("STATIC_IPS", "").split(",") if os.getenv("STATIC_IPS") else []
        )

        # AgentSpace configuration
        self.agentspace_app_id = self._get_env_var("AGENTSPACE_APP_ID")
        self.agent_display_name = self._get_env_var("AGENT_DISPLAY_NAME")
        self.agent_description = self._get_env_var("AGENT_DESCRIPTION")
        self.agent_icon_uri = self._get_env_var("AGENT_ICON_URI")

        # OAuth configuration for Databricks M2M
        self.databricks_oauth_client_id = self._get_env_var("DATABRICKS_CLIENT_ID")
        self.databricks_oauth_client_secret = self._get_env_var(
            "DATABRICKS_CLIENT_SECRET"
        )
        self.databricks_workspace_host = self._get_env_var("DATABRICKS_HOST").replace(
            "https://", ""
        )
        self.authorization_id = os.getenv("AUTHORIZATION_ID", "databricks-agent-auth")

        # Environment variables to pass to agent (M2M OAuth)
        self.agent_env_vars = {
            "DATABRICKS_HOST": os.getenv("DATABRICKS_HOST"),
            "DATABRICKS_CLIENT_ID": os.getenv("DATABRICKS_CLIENT_ID"),
            "DATABRICKS_CLIENT_SECRET": os.getenv("DATABRICKS_CLIENT_SECRET"),
            "DATABRICKS_SQL_WAREHOUSE_PATH": os.getenv("DATABRICKS_SQL_WAREHOUSE_PATH"),
            "DATABRICKS_CATALOG": os.getenv("DATABRICKS_CATALOG"),
            "DATABRICKS_SCHEMA": os.getenv("DATABRICKS_SCHEMA"),
            "ROOT_AGENT_MODEL": os.getenv("ROOT_AGENT_MODEL"),
            "DATABRICKS_AGENT_MODEL": os.getenv("DATABRICKS_AGENT_MODEL"),
            "ANALYTICS_AGENT_MODEL": os.getenv("ANALYTICS_AGENT_MODEL"),
            "BASELINE_NL2SQL_MODEL": os.getenv("BASELINE_NL2SQL_MODEL"),
            "NL2SQL_METHOD": os.getenv("NL2SQL_METHOD"),
            "CODE_INTERPRETER_EXTENSION_NAME": os.getenv(
                "CODE_INTERPRETER_EXTENSION_NAME"
            ),
        }

        # Filter out None and empty string values
        self.agent_env_vars = {
            k: v for k, v in self.agent_env_vars.items() if v is not None and v != ""
        }

        # Deployment state
        self.state_file = Path("deployment/.deployment_state.json")
        self.deployed_agent = None
        self.authorization_created = False

        logger.info(f"Deployer initialized for project: {self.project_id}")

    def _get_env_var(self, name: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(name)
        if not value:
            raise DeploymentError(f"Required environment variable {name} not set")
        return value

    def _get_access_token(self) -> str:
        """Get Google Cloud access token"""
        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise DeploymentError(f"Failed to get access token: {e}")

    def setup_staging_bucket(self) -> str:
        """Setup or verify staging bucket exists"""
        logger.info(f"Setting up staging bucket: {self.bucket_name}")

        storage_client = storage.Client(project=self.project_id)

        try:
            bucket = storage_client.lookup_bucket(self.bucket_name)
            if bucket:
                logger.info(f"Staging bucket gs://{self.bucket_name} already exists")
            else:
                logger.info(f"Creating staging bucket: gs://{self.bucket_name}")
                new_bucket = storage_client.create_bucket(
                    self.bucket_name, project=self.project_id, location=self.location
                )

                # Enable uniform bucket-level access
                new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
                new_bucket.patch()
                logger.info(
                    f"Created staging bucket with uniform access: gs://{new_bucket.name}"
                )

        except google_exceptions.Forbidden as e:
            raise DeploymentError(
                f"Permission denied for bucket {self.bucket_name}: {e}"
            )
        except google_exceptions.Conflict as e:
            logger.warning(f"Bucket conflict (may exist in another project): {e}")
        except Exception as e:
            raise DeploymentError(f"Failed to setup staging bucket: {e}")

        return f"gs://{self.bucket_name}"

    def deploy_to_agent_engine(self) -> str:
        """Deploy agent to Vertex AI Agent Engine"""
        logger.info("Deploying to Vertex AI Agent Engine...")

        try:
            # Setup staging bucket
            staging_bucket_uri = self.setup_staging_bucket()

            # Initialize Vertex AI (legacy API for compatibility)
            vertexai.init(
                project=self.project_id,
                location=self.location,
                staging_bucket=staging_bucket_uri,
            )

            # Import the root agent
            try:
                from agent.agent import root_agent
            except ImportError as e:
                raise DeploymentError(f"Failed to import root_agent: {e}")

            # Wrap agent with AdkApp
            adk_app = reasoning_engines.AdkApp(
                agent=root_agent,
                enable_tracing=True,
            )

            # Prepare requirements - Updated to latest versions
            requirements = [
                # Core Google ADK Framework
                "google-adk>=1.0.0",
                "google-genai>=0.8.0",
                "google-api-core>=2.0.0",
                # Vertex AI Agent Engine (Deployment)
                "google-cloud-aiplatform[adk,agent_engines]>=1.60.0",
                "google-cloud-storage>=2.10.0",
                # Databricks Integration
                "databricks-sdk>=0.20.0",
                "databricks-sql-connector>=3.0.0",
                # HTTP Client for API calls and Image Downloads
                "httpx>=0.24.0",
                "requests>=2.31.0",
                # Environment and Configuration
                "python-dotenv>=1.0.0",
                # Additional Dependencies for Agent Framework
                "typing-extensions>=4.0.0",
                "pydantic>=2.0.0",
                # ChaseSQL and SQL Processing Dependencies
                "immutabledict>=4.2.0",
                "regex>=2024.11.0",
                "sqlglot>=26.10.0",
                "db-dtypes>=1.4.0",
                "tabulate>=0.9.0",
                "absl-py>=2.2.0",
            ]

            # Deploy to Agent Engine
            logger.info("Creating Agent Engine deployment...")

            # Prepare deployment arguments (legacy API format)
            # Use relative path from project root to ensure proper package structure
            deploy_kwargs = {
                "agent_engine": adk_app,
                "requirements": requirements,
                "extra_packages": [
                    "agent"
                ],  # Relative path preserves package structure
                "env_vars": self.agent_env_vars,
            }

            # Add network attachment if available for static IP support
            if self.use_network_attachment and self.network_attachment_id:
                # Simplified PSC config - just network attachment for VPC access
                psc_config = {"network_attachment": self.network_attachment_id}
                deploy_kwargs["psc_interface_config"] = psc_config

                # Get proxy IP from environment (set after Terraform deployment)
                proxy_ip = os.getenv("PROXY_INTERNAL_IP")
                if proxy_ip:
                    # Add proxy environment variables to force traffic through proxy
                    proxy_url = f"http://{proxy_ip}:3128"
                    self.agent_env_vars.update(
                        {
                            "HTTP_PROXY": proxy_url,
                            "HTTPS_PROXY": proxy_url,
                            "NO_PROXY": "localhost,127.0.0.1,metadata.google.internal",
                        }
                    )
                    logger.info(f"Configured HTTP proxy: {proxy_url}")
                else:
                    logger.warning(
                        "PROXY_INTERNAL_IP not set - agent will not use proxy"
                    )

                logger.info(
                    f"Using network attachment for VPC access: {self.network_attachment_id}"
                )

                if self.static_ips:
                    logger.info(f"Static IPs (via proxy): {', '.join(self.static_ips)}")

            # Use legacy API for compatibility
            self.deployed_agent = agent_engines.create(**deploy_kwargs)

            resource_name = self.deployed_agent.resource_name
            logger.info(f"Successfully deployed to Agent Engine: {resource_name}")
            return resource_name

        except Exception as e:
            logger.error(f"Agent Engine deployment error details: {e}")
            raise DeploymentError(f"Agent Engine deployment failed: {e}")

    # OAuth authorization functions removed - not needed for M2M OAuth

    def register_in_agentspace(
        self, agent_resource_name: str, access_token: str
    ) -> str:
        """Register agent in AgentSpace (M2M OAuth - no authorizations needed)"""
        logger.info("Registering agent in AgentSpace with M2M OAuth...")

        agents_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/"
            f"projects/{self.project_id}/locations/global/collections/default_collection/"
            f"engines/{self.agentspace_app_id}/assistants/default_assistant/agents"
        )

        payload = {
            "displayName": self.agent_display_name,
            "description": self.agent_description,
            "icon": {"uri": self.agent_icon_uri},
            "adk_agent_definition": {
                "tool_settings": {"tool_description": self.agent_description},
                "provisioned_reasoning_engine": {
                    "reasoning_engine": agent_resource_name
                },
                # No authorizations needed for M2M OAuth
            },
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": self.project_id,
        }

        try:
            response = requests.post(agents_url, json=payload, headers=headers)

            if response.status_code in [200, 201]:
                agent_data = response.json()
                agent_id = agent_data.get("name", "").split("/")[-1]
                logger.info(f"Agent registered in AgentSpace: {agent_id}")
                return agent_id
            else:
                raise DeploymentError(
                    f"AgentSpace registration failed: {response.status_code} - {response.text}"
                )

        except requests.RequestException as e:
            raise DeploymentError(f"Failed to register in AgentSpace: {e}")

    def save_deployment_state(self, agent_resource_name: str, agent_id: str):
        """Save deployment state for undeployment (M2M OAuth - no authorization needed)"""
        state_data = {
            "deployment_timestamp": datetime.now().isoformat(),
            "project_id": self.project_id,
            "location": self.location,
            "agent_resource_name": agent_resource_name,
            "agent_id": agent_id,
            "agentspace_app_id": self.agentspace_app_id,
            "agent_display_name": self.agent_display_name,
            "oauth_mode": "m2m",  # Track that this uses M2M OAuth
        }

        # Ensure deployment directory exists
        self.state_file.parent.mkdir(exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(state_data, f, indent=2)

        logger.info(f"Deployment state saved to: {self.state_file}")

    def rollback_deployment(self):
        """Rollback deployment in case of partial failure"""
        logger.warning("Rolling back deployment due to failure...")

        try:
            if self.deployed_agent:
                logger.info("Deleting Agent Engine deployment...")
                self.deployed_agent.delete(force=True)
                logger.info("Agent Engine deployment deleted")
        except Exception as e:
            logger.error(f"Failed to rollback Agent Engine deployment: {e}")

        # Clean up state file if it exists
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("Cleaned up deployment state file")

    def deploy(self) -> Dict[str, Any]:
        """Execute complete deployment process"""
        logger.info("Starting Databricks Agent deployment...")

        try:
            # Step 1: Deploy to Agent Engine
            agent_resource_name = self.deploy_to_agent_engine()

            # Step 2: Get access token
            access_token = self._get_access_token()

            # Step 3: Register in AgentSpace (no OAuth authorization needed for M2M)
            agent_id = self.register_in_agentspace(agent_resource_name, access_token)

            # Step 4: Save deployment state
            self.save_deployment_state(agent_resource_name, agent_id)

            result = {
                "status": "success",
                "agent_resource_name": agent_resource_name,
                "agent_id": agent_id,
                "agentspace_url": f"https://agentspace.google.com/studio/{self.project_id}",
                "message": "Databricks Agent successfully deployed to Agent Engine and registered in AgentSpace with M2M OAuth",
            }

            logger.info("Deployment completed successfully!")
            logger.info(f"Agent Resource: {agent_resource_name}")
            logger.info(f"AgentSpace Agent ID: {agent_id}")
            logger.info(f"AgentSpace URL: {result['agentspace_url']}")

            return result

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.rollback_deployment()
            raise


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Deploy Databricks SQL Agent to Google Cloud Agent Engine and AgentSpace"
    )
    parser.add_argument(
        "--network-attachment",
        action="store_true",
        help="Use network attachment for static IP support (for Terraform integration)",
    )

    args = parser.parse_args()

    try:
        deployer = DatabricksAgentDeployer(
            use_network_attachment=args.network_attachment
        )

        if args.network_attachment:
            logger.info(
                "Network attachment mode enabled - using static IP configuration"
            )
            if not os.getenv("NETWORK_ATTACHMENT_ID"):
                logger.warning("NETWORK_ATTACHMENT_ID environment variable not set")

        result = deployer.deploy()

        print("\n" + "=" * 60)
        print("🎉 DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        print(f"Agent Resource: {result['agent_resource_name']}")
        print(f"AgentSpace Agent ID: {result['agent_id']}")
        print(f"AgentSpace URL: {result['agentspace_url']}")

        if args.network_attachment and deployer.static_ips:
            print(f"\n🌐 Static IP Configuration:")
            print(f"Network Attachment: {deployer.network_attachment_id}")
            print(f"Static IPs: {', '.join(deployer.static_ips)}")
            print("These IPs can be allowlisted in Databricks for secure access.")

        print("\nYour Databricks SQL Agent is now available in Google AgentSpace!")
        print("=" * 60)

        return 0

    except DeploymentError as e:
        print(f"\n❌ Deployment Error: {e}")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
