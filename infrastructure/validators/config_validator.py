"""
Configuration Validation

Provides validation logic for configuration classes with detailed
error and warning reporting.

Classes:
    ValidationResult: Container for validation results
    ConfigValidator: Configuration validation logic

Usage:
    from infrastructure.validators import ConfigValidator
    from infrastructure.config import RefreshConfig

    config = RefreshConfig.load()
    validator = ConfigValidator()
    result = validator.validate_refresh_config(config)

    if not result:
        print("Validation errors:")
        for error in result.errors:
            print(f"  ❌ {error}")

    if result.warnings:
        print("Validation warnings:")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")
"""

from dataclasses import dataclass, field
from typing import List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Container for validation results

    Attributes:
        is_valid: True if no errors, False otherwise
        errors: List of error messages (critical issues)
        warnings: List of warning messages (non-critical issues)

    Usage:
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_error("Critical issue found")
        result.add_warning("Minor issue found")

        if not result:
            # Handle validation failure
            pass
    """

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """
        Boolean evaluation returns is_valid status

        Example:
            if result:
                # Validation passed
            else:
                # Validation failed
        """
        return self.is_valid

    def add_error(self, message: str):
        """
        Add an error message and mark validation as failed

        Args:
            message: Error description
        """
        self.errors.append(message)
        self.is_valid = False
        logger.error(f"Validation error: {message}")

    def add_warning(self, message: str):
        """
        Add a warning message (does not affect is_valid)

        Args:
            message: Warning description
        """
        self.warnings.append(message)
        logger.warning(f"Validation warning: {message}")

    def summary(self) -> str:
        """
        Generate a human-readable summary

        Returns:
            Formatted summary string
        """
        status = "✅ PASSED" if self.is_valid else "❌ FAILED"
        error_count = len(self.errors)
        warning_count = len(self.warnings)

        summary = f"Validation {status}\n"
        summary += f"  Errors: {error_count}\n"
        summary += f"  Warnings: {warning_count}\n"

        if error_count > 0:
            summary += "\nErrors:\n"
            for error in self.errors:
                summary += f"  ❌ {error}\n"

        if warning_count > 0:
            summary += "\nWarnings:\n"
            for warning in self.warnings:
                summary += f"  ⚠️  {warning}\n"

        return summary


class ConfigValidator:
    """
    Configuration validation logic

    Provides validation methods for all configuration classes with
    detailed error and warning reporting.

    Methods:
        validate_refresh_config(): Validate RefreshConfig instance
        validate_ui_config(): Validate UIConfig instance

    Usage:
        validator = ConfigValidator()

        # Validate RefreshConfig
        refresh_config = RefreshConfig.load()
        result = validator.validate_refresh_config(refresh_config)

        # Validate UIConfig
        ui_config = UIConfig.load()
        result = validator.validate_ui_config(ui_config)
    """

    def validate_refresh_config(self, config: 'RefreshConfig') -> ValidationResult:
        """
        Validate RefreshConfig instance

        Checks:
        - Log level is valid
        - Max workers is reasonable
        - Enabled regions are valid
        - Rate limits are positive
        - Batch sizes are positive
        - Time estimates are positive
        - Checkpoint directory exists (warning if not)
        - Required directories exist (warning if not)

        Args:
            config: RefreshConfig instance to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Import here to avoid circular import
        from infrastructure.config import RefreshConfig

        # ===================================================================
        # Critical Validations (Errors)
        # ===================================================================

        # 1. Log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if config.log_level.upper() not in valid_log_levels:
            result.add_error(
                f"Invalid log_level: '{config.log_level}'. "
                f"Must be one of {valid_log_levels}"
            )

        # 2. Max workers
        if not (1 <= config.max_workers <= 16):
            result.add_error(
                f"Invalid max_workers: {config.max_workers}. "
                f"Must be between 1 and 16"
            )

        # 3. Enabled regions
        valid_regions = ["KR", "US", "CN", "HK", "JP", "VN"]
        for region in config.enabled_regions:
            if region not in valid_regions:
                result.add_error(
                    f"Invalid region: '{region}'. "
                    f"Must be one of {valid_regions}"
                )

        # 4. Rate limits
        for region, limit in config.rate_limits.items():
            if limit <= 0:
                result.add_error(
                    f"Invalid rate_limit for {region}: {limit}. "
                    f"Must be > 0"
                )

        # 5. Batch size
        if config.batch_size <= 0:
            result.add_error(
                f"Invalid batch_size: {config.batch_size}. "
                f"Must be > 0"
            )

        # 6. Lookback days
        if config.lookback_days < 0:
            result.add_error(
                f"Invalid lookback_days: {config.lookback_days}. "
                f"Must be >= 0"
            )

        # 7. Max history days
        if config.max_history_days <= 0:
            result.add_error(
                f"Invalid max_history_days: {config.max_history_days}. "
                f"Must be > 0"
            )

        # 8. Equity backfill time
        if config.equity_backfill_time_per_ticker <= 0:
            result.add_error(
                f"Invalid equity_backfill_time_per_ticker: "
                f"{config.equity_backfill_time_per_ticker}. Must be > 0"
            )

        # ===================================================================
        # Non-Critical Validations (Warnings)
        # ===================================================================

        # 1. Checkpoint directory
        checkpoint_dir = Path(config.checkpoint_dir)
        if not checkpoint_dir.exists():
            result.add_warning(
                f"Checkpoint directory does not exist: {checkpoint_dir}. "
                f"Will be created on first use."
            )

        # 2. Rate limit reasonableness
        for region, limit in config.rate_limits.items():
            if limit > 1000:
                result.add_warning(
                    f"Very high rate_limit for {region}: {limit}. "
                    f"Ensure API supports this rate."
                )

        # 3. Batch size reasonableness
        if config.batch_size > 1000:
            result.add_warning(
                f"Very large batch_size: {config.batch_size}. "
                f"May cause memory issues."
            )

        # 4. Max workers reasonableness
        if config.max_workers > 8:
            result.add_warning(
                f"High max_workers: {config.max_workers}. "
                f"May cause resource contention."
            )

        # 5. Equity batch sizes
        for batch_type, size in config.equity_batch_sizes.items():
            if size <= 0:
                result.add_error(
                    f"Invalid equity batch size for '{batch_type}': {size}. "
                    f"Must be > 0"
                )

        logger.debug(f"RefreshConfig validation: {len(result.errors)} errors, "
                    f"{len(result.warnings)} warnings")

        return result

    def validate_ui_config(self, config: 'UIConfig') -> ValidationResult:
        """
        Validate UIConfig instance

        Checks:
        - Version is not empty
        - App name is not empty
        - Description is not empty
        - Color scheme is properly initialized

        Args:
            config: UIConfig instance to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Import here to avoid circular import
        from infrastructure.config import UIConfig

        # ===================================================================
        # Critical Validations (Errors)
        # ===================================================================

        # 1. Version
        if not config.version:
            result.add_error("version cannot be empty")

        # 2. App name
        if not config.app_name:
            result.add_error("app_name cannot be empty")

        # 3. Description
        if not config.description:
            result.add_error("description cannot be empty")

        # 4. Color scheme initialization
        if not config.colors:
            result.add_error("colors dictionary not initialized")
        else:
            required_colors = ['header', 'success', 'warning', 'error', 'info', 'reset']
            for color_key in required_colors:
                if color_key not in config.colors:
                    result.add_error(f"Missing required color: '{color_key}'")

        # ===================================================================
        # Non-Critical Validations (Warnings)
        # ===================================================================

        # 1. Colorama availability
        if not config.colorama_enabled:
            result.add_warning(
                "colorama not available or disabled. "
                "Output will be plain text."
            )

        logger.debug(f"UIConfig validation: {len(result.errors)} errors, "
                    f"{len(result.warnings)} warnings")

        return result

    def validate_all(
        self,
        refresh_config: 'RefreshConfig',
        ui_config: 'UIConfig'
    ) -> ValidationResult:
        """
        Validate all configurations together

        Args:
            refresh_config: RefreshConfig instance
            ui_config: UIConfig instance

        Returns:
            Combined ValidationResult
        """
        # Validate individually
        refresh_result = self.validate_refresh_config(refresh_config)
        ui_result = self.validate_ui_config(ui_config)

        # Combine results
        combined = ValidationResult()

        # Merge errors
        combined.errors.extend(refresh_result.errors)
        combined.errors.extend(ui_result.errors)

        # Merge warnings
        combined.warnings.extend(refresh_result.warnings)
        combined.warnings.extend(ui_result.warnings)

        # Set validity
        combined.is_valid = refresh_result.is_valid and ui_result.is_valid

        logger.info(f"Combined validation: {len(combined.errors)} errors, "
                   f"{len(combined.warnings)} warnings")

        return combined
