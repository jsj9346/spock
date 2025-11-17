# Infrastructure Module

Core infrastructure components for the Spock Quant Platform, providing centralized configuration management, validation, and utilities.

## Overview

This module provides:
- **Configuration Management**: Priority-based configuration loading with environment overrides
- **Validation**: Comprehensive configuration validation with detailed error reporting
- **Extensibility**: Base classes for adding new configuration types

## Module Structure

```
infrastructure/
├── __init__.py
├── README.md                          # This file
├── config/
│   ├── __init__.py
│   ├── base_config.py                 # BaseConfig abstract class
│   ├── refresh_config.py              # RefreshConfig for database operations
│   └── ui_config.py                   # UIConfig for terminal UI
└── validators/
    ├── __init__.py
    └── config_validator.py            # Configuration validation logic
```

## Quick Start

### Basic Usage

```python
from infrastructure.config import RefreshConfig, UIConfig
from infrastructure.validators import ConfigValidator

# Load configurations
refresh_config = RefreshConfig.load()
ui_config = UIConfig.load()

# Validate configurations
validator = ConfigValidator()
result = validator.validate_refresh_config(refresh_config)

if not result:
    print("Configuration errors:")
    for error in result.errors:
        print(f"  ❌ {error}")

# Use configurations
print(f"Enabled regions: {refresh_config.enabled_regions}")
print(ui_config.format_banner())
```

### Custom Configuration File

```python
from pathlib import Path
from infrastructure.config import RefreshConfig

# Load from custom file
custom_config = RefreshConfig.load(Path('/path/to/custom_config.yaml'))
```

### Environment Variable Overrides

```bash
# Override log level
export SPOCK_LOG_LEVEL=DEBUG

# Override max workers
export SPOCK_MAX_WORKERS=8

# Disable colors
export NO_COLOR=1

# Run application
python3 spock_refresh.py
```

## Configuration Priority

Configurations are loaded with the following priority (highest to lowest):

1. **Environment Variables** (highest priority)
   - `SPOCK_*` variables override YAML settings
   - `NO_COLOR` disables color output (standard convention)

2. **User Configuration**
   - `~/.spock/config/refresh_config.yaml`
   - User-specific overrides

3. **Project Configuration**
   - `config/refresh_config.yaml`
   - Project defaults

4. **Code Defaults** (lowest priority)
   - Hardcoded defaults in dataclass definitions

### Priority Example

```yaml
# config/refresh_config.yaml (project default)
global:
  log_level: INFO
  max_workers: 4

# ~/.spock/config/refresh_config.yaml (user override)
global:
  max_workers: 8  # User prefers more workers

# Environment variable (highest priority)
# export SPOCK_LOG_LEVEL=DEBUG

# Final result:
#   log_level: DEBUG (from environment)
#   max_workers: 8 (from user config)
```

## Configuration Classes

### RefreshConfig

Database refresh and backfill configuration.

**Key Settings**:
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `max_workers`: Maximum concurrent workers
- `enabled_regions`: Active market regions
- `rate_limits`: API rate limits per region
- `batch_size`: OHLCV batch processing size
- `equity_backfill_time_per_ticker`: Time estimate for equity backfill

**Environment Variables**:
- `SPOCK_LOG_LEVEL`: Override log level
- `SPOCK_MAX_WORKERS`: Override max workers
- `SPOCK_CHECKPOINT_ENABLED`: Enable/disable checkpoints
- `SPOCK_ENABLED_REGIONS`: Comma-separated region list

**Example**:
```python
from infrastructure.config import RefreshConfig

config = RefreshConfig.load()

print(f"Log level: {config.log_level}")
print(f"Enabled regions: {config.enabled_regions}")
print(f"Batch size: {config.batch_size}")

# Get region-specific rate limit
kr_rate_limit = config.get_rate_limit('KR')
print(f"KR rate limit: {kr_rate_limit} requests/sec")

# Estimate backfill time
estimated_hours = config.estimate_equity_backfill_time(ticker_count=100)
print(f"Estimated backfill time: {estimated_hours:.1f} hours")
```

### UIConfig

Terminal UI and display configuration.

**Key Settings**:
- `colorama_enabled`: Color output support
- `banner_enabled`: Show application banner
- `emoji_enabled`: Use emoji in output
- `version`: Application version
- `app_name`: Application display name

**Environment Variables**:
- `NO_COLOR`: Disable color output (standard)
- `SPOCK_EMOJI_ENABLED`: Enable/disable emoji
- `SPOCK_BANNER_ENABLED`: Enable/disable banner

**Example**:
```python
from infrastructure.config import UIConfig

ui_config = UIConfig.load()

# Display banner
print(ui_config.format_banner())

# Colored output
print(ui_config.colored("Success!", "success"))  # Green
print(ui_config.colored("Warning", "warning"))    # Yellow
print(ui_config.colored("Error", "error"))        # Red

# Status messages with emoji
print(ui_config.format_status_message("Operation completed", "success"))
# Output: ✅ Operation completed

print(ui_config.format_status_message("Connection failed", "error"))
# Output: ❌ Connection failed
```

## Validation

### ValidationResult

Container for validation results with error and warning lists.

```python
from infrastructure.validators import ValidationResult

result = ValidationResult()
result.add_error("Critical issue")
result.add_warning("Minor issue")

if not result:
    print("Validation failed!")
    print(result.summary())
```

### ConfigValidator

Validation logic for all configuration classes.

