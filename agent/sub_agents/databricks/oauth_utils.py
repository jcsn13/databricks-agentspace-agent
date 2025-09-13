"""
Manual OAuth M2M token generation utilities for Databricks.

This module implements manual OAuth token generation following the official
Databricks documentation for M2M authentication.
"""

import time
import logging
import requests
from typing import Optional, Dict, Any
from ...utils.utils import get_env_var

logger = logging.getLogger(__name__)


class DatabricksOAuthManager:
    """Manages manual OAuth M2M token generation and refresh for Databricks."""

    def __init__(self):
        """Initialize the OAuth manager with environment variables."""
        self.workspace_url = get_env_var("DATABRICKS_HOST")
        self.client_id = get_env_var("DATABRICKS_CLIENT_ID")
        self.client_secret = get_env_var("DATABRICKS_CLIENT_SECRET")

        # Remove https:// prefix if present for token endpoint
        self.workspace_host = self.workspace_url.replace("https://", "")

        # Token cache
        self._token_cache = {}
        self._token_expiry = {}

    def get_oauth_token(
        self, workspace_url: str, client_id: str, client_secret: str
    ) -> str:
        """
        Get OAuth access token for Databricks workspace.

        Implementation based on official Databricks documentation:
        https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m#manually-generate-oauth-m2m-access-tokens

        Args:
            workspace_url: Databricks workspace URL
            client_id: Service principal client ID
            client_secret: Service principal OAuth secret

        Returns:
            OAuth access token

        Raises:
            Exception: If token generation fails
        """
        # Construct token endpoint URL
        auth_url = f"{workspace_url}/oidc/v1/token"

        # Prepare request data
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "all-apis",  # Scope for access to all Databricks APIs
        }

        try:
            # Make token request
            response = requests.post(auth_url, data=data)
            response.raise_for_status()  # Raise exception for HTTP errors

            # Parse response
            token_data = response.json()
            access_token = token_data["access_token"]

            logger.info("Successfully generated OAuth access token")
            return access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get OAuth token: {e}")
            raise Exception(f"OAuth token generation failed: {e}")
        except KeyError as e:
            logger.error(f"Invalid token response format: {e}")
            raise Exception(f"Invalid token response: {e}")

    def get_cached_token(self) -> str:
        """
        Get cached OAuth token, refreshing if necessary.

        Tokens are valid for 1 hour, so we cache and refresh as needed.

        Returns:
            Valid OAuth access token
        """
        cache_key = f"{self.workspace_host}:{self.client_id}"
        current_time = time.time()

        # Check if we have a valid cached token
        if (
            cache_key in self._token_cache
            and cache_key in self._token_expiry
            and current_time < self._token_expiry[cache_key]
        ):
            logger.debug("Using cached OAuth token")
            return self._token_cache[cache_key]

        # Generate new token
        logger.info("Generating new OAuth token")
        token = self.get_oauth_token(
            self.workspace_url, self.client_id, self.client_secret
        )

        # Cache token (expires in 1 hour = 3600 seconds, we refresh 5 minutes early)
        self._token_cache[cache_key] = token
        self._token_expiry[cache_key] = current_time + 3300  # 55 minutes

        return token

    def get_workspace_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for WorkspaceClient with manual token.

        Uses only the token to avoid conflicts with environment variables.

        Returns:
            Configuration dict for WorkspaceClient
        """
        token = self.get_cached_token()

        # Use only host and token to avoid OAuth env var conflicts
        return {"host": self.workspace_url, "token": token}

    def get_sql_connection_config(self) -> Dict[str, Any]:
        """
        Get configuration for SQL connector with manual token.

        Returns:
            Configuration dict for databricks.sql.connect()
        """
        token = self.get_cached_token()

        return {
            "server_hostname": self.workspace_host,
            "http_path": get_env_var("DATABRICKS_SQL_WAREHOUSE_PATH"),
            "access_token": token,
        }


# Global OAuth manager instance
_oauth_manager = None


def get_oauth_manager() -> DatabricksOAuthManager:
    """Get the global OAuth manager instance."""
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = DatabricksOAuthManager()
    return _oauth_manager
