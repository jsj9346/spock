#!/usr/bin/env python3
"""
Quant Platform - Authentication Schema Initialization

Creates authentication tables (users, sessions, audit_log) for multi-mode authentication.

Supports:
- Mode 1: Local Personal (No Auth)
- Mode 2: Personal Cloud (Simple Auth) - Default
- Mode 3: AWS CLI Integration
- Mode 4: Commercial/Multi-User (Full Auth)

Usage:
    python3 scripts/init_auth_schema.py                    # Initialize schema
    python3 scripts/init_auth_schema.py --drop             # Drop tables first
    python3 scripts/init_auth_schema.py --validate         # Validate only

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import os
import sys
import argparse
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class AuthSchemaInitializer:
    """Initialize authentication schema for Quant Platform"""

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 5432,
                 database: str = 'quant_platform',
                 user: Optional[str] = None,
                 password: Optional[str] = None):
        """
        Initialize schema creator

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user (defaults to env POSTGRES_USER or current user)
            password: Database password (defaults to env POSTGRES_PASSWORD)
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user or os.getenv('POSTGRES_USER', os.getenv('USER'))
        self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor()
            logger.info(f"✅ Connected to PostgreSQL: {self.database}@{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔌 Connection closed")

    def execute_sql(self, sql_statement: str, description: str = ""):
        """
        Execute SQL statement with error handling

        Args:
            sql_statement: SQL to execute
            description: Human-readable description for logging
        """
        try:
            if description:
                logger.info(f"⚙️  {description}")
            self.cursor.execute(sql_statement)
            logger.info(f"✅ {description or 'SQL executed'}")
        except Exception as e:
            logger.error(f"❌ {description or 'SQL failed'}: {e}")
            raise

    def drop_auth_tables(self):
        """Drop authentication tables (use with caution)"""
        logger.warning("⚠️  Dropping authentication tables...")

        drop_statements = [
            "DROP TABLE IF EXISTS audit_log CASCADE;",
            "DROP TABLE IF EXISTS sessions CASCADE;",
            "DROP TABLE IF EXISTS users CASCADE;",
            "DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;",
            "DROP FUNCTION IF EXISTS cleanup_expired_sessions CASCADE;"
        ]

        for stmt in drop_statements:
            try:
                self.cursor.execute(stmt)
                logger.info(f"  Dropped: {stmt.split()[4]}")
            except Exception as e:
                logger.warning(f"  Skip: {e}")

        logger.info("🗑️  Authentication tables dropped")

    def create_users_table(self):
        """Create users table for multi-mode authentication"""
        sql_statement = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255),           -- bcrypt hash (NULL for AWS users)
            aws_arn VARCHAR(255) UNIQUE,          -- AWS IAM ARN (for AWS auth mode)
            aws_account_id VARCHAR(12),           -- AWS account ID
            role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
            is_active BOOLEAN DEFAULT true,       -- Account status
            last_login TIMESTAMP,                 -- Last successful login
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        COMMENT ON TABLE users IS 'User accounts for multi-mode authentication';
        COMMENT ON COLUMN users.password_hash IS 'bcrypt hash for Simple Auth mode';
        COMMENT ON COLUMN users.aws_arn IS 'AWS IAM ARN for AWS CLI auth mode';
        COMMENT ON COLUMN users.role IS 'User role: admin, user, analyst';
        """

        self.execute_sql(sql_statement, "Creating users table")

        # Create indexes
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "CREATE INDEX IF NOT EXISTS idx_users_aws_arn ON users(aws_arn) WHERE aws_arn IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;"
        ]

        for idx_stmt in index_statements:
            self.execute_sql(idx_stmt, f"Creating index")

    def create_sessions_table(self):
        """Create sessions table for session-based authentication"""
        sql_statement = """
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(64) UNIQUE NOT NULL,  -- Cryptographically secure token
            expires_at TIMESTAMP NOT NULL,              -- Session expiration (7 days default)
            created_at TIMESTAMP DEFAULT NOW()
        );

        COMMENT ON TABLE sessions IS 'Session tokens for authenticated users';
        COMMENT ON COLUMN sessions.session_token IS '64-character URL-safe token';
        COMMENT ON COLUMN sessions.expires_at IS 'Session expiration timestamp (7 days for Simple Auth, 1 hour for AWS)';
        """

        self.execute_sql(sql_statement, "Creating sessions table")

        # Create indexes
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);"
        ]

        for idx_stmt in index_statements:
            self.execute_sql(idx_stmt, f"Creating index")

    def create_audit_log_table(self):
        """Create audit_log table for security tracking"""
        sql_statement = """
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            action VARCHAR(100) NOT NULL,           -- 'login', 'logout', 'backtest_run', 'optimize', etc.
            resource VARCHAR(255),                  -- Resource affected (strategy name, backtest ID, etc.)
            timestamp TIMESTAMP DEFAULT NOW(),
            ip_address INET,                        -- Client IP address
            status VARCHAR(20) DEFAULT 'success'    -- 'success', 'failure'
        );

        COMMENT ON TABLE audit_log IS 'Security audit trail for all user actions';
        COMMENT ON COLUMN audit_log.action IS 'Action type: login, logout, backtest_run, optimize, etc.';
        COMMENT ON COLUMN audit_log.resource IS 'Resource identifier (strategy name, backtest ID)';
        COMMENT ON COLUMN audit_log.status IS 'Action result: success, failure';
        """

        self.execute_sql(sql_statement, "Creating audit_log table")

        # Create indexes
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_status ON audit_log(status) WHERE status = 'failure';"
        ]

        for idx_stmt in index_statements:
            self.execute_sql(idx_stmt, f"Creating index")

    def create_helper_functions(self):
        """Create helper functions and triggers"""

        # Trigger function to update updated_at column
        update_trigger_function = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """

        self.execute_sql(update_trigger_function, "Creating update_updated_at_column function")

        # Attach trigger to users table
        create_trigger = """
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """

        self.execute_sql(create_trigger, "Creating trigger on users table")

        # Function to clean expired sessions
        cleanup_function = """
        CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM sessions WHERE expires_at < NOW();
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;

        COMMENT ON FUNCTION cleanup_expired_sessions IS 'Delete expired session tokens';
        """

        self.execute_sql(cleanup_function, "Creating cleanup_expired_sessions function")

    def validate_schema(self):
        """Validate authentication schema setup"""
        logger.info("🔍 Validating authentication schema...")

        # Check tables exist
        tables = ['users', 'sessions', 'audit_log']
        for table in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM pg_tables WHERE tablename = '{table}';")
            count = self.cursor.fetchone()[0]
            if count > 0:
                logger.info(f"  ✅ Table '{table}' exists")
            else:
                logger.error(f"  ❌ Table '{table}' missing")
                return False

        # Check functions exist
        functions = ['update_updated_at_column', 'cleanup_expired_sessions']
        for func in functions:
            self.cursor.execute(f"SELECT COUNT(*) FROM pg_proc WHERE proname = '{func}';")
            count = self.cursor.fetchone()[0]
            if count > 0:
                logger.info(f"  ✅ Function '{func}' exists")
            else:
                logger.error(f"  ❌ Function '{func}' missing")
                return False

        # Check row counts
        for table in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = self.cursor.fetchone()[0]
            logger.info(f"  📊 Table '{table}': {count} rows")

        logger.info("✅ Authentication schema validation complete")
        return True

    def initialize_schema(self, drop_first: bool = False):
        """
        Initialize complete authentication schema

        Args:
            drop_first: Drop existing tables before creating
        """
        try:
            self.connect()

            if drop_first:
                self.drop_auth_tables()

            logger.info("🚀 Initializing authentication schema...")

            # Create tables in order
            self.create_users_table()
            self.create_sessions_table()
            self.create_audit_log_table()
            self.create_helper_functions()

            # Validate
            if self.validate_schema():
                logger.info("✅ Authentication schema initialization complete")
                logger.info("")
                logger.info("Next steps:")
                logger.info("  1. Create admin user: python3 quant_platform.py setup")
                logger.info("  2. Login: python3 quant_platform.py auth login")
                logger.info("  3. Run backtest: python3 quant_platform.py backtest run --strategy momentum_value")
                return True
            else:
                logger.error("❌ Schema validation failed")
                return False

        except Exception as e:
            logger.error(f"❌ Schema initialization failed: {e}")
            return False
        finally:
            self.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Initialize Quant Platform authentication schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize authentication schema
  python3 scripts/init_auth_schema.py

  # Drop existing tables and recreate
  python3 scripts/init_auth_schema.py --drop

  # Validate existing schema
  python3 scripts/init_auth_schema.py --validate

  # Use custom database connection
  python3 scripts/init_auth_schema.py --host localhost --port 5432 --database quant_platform
        """
    )

    parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--database', default='quant_platform', help='Database name')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables first')
    parser.add_argument('--validate', action='store_true', help='Validate schema only')

    args = parser.parse_args()

    # Initialize schema
    initializer = AuthSchemaInitializer(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password
    )

    if args.validate:
        # Validate only
        initializer.connect()
        success = initializer.validate_schema()
        initializer.close()
    else:
        # Initialize schema
        success = initializer.initialize_schema(drop_first=args.drop)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
