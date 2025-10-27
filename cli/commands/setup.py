"""
Setup Command - First-Time Setup Wizard

Creates admin account if database is empty.
Guides users through initial configuration.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
import os
from pathlib import Path
import getpass
import re

import psycopg2
from rich.console import Console
from rich.prompt import Prompt, Confirm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.utils.config_loader import get_config
from cli.utils.output_formatter import print_success, print_error, print_warning, print_info, print_panel
from cli.utils.auth_manager import AuthManager

console = Console()


def run_setup():
    """
    Run first-time setup wizard

    Creates admin account if database is empty.
    """
    console.print("\n[bold cyan]Quant Platform - First-Time Setup[/bold cyan]\n")

    # Load configuration
    config = get_config()
    db_config = config.get_database_config()

    # Connect to database
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()
    except Exception as e:
        print_error("Failed to connect to database", str(e))
        print_info("Make sure PostgreSQL is running and database 'quant_platform' exists")
        print_info("Run: python3 scripts/init_postgres_schema.py")
        sys.exit(1)

    try:
        # Check if users table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        users_table_exists = cursor.fetchone()[0]

        if not users_table_exists:
            print_error("Users table does not exist")
            print_info("Run authentication schema initialization first:")
            print_info("  python3 scripts/init_auth_schema.py")
            sys.exit(1)

        # Check if users exist
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            print_warning("No users found in database.")
            console.print("Let's create your admin account.\n")

            # Create admin account
            admin_created = create_admin_account(cursor, conn)

            if admin_created:
                conn.commit()
                print_panel(
                    "[green]Setup complete![/green]\n\n"
                    "Next steps:\n"
                    "  1. Login: [cyan]python3 quant_platform.py auth login[/cyan]\n"
                    "  2. Run backtest: [cyan]python3 quant_platform.py backtest run --strategy momentum_value[/cyan]",
                    title="Success",
                    style="green"
                )
            else:
                print_error("Setup cancelled")
                sys.exit(1)

        else:
            print_info(f"Found {user_count} existing user(s).")
            console.print("Use [cyan]python3 quant_platform.py auth login[/cyan] to authenticate.\n")

            # Ask if user wants to create additional admin
            if Confirm.ask("Do you want to create another admin account?", default=False):
                admin_created = create_admin_account(cursor, conn)
                if admin_created:
                    conn.commit()
                    print_success("Additional admin account created successfully")

    except Exception as e:
        print_error("Setup failed", str(e))
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


def create_admin_account(cursor, conn) -> bool:
    """
    Create admin account interactively

    Args:
        cursor: Database cursor
        conn: Database connection

    Returns:
        True if account created, False if cancelled
    """
    # Get username
    while True:
        username = Prompt.ask("Admin username", default="admin")

        # Validate username (alphanumeric, underscore, hyphen only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            print_warning("Username can only contain letters, numbers, underscore, and hyphen")
            continue

        # Check if username exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s;", (username,))
        if cursor.fetchone()[0] > 0:
            print_warning(f"Username '{username}' already exists")
            continue

        break

    # Get email
    while True:
        email = Prompt.ask("Admin email")

        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            print_warning("Invalid email format")
            continue

        # Check if email exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s;", (email,))
        if cursor.fetchone()[0] > 0:
            print_warning(f"Email '{email}' already registered")
            continue

        break

    # Get password with confirmation
    while True:
        password = getpass.getpass("Admin password (min 8 characters): ")

        if len(password) < 8:
            print_warning("Password must be at least 8 characters")
            continue

        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print_warning("Passwords don't match. Try again.")
            continue

        break

    # Hash password
    password_hash = AuthManager.hash_password(password)

    # Create user in database
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, is_active, created_at)
            VALUES (%s, %s, %s, 'admin', true, NOW())
        """, (username, email, password_hash))

        print_success(f"Admin account created: {username}")
        return True

    except Exception as e:
        print_error("Failed to create admin account", str(e))
        return False


if __name__ == '__main__':
    run_setup()
