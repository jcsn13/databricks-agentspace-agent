"""
Manual OAuth M2M token generation utilities for Databricks.

This module implements manual OAuth token generation following the official
Databricks documentation for M2M authentication.
"""

import os
import time
import logging
import requests
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

        # Create resilient session with retries and timeouts
        self._session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        """Create a requests session with retry logic and timeouts."""
        session = requests.Session()

        # Configure proxy settings from environment variables if present
        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY", http_proxy)  # Fallback to HTTP_PROXY

        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy

            session.proxies.update(proxies)
            logger.info(
                f"Configured session to use proxy: {proxies.get('https', proxies.get('http'))}"
            )

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
            allowed_methods=["POST"],  # Only retry POST requests
        )

        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

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
            logger.info(f"Attempting OAuth token request to: {auth_url}")

            # Make token request with resilient session and timeouts
            response = self._session.post(
                auth_url,
                data=data,
                timeout=(10, 30),  # 10s connect timeout, 30s read timeout
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Databricks-Agent/1.0",
                },
            )

            logger.info(f"OAuth request completed with status: {response.status_code}")
            response.raise_for_status()  # Raise exception for HTTP errors

            # Parse response
            token_data = response.json()
            access_token = token_data["access_token"]

            logger.info("Successfully generated OAuth access token")
            return access_token

        except requests.exceptions.Timeout as e:
            error_msg = f"OAuth request timed out after 30 seconds: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to Databricks OAuth endpoint: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"OAuth request failed: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except KeyError as e:
            error_msg = f"Invalid OAuth response format - missing {e}: {response.text if 'response' in locals() else 'Unknown'}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during OAuth token generation: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

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
