"""
Infrastructure Module

Provides core infrastructure components for the Spock Quant Platform:
- Configuration management with priority-based loading
- Logging and monitoring setup
- Database connection management
- Validation and error handling
- Custom exception hierarchy

Modules:
    config: Configuration management system
    validators: Configuration and data validation
    exceptions: Custom exception hierarchy

Usage:
    from infrastructure.config import RefreshConfig, UIConfig
    from infrastructure.validators import ConfigValidator
    from infrastructure.exceptions import DatabaseException, APIException

    config = RefreshConfig.load()
    validator = ConfigValidator()
    result = validator.validate_refresh_config(config)
"""

__version__ = "1.0.0"
__author__ = "Spock Quant Platform Team"

__all__ = [
    'config',
    'validators',
    'exceptions'
]
