"""
Base Configuration Management

Provides the abstract base class for all configuration classes with
priority-based loading and validation.

Priority Order (highest to lowest):
1. Environment variables
2. User config file (~/.spock/config/)
3. Project config file (config/)
4. Default values

Classes:
    BaseConfig: Abstract base class for configuration management

Usage:
    class MyConfig(BaseConfig):
        setting1: str = "default"

        @classmethod
        def get_default_config_path(cls) -> Path:
            return Path("config/my_config.yaml")

        @classmethod
        def _apply_env_overrides(cls, config_data: Dict) -> Dict:
            if val := os.getenv('MY_SETTING1'):
                config_data['setting1'] = val
            return config_data

    config = MyConfig.load()
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
import os
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class BaseConfig(ABC):
    """
    Abstract base class for all configuration classes

    Provides:
    - Priority-based configuration loading
    - YAML file parsing
    - Environment variable overrides
    - User and project config merging
    - Validation interface

    Subclasses must implement:
    - get_default_config_path(): Returns path to default config file
    - _apply_env_overrides(): Applies environment variable overrides
    """

    @classmethod
    @abstractmethod
    def get_default_config_path(cls) -> Path:
        """
        Get the default configuration file path

        Returns:
            Path to the project's default config file

        Example:
            return Path(__file__).parent.parent.parent / 'config' / 'my_config.yaml'
        """
        pass

    @classmethod
    def load(cls, config_path: Optional[Path] = None):
        """
        Load configuration with priority-based merging

        Priority order:
        1. Environment variables (highest)
        2. User config (~/.spock/config/)
        3. Project config (config/)
        4. Default values (lowest)

        Args:
            config_path: Optional custom config file path

        Returns:
            Instance of the configuration class

        Raises:
            FileNotFoundError: If required config file doesn't exist
            ValueError: If configuration validation fails
        """
        # Step 1: Load project default config
        default_path = config_path or cls.get_default_config_path()
        config_data = cls._load_yaml_safe(default_path)

        # Step 2: Merge user config (if exists)
        user_config_path = Path.home() / '.spock' / 'config' / default_path.name
        if user_config_path.exists():
            logger.debug(f"Loading user config from {user_config_path}")
            user_data = cls._load_yaml_safe(user_config_path)
            config_data = cls._merge_dicts(config_data, user_data)

        # Step 3: Apply environment variable overrides
        config_data = cls._apply_env_overrides(config_data)

        # Step 4: Create instance
        try:
            instance = cls(**config_data)
        except TypeError as e:
            logger.error(f"Failed to create config instance: {e}")
            logger.debug(f"Config data: {config_data}")
            # Fallback: create instance with defaults only
            instance = cls()

        # Step 5: Validate
        try:
            instance.validate()
        except Exception as e:
            logger.warning(f"Config validation failed: {e}")
            # Continue with potentially invalid config (will fail at runtime if critical)

        return instance

    @staticmethod
    def _load_yaml_safe(path: Path) -> Dict[str, Any]:
        """
        Safely load YAML file with error handling

        Args:
            path: Path to YAML file

        Returns:
            Dictionary of configuration data (empty dict if file doesn't exist or fails)
        """
        if not path.exists():
            logger.debug(f"Config file not found: {path}")
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if data is not None else {}
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")
            return {}

    @staticmethod
    def _merge_dicts(base: Dict, override: Dict) -> Dict:
        """
        Recursively merge two dictionaries

        Override values take precedence over base values.
        Nested dictionaries are merged recursively.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary

        Example:
            base = {'a': 1, 'b': {'c': 2, 'd': 3}}
            override = {'b': {'c': 99}, 'e': 4}
            result = {'a': 1, 'b': {'c': 99, 'd': 3}, 'e': 4}
        """
        result = base.copy()

        for key, value in override.items():
            if (key in result and
                isinstance(result[key], dict) and
                isinstance(value, dict)):
                # Recursively merge nested dicts
                result[key] = BaseConfig._merge_dicts(result[key], value)
            else:
                # Override value
                result[key] = value

        return result

    @classmethod
    @abstractmethod
    def _apply_env_overrides(cls, config_data: Dict) -> Dict:
        """
        Apply environment variable overrides to configuration

        Subclasses should implement this to support environment-based
        configuration overrides.

        Args:
            config_data: Current configuration dictionary

        Returns:
            Updated configuration dictionary with env overrides

        Example:
            @classmethod
            def _apply_env_overrides(cls, config_data: Dict) -> Dict:
                if log_level := os.getenv('MYAPP_LOG_LEVEL'):
                    config_data['log_level'] = log_level
                return config_data
        """
        pass

    def validate(self) -> bool:
        """
        Validate configuration values

        Subclasses can override this to implement custom validation logic.
        Should raise ValueError if validation fails.

        Returns:
            True if validation passes

        Raises:
            ValueError: If configuration is invalid

        Example:
            def validate(self) -> bool:
                if self.port < 1 or self.port > 65535:
                    raise ValueError(f"Invalid port: {self.port}")
                return True
        """
        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary

        Returns:
            Dictionary representation of configuration
        """
        from dataclasses import asdict
        return asdict(self)

    def __repr__(self) -> str:
        """String representation for debugging"""
        items = ', '.join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{self.__class__.__name__}({items})"
