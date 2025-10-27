"""
API Client for Quant Platform CLI

Handles HTTP communication with FastAPI backend.
Includes retry logic, session token injection, and error handling.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.utils.config_loader import get_config
from cli.utils.auth_manager import AuthManager


class APIClient:
    """
    HTTP client for FastAPI backend communication.

    Features:
    - Automatic session token injection
    - Exponential backoff retry for 5xx errors
    - Session refresh on 401 Unauthorized
    - User-friendly error messages
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize API client.

        Args:
            base_url: API base URL (defaults to config)
            timeout: Request timeout in seconds
        """
        config = get_config()

        # Get base URL from config or parameter
        if base_url is None:
            base_url = config.get_api_base_url()

        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.auth_manager = AuthManager(mode=config.get_auth_mode())

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # Initial delay in seconds

        logger.debug(f"APIClient initialized: {self.base_url}")

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with session token.

        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Inject session token if authenticated
        session_token = self.auth_manager.get_session_token()
        if session_token:
            headers["Authorization"] = f"Bearer {session_token}"

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/auth/login")
            data: Request body data
            params: Query parameters
            headers: Additional headers (merged with defaults)

        Returns:
            Response JSON data

        Raises:
            APIError: On API errors (4xx, 5xx)
            ConnectionError: On connection failures
        """
        # Build full URL
        url = f"{self.base_url}{endpoint}"

        # Merge headers
        default_headers = self._get_headers()
        if headers:
            default_headers.update(headers)

        # Retry loop
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=data,
                        params=params,
                        headers=default_headers
                    )

                    # Handle success (2xx)
                    if 200 <= response.status_code < 300:
                        logger.debug(f"{method} {endpoint} → {response.status_code}")
                        return response.json() if response.content else {}

                    # Handle 401 Unauthorized (session expired)
                    if response.status_code == 401:
                        logger.warning("Session expired (401), clearing session")
                        self.auth_manager.clear_session()
                        raise APIError(
                            status_code=401,
                            message="Session expired. Please login again.",
                            details=response.text
                        )

                    # Handle 4xx Client Errors (non-retryable)
                    if 400 <= response.status_code < 500:
                        error_data = response.json() if response.content else {}
                        raise APIError(
                            status_code=response.status_code,
                            message=error_data.get('detail', 'Client error'),
                            details=response.text
                        )

                    # Handle 5xx Server Errors (retryable)
                    if response.status_code >= 500:
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(
                                f"Server error {response.status_code}, "
                                f"retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            raise APIError(
                                status_code=response.status_code,
                                message="Server error (max retries exceeded)",
                                details=response.text
                            )

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Timeout, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise ConnectionError(f"Request timeout after {self.max_retries} attempts")

            except httpx.ConnectError as e:
                raise ConnectionError(f"Failed to connect to API server: {e}")

            except httpx.HTTPError as e:
                raise ConnectionError(f"HTTP error: {e}")

        # Should not reach here
        raise APIError(status_code=500, message="Unexpected error")

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response JSON data
        """
        return await self.request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request.

        Args:
            endpoint: API endpoint
            data: Request body data

        Returns:
            Response JSON data
        """
        return await self.request("POST", endpoint, data=data)

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make PUT request.

        Args:
            endpoint: API endpoint
            data: Request body data

        Returns:
            Response JSON data
        """
        return await self.request("PUT", endpoint, data=data)

    async def delete(
        self,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Make DELETE request.

        Args:
            endpoint: API endpoint

        Returns:
            Response JSON data
        """
        return await self.request("DELETE", endpoint)


class APIError(Exception):
    """API error exception with status code and details."""

    def __init__(self, status_code: int, message: str, details: str = ""):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"{status_code}: {message}")


# Convenience function for synchronous usage
def sync_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """
    Synchronous wrapper for API requests.

    Args:
        method: HTTP method
        endpoint: API endpoint
        **kwargs: Additional arguments for request()

    Returns:
        Response JSON data
    """
    client = APIClient()
    return asyncio.run(client.request(method, endpoint, **kwargs))


if __name__ == '__main__':
    # Test API client
    async def test():
        client = APIClient()

        # Test connectivity
        try:
            response = await client.get("/health")
            print("✓ API server is healthy:", response)
        except Exception as e:
            print("✗ API server error:", e)

    asyncio.run(test())
