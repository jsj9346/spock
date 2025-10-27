"""
Authentication Routes

FastAPI routes for user authentication.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from loguru import logger
import bcrypt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.models.auth_models import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserInfo,
    ErrorResponse
)
from cli.utils.auth_manager import AuthManager


router = APIRouter()


# Dependency: Get database connection
def get_db():
    """Get database connection from pool."""
    from api.main import get_db_connection, release_db_connection

    conn = get_db_connection()
    try:
        yield conn
    finally:
        release_db_connection(conn)


# Dependency: Get current user from session token
def get_current_user(
    authorization: Optional[str] = Header(None),
    conn = Depends(get_db)
) -> UserInfo:
    """
    Get current authenticated user from session token.

    Args:
        authorization: Authorization header (Bearer token)
        conn: Database connection

    Returns:
        UserInfo object

    Raises:
        HTTPException: If token invalid or session expired
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    session_token = authorization.replace("Bearer ", "")

    cursor = conn.cursor()

    try:
        # Find session and user
        cursor.execute("""
            SELECT
                u.id, u.username, u.email, u.role, u.is_active, u.last_login, u.created_at,
                s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s
        """, (session_token,))

        result = cursor.fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token"
            )

        user_id, username, email, role, is_active, last_login, created_at, expires_at = result

        # Check if session expired
        if expires_at < datetime.now():
            # Delete expired session
            cursor.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
            conn.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please login again."
            )

        # Check if user is active
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )

        return UserInfo(
            id=user_id,
            username=username,
            email=email,
            role=role,
            is_active=is_active,
            last_login=last_login,
            created_at=created_at
        )

    finally:
        cursor.close()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, conn = Depends(get_db)):
    """
    Authenticate user with username and password.

    Creates a new session in the database and returns session token.

    Args:
        request: Login credentials
        conn: Database connection

    Returns:
        LoginResponse with session token and user info

    Raises:
        HTTPException: If credentials invalid or account disabled
    """
    cursor = conn.cursor()

    try:
        # Find user by username
        cursor.execute("""
            SELECT id, username, email, password_hash, role, is_active
            FROM users
            WHERE username = %s
        """, (request.username,))

        user = cursor.fetchone()

        if not user:
            # Log failed login attempt (without user_id since user not found)
            logger.warning(f"Login failed: user not found ({request.username})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        user_id, username, email, password_hash, role, is_active = user

        # Verify password
        if not AuthManager.verify_password(request.password, password_hash):
            # Log failed login attempt
            cursor.execute("""
                INSERT INTO audit_log (user_id, action, status, timestamp)
                VALUES (%s, 'login', 'failure', NOW())
            """, (user_id,))
            conn.commit()

            logger.warning(f"Login failed: invalid password (user_id={user_id})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Check if account is active
        if not is_active:
            logger.warning(f"Login failed: account disabled (user_id={user_id})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Contact administrator."
            )

        # Generate session token
        session_token = AuthManager.generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)  # 7-day session

        # Create session in database
        cursor.execute("""
            INSERT INTO sessions (user_id, session_token, expires_at, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (user_id, session_token, expires_at))

        # Update last login timestamp
        cursor.execute("""
            UPDATE users
            SET last_login = NOW()
            WHERE id = %s
        """, (user_id,))

        # Log successful login
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, status, timestamp)
            VALUES (%s, 'login', 'success', NOW())
        """, (user_id,))

        conn.commit()

        logger.info(f"Login successful: {username} (user_id={user_id})")

        return LoginResponse(
            session_token=session_token,
            expires_at=expires_at,
            user=UserInfo(
                id=user_id,
                username=username,
                email=email,
                role=role,
                is_active=is_active,
                last_login=datetime.now(),
                created_at=datetime.now()  # Actual value would need separate query
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to server error"
        )
    finally:
        cursor.close()


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    current_user: UserInfo = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    conn = Depends(get_db)
):
    """
    Logout current user by invalidating session.

    Args:
        current_user: Current authenticated user
        authorization: Authorization header with session token
        conn: Database connection

    Returns:
        LogoutResponse confirmation message
    """
    session_token = authorization.replace("Bearer ", "")

    cursor = conn.cursor()

    try:
        # Delete session from database
        cursor.execute("""
            DELETE FROM sessions
            WHERE session_token = %s
        """, (session_token,))

        # Log logout
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, status, timestamp)
            VALUES (%s, 'logout', 'success', NOW())
        """, (current_user.id,))

        conn.commit()

        logger.info(f"Logout successful: {current_user.username} (user_id={current_user.id})")

        return LogoutResponse(message="Logged out successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Logout error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to server error"
        )
    finally:
        cursor.close()


@router.get("/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: UserInfo = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserInfo object
    """
    logger.debug(f"Get user info: {current_user.username} (user_id={current_user.id})")
    return current_user
