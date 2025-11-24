"""
UI Configuration Management

Configuration for terminal UI, including colorama support, output formatting,
and application metadata.

Classes:
    UIConfig: Terminal UI and display configuration

Usage:
    from infrastructure.config import UIConfig

    # Load configuration
    ui_config = UIConfig.load()

    # Check color support
    if ui_config.colorama_enabled:
        print(ui_config.colored("Success!", "success"))

    # Display banner
    print(ui_config.format_banner())

    # Access colors
    print(f"{ui_config.colors['header']}Header Text{ui_config.colors['reset']}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
import os
import logging

from .base_config import BaseConfig

logger = logging.getLogger(__name__)

# Try to import colorama (optional dependency)
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    logger.warning("colorama not available, color output disabled")
    HAS_COLOR = False

    # Fallback classes for when colorama is not available
    class Fore:
        """Fallback Fore class with empty strings"""
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ''

    class Style:
        """Fallback Style class with empty strings"""
        BRIGHT = DIM = NORMAL = RESET_ALL = ''


@dataclass
class UIConfig(BaseConfig):
    """
    Terminal UI configuration

    Manages:
    - Color support detection and configuration
    - Application banner and metadata
    - Output formatting preferences
    - Emoji support

    Attributes:
        colorama_enabled: Whether color output is supported/enabled
        banner_enabled: Display application banner on startup
        emoji_enabled: Use emoji in output (🚀, ✅, ❌, etc.)
        progress_bar_enabled: Show progress bars for long operations

        version: Application version string
        app_name: Application display name
        description: Short application description

        colors: Color scheme dictionary (when colorama available)
    """

    # ========================================================================
    # Color Support
    # ========================================================================
    colorama_enabled: bool = HAS_COLOR

    # ========================================================================
    # UI Features
    # ========================================================================
    banner_enabled: bool = True
    emoji_enabled: bool = True
    progress_bar_enabled: bool = True

    # ========================================================================
    # Application Metadata
    # ========================================================================
    version: str = "2.0.0"
    app_name: str = "Spock Database Refresh Tool"
    description: str = "Cross-platform data update utility"

    # ========================================================================
    # Color Scheme (populated in __post_init__)
    # ========================================================================
    colors: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize color scheme based on colorama availability"""
        if self.colorama_enabled and HAS_COLOR:
            # Full color scheme when colorama is available
            self.colors = {
                'header': Fore.CYAN,
                'success': Fore.GREEN,
                'warning': Fore.YELLOW,
                'error': Fore.RED,
                'info': Fore.WHITE,
                'highlight': Fore.CYAN + Style.BRIGHT,
                'dim': Style.DIM,
                'bright': Style.BRIGHT,
                'reset': Style.RESET_ALL,

                # Additional semantic colors
                'primary': Fore.CYAN,
                'secondary': Fore.BLUE,
                'danger': Fore.RED,
                'accent': Fore.MAGENTA,
            }
        else:
            # Empty strings when colors are disabled
            self.colors = {
                'header': '',
                'success': '',
                'warning': '',
                'error': '',
                'info': '',
                'highlight': '',
                'dim': '',
                'bright': '',
                'reset': '',
                'primary': '',
                'secondary': '',
                'danger': '',
                'accent': '',
            }

        logger.debug(f"UI Config initialized (colorama_enabled={self.colorama_enabled})")

    @classmethod
    def get_default_config_path(cls) -> Path:
        """
        Get the default configuration file path

        Note: UI config typically uses defaults, but can be overridden
        via ui_config.yaml if needed.
        """
        return Path(__file__).parent.parent.parent / 'config' / 'ui_config.yaml'

    @classmethod
    def _apply_env_overrides(cls, config_data: Dict) -> Dict:
        """
        Apply environment variable overrides

        Supported environment variables:
            NO_COLOR: Standard env var to disable color output (any value)
            SPOCK_EMOJI_ENABLED: Enable/disable emoji (true/false)
            SPOCK_BANNER_ENABLED: Enable/disable banner (true/false)
            SPOCK_PROGRESS_BAR_ENABLED: Enable/disable progress bars (true/false)

        Example:
            export NO_COLOR=1  # Disable colors (standard convention)
            export SPOCK_EMOJI_ENABLED=false
        """
        # NO_COLOR environment variable (standard convention)
        # https://no-color.org/
        if os.getenv('NO_COLOR') is not None:
            config_data['colorama_enabled'] = False
            logger.debug("Environment override: NO_COLOR detected, colors disabled")

        # SPOCK_COLORAMA_ENABLED (explicit override)
        if colorama := os.getenv('SPOCK_COLORAMA_ENABLED'):
            config_data['colorama_enabled'] = colorama.lower() in ('true', '1', 'yes')
            logger.debug(f"Environment override: colorama_enabled={colorama}")

        # Emoji support
        if emoji := os.getenv('SPOCK_EMOJI_ENABLED'):
            config_data['emoji_enabled'] = emoji.lower() in ('true', '1', 'yes')
            logger.debug(f"Environment override: emoji_enabled={emoji}")

        # Banner display
        if banner := os.getenv('SPOCK_BANNER_ENABLED'):
            config_data['banner_enabled'] = banner.lower() in ('true', '1', 'yes')
            logger.debug(f"Environment override: banner_enabled={banner}")

        # Progress bar
        if progress := os.getenv('SPOCK_PROGRESS_BAR_ENABLED'):
            config_data['progress_bar_enabled'] = progress.lower() in ('true', '1', 'yes')
            logger.debug(f"Environment override: progress_bar_enabled={progress}")

        return config_data

    def colored(self, text: str, color_key: str = 'info') -> str:
        """
        Apply color to text using color scheme

        Args:
            text: Text to colorize
            color_key: Color scheme key (header, success, warning, error, info, etc.)

        Returns:
            Colored text if colors enabled, plain text otherwise

        Example:
            >>> ui = UIConfig.load()
            >>> print(ui.colored("Success!", "success"))
            # Prints green "Success!" if colors enabled
        """
        if self.colorama_enabled and color_key in self.colors:
            return f"{self.colors[color_key]}{text}{self.colors['reset']}"
        return text

    def format_banner(self) -> str:
        """
        Generate application banner

        Returns:
            Formatted banner string (empty if banner_enabled=False)

        Example:
            ╔════════════════════════════════════════╗
            ║   📊 Spock Database Refresh Tool      ║
            ║   Cross-platform data update utility   ║
            ║   Version 1.0.0                        ║
            ╚════════════════════════════════════════╝
        """
        if not self.banner_enabled:
            return ""

        c = self.colors

        # Box drawing characters
        box_top = "╔" + "═" * 62 + "╗"
        box_bottom = "╚" + "═" * 62 + "╝"
        box_side = "║"

        # Emoji prefix (if enabled)
        emoji_prefix = "📊 " if self.emoji_enabled else ""

        # Build banner
        banner = f"""
{c['header']}{box_top}
{c['header']}{box_side}   {c['highlight']}{emoji_prefix}{self.app_name}{' ' * (58 - len(self.app_name) - len(emoji_prefix))}{c['header']}{box_side}
{c['header']}{box_side}   {c['info']}{self.description}{' ' * (58 - len(self.description))}{c['header']}{box_side}
{c['header']}{box_side}   {c['info']}Version {self.version}{' ' * (51 - len(self.version))}{c['header']}{box_side}
{c['header']}{box_bottom}{c['reset']}
        """
        return banner

    def format_section_header(self, title: str, width: int = 70) -> str:
        """
        Format a section header with separator lines

        Args:
            title: Section title
            width: Header width in characters

        Returns:
            Formatted section header

        Example:
            📊 Database Status
            ══════════════════════════════════════════
        """
        emoji_prefix = "📊 " if self.emoji_enabled else ""
        separator = "═" * width

        return f"\n{self.colored(emoji_prefix + title, 'header')}\n{separator}"

    def format_status_message(
        self,
        message: str,
        status: str = 'info'
    ) -> str:
        """
        Format a status message with appropriate color and emoji

        Args:
            message: Status message
            status: Status type (success, error, warning, info)

        Returns:
            Formatted status message

        Example:
            ✅ Operation completed successfully
            ❌ Error: Database connection failed
            ⚠️  Warning: Low disk space
        """
        emoji_map = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️ ',
            'info': 'ℹ️ ',
            'progress': '🔄'
        } if self.emoji_enabled else {
            'success': '[OK]',
            'error': '[ERROR]',
            'warning': '[WARN]',
            'info': '[INFO]',
            'progress': '[...]'
        }

        color_map = {
            'success': 'success',
            'error': 'error',
            'warning': 'warning',
            'info': 'info',
            'progress': 'primary'
        }

        emoji = emoji_map.get(status, '')
        color_key = color_map.get(status, 'info')

        formatted = f"{emoji} {message}" if emoji else message
        return self.colored(formatted, color_key)

    def validate(self) -> bool:
        """
        Validate UI configuration

        Returns:
            True if validation passes

        Raises:
            ValueError: If configuration is invalid
        """
        # Version format validation (basic)
        if not self.version:
            raise ValueError("version cannot be empty")

        # App name validation
        if not self.app_name:
            raise ValueError("app_name cannot be empty")

        logger.debug("UI configuration validation passed")
        return True
