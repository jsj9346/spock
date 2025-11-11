# mcp_server/config.py
"""
MCP Server Configuration

Loads configuration from environment variables and provides
default values for development and production environments.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    """MCP Server Configuration"""

    # Database Configuration
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # Performance Configuration
    cache_max_size_mb: int = 500
    cache_ttl_seconds: int = 3600
    batch_size: int = 100

    # Logging Configuration
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Security Configuration (Phase 2)
    api_key: Optional[str] = None
    rate_limit_per_minute: int = 60

    # MCP Server Configuration
    server_name: str = "spock"
    server_version: str = "0.1.0"

    # Security Configuration - Project Path Restriction
    allowed_project_path: str = "/Users/13ruce/spock"

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Environment variables:
        - POSTGRES_HOST: PostgreSQL server host (default: localhost)
        - POSTGRES_PORT: PostgreSQL server port (default: 5432)
        - POSTGRES_DB: Database name (default: quant_platform)
        - POSTGRES_USER: Database user (default: bruce)
        - POSTGRES_PASSWORD: Database password (default: empty)
        - CACHE_MAX_SIZE_MB: Maximum cache size in MB (default: 500)
        - LOG_LEVEL: Logging level (default: INFO)
        - SPOCK_MCP_API_KEY: API key for authentication (optional, Phase 2)
        - SPOCK_PROJECT_PATH: Allowed project directory path (default: /Users/13ruce/spock)

        Returns:
            Config: Configuration object
        """
        # Load environment variables from .env file if it exists
        load_dotenv()

        return cls(
            # Database
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "quant_platform"),
            postgres_user=os.getenv("POSTGRES_USER", "bruce"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            # Performance
            cache_max_size_mb=int(os.getenv("CACHE_MAX_SIZE_MB", "500")),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            batch_size=int(os.getenv("BATCH_SIZE", "100")),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", "logs"),
            # Security (Phase 2)
            api_key=os.getenv("SPOCK_MCP_API_KEY"),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
            # Project Path Restriction
            allowed_project_path=os.getenv("SPOCK_PROJECT_PATH", "/Users/13ruce/spock"),
        )

    def get_database_url(self) -> str:
        """
        Get PostgreSQL connection URL.

        Returns:
            str: Database connection URL
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def __repr__(self) -> str:
        """
        String representation of configuration (masks sensitive data).

        Returns:
            str: Configuration summary
        """
        return (
            f"Config(postgres_host={self.postgres_host}, "
            f"postgres_db={self.postgres_db}, "
            f"log_level={self.log_level}, "
            f"cache_size={self.cache_max_size_mb}MB)"
        )
