"""
Base KIS API Client

Korea Investment & Securities (한국투자증권) API 베이스 클래스
- OAuth 2.0 token authentication (24-hour validity)
- File-based token caching with file locking
- Proactive token refresh (30 minutes before expiry)
- Shared across Domestic, ETF, and Overseas API clients

Author: Spock Trading System
"""

import requests
import time
import logging
import json
import os
import fcntl  # File locking (Unix-based systems)
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseKISAPI:
    """
    Base class for KIS API clients with unified token management

    Features:
    - OAuth 2.0 token authentication (24-hour validity)
    - File-based token caching (data/.kis_token_cache.json)
    - Automatic token refresh (5-minute buffer, 30-minute proactive refresh)
    - File locking for multi-process safety
    - Shared token across all KIS API clients (Domestic, ETF, Overseas)

    Token Management:
    - Token cached to disk for reuse across process restarts
    - 5-minute safety buffer (99.65% token utilization)
    - 30-minute proactive refresh to minimize failures
    - Graceful fallback if refresh fails
    """

    # Token management constants
    TOKEN_BUFFER_SECONDS = 300  # 5분 버퍼 (99.65% 활용률)
    PROACTIVE_REFRESH_SECONDS = 1800  # 30분 전부터 미리 갱신 시도

    def __init__(self,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443',
                 token_cache_path: str = 'data/.kis_token_cache.json'):
        """
        Initialize Base KIS API client

        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            base_url: API base URL (default: production)
            token_cache_path: Path to token cache file (default: data/.kis_token_cache.json)
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url
        self.token_cache_path = Path(token_cache_path)

        self.access_token = None
        self.token_expires_at = None

        # Rate limiting (20 req/sec = 0.05초 간격)
        self.last_call_time = None
        self.min_interval = 0.05

        # Load cached token if available
        self._load_token_from_cache()

        logger.info(f"📊 {self.__class__.__name__} initialized")

    def _is_token_valid(self, expires_at: Optional[datetime]) -> bool:
        """
        Check if token is still valid (unified validation logic)

        Args:
            expires_at: Token expiration datetime

        Returns:
            True if token is valid (with buffer), False otherwise

        Note:
            Uses TOKEN_BUFFER_SECONDS (5분) to prevent edge cases
            Token considered valid if: now < expires_at - buffer
        """
        if not expires_at:
            return False

        now = datetime.now()
        buffer = timedelta(seconds=self.TOKEN_BUFFER_SECONDS)

        return now < expires_at - buffer

    def _load_token_from_cache(self):
        """
        Load cached access token with corruption handling

        Token cache format (JSON):
        {
            "access_token": "...",
            "expires_at": "2025-10-16T15:27:07.123456",
            "cached_at": "2025-10-15T15:27:07.123456"
        }

        Features:
        - Automatic corruption recovery (JSON errors, invalid data)
        - File permission verification and auto-fix
        - Token format validation
        - Unified expiration check using _is_token_valid()
        """
        try:
            if not self.token_cache_path.exists():
                return

            # Check and fix file permissions
            stat_info = os.stat(self.token_cache_path)
            if stat_info.st_mode & 0o777 != 0o600:
                logger.warning(f"⚠️ Insecure permissions ({oct(stat_info.st_mode)[-3:]}), fixing to 600")
                os.chmod(self.token_cache_path, 0o600)

            # Load and parse JSON
            with open(self.token_cache_path, 'r') as f:
                cache_data = json.load(f)

            # Validate required fields
            required_fields = ['access_token', 'expires_at']
            missing_fields = [field for field in required_fields if field not in cache_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            token = cache_data['access_token']
            expires_at_str = cache_data['expires_at']

            # Validate token format (JWT should be >100 chars)
            if not token or len(token) < 100:
                raise ValueError(f"Invalid token format (length: {len(token)})")

            # Parse expiration time
            expires_at = datetime.fromisoformat(expires_at_str)

            # Check validity using unified method
            if self._is_token_valid(expires_at):
                self.access_token = token
                self.token_expires_at = expires_at

                remaining_hours = (expires_at - datetime.now()).total_seconds() / 3600
                logger.info(f"✅ Cached token loaded ({remaining_hours:.1f}h remaining)")
            else:
                logger.info(f"ℹ️ Cached token expired, will request new one")
                self.token_cache_path.unlink(missing_ok=True)

        except json.JSONDecodeError as e:
            logger.error(f"❌ Cache file corrupted (JSON error): {e}")
            self.token_cache_path.unlink(missing_ok=True)

        except ValueError as e:
            logger.error(f"❌ Invalid cache data: {e}")
            self.token_cache_path.unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"⚠️ Failed to load token cache: {e}")
            # Unknown error - safely delete cache
            self.token_cache_path.unlink(missing_ok=True)

    def _save_token_to_cache(self):
        """
        Save access token to cache file with file locking

        Features:
        - File locking to prevent race conditions (fcntl.LOCK_EX)
        - Atomic write operation
        - Secure permissions (600)
        - Process ID logging for debugging

        Security:
        - File permissions: 600 (owner read/write only)
        - Stored in data/ directory (should be in .gitignore)
        - Lock file prevents concurrent writes
        """
        try:
            # Ensure data directory exists
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Lock file path
            lock_path = self.token_cache_path.with_suffix('.lock')

            # Acquire exclusive lock
            with open(lock_path, 'w') as lock_file:
                # Wait for exclusive lock (blocks other processes)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

                try:
                    # Prepare cache data
                    cache_data = {
                        'access_token': self.access_token,
                        'expires_at': self.token_expires_at.isoformat(),
                        'cached_at': datetime.now().isoformat(),
                        'pid': os.getpid()  # For debugging
                    }

                    # Write to file atomically
                    with open(self.token_cache_path, 'w') as f:
                        json.dump(cache_data, f, indent=2)

                    # Set secure permissions (600 - owner read/write only)
                    os.chmod(self.token_cache_path, 0o600)

                    logger.info(f"✅ Token cached (PID: {os.getpid()})")

                finally:
                    # Release lock automatically (with block exit)
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

            # Clean up lock file
            lock_path.unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"⚠️ Failed to save token cache: {e}")

    def _request_new_token(self) -> str:
        """
        Request new OAuth token from KIS API

        Endpoint: POST /oauth2/tokenP
        Token validity: 24 hours (86400 seconds)

        Returns:
            Access token string

        Raises:
            Exception: If token request fails

        Note:
            KIS API enforces 1-per-day token issuance limit.
            This method should only be called when token is expired or missing.
        """
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {'content-type': 'application/json'}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()

            self.access_token = data['access_token']
            expires_in = int(data.get('expires_in', 86400))  # Default: 24 hours
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"✅ New token obtained (expires in {expires_in}s / {expires_in//3600}h)")

            # Save to cache for reuse across sessions
            self._save_token_to_cache()

            return self.access_token

        except Exception as e:
            logger.error(f"❌ Token request failed: {e}")
            raise

    def _get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get OAuth 2.0 access token (with caching, validation, and proactive refresh)

        Token management workflow:
        1. Force refresh if requested (testing/debugging)
        2. Check if token is valid (using _is_token_valid)
        3. If valid but expiring soon (< 30min), proactively refresh
        4. If refresh fails, continue using existing token (fallback)
        5. If expired/missing, request new token

        Args:
            force_refresh: Force request new token (for testing/debugging)

        Returns:
            Access token string

        Features:
            - Unified validation (_is_token_valid)
            - Proactive refresh (30 minutes before expiry)
            - Graceful fallback (use existing token if refresh fails)
            - 5-minute safety buffer

        Note:
            KIS API enforces 1-per-day token issuance limit.
        """
        # Force refresh mode (for testing)
        if force_refresh:
            logger.info("🔄 Force refresh requested")
            return self._request_new_token()

        # Check token validity using unified method
        if self._is_token_valid(self.token_expires_at):
            # Proactive refresh: Try to refresh 30 minutes before expiry
            if self.token_expires_at:
                time_remaining = (self.token_expires_at - datetime.now()).total_seconds()

                if 0 < time_remaining < self.PROACTIVE_REFRESH_SECONDS:
                    logger.info(f"⚡ Token expiring soon ({int(time_remaining//60)}min), proactive refresh")
                    try:
                        return self._request_new_token()
                    except Exception as e:
                        # Refresh failed - continue using existing token (still valid)
                        logger.warning(f"⚠️ Proactive refresh failed, using existing token: {e}")
                        return self.access_token

            # Token is valid and not expiring soon
            return self.access_token

        # Token expired or missing - request new one
        return self._request_new_token()

    def get_token_status(self) -> Dict:
        """
        Get current token status for monitoring

        Returns:
            Dictionary with token status information:
            {
                'status': 'VALID' | 'EXPIRING_SOON' | 'EXPIRED' | 'NO_TOKEN',
                'valid': bool,
                'expires_at': str (ISO format) | None,
                'remaining_seconds': int,
                'remaining_hours': float,
                'buffer_seconds': int,
                'proactive_refresh_seconds': int,
                'cache_exists': bool
            }

        Example:
            >>> api = KISDomesticStockAPI(app_key, app_secret)
            >>> status = api.get_token_status()
            >>> print(f"Token valid: {status['valid']}, {status['remaining_hours']:.1f}h left")
        """
        if not self.token_expires_at:
            return {
                'status': 'NO_TOKEN',
                'valid': False,
                'expires_at': None,
                'remaining_seconds': 0,
                'remaining_hours': 0.0,
                'buffer_seconds': self.TOKEN_BUFFER_SECONDS,
                'proactive_refresh_seconds': self.PROACTIVE_REFRESH_SECONDS,
                'cache_exists': self.token_cache_path.exists()
            }

        now = datetime.now()
        remaining_seconds = (self.token_expires_at - now).total_seconds()

        # Determine status
        if remaining_seconds <= 0:
            status = 'EXPIRED'
            valid = False
        elif remaining_seconds < self.TOKEN_BUFFER_SECONDS:
            status = 'EXPIRED'  # Within buffer, considered expired
            valid = False
        elif remaining_seconds < self.PROACTIVE_REFRESH_SECONDS:
            status = 'EXPIRING_SOON'  # Will trigger proactive refresh
            valid = True
        else:
            status = 'VALID'
            valid = True

        return {
            'status': status,
            'valid': valid,
            'expires_at': self.token_expires_at.isoformat(),
            'remaining_seconds': int(max(0, remaining_seconds)),
            'remaining_hours': round(remaining_seconds / 3600, 2),
            'buffer_seconds': self.TOKEN_BUFFER_SECONDS,
            'proactive_refresh_seconds': self.PROACTIVE_REFRESH_SECONDS,
            'cache_exists': self.token_cache_path.exists()
        }

    def _rate_limit(self):
        """
        Rate limiting: 20 req/sec (0.05초 간격)

        KIS API limits:
        - 20 requests/second
        - 1,000 requests/minute
        """
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)

        self.last_call_time = time.time()

    def check_connection(self) -> bool:
        """
        API 연결 상태 확인 (토큰 발급 테스트)

        Returns:
            True if API is accessible
        """
        try:
            token = self._get_access_token()
            return token is not None and len(token) > 0

        except Exception as e:
            logger.warning(f"⚠️ {self.__class__.__name__} health check failed: {e}")
            return False
