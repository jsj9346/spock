"""
Authentication Commands

Handles user authentication:
- login: Authenticate user and create session
- logout: Terminate session
- status: Show current authentication status

Supports both API and direct database access based on deployment mode.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
import os
from pathlib import Path
import getpass
from datetime import datetime, timedelta
import asyncio

import psycopg2
from rich.console import Console

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.utils.config_loader import get_config
from cli.utils.output_formatter import print_success, print_error, print_warning, print_info, print_key_value
from cli.utils.auth_manager import AuthManager
from cli.utils.api_client import APIClient, APIError

console = Console()


def login_via_api(username: str, password: str, auth_manager: AuthManager):
    """
    Login via FastAPI backend.

    Args:
        username: Username
        password: Password
        auth_manager: AuthManager instance
    """
    async def _login():
        client = APIClient()

        try:
            response = await client.post('/api/v1/auth/login', data={
                'username': username,
                'password': password
            })

            # Save session locally
            session_token = response['session_token']
            expires_at = datetime.fromisoformat(response['expires_at'])
            user = response['user']

            auth_manager.save_session(
                session_token=session_token,
                expires_at=expires_at,
                username=user['username'],
                email=user['email'],
                role=user['role']
            )

            print_success(f"Login successful. Welcome, {user['username']}!")
            print_info(f"Session expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

        except APIError as e:
            if e.status_code == 401:
                print_error("Invalid username or password")
            elif e.status_code == 403:
                print_error("Account is disabled. Contact administrator.")
            else:
                print_error(f"Login failed: {e.message}")
            sys.exit(1)

        except ConnectionError as e:
            print_error("Failed to connect to API server", str(e))
            print_info("Make sure FastAPI server is running: uvicorn api.main:app --reload")
            sys.exit(1)

        except Exception as e:
            print_error("Login failed", str(e))
            sys.exit(1)

    asyncio.run(_login())


def login_via_database(username: str, password: str, auth_manager: AuthManager, config):
    """
    Login via direct database access.

    Args:
        username: Username
        password: Password
        auth_manager: AuthManager instance
        config: Config instance
    """
    db_config = config.get_database_config()

    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()

        # Find user
        cursor.execute("""
            SELECT id, username, email, password_hash, role, is_active
            FROM users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        if not user:
            print_error("Invalid username or password")
            sys.exit(1)

        user_id, db_username, email, password_hash, role, is_active = user

        # Verify password
        if not AuthManager.verify_password(password, password_hash):
            print_error("Invalid username or password")

            # Log failed login attempt
            cursor.execute("""
                INSERT INTO audit_log (user_id, action, status, timestamp)
                VALUES (%s, 'login', 'failure', NOW())
            """, (user_id,))
            conn.commit()

            sys.exit(1)

        # Check if account is active
        if not is_active:
            print_error("Account is disabled. Contact administrator.")
            sys.exit(1)

        # Generate session token
        session_token = AuthManager.generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)  # 7 days

        # Create session in database
        cursor.execute("""
            INSERT INTO sessions (user_id, session_token, expires_at, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (user_id, session_token, expires_at))

        # Update last login
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

        # Save session locally
        auth_manager.save_session(
            session_token=session_token,
            expires_at=expires_at,
            username=db_username,
            email=email,
            role=role
        )

        print_success(f"Login successful. Welcome, {db_username}!")
        print_info(f"Session expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

    except psycopg2.Error as e:
        print_error("Database error during login", str(e))
        sys.exit(1)

    except Exception as e:
        print_error("Login failed", str(e))
        sys.exit(1)

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def login():
    """
    Authenticate user with username/password

    Creates session token stored in ~/.quant_platform/session.json
    """
    config = get_config()
    mode = config.get_mode()
    auth_mode = config.get_auth_mode()

    if auth_mode == 'local':
        print_warning("Authentication not required in local mode")
        return

    # Check if already logged in
    auth_manager = AuthManager(mode=auth_mode)
    if auth_manager.is_authenticated():
        current_user = auth_manager.get_current_user()
        print_info(f"Already logged in as: {current_user['username']}")

        from rich.prompt import Confirm
        if not Confirm.ask("Do you want to login as a different user?", default=False):
            return
        else:
            auth_manager.clear_session()

    console.print("\n[bold cyan]Quant Platform - Login[/bold cyan]\n")

    # Get credentials
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    if not username or not password:
        print_error("Username and password are required")
        sys.exit(1)

    # Route to API or database based on mode
    if mode == 'cloud':
        # Use API
        login_via_api(username, password, auth_manager)
    else:
        # Direct database access (local mode)
        login_via_database(username, password, auth_manager, config)


def logout_via_api(auth_manager: AuthManager):
    """
    Logout via FastAPI backend.

    Args:
        auth_manager: AuthManager instance
    """
    async def _logout():
        client = APIClient()

        try:
            await client.post('/api/v1/auth/logout')
            auth_manager.clear_session()
            print_success("Logged out successfully")

        except APIError as e:
            print_warning(f"Logout warning: {e.message}")
            auth_manager.clear_session()

        except Exception as e:
            print_warning(f"Failed to logout via API: {e}")
            auth_manager.clear_session()

    asyncio.run(_logout())


def logout_via_database(auth_manager: AuthManager, config):
    """
    Logout via direct database access.

    Args:
        auth_manager: AuthManager instance
        config: Config instance
    """
    session_token = auth_manager.get_session_token()

    if session_token:
        db_config = config.get_database_config()

        try:
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password']
            )
            cursor = conn.cursor()

            # Get user_id from session
            cursor.execute("""
                SELECT user_id FROM sessions WHERE session_token = %s
            """, (session_token,))

            result = cursor.fetchone()
            user_id = result[0] if result else None

            # Delete session from database
            cursor.execute("""
                DELETE FROM sessions WHERE session_token = %s
            """, (session_token,))

            # Log logout
            if user_id:
                cursor.execute("""
                    INSERT INTO audit_log (user_id, action, status, timestamp)
                    VALUES (%s, 'logout', 'success', NOW())
                """, (user_id,))

            conn.commit()

        except Exception as e:
            print_warning(f"Failed to delete session from database: {e}")

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

    # Clear local session
    auth_manager.clear_session()
    print_success("Logged out successfully")


def logout():
    """
    Terminate current session

    Deletes session token from database and local storage
    """
    config = get_config()
    mode = config.get_mode()
    auth_mode = config.get_auth_mode()

    if auth_mode == 'local':
        print_warning("Authentication not required in local mode")
        return

    auth_manager = AuthManager(mode=auth_mode)

    # Check if logged in
    if not auth_manager.is_authenticated():
        print_info("Not currently logged in")
        return

    # Route to API or database based on mode
    if mode == 'cloud':
        logout_via_api(auth_manager)
    else:
        logout_via_database(auth_manager, config)


def status():
    """
    Show current authentication status
    """
    config = get_config()
    auth_mode = config.get_auth_mode()

    console.print("\n[bold cyan]Authentication Status[/bold cyan]\n")

    status_data = {
        "Authentication Mode": auth_mode,
        "Deployment Mode": config.get_mode()
    }

    if auth_mode == 'local':
        status_data["Status"] = "No authentication required"
    else:
        auth_manager = AuthManager(mode=auth_mode)

        if auth_manager.is_authenticated():
            user = auth_manager.get_current_user()
            status_data["Status"] = "Authenticated"
            status_data["Username"] = user['username']
            status_data["Role"] = user['role']
            status_data["Session Expires"] = user['session_expires_at']
        else:
            status_data["Status"] = "Not authenticated"

    print_key_value(status_data)
    console.print()


if __name__ == '__main__':
    # Test commands
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'login':
            login()
        elif command == 'logout':
            logout()
        elif command == 'status':
            status()
