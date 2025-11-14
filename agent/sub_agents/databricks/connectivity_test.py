"""
Connectivity testing utilities for Databricks Agent.

This module provides tools to test network connectivity and diagnose
issues with static IP routing through NAT gateway.
"""

import os
import time
import logging
import requests
import socket
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ...utils.utils import get_env_var

logger = logging.getLogger(__name__)


class ConnectivityTester:
    """Test network connectivity to Databricks services."""

    def __init__(self):
        """Initialize connectivity tester."""
        self.workspace_url = get_env_var("DATABRICKS_HOST")
        self.workspace_host = self.workspace_url.replace("https://", "")

        # Create a simple session for testing
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Databricks-Connectivity-Test/1.0"})

    def test_dns_resolution(self) -> Dict[str, Any]:
        """Test DNS resolution for Databricks workspace."""
        try:
            logger.info(f"Testing DNS resolution for: {self.workspace_host}")
            start_time = time.time()

            # Resolve hostname to IP
            ip_address = socket.gethostbyname(self.workspace_host)
            resolution_time = time.time() - start_time

            logger.info(
                f"DNS resolution successful: {self.workspace_host} -> {ip_address}"
            )

            return {
                "success": True,
                "hostname": self.workspace_host,
                "ip_address": ip_address,
                "resolution_time_ms": round(resolution_time * 1000, 2),
                "message": f"Successfully resolved {self.workspace_host} to {ip_address}",
            }

        except socket.gaierror as e:
            error_msg = f"DNS resolution failed for {self.workspace_host}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "hostname": self.workspace_host,
                "ip_address": None,
                "error": str(e),
                "message": error_msg,
            }

    def test_basic_connectivity(self, timeout: int = 10) -> Dict[str, Any]:
        """Test basic HTTP connectivity to Databricks workspace."""
        try:
            logger.info(f"Testing basic connectivity to: {self.workspace_url}")
            start_time = time.time()

            # Test basic GET request to workspace root
            response = self.session.get(
                self.workspace_url, timeout=(timeout, timeout), allow_redirects=True
            )

            connection_time = time.time() - start_time

            logger.info(
                f"Basic connectivity test completed: Status {response.status_code}"
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "connection_time_ms": round(connection_time * 1000, 2),
                "headers": dict(response.headers),
                "message": f"Successfully connected to {self.workspace_url}",
            }

        except requests.exceptions.Timeout as e:
            error_msg = f"Connection timeout after {timeout}s: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "timeout",
                "timeout_seconds": timeout,
                "message": error_msg,
            }
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {e}"
            logger.error(error_msg)
            return {"success": False, "error": "connection_error", "message": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return {"success": False, "error": "unexpected_error", "message": error_msg}

    def test_oauth_endpoint(self, timeout: int = 30) -> Dict[str, Any]:
        """Test connectivity specifically to OAuth endpoint."""
        oauth_url = f"{self.workspace_url}/oidc/v1/token"

        try:
            logger.info(f"Testing OAuth endpoint connectivity: {oauth_url}")
            start_time = time.time()

            # Test POST request to OAuth endpoint (will fail auth but tests connectivity)
            response = self.session.post(
                oauth_url,
                data={"grant_type": "test"},  # Invalid data, just testing connectivity
                timeout=(timeout, timeout),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            connection_time = time.time() - start_time

            logger.info(
                f"OAuth endpoint connectivity test completed: Status {response.status_code}"
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "connection_time_ms": round(connection_time * 1000, 2),
                "message": f"Successfully reached OAuth endpoint (auth will fail with test data)",
            }

        except requests.exceptions.Timeout as e:
            error_msg = f"OAuth endpoint timeout after {timeout}s: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "timeout",
                "timeout_seconds": timeout,
                "message": error_msg,
            }
        except requests.exceptions.ConnectionError as e:
            error_msg = f"OAuth endpoint connection error: {e}"
            logger.error(error_msg)
            return {"success": False, "error": "connection_error", "message": error_msg}
        except Exception as e:
            error_msg = f"OAuth endpoint unexpected error: {e}"
            logger.error(error_msg)
            return {"success": False, "error": "unexpected_error", "message": error_msg}

    def test_external_ip_detection(self, timeout: int = 10) -> Dict[str, Any]:
        """Test what external IP address is being used for outbound connections."""
        ip_services = [
            "https://httpbin.org/ip",
            "https://api.ipify.org?format=json",
            "https://ifconfig.me/all.json",
        ]

        # Check if proxy is configured
        proxy_url = os.getenv("HTTP_PROXY")
        using_proxy = proxy_url is not None

        if using_proxy:
            logger.info(f"HTTP Proxy configured: {proxy_url}")
            # Configure session to use proxy
            self.session.proxies.update(
                {"http": proxy_url, "https": os.getenv("HTTPS_PROXY", proxy_url)}
            )

        for service_url in ip_services:
            try:
                logger.info(f"Testing external IP detection via: {service_url}")
                start_time = time.time()

                response = self.session.get(service_url, timeout=(timeout, timeout))
                connection_time = time.time() - start_time

                if response.status_code == 200:
                    data = response.json()
                    # Extract IP based on service response format
                    if "origin" in data:  # httpbin format
                        external_ip = data["origin"]
                    elif "ip" in data:  # ipify format
                        external_ip = data["ip"]
                    elif "ip_addr" in data:  # ifconfig.me format
                        external_ip = data["ip_addr"]
                    else:
                        external_ip = str(data)

                    logger.info(f"External IP detected: {external_ip}")

                    # Check if this is one of our static IPs
                    static_ips = [
                        "34.171.114.41",
                        "34.61.54.145",
                        "34.45.177.35",
                        "34.56.173.137",
                    ]
                    is_static_ip = any(ip in external_ip for ip in static_ips)

                    return {
                        "success": True,
                        "external_ip": external_ip,
                        "service_used": service_url,
                        "is_using_static_ip": is_static_ip,
                        "expected_static_ips": static_ips,
                        "connection_time_ms": round(connection_time * 1000, 2),
                        "message": f"External IP: {external_ip} - {'✅ Using our static IPs' if is_static_ip else '❌ NOT using our static IPs'}",
                    }

            except Exception as e:
                logger.warning(f"Failed to get IP from {service_url}: {e}")
                continue

        error_msg = "Failed to detect external IP from all services"
        logger.error(error_msg)
        return {
            "success": False,
            "error": "ip_detection_failed",
            "message": error_msg,
        }

    def run_full_connectivity_test(self) -> Dict[str, Any]:
        """Run comprehensive connectivity test."""
        logger.info("Starting comprehensive connectivity test")

        results = {
            "timestamp": time.time(),
            "workspace_url": self.workspace_url,
            "workspace_host": self.workspace_host,
            "tests": {},
        }

        # Test 1: DNS Resolution
        logger.info("Running DNS resolution test...")
        results["tests"]["dns_resolution"] = self.test_dns_resolution()

        # Test 2: External IP Detection - CRITICAL TEST
        logger.info("Running external IP detection test...")
        results["tests"]["external_ip"] = self.test_external_ip_detection()

        # Test 3: Basic Connectivity
        logger.info("Running basic connectivity test...")
        results["tests"]["basic_connectivity"] = self.test_basic_connectivity()

        # Test 4: OAuth Endpoint
        logger.info("Running OAuth endpoint connectivity test...")
        results["tests"]["oauth_endpoint"] = self.test_oauth_endpoint()

        # Overall status
        all_tests_passed = all(
            test_result.get("success", False)
            for test_result in results["tests"].values()
        )

        results["overall_success"] = all_tests_passed
        results["summary"] = self._generate_summary(results["tests"])

        logger.info(f"Connectivity test completed. Overall success: {all_tests_passed}")

        return results

    def _generate_summary(self, tests: Dict[str, Any]) -> str:
        """Generate a human-readable summary of test results."""
        summaries = []

        for test_name, result in tests.items():
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            message = result.get("message", "No details")
            summaries.append(f"{status} {test_name}: {message}")

        return "\n".join(summaries)


def run_connectivity_test() -> Dict[str, Any]:
    """Run a complete connectivity test and return results."""
    tester = ConnectivityTester()
    return tester.run_full_connectivity_test()


def log_connectivity_results(results: Dict[str, Any]) -> None:
    """Log connectivity test results in a readable format."""
    logger.info("=" * 60)
    logger.info("DATABRICKS CONNECTIVITY TEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Workspace: {results['workspace_url']}")
    logger.info(f"Timestamp: {time.ctime(results['timestamp'])}")
    logger.info(
        f"Overall Status: {'SUCCESS' if results['overall_success'] else 'FAILURE'}"
    )
    logger.info("-" * 60)
    logger.info("Test Details:")
    logger.info(results["summary"])
    logger.info("=" * 60)
