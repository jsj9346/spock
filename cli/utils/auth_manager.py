"""
Authentication Manager for Quant Platform CLI

Manages multi-mode authentication:
- Mode 1: Local (No Auth) - Direct database access
- Mode 2: Simple Auth - Username/password with session tokens
- Mode 3: AWS Auth - AWS CLI integration
- Mode 4: JWT Auth - Full authentication (future)

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import os
import sys
import json
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import bcrypt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class AuthManager:
    """
    Unified authentication manager supporting multiple modes.
    """

    SESSION_FILE = Path.home() / '.quant_platform' / 'session.json'

    def __init__(self, mode: str = "local"):
        """
        Initialize authentication manager.

        Args:
            mode: Authentication mode (local, simple, aws, jwt)
        """
        self.mode = mode
        self.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def authenticate(self) -> bool:
        """
        Check if user is authenticated based on mode.

        Returns:
            True if authenticated, False otherwise
        """
        if self.mode == "local":
            # No authentication needed for local mode
            return True

        elif self.mode in ["simple", "aws", "jwt"]:
            # Check for valid session
            session = self._load_session()
            if session:
                # Check expiration
                try:
                    expires_at = datetime.fromisoformat(session['expires_at'])
                    if expires_at > datetime.now():
                        return True
                    else:
                        # Session expired
                        self.clear_session()
                        return False
                except (KeyError, ValueError):
                    return False
            return False

        return False

    def get_session_token(self) -> Optional[str]:
        """
        Get current session token

        Returns:
            Session token if available, None otherwise
        """
        session = self._load_session()
        return session.get('session_token') if session else None

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user information

        Returns:
            User information dictionary or None
        """
        session = self._load_session()
        if session and self.authenticate():
            return {
                'username': session.get('username'),
                'email': session.get('email'),
                'role': session.get('role'),
                'session_expires_at': session.get('expires_at')
            }
        return None

    def save_session(self, session_token: str, expires_at: datetime,
                     username: str, email: str = "", role: str = "user"):
        """
        Save session information to local file

        Args:
            session_token: Session token
            expires_at: Session expiration datetime
            username: Username
            email: User email
            role: User role
        """
        session_data = {
            'session_token': session_token,
            'expires_at': expires_at.isoformat(),
            'username': username,
            'email': email,
            'role': role,
            'created_at': datetime.now().isoformat()
        }

        try:
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)

            # Set file permissions (owner read/write only)
            os.chmod(self.SESSION_FILE, 0o600)

        except Exception as e:
            print(f"Warning: Failed to save session: {e}", file=sys.stderr)

    def clear_session(self):
        """Delete session file"""
        try:
            if self.SESSION_FILE.exists():
                self.SESSION_FILE.unlink()
        except Exception as e:
            print(f"Warning: Failed to clear session: {e}", file=sys.stderr)

    def _load_session(self) -> Optional[Dict[str, Any]]:
        """
        Load session from local file

        Returns:
            Session dictionary or None
        """
        try:
            if not self.SESSION_FILE.exists():
                return None

            with open(self.SESSION_FILE, 'r') as f:
                return json.load(f)

        except Exception:
            return None

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt

        Args:
            password: Plaintext password

        Returns:
            Bcrypt password hash
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash

        Args:
            password: Plaintext password
            password_hash: Bcrypt hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False

    @staticmethod
    def generate_session_token() -> str:
        """
        Generate cryptographically secure session token

        Returns:
            64-character URL-safe token
        """
        return secrets.token_urlsafe(48)  # 48 bytes = 64 characters

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated

        Returns:
            True if authenticated, False otherwise
        """
        return self.authenticate()

    def get_database_credentials(self) -> Dict[str, str]:
        """
        Get database credentials based on authentication mode

        Returns:
            Database credentials dictionary
        """
        # For local mode, read from environment or config
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "quant_platform"),
            "user": os.getenv("DB_USER", os.getenv("USER", "postgres")),
            "password": os.getenv("DB_PASSWORD", "")
        }
