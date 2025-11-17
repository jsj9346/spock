"""
Configuration Management Module

Provides centralized configuration management with priority-based loading:
1. Environment variables (highest priority)
2. User config files (~/.spock/config/)
3. Project config files (config/)
4. Default values (lowest priority)

Classes:
    BaseConfig: Abstract base class for all configuration classes
    RefreshConfig: Database refresh and backfill configuration
    UIConfig: Terminal UI and display configuration

Usage:
    from infrastructure.config import RefreshConfig, UIConfig

    # Load with defaults
    refresh_config = RefreshConfig.load()
    ui_config = UIConfig.load()

    # Load with custom config file
    custom_config = RefreshConfig.load(Path('/path/to/config.yaml'))

    # Access settings
    print(f"Log level: {refresh_config.log_level}")
    print(f"Colorama enabled: {ui_config.colorama_enabled}")
"""

from .base_config import BaseConfig
from .refresh_config import RefreshConfig
from .ui_config import UIConfig

__all__ = [
    'BaseConfig',
    'RefreshConfig',
    'UIConfig'
]
