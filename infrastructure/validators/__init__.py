"""
Validation Module

Provides validation utilities for configuration and data validation.

Classes:
    ValidationResult: Result container for validation operations
    ConfigValidator: Configuration validation logic

Usage:
    from infrastructure.validators import ConfigValidator, ValidationResult

    validator = ConfigValidator()
    result = validator.validate_refresh_config(refresh_config)

    if not result:
        print("Validation failed:")
        for error in result.errors:
            print(f"  - {error}")
"""

from .config_validator import ConfigValidator, ValidationResult

__all__ = [
    'ConfigValidator',
    'ValidationResult'
]