```python
from infrastructure.validators import ConfigValidator
from infrastructure.config import RefreshConfig, UIConfig

# Create validator
validator = ConfigValidator()

# Validate individual configs
refresh_config = RefreshConfig.load()
result = validator.validate_refresh_config(refresh_config)

ui_config = UIConfig.load()
result = validator.validate_ui_config(ui_config)

# Validate all configs together
combined_result = validator.validate_all(refresh_config, ui_config)

if not combined_result:
    print(combined_result.summary())
```

## Extending Configuration

To add a new configuration class:

1. **Create Configuration Class**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from infrastructure.config import BaseConfig

@dataclass
class MyConfig(BaseConfig):
    """My custom configuration"""

    my_setting: str = "default_value"
    my_number: int = 42

    @classmethod
    def get_default_config_path(cls) -> Path:
        return Path(__file__).parent.parent.parent / 'config' / 'my_config.yaml'

    @classmethod
    def _apply_env_overrides(cls, config_data: Dict) -> Dict:
        import os
        if value := os.getenv('MYAPP_MY_SETTING'):
            config_data['my_setting'] = value
        return config_data

    def validate(self) -> bool:
        if self.my_number < 0:
            raise ValueError("my_number must be >= 0")
        return True
```

2. **Create YAML Configuration** (`config/my_config.yaml`):

```yaml
my_setting: "production_value"
my_number: 100
```

3. **Add Validation** (optional):

```python
# In infrastructure/validators/config_validator.py
def validate_my_config(self, config: 'MyConfig') -> ValidationResult:
    result = ValidationResult()

    if not config.my_setting:
        result.add_error("my_setting cannot be empty")

    if config.my_number < 0:
        result.add_error("my_number must be >= 0")

    return result
```

4. **Export in `__init__.py`**:

```python
# infrastructure/config/__init__.py
from .my_config import MyConfig

__all__ = ['BaseConfig', 'RefreshConfig', 'UIConfig', 'MyConfig']
```

## Testing

### Unit Tests

```python
import pytest
from infrastructure.config import RefreshConfig, UIConfig
from infrastructure.validators import ConfigValidator

def test_refresh_config_load():
    """Test RefreshConfig loading"""
    config = RefreshConfig.load()
    assert config.log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    assert 1 <= config.max_workers <= 16
    assert len(config.enabled_regions) > 0

def test_ui_config_load():
    """Test UIConfig loading"""
    config = UIConfig.load()
    assert config.version is not None
    assert config.app_name is not None
    assert 'header' in config.colors

def test_config_validation():
    """Test configuration validation"""
    config = RefreshConfig(log_level="INVALID", max_workers=20)

    validator = ConfigValidator()
    result = validator.validate_refresh_config(config)

    assert not result.is_valid
    assert len(result.errors) > 0
```

### Integration Tests

```python
def test_environment_override():
    """Test environment variable override"""
    import os
    os.environ['SPOCK_LOG_LEVEL'] = 'DEBUG'

    config = RefreshConfig.load()
    assert config.log_level == 'DEBUG'

    del os.environ['SPOCK_LOG_LEVEL']

def test_user_config_merge():
    """Test user config merging"""
    from pathlib import Path

    # Create temporary user config
    user_config_path = Path.home() / '.spock' / 'config' / 'refresh_config.yaml'
    # ... test user config merging ...
```

## Troubleshooting

### Configuration Not Loading

**Problem**: Configuration fails to load or uses unexpected values

**Solution**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging
from infrastructure.config import RefreshConfig
config = RefreshConfig.load()

# Check logs for loading sequence
```

### Validation Failures

**Problem**: Configuration validation fails with unclear errors

**Solution**:
```python
from infrastructure.validators import ConfigValidator

validator = ConfigValidator()
result = validator.validate_refresh_config(config)

# Print detailed summary
print(result.summary())
```

### Environment Variables Not Working

**Problem**: Environment variables not overriding configuration

**Solution**:
```bash
# Check environment variable names (must use SPOCK_ prefix)
env | grep SPOCK

# Verify spelling and case sensitivity
export SPOCK_LOG_LEVEL=DEBUG  # Correct
export spock_log_level=DEBUG  # Wrong (case)
export LOG_LEVEL=DEBUG        # Wrong (no prefix)
```

## Best Practices

1. **Always Validate**: Call `validate()` after loading configurations
2. **Use Type Hints**: Maintain type hints for better IDE support
3. **Document Defaults**: Comment default values and their rationale
4. **Environment Override Naming**: Use consistent `SPOCK_*` prefix
5. **Sensible Defaults**: Provide safe defaults for all settings
6. **Test Configuration**: Write tests for custom configurations

## Migration from Hardcoded Values

### Before (Hardcoded)

```python
# Old code
LOG_LEVEL = "INFO"
MAX_WORKERS = 4
EQUITY_TIME = 0.09

if LOG_LEVEL == "DEBUG":
    print("Debug mode")
```

### After (Configuration Management)

```python
# New code
from infrastructure.config import RefreshConfig

config = RefreshConfig.load()

if config.log_level == "DEBUG":
    print("Debug mode")

# Use config values
estimated_time = config.estimate_equity_backfill_time(ticker_count=100)
```

## Version History

- **v1.0.0** (2025-11-11): Initial release
  - BaseConfig with priority-based loading
  - RefreshConfig for database operations
  - UIConfig for terminal UI
  - ConfigValidator for validation logic

## License

Part of the Spock Quant Platform.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review configuration validation errors
3. Enable debug logging for detailed information
4. Consult the Quant Platform documentation
