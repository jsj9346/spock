"""
Configuration Loader for Quant Platform CLI

Loads and manages configuration settings with priority hierarchy:
1. Environment variables (highest priority)
2. User config file (~/.quant_platform/config.yaml)
3. Project config file (config/cli_config.yaml)
4. Defaults (lowest priority)

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ConfigLoader:
    """
    Load and manage configuration settings.

    Priority order:
    1. Environment variables (highest)
    2. User config file (~/.quant_platform/config.yaml)
    3. Project config file (config/cli_config.yaml)
    4. Defaults (lowest)
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "cli_config.yaml"
    USER_CONFIG_PATH = Path.home() / ".quant_platform" / "config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config loader

        Args:
            config_path: Optional custom config file path
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration with priority hierarchy

        Returns:
            Merged configuration dictionary
        """
        # Start with default config
        config = self._load_yaml_file(self.config_path)

        # Override with user config if exists
        if self.USER_CONFIG_PATH.exists():
            user_config = self._load_yaml_file(self.USER_CONFIG_PATH)
            config = self._merge_configs(config, user_config)

        # Override with environment variables
        config = self._apply_env_overrides(config)

        return config

    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """
        Load YAML configuration file

        Args:
            path: Path to YAML file

        Returns:
            Configuration dictionary
        """
        try:
            if not path.exists():
                return {}

            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}", file=sys.stderr)
            return {}

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge configuration dictionaries

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides

        Environment variables follow pattern: QUANT_PLATFORM_<SECTION>_<KEY>
        Example: QUANT_PLATFORM_API_BASE_URL

        Args:
            config: Base configuration

        Returns:
            Configuration with environment overrides
        """
        # API configuration
        if os.getenv('QUANT_PLATFORM_API_BASE_URL'):
            mode = config.get('mode', 'local')
            if 'api' not in config:
                config['api'] = {}
            if mode not in config['api']:
                config['api'][mode] = {}
            config['api'][mode]['base_url'] = os.getenv('QUANT_PLATFORM_API_BASE_URL')

        # Database configuration
        if os.getenv('DB_HOST'):
            if 'database' not in config:
                config['database'] = {}
            config['database']['host'] = os.getenv('DB_HOST')

        if os.getenv('DB_PORT'):
            if 'database' not in config:
                config['database'] = {}
            config['database']['port'] = int(os.getenv('DB_PORT'))

        if os.getenv('DB_NAME'):
            if 'database' not in config:
                config['database'] = {}
            config['database']['database'] = os.getenv('DB_NAME')

        if os.getenv('DB_USER'):
            if 'database' not in config:
                config['database'] = {}
            config['database']['user'] = os.getenv('DB_USER')

        if os.getenv('DB_PASSWORD'):
            if 'database' not in config:
                config['database'] = {}
            config['database']['password'] = os.getenv('DB_PASSWORD')

        # Deployment mode
        if os.getenv('QUANT_PLATFORM_MODE'):
            config['mode'] = os.getenv('QUANT_PLATFORM_MODE')

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (supports nested keys with dot notation)

        Args:
            key: Configuration key (e.g., 'api.local.base_url')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_mode(self) -> str:
        """
        Get deployment mode

        Returns:
            Deployment mode (local, cloud)
        """
        return self.config.get('mode', 'local')

    def get_api_base_url(self) -> str:
        """
        Get API base URL for current mode

        Returns:
            API base URL
        """
        mode = self.get_mode()
        return self.config.get('api', {}).get(mode, {}).get('base_url', 'http://localhost:8000')

    def get_auth_mode(self) -> str:
        """
        Get authentication mode

        Returns:
            Authentication mode (local, simple, aws, jwt)
        """
        auth_mode = self.config.get('authentication', {}).get('mode', 'auto')

        if auth_mode == 'auto':
            # Auto-detect based on deployment mode
            deployment_mode = self.get_mode()

            if deployment_mode == 'local':
                return 'local'  # No auth for local
            else:
                # Check if AWS CLI is configured
                aws_config = Path.home() / '.aws' / 'credentials'
                if aws_config.exists():
                    # AWS available but default to simple for personal use
                    return 'simple'
                else:
                    return 'simple'

        return auth_mode

    def get_database_config(self) -> Dict[str, Any]:
        """
        Get database configuration

        Returns:
            Database configuration dictionary
        """
        db_config = self.config.get('database', {})

        # Apply defaults
        defaults = {
            'type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'database': 'quant_platform',
            'user': os.getenv('USER'),
            'password': ''
        }

        return {**defaults, **db_config}

    def is_cloud_mode(self) -> bool:
        """
        Check if running in cloud mode

        Returns:
            True if cloud mode, False otherwise
        """
        return self.get_mode() == 'cloud'

    def is_auth_enabled(self) -> bool:
        """
        Check if authentication is enabled

        Returns:
            True if authentication enabled, False otherwise
        """
        return self.get_auth_mode() != 'local'


# Global config instance
_config_instance: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """
    Get global configuration instance (singleton pattern)

    Returns:
        ConfigLoader instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigLoader()

    return _config_instance


def reload_config():
    """Reload configuration from files"""
    global _config_instance
    _config_instance = None
    return get_config()
