#!/usr/bin/env python3
"""
Spock Database Refresh Tool

User-friendly database update script with interactive menu and CLI modes.
Supports Mac, Windows, and Linux.

Features:
- Interactive menu for easy selection
- CLI mode for advanced users
- Preset modes (quick, full, incremental)
- Status monitoring
- Schedule setup helper
- Cross-platform support

Usage:
    # Interactive mode (recommended for beginners)
    python3 spock_refresh.py

    # CLI mode (advanced users)
    python3 spock_refresh.py --quick
    python3 spock_refresh.py --full --regions KR US
    python3 spock_refresh.py --incremental --dry-run

    # Status check
    python3 spock_refresh.py --status

Author: Spock Quant Platform
Date: 2025-11-04
"""

import sys
import os
import argparse
import subprocess
from datetime import datetime, timedelta, date
from typing import Optional, List
import platform

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Gap Analysis Components (Phase 3)
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.data_structures import GapPriority
from modules.db_manager_postgres import PostgresDatabaseManager

# Concurrency Control (Lock Management)
from modules.concurrency import with_lock, LockError, cleanup_stale_locks, is_operation_locked, get_operation_info

# Technical Indicator Calculation (Direct Integration)
from scripts.calculate_technical_indicators import TechnicalIndicatorCalculator

# Infrastructure Components (Phase 1 - Configuration Management)
try:
    from infrastructure.config import RefreshConfig, UIConfig
    from infrastructure.validators import ConfigValidator
    USE_NEW_CONFIG = True
except ImportError as e:
    print(f"⚠️  Warning: Infrastructure module not available ({e})")
    print("   Using legacy hardcoded configuration...")
    USE_NEW_CONFIG = False

# Try to import colored output (optional)
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback to no color
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''


def load_configurations():
    """
    Load and validate configurations

    Uses the new infrastructure.config system with fallback to legacy values.

    Returns:
        tuple: (refresh_config, ui_config)
    """
    if not USE_NEW_CONFIG:
        # Return None when infrastructure not available
        return None, None

    try:
        # Load configurations
        refresh_config = RefreshConfig.load()
        ui_config = UIConfig.load()

        # Validate configurations
        validator = ConfigValidator()
        validation = validator.validate_all(refresh_config, ui_config)

        if not validation.is_valid:
            print("⚠️  Configuration validation failed:")
            for error in validation.errors:
                print(f"   ❌ {error}")

        if validation.warnings:
            print("⚠️  Configuration warnings:")
            for warning in validation.warnings:
                print(f"   ⚠️  {warning}")

        return refresh_config, ui_config

    except Exception as e:
        print(f"⚠️  Failed to load configuration: {e}")
        print("   Using default settings...")
        # Fallback to defaults
        try:
            return RefreshConfig(), UIConfig()
        except:
            return None, None


# Create checkpoint directory before configuration loading to avoid validation warnings
try:
    os.makedirs('data/checkpoints', exist_ok=True)
except Exception:
    pass  # Silent failure if directory creation fails

# Initialize configurations (global)
REFRESH_CONFIG, UI_CONFIG = load_configurations()

# Legacy compatibility: maintain HAS_COLOR and Fore/Style references
if UI_CONFIG is not None:
    HAS_COLOR = UI_CONFIG.colorama_enabled
    # Keep original Fore and Style for backward compatibility
else:
    # Already initialized above
    pass


def colored(text: str, color: str = '') -> str:
    """
    Return colored text if colorama available

    Supports both legacy Fore.XXX format and new color key format.

    Args:
        text: Text to colorize
        color: Fore.XXX constant or color key (header, success, warning, error, info)

    Returns:
        Colored text or plain text if colors disabled
    """
    # New config system (preferred)
    if UI_CONFIG is not None:
        # Map legacy Fore.XXX to color keys
        color_map = {
            str(Fore.RED): 'error',
            str(Fore.GREEN): 'success',
            str(Fore.YELLOW): 'warning',
            str(Fore.CYAN): 'header',
            str(Fore.WHITE): 'info',
            str(Fore.MAGENTA): 'accent',
            str(Fore.BLUE): 'secondary'
        }

        # Try to map legacy color to key
        color_key = color_map.get(str(color), 'info')

        # Or use color directly if it's a key
        if isinstance(color, str) and color in UI_CONFIG.colors:
            color_key = color

        return UI_CONFIG.colored(text, color_key)

    # Legacy fallback
    if HAS_COLOR:
        return f"{color}{text}{Style.RESET_ALL}"
    return text



def select_regions(default_regions: List[str] = None, prompt_message: str = None) -> List[str]:
    """
    Interactive region selection with preset options

    Args:
        default_regions: Default regions if user presses Enter
        prompt_message: Custom prompt message (optional)

    Returns:
        List of selected regions
    """
    if default_regions is None:
        default_regions = ['KR']

    if prompt_message is None:
        prompt_message = "Select regions:"

    print(f"\n{colored(prompt_message, Fore.CYAN + Style.BRIGHT)}")
    print(f"  {colored('0.', Fore.WHITE)} 🌍 {colored('All Markets', Fore.RED + Style.BRIGHT)} (전체: KR, US, HK, JP, CN, VN)")
    print(f"  {colored('1.', Fore.WHITE)} 🇰🇷 {colored('KR only', Fore.GREEN)} (한국)")
    print(f"  {colored('2.', Fore.WHITE)} 🇺🇸 {colored('US only', Fore.BLUE)} (미국)")
    print(f"  {colored('3.', Fore.WHITE)} 🇭🇰 {colored('HK only', Fore.MAGENTA)} (홍콩)")
    print(f"  {colored('4.', Fore.WHITE)} 🇯🇵 {colored('JP only', Fore.CYAN)} (일본)")
    print(f"  {colored('5.', Fore.WHITE)} 🌏 {colored('KR + US', Fore.YELLOW)} (한국 + 미국)")
    print(f"  {colored('6.', Fore.WHITE)} 🌏 {colored('KR + HK', Fore.YELLOW)} (한국 + 홍콩)")
    print(f"  {colored('7.', Fore.WHITE)} 🌏 {colored('All Asian', Fore.YELLOW)} (KR + HK + JP)")
    print(f"  {colored('8.', Fore.WHITE)} ⚙️  {colored('Custom', Fore.MAGENTA)} (직접 입력)")
    default_str = ', '.join(default_regions)
    print(f"  {colored('Enter', Fore.WHITE)} {colored(f'Default ({default_str})', Fore.GREEN)}")
    print()

    choice = input(f"{colored('선택 (0-8 or Enter):', Fore.CYAN)} ").strip().lower()

    if not choice:
        return default_regions
    elif choice in ['0', 'a', 'all']:  # All Markets (단축키 지원)
        return ['KR', 'US', 'HK', 'JP', 'CN', 'VN']
    elif choice == '1':
        return ['KR']
    elif choice == '2':
        return ['US']
    elif choice == '3':
        return ['HK']
    elif choice == '4':
        return ['JP']
    elif choice == '5':
        return ['KR', 'US']
    elif choice == '6':
        return ['KR', 'HK']
    elif choice == '7':
        return ['KR', 'HK', 'JP']
    elif choice == '8':
        print(f"\n{colored('Available regions:', Fore.CYAN)} KR US HK JP CN VN")
        regions_input = input(f"{colored('Enter regions (space-separated):', Fore.CYAN)} ").strip()
        if regions_input:
            return regions_input.split()
        return default_regions
    else:
        print(f"{colored('❌ Invalid choice. Using default.', Fore.RED)}")
        return default_regions


def print_banner():
    """
    Print application banner

    Uses UI_CONFIG.format_banner() if available, otherwise legacy format.
    """
    if UI_CONFIG is not None:
        # New config system with formatted banner
        print(UI_CONFIG.format_banner())
    else:
        # Legacy fallback
        banner = f"""
{colored('╔════════════════════════════════════════════════════════════════╗', Fore.CYAN)}
{colored('║', Fore.CYAN)}   {colored('📊 Spock Database Refresh Tool', Fore.WHITE + Style.BRIGHT)}                          {colored('║', Fore.CYAN)}
{colored('║', Fore.CYAN)}   {colored('Cross-platform data update utility', Fore.WHITE)}                       {colored('║', Fore.CYAN)}
{colored('║', Fore.CYAN)}   {colored('Version 1.0.0', Fore.WHITE)}                                             {colored('║', Fore.CYAN)}
{colored('╚════════════════════════════════════════════════════════════════╝', Fore.CYAN)}
        """
        print(banner)


def get_database_status():
    """Get current database status with regional breakdown"""
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()

        # Get counts using execute_query
        # OHLCV data - overall
        ohlcv_result = db.execute_query("SELECT COUNT(*), MAX(date) FROM ohlcv_data")
        if ohlcv_result:
            ohlcv_count = ohlcv_result[0]['count']
            latest_ohlcv = ohlcv_result[0]['max']
        else:
            ohlcv_count, latest_ohlcv = 0, None

        # OHLCV data - by region
        ohlcv_by_region_query = """
        SELECT
            region,
            COUNT(*) as count,
            MAX(date) as latest_date
        FROM ohlcv_data
        GROUP BY region
        ORDER BY region
        """
        ohlcv_by_region = db.execute_query(ohlcv_by_region_query)

        # Convert to dict for easier access
        regional_data = {}
        if ohlcv_by_region:
            for row in ohlcv_by_region:
                regional_data[row['region']] = {
                    'count': row['count'],
                    'latest_date': row['latest_date']
                }

        # Tickers
        ticker_result = db.execute_query("SELECT COUNT(*) FROM tickers")
        ticker_count = ticker_result[0]['count'] if ticker_result else 0

        # Fundamentals
        fund_result = db.execute_query("SELECT COUNT(*), MAX(date) FROM ticker_fundamentals")
        if fund_result:
            fund_count = fund_result[0]['count']
            latest_fund = fund_result[0]['max']
        else:
            fund_count, latest_fund = 0, None

        # Factor scores
        factor_result = db.execute_query("SELECT COUNT(*), MAX(date) FROM factor_scores")
        if factor_result:
            factor_count = factor_result[0]['count']
            latest_factor = factor_result[0]['max']
        else:
            factor_count, latest_factor = 0, None

        # Macro data - Global Market Indices
        indices_result = db.execute_query("SELECT COUNT(*), MAX(date) FROM global_market_indices")
        if indices_result:
            indices_count = indices_result[0]['count']
            latest_indices = indices_result[0]['max']
        else:
            indices_count, latest_indices = 0, None

        # Macro data - Market Sentiment
        sentiment_result = db.execute_query("SELECT COUNT(*), MAX(date) FROM market_sentiment")
        if sentiment_result:
            sentiment_count = sentiment_result[0]['count']
            latest_sentiment = sentiment_result[0]['max']
        else:
            sentiment_count, latest_sentiment = 0, None

        db.close_pool()

        return {
            'ohlcv_count': ohlcv_count,
            'latest_ohlcv': latest_ohlcv,
            'ohlcv_by_region': regional_data,
            'ticker_count': ticker_count,
            'fund_count': fund_count,
            'latest_fund': latest_fund,
            'factor_count': factor_count,
            'latest_factor': latest_factor,
            'indices_count': indices_count,
            'latest_indices': latest_indices,
            'sentiment_count': sentiment_count,
            'latest_sentiment': latest_sentiment
        }
    except Exception as e:
        return None


def get_listing_date_coverage():
    """
    Get listing_date coverage by region

    Returns:
        dict: {
            'KR': {'total': 3799, 'with_date': 3793, 'coverage': 99.84},
            'US': {'total': 6532, 'with_date': 6017, 'coverage': 92.12},
            ...
        }
    """
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()

        query = """
        SELECT
            region,
            COUNT(*) as total_tickers,
            COUNT(listing_date) as with_listing_date,
            ROUND(COUNT(listing_date)::numeric / COUNT(*) * 100, 2) as coverage_pct
        FROM tickers
        WHERE is_active = true
        GROUP BY region
        ORDER BY region
        """

        rows = db.execute_query(query)
        db.close_pool()

        if not rows:
            return None

        result = {}
        for row in rows:
            region = row['region']
            total = row['total_tickers']
            with_date = row['with_listing_date']
            coverage = float(row['coverage_pct'])

            result[region] = {
                'total': total,
                'with_date': with_date,
                'coverage': coverage
            }

        return result

    except Exception as e:
        return None


def get_listing_date_coverage_detailed():
    """
    Enhanced coverage with backfill metadata and recommendations

    Returns:
        dict: {
            'KR': {
                'total': 3799,
                'with_date': 3793,
                'without_date': 6,
                'coverage': 99.84,
                'status': 'excellent',  # excellent/good/fair/poor
                'yfinance_unavailable': 0,
                'yfinance_limit_reached': False,
                'estimated_backfill_time_sec': 30.0,
                'last_backfill_date': datetime,
                'recommendation': 'optimal_coverage'
            },
            ...
        }
        None if database unavailable
    """
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()

        # Base coverage query
        base_query = """
        SELECT
            region,
            COUNT(*) as total_tickers,
            COUNT(listing_date) as with_listing_date,
            COUNT(*) FILTER (WHERE listing_date IS NULL) as without_listing_date,
            ROUND(COUNT(listing_date)::numeric / COUNT(*) * 100, 2) as coverage_pct
        FROM tickers
        WHERE is_active = true
        GROUP BY region
        ORDER BY region
        """

        # Yfinance unavailable count
        yfinance_query = """
        SELECT
            region,
            COUNT(*) as yfinance_unavailable_count
        FROM tickers
        WHERE is_active = true
          AND data_source = 'yfinance_unavailable'
        GROUP BY region
        """

        # Last backfill timestamp
        last_backfill_query = """
        SELECT
            region,
            MAX(last_updated) as last_backfill
        FROM tickers
        WHERE is_active = true
          AND listing_date IS NOT NULL
        GROUP BY region
        """

        base_rows = db.execute_query(base_query)
        yfinance_rows = db.execute_query(yfinance_query)
        last_backfill_rows = db.execute_query(last_backfill_query)

        db.close_pool()

        # Build detailed result
        result = {}
        yfinance_dict = {r['region']: r['yfinance_unavailable_count'] for r in (yfinance_rows or [])}
        last_backfill_dict = {r['region']: r['last_backfill'] for r in (last_backfill_rows or [])}

        for row in (base_rows or []):
            region = row['region']
            total = row['total_tickers']
            with_date = row['with_listing_date']
            without_date = row['without_listing_date']
            coverage = float(row['coverage_pct'])

            # yfinance unavailable count
            yfinance_unavailable = yfinance_dict.get(region, 0)
            yfinance_limit_reached = (yfinance_unavailable == without_date and without_date > 0)

            # Status classification
            if coverage >= 95:
                status = 'excellent'
            elif coverage >= 80:
                status = 'good'
            elif coverage >= 50:
                status = 'fair'
            else:
                status = 'poor'

            # Estimated backfill time (rough approximations)
            time_per_ticker_sec = {
                'KR': 0.02,   # KRX API (fast)
                'US': 2.5,    # yfinance (slow)
                'JP': 2.0,    # yfinance (slow)
                'HK': 2.0,    # yfinance (slow)
                'CN': 2.0,    # yfinance (slow)
                'VN': 2.0     # yfinance (slow)
            }
            estimated_time = without_date * time_per_ticker_sec.get(region, 2.0)

            # Recommendation logic
            if yfinance_limit_reached:
                recommendation = 'optimal_coverage'  # Cannot improve further
            elif coverage >= 95:
                recommendation = 'no_action_needed'
            elif coverage >= 80:
                recommendation = 'optional_backfill'
            else:
                recommendation = 'backfill_recommended'

            result[region] = {
                'total': total,
                'with_date': with_date,
                'without_date': without_date,
                'coverage': coverage,
                'status': status,
                'yfinance_unavailable': yfinance_unavailable,
                'yfinance_limit_reached': yfinance_limit_reached,
                'estimated_backfill_time_sec': estimated_time,
                'last_backfill_date': last_backfill_dict.get(region),
                'recommendation': recommendation
            }

        return result

    except Exception as e:
        return None


def print_listing_date_status():
    """Print listing_date coverage status by region"""
    print(f"\n{colored('📅 Listing Date Coverage Status', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 70)

    coverage = get_listing_date_coverage()

    if coverage:
        print(f"{'Region':<8} {'Total':<10} {'With Date':<12} {'Coverage':<12} {'Status'}")
        print("-" * 70)

        for region, data in coverage.items():
            total = data['total']
            with_date = data['with_date']
            cov_pct = data['coverage']

            # Color and status icon
            if cov_pct >= 95:
                status = colored('✅ Excellent', Fore.GREEN)
                cov_color = Fore.GREEN
            elif cov_pct >= 80:
                status = colored('⚠️  Good', Fore.YELLOW)
                cov_color = Fore.YELLOW
            elif cov_pct >= 50:
                status = colored('⚠️  Fair', Fore.YELLOW)
                cov_color = Fore.YELLOW
            else:
                status = colored('❌ Poor', Fore.RED)
                cov_color = Fore.RED

            print(f"{region:<8} {total:<10} {with_date:<12} "
                  f"{colored(f'{cov_pct:.2f}%', cov_color):<20} {status}")

        print("-" * 70)

        # Overall summary
        total_all = sum(d['total'] for d in coverage.values())
        with_date_all = sum(d['with_date'] for d in coverage.values())
        overall_cov = (with_date_all / total_all * 100) if total_all > 0 else 0

        print(f"Overall: {with_date_all:,} / {total_all:,} tickers "
              f"({colored(f'{overall_cov:.2f}%', Fore.CYAN)})")
    else:
        print(f"  {colored('❌ Cannot connect to database', Fore.RED)}")
        print(f"  {colored('💡 Make sure PostgreSQL is running and .env is configured', Fore.YELLOW)}")

    print("=" * 70)


def print_listing_date_status_enhanced():
    """Print enhanced listing_date coverage with smart recommendations"""
    print(f"\n{colored('📅 Listing Date Coverage Analysis (Enhanced)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 120)

    coverage = get_listing_date_coverage_detailed()

    if coverage:
        # Header
        print(f"{'Region':<8} {'Total':<8} {'With Date':<10} {'Without':<9} "
              f"{'Coverage':<12} {'Status':<15} {'yfinance N/A':<14} {'Est. Time':<12} {'Recommendation'}")
        print("-" * 120)

        total_all = 0
        with_date_all = 0
        without_date_all = 0
        yfinance_unavailable_all = 0

        for region, data in sorted(coverage.items()):
            total = data['total']
            with_date = data['with_date']
            without_date = data['without_date']
            cov_pct = data['coverage']
            status_key = data['status']
            yfinance_unavailable = data['yfinance_unavailable']
            yfinance_limit_reached = data['yfinance_limit_reached']
            estimated_time_sec = data['estimated_backfill_time_sec']
            recommendation = data['recommendation']
            last_backfill = data.get('last_backfill_date')

            # Accumulate totals
            total_all += total
            with_date_all += with_date
            without_date_all += without_date
            yfinance_unavailable_all += yfinance_unavailable

            # Color and status display
            if status_key == 'excellent':
                status_display = colored('✅ Excellent', Fore.GREEN)
                cov_color = Fore.GREEN
            elif status_key == 'good':
                status_display = colored('✔️  Good', Fore.YELLOW)
                cov_color = Fore.YELLOW
            elif status_key == 'fair':
                status_display = colored('⚠️  Fair', Fore.YELLOW)
                cov_color = Fore.YELLOW
            else:
                status_display = colored('❌ Poor', Fore.RED)
                cov_color = Fore.RED

            # yfinance unavailable display
            if yfinance_limit_reached:
                yf_display = colored(f'{yfinance_unavailable} (limit)', Fore.RED)
            elif yfinance_unavailable > 0:
                yf_display = colored(f'{yfinance_unavailable}', Fore.YELLOW)
            else:
                yf_display = colored('0', Fore.GREEN)

            # Estimated time display
            if estimated_time_sec < 60:
                time_display = f"{estimated_time_sec:.1f}s"
            else:
                time_display = f"{estimated_time_sec / 60:.1f}m"

            # Recommendation display
            if recommendation == 'optimal_coverage':
                rec_display = colored('✅ Optimal', Fore.GREEN)
            elif recommendation == 'no_action_needed':
                rec_display = colored('✔️  No Action', Fore.CYAN)
            elif recommendation == 'optional_backfill':
                rec_display = colored('💡 Optional', Fore.YELLOW)
            else:
                rec_display = colored('⚠️  Recommended', Fore.RED)

            print(f"{region:<8} {total:<8} {with_date:<10} {without_date:<9} "
                  f"{colored(f'{cov_pct:.2f}%', cov_color):<20} {status_display:<23} "
                  f"{yf_display:<22} {time_display:<12} {rec_display}")

        print("-" * 120)

        # Overall summary
        overall_cov = (with_date_all / total_all * 100) if total_all > 0 else 0
        print(f"\n{colored('📊 Overall Summary:', Fore.CYAN + Style.BRIGHT)}")
        print(f"  Total Tickers:         {colored(f'{total_all:,}', Fore.WHITE)}")
        print(f"  With Listing Date:     {colored(f'{with_date_all:,}', Fore.GREEN)} ({overall_cov:.2f}%)")
        print(f"  Without Listing Date:  {colored(f'{without_date_all:,}', Fore.YELLOW)}")
        print(f"  yfinance Unavailable:  {colored(f'{yfinance_unavailable_all:,}', Fore.RED)}")

        # Smart recommendations
        print(f"\n{colored('💡 Smart Recommendations:', Fore.YELLOW + Style.BRIGHT)}")
        if overall_cov >= 95:
            print(f"  {colored('✅ Coverage is excellent. No action needed.', Fore.GREEN)}")
        elif overall_cov >= 80:
            print(f"  {colored('✔️  Coverage is good. Consider optional backfill for completeness.', Fore.CYAN)}")
        else:
            print(f"  {colored('⚠️  Coverage is below target. Backfill recommended.', Fore.YELLOW)}")

        if yfinance_unavailable_all > 0:
            print(f"  {colored(f'⚠️  {yfinance_unavailable_all} tickers unavailable via yfinance (special securities, delisted, etc.)', Fore.YELLOW)}")

    else:
        print(f"  {colored('❌ Cannot connect to database', Fore.RED)}")
        print(f"  {colored('💡 Make sure PostgreSQL is running and .env is configured', Fore.YELLOW)}")

    print("=" * 120)


def validate_backfill_readiness():
    """
    Pre-execution validation for listing_date backfill

    Returns:
        tuple: (bool: is_ready, list: issues)
    """
    import os
    import shutil

    issues = []

    # 1. Database connection check
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager
        db = PostgresDatabaseManager()
        test_query = "SELECT 1"
        db.execute_query(test_query)
        db.close_pool()
    except Exception as e:
        issues.append(f"❌ Database connection failed: {str(e)}")

    # 2. Backfill scripts existence check
    kr_script = "scripts/backfill_listing_dates_kr.py"
    overseas_script = "scripts/backfill_listing_dates_overseas.py"

    if not os.path.exists(kr_script):
        issues.append(f"❌ KR backfill script not found: {kr_script}")
    if not os.path.exists(overseas_script):
        issues.append(f"❌ Overseas backfill script not found: {overseas_script}")

    # 3. API keys and environment variables check
    try:
        from dotenv import load_dotenv
        load_dotenv()

        # Check KIS API keys (for KR market)
        kis_app_key = os.getenv("KIS_APP_KEY")
        kis_app_secret = os.getenv("KIS_APP_SECRET")

        if not kis_app_key or not kis_app_secret:
            issues.append("⚠️  KIS API keys not configured (required for KR market)")

    except Exception as e:
        issues.append(f"⚠️  Environment configuration issue: {str(e)}")

    # 4. Python dependencies check
    try:
        import yfinance
    except ImportError:
        issues.append("❌ yfinance library not installed (required for overseas markets)")

    try:
        import pykrx
    except ImportError:
        issues.append("⚠️  pykrx library not installed (optional for KR market)")

    # 5. Disk space check (require at least 100MB free)
    try:
        stat = shutil.disk_usage(".")
        free_mb = stat.free / (1024 * 1024)
        if free_mb < 100:
            issues.append(f"⚠️  Low disk space: {free_mb:.1f} MB free (recommend >100MB)")
    except Exception as e:
        issues.append(f"⚠️  Disk space check failed: {str(e)}")

    # Note: Process-level concurrency control is now handled by file-based locks
    # (see modules/concurrency/lock_manager.py and @with_lock decorators)

    is_ready = len(issues) == 0
    return is_ready, issues


def generate_smart_recommendations():
    """
    Generate smart recommendations based on coverage analysis

    Returns:
        list: [
            {
                'region': 'KR',
                'priority': 1,  # 1=high, 2=medium, 3=low
                'action': 'backfill_recommended',
                'reason': 'Coverage below 80%',
                'estimated_time_sec': 120.0,
                'command': 'python3 scripts/backfill_listing_dates_kr.py'
            },
            ...
        ]
    """
    coverage = get_listing_date_coverage_detailed()

    if not coverage:
        return []

    recommendations = []

    for region, data in sorted(coverage.items()):
        recommendation_type = data['recommendation']
        cov_pct = data['coverage']
        without_date = data['without_date']
        yfinance_limit_reached = data['yfinance_limit_reached']
        estimated_time_sec = data['estimated_backfill_time_sec']

        # Determine priority and action
        if recommendation_type == 'optimal_coverage':
            # yfinance limit reached, cannot improve further
            priority = 3
            action = 'no_action'
            reason = f'Optimal coverage ({cov_pct:.2f}%). yfinance limit reached for remaining tickers.'
        elif recommendation_type == 'no_action_needed':
            priority = 3
            action = 'no_action'
            reason = f'Excellent coverage ({cov_pct:.2f}%). No action needed.'
        elif recommendation_type == 'optional_backfill':
            priority = 2
            action = 'optional_backfill'
            reason = f'Good coverage ({cov_pct:.2f}%). Optional backfill for {without_date} tickers.'
        else:  # backfill_recommended
            priority = 1
            action = 'backfill_recommended'
            reason = f'Coverage below target ({cov_pct:.2f}%). Backfill {without_date} tickers recommended.'

        # Generate command
        if region == 'KR':
            command = 'python3 scripts/backfill_listing_dates_kr.py'
        else:
            command = f'python3 scripts/backfill_listing_dates_overseas.py --regions {region} --delay 0.2'

        recommendations.append({
            'region': region,
            'priority': priority,
            'action': action,
            'reason': reason,
            'estimated_time_sec': estimated_time_sec,
            'command': command
        })

    # Sort by priority (high to low)
    recommendations.sort(key=lambda x: x['priority'])

    return recommendations


def print_smart_recommendations():
    """Print smart recommendations for listing_date backfill"""
    print(f"\n{colored('🎯 Smart Recommendations', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 100)

    recommendations = generate_smart_recommendations()

    if not recommendations:
        print(f"  {colored('❌ Cannot generate recommendations (database unavailable)', Fore.RED)}")
        print("=" * 100)
        return

    high_priority = [r for r in recommendations if r['priority'] == 1]
    medium_priority = [r for r in recommendations if r['priority'] == 2]
    low_priority = [r for r in recommendations if r['priority'] == 3]

    # High priority recommendations
    if high_priority:
        print(f"\n{colored('🚨 High Priority (Action Recommended):', Fore.RED + Style.BRIGHT)}")
        for rec in high_priority:
            print(f"\n  Region: {colored(rec['region'], Fore.WHITE + Style.BRIGHT)}")
            print(f"  Reason: {rec['reason']}")
            if rec['estimated_time_sec'] < 60:
                time_str = f"{rec['estimated_time_sec']:.1f} seconds"
            else:
                time_str = f"{rec['estimated_time_sec'] / 60:.1f} minutes"
            print(f"  Estimated Time: {colored(time_str, Fore.YELLOW)}")
            print(f"  Command: {colored(rec['command'], Fore.CYAN)}")

    # Medium priority recommendations
    if medium_priority:
        print(f"\n{colored('💡 Medium Priority (Optional):', Fore.YELLOW + Style.BRIGHT)}")
        for rec in medium_priority:
            print(f"\n  Region: {colored(rec['region'], Fore.WHITE + Style.BRIGHT)}")
            print(f"  Reason: {rec['reason']}")
            if rec['estimated_time_sec'] < 60:
                time_str = f"{rec['estimated_time_sec']:.1f} seconds"
            else:
                time_str = f"{rec['estimated_time_sec'] / 60:.1f} minutes"
            print(f"  Estimated Time: {colored(time_str, Fore.YELLOW)}")
            print(f"  Command: {colored(rec['command'], Fore.CYAN)}")

    # Low priority recommendations (no action needed)
    if low_priority:
        print(f"\n{colored('✅ Low Priority (No Action Needed):', Fore.GREEN + Style.BRIGHT)}")
        for rec in low_priority:
            print(f"  {rec['region']}: {rec['reason']}")

    # Overall summary
    total_estimated_time = sum(r['estimated_time_sec'] for r in high_priority + medium_priority)
    if total_estimated_time > 0:
        if total_estimated_time < 60:
            total_time_str = f"{total_estimated_time:.1f} seconds"
        else:
            total_time_str = f"{total_estimated_time / 60:.1f} minutes"

        print(f"\n{colored('📊 Summary:', Fore.CYAN + Style.BRIGHT)}")
        print(f"  Total recommended actions: {colored(len(high_priority + medium_priority), Fore.YELLOW)}")
        print(f"  Total estimated time: {colored(total_time_str, Fore.YELLOW)}")

    print("\n" + "=" * 100)


def print_status():
    """Print current database status with regional breakdown"""
    print(f"\n{colored('📊 Current Database Status', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 80)

    status = get_database_status()

    if status:
        print(f"  Tickers:        {colored(f'{status['ticker_count']:,}', Fore.GREEN)}")
        print(f"  OHLCV Records:  {colored(f'{status['ohlcv_count']:,}', Fore.GREEN)} (latest: {status['latest_ohlcv']})")

        # Regional OHLCV breakdown
        regional_data = status.get('ohlcv_by_region', {})
        if regional_data:
            region_emojis = {
                'KR': '🇰🇷',
                'US': '🇺🇸',
                'HK': '🇭🇰',
                'JP': '🇯🇵',
                'CN': '🇨🇳',
                'VN': '🇻🇳'
            }

            print(f"\n  {colored('Regional OHLCV Breakdown:', Fore.YELLOW + Style.BRIGHT)}")

            # Sort regions by predefined order
            region_order = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']
            sorted_regions = [r for r in region_order if r in regional_data]
            sorted_regions.extend([r for r in regional_data.keys() if r not in region_order])

            for region in sorted_regions:
                data = regional_data[region]
                count = data['count']
                latest_date = data['latest_date']

                # Calculate days old
                if latest_date:
                    days_old = (datetime.now().date() - latest_date).days
                    status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
                    freshness = f"({days_old} days old)" if days_old > 0 else "(up to date)"
                else:
                    status_color = Fore.RED
                    freshness = "(no data)"

                emoji = region_emojis.get(region, '🌍')
                print(f"    {emoji} {colored(region, Fore.WHITE)}: "
                      f"{colored(f'{count:,}', Fore.CYAN)} records | "
                      f"Latest: {colored(str(latest_date), status_color)} "
                      f"{colored(freshness, status_color)}")

        print(f"\n  Fundamentals:   {colored(f'{status['fund_count']:,}', Fore.GREEN)} (latest: {status['latest_fund']})")
        print(f"  Factor Scores:  {colored(f'{status['factor_count']:,}', Fore.GREEN)} (latest: {status['latest_factor']})")

        # Macro indicators
        print(f"\n  {colored('Macro Indicators:', Fore.YELLOW + Style.BRIGHT)}")

        # Global Market Indices
        indices_count = status.get('indices_count', 0)
        latest_indices = status.get('latest_indices')
        if latest_indices:
            days_old = (datetime.now().date() - latest_indices).days
            status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
            freshness = f"({days_old} days old)" if days_old > 0 else "(up to date)"
        else:
            status_color = Fore.RED
            freshness = "(no data)"

        print(f"    📊 Global Indices: {colored(f'{indices_count:,}', Fore.CYAN)} records | "
              f"Latest: {colored(str(latest_indices), status_color)} {colored(freshness, status_color)}")

        # Market Sentiment
        sentiment_count = status.get('sentiment_count', 0)
        latest_sentiment = status.get('latest_sentiment')
        if latest_sentiment:
            days_old = (datetime.now().date() - latest_sentiment).days
            status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
            freshness = f"({days_old} days old)" if days_old > 0 else "(up to date)"
        else:
            status_color = Fore.RED
            freshness = "(no data)"

        print(f"    📈 Market Sentiment: {colored(f'{sentiment_count:,}', Fore.CYAN)} records | "
              f"Latest: {colored(str(latest_sentiment), status_color)} {colored(freshness, status_color)}")

        # Check overall freshness
        if status['latest_ohlcv']:
            days_old = (datetime.now().date() - status['latest_ohlcv']).days
            if days_old == 0:
                print(f"\n  Overall Freshness: {colored('✅ Up to date!', Fore.GREEN)}")
            elif days_old <= 3:
                print(f"\n  Overall Freshness: {colored(f'⚠️  {days_old} days old', Fore.YELLOW)}")
            else:
                print(f"\n  Overall Freshness: {colored(f'❌ {days_old} days old - update recommended', Fore.RED)}")
    else:
        print(f"  {colored('❌ Cannot connect to database', Fore.RED)}")
        print(f"  {colored('💡 Make sure PostgreSQL is running and .env is configured', Fore.YELLOW)}")

    print("=" * 60)


def interactive_menu():
    """Show interactive menu and handle user selection"""
    # Cleanup stale locks on startup (silent, non-blocking)
    try:
        cleanup_stale_locks(max_age_hours=24)
    except Exception:
        pass  # Don't fail if cleanup has issues

    while True:
        print_banner()

        # Show status
        status = get_database_status()
        if status:
            # Regional OHLCV status
            regional_data = status.get('ohlcv_by_region', {})

            # Define region emojis
            region_emojis = {
                'KR': '🇰🇷',
                'US': '🇺🇸',
                'HK': '🇭🇰',
                'JP': '🇯🇵',
                'CN': '🇨🇳',
                'VN': '🇻🇳'
            }

            print(f"{colored('Current Status:', Fore.CYAN + Style.BRIGHT)} "
                  f"{colored(f'{status['ohlcv_count']:,} total records', Fore.WHITE)}")

            if regional_data:
                # Sort regions by predefined order
                region_order = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']
                sorted_regions = [r for r in region_order if r in regional_data]
                sorted_regions.extend([r for r in regional_data.keys() if r not in region_order])

                # Build regional status line
                regional_status_parts = []
                for region in sorted_regions:
                    data = regional_data[region]
                    count = data['count']
                    latest_date = data['latest_date']

                    # Calculate days old
                    if latest_date:
                        days_old = (datetime.now().date() - latest_date).days
                        status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
                    else:
                        days_old = 999
                        status_color = Fore.RED

                    # Format count (K/M notation for brevity)
                    if count >= 1_000_000:
                        count_str = f"{count / 1_000_000:.1f}M"
                    elif count >= 1_000:
                        count_str = f"{count / 1_000:.0f}K"
                    else:
                        count_str = str(count)

                    emoji = region_emojis.get(region, '🌍')
                    regional_status_parts.append(
                        f"{emoji} {colored(region, Fore.WHITE)}: {colored(count_str, Fore.CYAN)} "
                        f"{colored(f'({days_old}d)', status_color)}"
                    )

                # Print regional status (2 regions per line for readability)
                print(f"  {' | '.join(regional_status_parts[:3])}")
                if len(regional_status_parts) > 3:
                    print(f"  {' | '.join(regional_status_parts[3:])}")

            # Macro indicators summary
            indices_count = status.get('indices_count', 0)
            latest_indices = status.get('latest_indices')
            sentiment_count = status.get('sentiment_count', 0)
            latest_sentiment = status.get('latest_sentiment')

            macro_parts = []

            # Global Indices
            if indices_count > 0:
                if latest_indices:
                    days_old = (datetime.now().date() - latest_indices).days
                    status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
                else:
                    days_old = 999
                    status_color = Fore.RED

                if indices_count >= 1_000:
                    count_str = f"{indices_count / 1_000:.1f}K"
                else:
                    count_str = str(indices_count)

                macro_parts.append(
                    f"📊 Indices: {colored(count_str, Fore.CYAN)} {colored(f'({days_old}d)', status_color)}"
                )

            # Market Sentiment
            if sentiment_count > 0:
                if latest_sentiment:
                    days_old = (datetime.now().date() - latest_sentiment).days
                    status_color = Fore.GREEN if days_old == 0 else (Fore.YELLOW if days_old <= 3 else Fore.RED)
                else:
                    days_old = 999
                    status_color = Fore.RED

                if sentiment_count >= 1_000:
                    count_str = f"{sentiment_count / 1_000:.1f}K"
                else:
                    count_str = str(sentiment_count)

                macro_parts.append(
                    f"📈 Sentiment: {colored(count_str, Fore.CYAN)} {colored(f'({days_old}d)', status_color)}"
                )

            if macro_parts:
                print(f"  {colored('Macro:', Fore.YELLOW)} {' | '.join(macro_parts)}")
        else:
            print(f"{colored('Current Status:', Fore.CYAN)} {colored('❌ Database not connected', Fore.RED)}")

        print()

        # Check for currently running operations
        locked_operations = []
        for operation in ['quick_refresh', 'full_refresh', 'incremental_refresh', 'listing_date_backfill',
                          'listing_date_backfill_enhanced', 'macro_data_update', 'equity_backfill']:
            if is_operation_locked(operation):
                info = get_operation_info(operation)
                if info:
                    pid = info.get('pid', 'unknown')
                    started = info.get('started', 'unknown')
                    locked_operations.append(f"{operation} (PID: {pid}, started: {started})")

        if locked_operations:
            print(f"{colored('⚠️  Currently Running:', Fore.YELLOW + Style.BRIGHT)}")
            for op in locked_operations:
                print(f"  {colored('▶', Fore.YELLOW)} {op}")
            print()

        # Menu options
        print(f"{colored('선택하세요:', Fore.CYAN + Style.BRIGHT)}")
        print(f"  {colored('1.', Fore.WHITE)} 🚀 {colored('Quick Refresh', Fore.GREEN)} (5분) - OHLCV + 기본적 + 기술적 지표")
        print(f"  {colored('2.', Fore.WHITE)} 📈 {colored('Full Refresh', Fore.YELLOW)} (30분) - 전체 데이터 업데이트")
        print(f"  {colored('3.', Fore.WHITE)} 🔄 {colored('Incremental', Fore.CYAN)} (10분) - 누락된 데이터만")
        print(f"  {colored('4.', Fore.WHITE)} ⚙️  {colored('Custom', Fore.MAGENTA)} - 직접 설정")
        print(f"  {colored('5.', Fore.WHITE)} 📅 {colored('Listing Date Setup', Fore.BLUE)} - 상장일 관리")
        print(f"  {colored('6.', Fore.WHITE)} 📅 {colored('Schedule Setup', Fore.BLUE)} - 자동화 설정")
        print(f"  {colored('7.', Fore.WHITE)} 📊 {colored('Status', Fore.WHITE)} - 현재 데이터 상태 확인")
        print(f"  {colored('8.', Fore.WHITE)} 💰 {colored('Equity Backfill', Fore.CYAN)} - 자본계정 백필")
        print(f"  {colored('9.', Fore.WHITE)} 📈 {colored('Macro Data', Fore.MAGENTA)} - 매크로 데이터 수집")
        print(f"  {colored('10.', Fore.WHITE)} 💹 {colored('Daily PER/PBR', Fore.YELLOW)} - 일일 밸류에이션 업데이트")
        print(f"  {colored('11.', Fore.WHITE)} 📉 {colored('Technical Indicators', Fore.CYAN)} - 기술적 지표 계산")
        print(f"  {colored('12.', Fore.WHITE)} 🔍 {colored('Data Validation', Fore.BLUE)} - 백테스트 데이터 검증")
        print(f"  {colored('13.', Fore.WHITE)} 📊 {colored('Stock Screening', Fore.GREEN)} - 종목 스크리닝")
        print(f"  {colored('0.', Fore.WHITE)} 🚪 {colored('종료', Fore.RED)}")
        print()

        choice = input(f"{colored('선택 (0-13):', Fore.CYAN)} ").strip()

        if choice == '1':
            run_quick_refresh()
        elif choice == '2':
            run_full_refresh()
        elif choice == '3':
            run_incremental_refresh()
        elif choice == '4':
            run_custom_refresh()
        elif choice == '5':
            setup_listing_dates_enhanced()
        elif choice == '6':
            setup_schedule()
        elif choice == '7':
            print_status()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
        elif choice == '8':
            setup_equity_backfill_submenu()
        elif choice == '9':
            setup_macro_data_submenu()
        elif choice == '10':
            run_daily_valuation_update()
        elif choice == '11':
            run_technical_indicators_update()
        elif choice == '12':
            run_data_validation()
        elif choice == '13':
            run_stock_screening()
        elif choice == '0':
            print(f"\n{colored('👋 Bye!', Fore.GREEN)}")
            sys.exit(0)
        else:
            print(f"{colored('❌ Invalid choice. Please select 0-13.', Fore.RED)}")
            input(f"{colored('Press Enter to continue...', Fore.CYAN)}")


def run_update_database(args: List[str], description: str, auto_confirm: bool = False):
    """
    Run update_database.py with given arguments

    Args:
        args: Arguments to pass to update_database.py
        description: User-friendly description of the operation
        auto_confirm: If True, skip confirmation prompts (for CI/CD and automation)
    """
    print(f"\n{colored('🚀 Starting:', Fore.CYAN + Style.BRIGHT)} {description}")
    print("=" * 60)

    # Build command
    cmd = [sys.executable, 'scripts/update_database.py'] + args

    # Show command
    print(f"{colored('Command:', Fore.YELLOW)} {' '.join(cmd)}")
    print()

    # Confirm (skip if auto_confirm or non-interactive terminal)
    if not auto_confirm and sys.stdin.isatty():
        confirm = input(f"{colored('Continue? [Y/n]:', Fore.CYAN)} ").strip().lower()
        if confirm and confirm != 'y':
            print(f"{colored('❌ Cancelled', Fore.YELLOW)}")
            return
    elif auto_confirm:
        print(f"{colored('Continue? [Y/n]:', Fore.CYAN)} y (auto-confirmed)")

    # Run
    try:
        start_time = datetime.now()
        result = subprocess.run(cmd, check=True)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n{colored('✅ Completed successfully!', Fore.GREEN)} ({elapsed:.1f}s)")

    except subprocess.CalledProcessError as e:
        print(f"\n{colored('❌ Update failed!', Fore.RED)}")
        print(f"{colored('Error:', Fore.RED)} {e}")
    except KeyboardInterrupt:
        print(f"\n{colored('⚠️  Interrupted by user', Fore.YELLOW)}")

    # Press Enter to continue (only in interactive mode)
    if sys.stdin.isatty() and not auto_confirm:
        input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


# ============================================================================
# Technical Indicator Calculation Helper Functions
# ============================================================================

def _run_technical_indicators_direct(
    regions: List[str],
    batch_size: int = 100,
    incremental: bool = True,
    dry_run: bool = False
) -> dict:
    """
    Run technical indicator calculation directly using TechnicalIndicatorCalculator.

    This function provides direct integration with the technical indicator calculation
    engine, replacing subprocess-based approach with better progress monitoring and
    error handling.

    Args:
        regions: List of regions to process (KR, HK, US, JP, CN, VN)
        batch_size: Number of tickers to process per batch (50-200)
        incremental: If True, only calculate missing indicators; if False, recalculate all
        dry_run: If True, preview without execution

    Returns:
        dict: Results per region with keys:
            {
                'region_name': {
                    'total_tickers': int,
                    'success_count': int,
                    'failed_count': int,
                    'duration_minutes': float
                }
            }
    """
    import time
    from typing import Dict, Any

    db_manager = PostgresDatabaseManager()
    calculator = TechnicalIndicatorCalculator(db_manager)

    results = {}

    for region in regions:
        print(f"\n{colored('📊 Processing:', Fore.CYAN + Style.BRIGHT)} {region}")
        print("=" * 60)

        if dry_run:
            print(f"{colored('DRY RUN MODE', Fore.YELLOW)} - No actual calculation performed")
            results[region] = {
                'total_tickers': 0,
                'success_count': 0,
                'failed_count': 0,
                'duration_minutes': 0.0
            }
            continue

        try:
            # Run calculation for region
            result = calculator.calculate_all_tickers(
                region=region,
                batch_size=batch_size,
                incremental=incremental
            )

            results[region] = result

            # Progress summary
            print(f"\n{colored('✅ Completed:', Fore.GREEN)} {region}")
            print(f"   Success: {result['success_count']}/{result['total_tickers']} tickers")
            print(f"   Failed: {result['failed_count']} tickers")
            print(f"   Duration: {result['duration_minutes']:.1f} minutes")

        except Exception as e:
            print(f"\n{colored('❌ Error:', Fore.RED)} Failed to calculate indicators for {region}")
            print(f"   {str(e)}")
            results[region] = {
                'total_tickers': 0,
                'success_count': 0,
                'failed_count': 0,
                'duration_minutes': 0.0,
                'error': str(e)
            }

    return results


def select_regions_custom() -> List[str]:
    """
    Interactive custom region selection for technical indicators calculation.

    Allows users to select specific regions or all regions at once.

    Returns:
        List[str]: Selected region codes (e.g., ['KR', 'HK', 'US'])
    """
    available = ['KR', 'HK', 'US', 'JP', 'CN', 'VN']
    selected = []

    print(f"\n{colored('Select regions (space-separated):', Fore.CYAN)}")
    print("  Available regions: KR HK US JP CN VN")
    print()
    print("  Examples:")
    print("    KR HK          - Korea and Hong Kong")
    print("    US JP CN       - United States, Japan, and China")
    print("    ALL            - All regions")
    print()

    input_str = input(f"{colored('Enter regions [KR]:', Fore.CYAN)} ").strip().upper()

    if not input_str:
        return ['KR']  # Default to KR

    if input_str == 'ALL':
        return available

    # Parse space-separated regions
    for region in input_str.split():
        if region in available and region not in selected:
            selected.append(region)
        elif region not in available:
            print(f"{colored('⚠️  Warning:', Fore.YELLOW)} '{region}' is not a valid region (skipped)")

    if not selected:
        print(f"{colored('⚠️  No valid regions selected. Defaulting to KR.', Fore.YELLOW)}")
        return ['KR']

    return selected


@with_lock('quick_refresh', timeout=300)
def run_quick_refresh():
    """Quick refresh - OHLCV + Daily Valuation + Technical Indicators (2-phase execution)"""
    regions = select_regions(default_regions=['KR'], prompt_message="🚀 Quick Refresh - Select regions:")

    # Phase 1: OHLCV + Daily Valuation (via update_database.py)
    print(f"\n{colored('Phase 1: Data Update', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)
    args = [
        '--regions'] + regions + [
        '--steps', 'ohlcv', 'daily_valuation', 'dividend', 'fx_tracking',
        '--incremental',
        '--verbose'
    ]
    run_update_database(args, f'Quick Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation, incremental mode)
    print(f"\n{colored('Phase 2: Technical Indicators Calculation (Incremental)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=True,  # Only calculate missing indicators
        dry_run=False
    )

    # Summary
    total_success = sum(r.get('success_count', 0) for r in results.values())
    total_tickers = sum(r.get('total_tickers', 0) for r in results.values())
    total_time = sum(r.get('duration_minutes', 0.0) for r in results.values())

    print(f"\n{colored('✅ Quick Refresh Complete!', Fore.GREEN + Style.BRIGHT)}")
    print("=" * 60)
    print(f"Regions: {', '.join(regions)}")
    print(f"Technical Indicators: {total_success}/{total_tickers} tickers")
    print(f"Total Time: {total_time:.1f} minutes")
    print("=" * 60)


def check_and_warn_listing_dates():
    """
    Check listing_date coverage before Full Refresh
    Warn if coverage < 80% for active markets

    Returns:
        bool: True to continue, False to cancel
    """
    try:
        coverage = get_listing_date_coverage()

        if not coverage:
            # Database unavailable, continue anyway
            return True

        # Check active markets only (KR, US, JP)
        active_markets = ['KR', 'US', 'JP']
        low_coverage_markets = []

        for region in active_markets:
            if region in coverage and coverage[region]['coverage'] < 80:
                low_coverage_markets.append((region, coverage[region]['coverage']))

        if low_coverage_markets:
            print(f"\n{colored('⚠️  Listing Date Coverage Warning', Fore.YELLOW + Style.BRIGHT)}")
            print("=" * 70)
            print("Some markets have low listing_date coverage:")
            for region, cov in low_coverage_markets:
                print(f"  {region}: {colored(f'{cov:.2f}%', Fore.YELLOW)}")

            print(f"\n{colored('💡 Recommendation:', Fore.CYAN)} Update listing dates for better filtering")
            print("   This helps avoid unnecessary API calls for recently-listed tickers.")
            print(f"\n   Run: {colored('Menu Option 5 > Listing Date Setup', Fore.WHITE)}")

            proceed = input(f"\n{colored('Continue with Full Refresh anyway? [Y/n]:', Fore.CYAN)} ").strip().lower()
            if proceed and proceed != 'y':
                return False

    except Exception as e:
        # Check failed, continue anyway (optional)
        print(f"{colored('⚠️  Could not check listing_date coverage:', Fore.YELLOW)} {e}")

    return True


@with_lock('full_refresh', timeout=600)
def run_full_refresh():
    """Full refresh - all data (2-phase execution)"""
    print(f"\n{colored('⚠️  Warning:', Fore.YELLOW)} Full refresh may take 30+ minutes")

    regions = select_regions(default_regions=['KR', 'US'], prompt_message="📈 Full Refresh - Select regions:")

    # Check listing_date coverage first
    if not check_and_warn_listing_dates():
        print(f"\n{colored('⏭️  Full refresh cancelled', Fore.YELLOW)}")
        input(f"{colored('Press Enter to continue...', Fore.CYAN)}")
        return

    # Phase 1: All data except technical indicators (via update_database.py)
    print(f"\n{colored('Phase 1: Data Update', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)
    args = [
        '--regions'] + regions + [
        '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'dividend', 'fx_tracking',
        '--verbose'
    ]
    run_update_database(args, f'Full Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation, full recalculation)
    print(f"\n{colored('Phase 2: Technical Indicators Calculation (Full Recalculation)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=False,  # Recalculate all indicators (full refresh)
        dry_run=False
    )

    # Summary
    total_success = sum(r.get('success_count', 0) for r in results.values())
    total_tickers = sum(r.get('total_tickers', 0) for r in results.values())
    total_time = sum(r.get('duration_minutes', 0.0) for r in results.values())

    print(f"\n{colored('✅ Full Refresh Complete!', Fore.GREEN + Style.BRIGHT)}")
    print("=" * 60)
    print(f"Regions: {', '.join(regions)}")
    print(f"Technical Indicators: {total_success}/{total_tickers} tickers")
    print(f"Total Time: {total_time:.1f} minutes")
    print("=" * 60)


@with_lock('incremental_refresh', timeout=600)
def run_incremental_refresh():
    """Incremental refresh - missing data only (2-phase execution)"""
    regions = select_regions(default_regions=['KR'], prompt_message="🔄 Incremental Refresh - Select regions:")

    # Phase 1: Missing data except technical indicators (via update_database.py)
    print(f"\n{colored('Phase 1: Data Update (Incremental)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)
    args = [
        '--regions'] + regions + [
        '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'dividend', 'fx_tracking',
        '--incremental',
        '--verbose'
    ]
    run_update_database(args, f'Incremental Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation, incremental mode)
    print(f"\n{colored('Phase 2: Technical Indicators Calculation (Incremental)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=True,  # Only calculate missing indicators (incremental)
        dry_run=False
    )

    # Summary
    total_success = sum(r.get('success_count', 0) for r in results.values())
    total_tickers = sum(r.get('total_tickers', 0) for r in results.values())
    total_time = sum(r.get('duration_minutes', 0.0) for r in results.values())

    print(f"\n{colored('✅ Incremental Refresh Complete!', Fore.GREEN + Style.BRIGHT)}")
    print("=" * 60)
    print(f"Regions: {', '.join(regions)}")
    print(f"Technical Indicators: {total_success}/{total_tickers} tickers")
    print(f"Total Time: {total_time:.1f} minutes")
    print("=" * 60)


def run_custom_refresh():
    """Custom refresh with user input (supports 2-phase execution for technical indicators)"""
    print(f"\n{colored('⚙️  Custom Refresh', Fore.MAGENTA + Style.BRIGHT)}")
    print("=" * 60)

    # Select regions
    print(f"\n{colored('Select regions (space-separated):', Fore.CYAN)}")
    print("  Available: KR US HK JP CN VN")
    regions_input = input(f"{colored('Regions [KR]:', Fore.CYAN)} ").strip()
    regions = regions_input.split() if regions_input else ['KR']

    # Select steps
    print(f"\n{colored('Select steps (space-separated):', Fore.CYAN)}")
    print("  Available: tickers ohlcv fundamentals daily_valuation technical_indicators dividend fx_tracking")
    steps_input = input(f"{colored('Steps [ohlcv fundamentals]:', Fore.CYAN)} ").strip()
    steps = steps_input.split() if steps_input else ['ohlcv', 'fundamentals']

    # Incremental?
    incremental_input = input(f"\n{colored('Incremental mode? [Y/n]:', Fore.CYAN)} ").strip().lower()
    incremental = incremental_input != 'n'

    # Dry run?
    dry_run_input = input(f"{colored('Dry run (preview only)? [y/N]:', Fore.CYAN)} ").strip().lower()
    dry_run = dry_run_input == 'y'

    # Check if technical_indicators is in steps
    has_technical_indicators = 'technical_indicators' in steps

    if has_technical_indicators:
        # 2-phase execution: separate technical_indicators from other steps
        other_steps = [s for s in steps if s != 'technical_indicators']

        # Phase 1: Other data updates (if any)
        if other_steps:
            print(f"\n{colored('Phase 1: Data Update', Fore.CYAN + Style.BRIGHT)}")
            print("=" * 60)
            args = ['--regions'] + regions + ['--steps'] + other_steps
            if incremental:
                args.append('--incremental')
            if dry_run:
                args.append('--dry-run')
            args.append('--verbose')

            run_update_database(args, f"Custom Refresh - Data Update (regions={regions}, steps={other_steps})")

        # Phase 2: Technical Indicators (direct calculation)
        print(f"\n{colored('Phase 2: Technical Indicators Calculation', Fore.CYAN + Style.BRIGHT)}")
        print("=" * 60)

        results = _run_technical_indicators_direct(
            regions=regions,
            batch_size=100,
            incremental=incremental,
            dry_run=dry_run
        )

        # Summary
        total_success = sum(r.get('success_count', 0) for r in results.values())
        total_tickers = sum(r.get('total_tickers', 0) for r in results.values())
        total_time = sum(r.get('duration_minutes', 0.0) for r in results.values())

        print(f"\n{colored('✅ Custom Refresh Complete!', Fore.GREEN + Style.BRIGHT)}")
        print("=" * 60)
        print(f"Regions: {', '.join(regions)}")
        print(f"Steps: {', '.join(steps)}")
        print(f"Technical Indicators: {total_success}/{total_tickers} tickers")
        print(f"Total Time: {total_time:.1f} minutes")
        print("=" * 60)

    else:
        # No technical_indicators: use original subprocess approach
        args = ['--regions'] + regions + ['--steps'] + steps
        if incremental:
            args.append('--incremental')
        if dry_run:
            args.append('--dry-run')
        args.append('--verbose')

        run_update_database(args, f"Custom Refresh (regions={regions}, steps={steps})")


@with_lock('listing_date_backfill_enhanced', timeout=1800)
def run_listing_date_backfill_enhanced():
    """
    Enhanced listing_date backfill with validation, smart recommendations, and progress tracking

    Workflow:
        1. Pre-execution validation
        2. Display current coverage and recommendations
        3. User selection
        4. Execute backfill with monitoring
        5. Post-execution verification
    """
    import subprocess
    import time

    print(f"\n{colored('🚀 Listing Date Backfill (Enhanced)', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 100)

    # Step 1: Pre-execution validation
    print(f"\n{colored('Step 1: Pre-Execution Validation', Fore.YELLOW + Style.BRIGHT)}")
    is_ready, issues = validate_backfill_readiness()

    if not is_ready:
        print(f"\n{colored('⚠️  Validation Issues Detected:', Fore.RED + Style.BRIGHT)}")
        for issue in issues:
            print(f"  {issue}")
        print(f"\n{colored('Please resolve issues before continuing.', Fore.YELLOW)}")

        confirm = input(f"\n{colored('Continue anyway? [y/N]:', Fore.YELLOW)} ").strip().lower()
        if confirm != 'y':
            print(f"{colored('❌ Backfill cancelled.', Fore.RED)}")
            return
    else:
        print(f"{colored('✅ All validation checks passed!', Fore.GREEN)}")

    # Step 2: Display current coverage and recommendations
    print(f"\n{colored('Step 2: Current Coverage & Recommendations', Fore.YELLOW + Style.BRIGHT)}")
    print_listing_date_status_enhanced()
    print_smart_recommendations()

    # Step 3: User selection
    print(f"\n{colored('Step 3: Select Markets to Backfill', Fore.YELLOW + Style.BRIGHT)}")
    print("=" * 100)
    print("  1. KR (Korea)")
    print("  2. HK (Hong Kong)")
    print("  3. CN (China)")
    print("  4. VN (Vietnam)")
    print("  5. US (United States)")
    print("  6. JP (Japan)")
    print("  7. All Markets")
    print("  0. Cancel")
    print("=" * 100)

    choice = input(f"{colored('Select option [0-7]:', Fore.CYAN)} ").strip()

    region_map = {
        '1': ['KR'],
        '2': ['HK'],
        '3': ['CN'],
        '4': ['VN'],
        '5': ['US'],
        '6': ['JP'],
        '7': ['KR', 'HK', 'CN', 'VN', 'US', 'JP']
    }

    if choice == '0':
        print(f"{colored('❌ Backfill cancelled.', Fore.RED)}")
        return

    if choice not in region_map:
        print(f"{colored('❌ Invalid selection.', Fore.RED)}")
        return

    selected_regions = region_map[choice]

    # Step 4: Execute backfill with monitoring
    print(f"\n{colored('Step 4: Executing Backfill', Fore.YELLOW + Style.BRIGHT)}")
    print(f"  Regions: {', '.join(selected_regions)}")
    print("=" * 100)

    confirm = input(f"{colored('Proceed with backfill? [Y/n]:', Fore.CYAN)} ").strip().lower()
    if confirm and confirm != 'y':
        print(f"{colored('❌ Backfill cancelled.', Fore.RED)}")
        return

    overall_start = time.time()
    results = []

    for region in selected_regions:
        print(f"\n{colored(f'▶️  Processing {region} market...', Fore.CYAN + Style.BRIGHT)}")

        if region == 'KR':
            cmd = [sys.executable, 'scripts/backfill_listing_dates_kr.py']
        else:
            cmd = [sys.executable, 'scripts/backfill_listing_dates_overseas.py', '--regions', region, '--delay', '0.2']

        print(f"  Command: {' '.join(cmd)}")

        try:
            start_time = time.time()
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            elapsed = time.time() - start_time

            print(f"  {colored(f'✅ {region} backfill completed in {elapsed:.1f}s', Fore.GREEN)}")
            results.append({'region': region, 'status': 'success', 'elapsed': elapsed})

        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"  {colored(f'❌ {region} backfill failed: {e}', Fore.RED)}")
            results.append({'region': region, 'status': 'failed', 'elapsed': elapsed, 'error': str(e)})

    overall_elapsed = time.time() - overall_start

    # Step 5: Post-execution verification
    print(f"\n{colored('Step 5: Post-Execution Verification', Fore.YELLOW + Style.BRIGHT)}")
    print("=" * 100)
    print_listing_date_status_enhanced()

    # Step 6: Summary
    print(f"\n{colored('📊 Backfill Summary', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 100)
    print(f"  Total Time: {colored(f'{overall_elapsed:.1f}s', Fore.YELLOW)}")
    print(f"  Successful: {colored(sum(1 for r in results if r['status'] == 'success'), Fore.GREEN)}")
    print(f"  Failed: {colored(sum(1 for r in results if r['status'] == 'failed'), Fore.RED)}")
    print("=" * 100)


@with_lock('listing_date_backfill', timeout=1200)
def run_listing_date_backfill(regions: List[str]):
    """
    Run listing_date backfill for specified regions

    Args:
        regions: List of regions to backfill (e.g., ['KR', 'US', 'JP'])
    """
    print(f"\n{colored('🚀 Starting Listing Date Backfill', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 70)

    # KR market backfill
    if 'KR' in regions:
        print(f"\n{colored('📍 KR Market:', Fore.YELLOW)} Using backfill_listing_dates_kr.py")
        cmd_kr = [sys.executable, 'scripts/backfill_listing_dates_kr.py']
        print(f"  Command: {' '.join(cmd_kr)}")

        confirm = input(f"{colored('Continue? [Y/n]:', Fore.CYAN)} ").strip().lower()
        if not confirm or confirm == 'y':
            try:
                start_time = datetime.now()
                subprocess.run(cmd_kr, check=True)
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"{colored('✅ KR backfill completed', Fore.GREEN)} ({elapsed:.1f}s)")
            except subprocess.CalledProcessError as e:
                print(f"{colored('❌ KR backfill failed:', Fore.RED)} {e}")
        else:
            print(f"{colored('⏭️  Skipped KR market', Fore.YELLOW)}")

    # Overseas markets backfill
    overseas_regions = [r for r in regions if r != 'KR']
    if overseas_regions:
        print(f"\n{colored(f'🌍 Overseas Markets:', Fore.YELLOW)} {', '.join(overseas_regions)}")
        print(f"  Using backfill_listing_dates_overseas.py")

        cmd_overseas = [
            sys.executable,
            'scripts/backfill_listing_dates_overseas.py',
            '--regions'
        ] + overseas_regions + [
            '--delay', '0.2'
        ]

        print(f"  Command: {' '.join(cmd_overseas)}")
        print(f"\n{colored('⚠️  Warning:', Fore.YELLOW)} This may take several hours for large markets")
        print(f"  Estimated time: US ~22min, JP ~13min, HK ~9min, CN ~12min, VN ~2min")

        confirm = input(f"{colored('Continue? [Y/n]:', Fore.CYAN)} ").strip().lower()
        if not confirm or confirm == 'y':
            try:
                start_time = datetime.now()
                subprocess.run(cmd_overseas, check=True)
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"{colored('✅ Overseas backfill completed', Fore.GREEN)} ({elapsed:.1f}s)")
            except subprocess.CalledProcessError as e:
                print(f"{colored('❌ Overseas backfill failed:', Fore.RED)} {e}")
        else:
            print(f"{colored('⏭️  Skipped overseas markets', Fore.YELLOW)}")

    # Show updated coverage
    print(f"\n{colored('📊 Updated Coverage:', Fore.CYAN)}")
    print_listing_date_status()

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def setup_listing_dates_enhanced():
    """Enhanced listing date setup submenu with smart recommendations"""
    while True:
        print(f"\n{colored('📅 Listing Date Setup (Enhanced)', Fore.CYAN + Style.BRIGHT)}")
        print("=" * 100)

        # Current status summary
        coverage_detailed = get_listing_date_coverage_detailed()
        if coverage_detailed:
            # Calculate overall statistics
            total_all = sum(d['total'] for d in coverage_detailed.values())
            with_date_all = sum(d['with_date'] for d in coverage_detailed.values())
            without_date_all = sum(d['without_date'] for d in coverage_detailed.values())
            overall_cov = (with_date_all / total_all * 100) if total_all > 0 else 0

            print(f"Overall Coverage: {colored(f'{overall_cov:.2f}%', Fore.CYAN)} "
                  f"({with_date_all:,} / {total_all:,} tickers)")
            print(f"Tickers without listing_date: {colored(f'{without_date_all:,}', Fore.YELLOW)}")

            # Status indicator
            if overall_cov >= 95:
                status_icon = colored('✅ Excellent', Fore.GREEN)
            elif overall_cov >= 80:
                status_icon = colored('✔️  Good', Fore.YELLOW)
            else:
                status_icon = colored('⚠️  Needs Improvement', Fore.RED)
            print(f"Status: {status_icon}")
        else:
            print(f"Overall Coverage: {colored('❌ Database unavailable', Fore.RED)}")

        print()

        # Submenu options
        print(f"{colored('Options:', Fore.CYAN)}")
        print("  1. View Detailed Coverage Status")
        print("  2. View Smart Recommendations")
        print("  3. Run Enhanced Backfill Wizard")
        print("  4. Run Legacy Backfill (basic)")
        print("  0. Back to Main Menu")
        print("=" * 100)

        choice = input(f"{colored('Select option [0-4]:', Fore.CYAN)} ").strip()

        if choice == '1':
            # View detailed coverage status
            print_listing_date_status_enhanced()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '2':
            # View smart recommendations
            print_smart_recommendations()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '3':
            # Run enhanced backfill wizard
            run_listing_date_backfill_enhanced()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '4':
            # Run legacy backfill (for backward compatibility)
            print(f"\n{colored('📋 Legacy Backfill Mode', Fore.YELLOW)}")
            print("  Select regions: KR, HK, CN, VN, US, JP (comma-separated)")
            print("  Example: KR,US,JP")

            regions_input = input(f"{colored('Regions:', Fore.CYAN)} ").strip().upper()
            if regions_input:
                regions = [r.strip() for r in regions_input.split(',')]
                run_listing_date_backfill(regions)
            else:
                print(f"{colored('❌ No regions selected.', Fore.RED)}")

            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '0':
            # Back to main menu
            break

        else:
            print(f"{colored('❌ Invalid selection. Please try again.', Fore.RED)}")
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def setup_listing_dates():
    """Listing date setup submenu"""
    while True:
        print(f"\n{colored('📅 Listing Date Setup', Fore.CYAN + Style.BRIGHT)}")
        print("=" * 70)

        # Current status summary
        coverage = get_listing_date_coverage()
        if coverage:
            total_all = sum(d['total'] for d in coverage.values())
            with_date_all = sum(d['with_date'] for d in coverage.values())
            overall = (with_date_all / total_all * 100) if total_all > 0 else 0
            print(f"Current Overall Coverage: {colored(f'{overall:.2f}%', Fore.CYAN)}")
        else:
            print(f"Current Overall Coverage: {colored('❌ Database unavailable', Fore.RED)}")
        print()

        # Submenu options
        print(f"{colored('Options:', Fore.CYAN)}")
        print(f"  {colored('1.', Fore.WHITE)} 📊 {colored('Check Coverage Status', Fore.CYAN)} - 시장별 커버리지 확인")
        print(f"  {colored('2.', Fore.WHITE)} 🇰🇷 {colored('Backfill KR Market', Fore.GREEN)} (~30초)")
        print(f"  {colored('3.', Fore.WHITE)} 🌍 {colored('Backfill Overseas Markets', Fore.YELLOW)} (~1-4시간)")
        print(f"  {colored('4.', Fore.WHITE)} 🌎 {colored('Backfill All Markets', Fore.MAGENTA)} (~1-4시간)")
        print(f"  {colored('0.', Fore.WHITE)} ◀️  {colored('Back to Main Menu', Fore.RED)}")
        print()

        choice = input(f"{colored('Select (0-4):', Fore.CYAN)} ").strip()

        if choice == '1':
            print_listing_date_status()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '2':
            run_listing_date_backfill(['KR'])

        elif choice == '3':
            print(f"\n{colored('Select overseas regions (space-separated):', Fore.CYAN)}")
            print("  Available: US HK JP CN VN")
            regions_input = input(f"{colored('Regions [US JP]:', Fore.CYAN)} ").strip()
            regions = regions_input.split() if regions_input else ['US', 'JP']
            run_listing_date_backfill(regions)

        elif choice == '4':
            print(f"\n{colored('⚠️  Warning:', Fore.YELLOW)} This will backfill ALL markets (may take 4+ hours)")
            confirm = input(f"{colored('Proceed? [y/N]:', Fore.CYAN)} ").strip().lower()
            if confirm == 'y':
                run_listing_date_backfill(['KR', 'US', 'HK', 'JP', 'CN', 'VN'])
            else:
                print(f"{colored('⏭️  Cancelled', Fore.YELLOW)}")
                input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '0':
            break

        else:
            print(f"{colored('❌ Invalid choice. Please select 0-4.', Fore.RED)}")
            input(f"{colored('Press Enter to continue...', Fore.CYAN)}")


def setup_schedule():
    """Setup automated scheduling"""
    print(f"\n{colored('📅 Schedule Setup', Fore.BLUE + Style.BRIGHT)}")
    print("=" * 60)

    os_name = platform.system()

    if os_name == 'Darwin':  # macOS
        print(f"\n{colored('macOS detected - Using launchd', Fore.GREEN)}")
        setup_schedule_macos()
    elif os_name == 'Linux':
        print(f"\n{colored('Linux detected - Using cron', Fore.GREEN)}")
        setup_schedule_linux()
    elif os_name == 'Windows':
        print(f"\n{colored('Windows detected - Using Task Scheduler', Fore.GREEN)}")
        setup_schedule_windows()
    else:
        print(f"{colored('❌ Unsupported OS:', Fore.RED)} {os_name}")

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def setup_schedule_macos():
    """Setup launchd schedule for macOS"""
    plist_path = os.path.expanduser('~/Library/LaunchAgents/com.spock.refresh.plist')

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spock.refresh</string>

    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{os.path.abspath(__file__)}</string>
        <string>--quick</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>{os.path.expanduser('~/spock_refresh.log')}</string>

    <key>StandardErrorPath</key>
    <string>{os.path.expanduser('~/spock_refresh_error.log')}</string>
</dict>
</plist>
"""

    print(f"\n{colored('📝 LaunchAgent plist file:', Fore.CYAN)}")
    print(f"  Location: {plist_path}")
    print(f"  Schedule: Daily at 09:00 AM")
    print(f"  Command:  {sys.executable} {os.path.abspath(__file__)} --quick")

    create = input(f"\n{colored('Create this schedule? [Y/n]:', Fore.CYAN)} ").strip().lower()
    if create and create != 'y':
        return

    # Create file
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
    with open(plist_path, 'w') as f:
        f.write(plist_content)

    print(f"\n{colored('✅ plist file created!', Fore.GREEN)}")
    print(f"\n{colored('Next steps:', Fore.YELLOW)}")
    print(f"  1. Load the agent:")
    print(f"     {colored(f'launchctl load {plist_path}', Fore.WHITE)}")
    print(f"  2. Check status:")
    print(f"     {colored('launchctl list | grep spock', Fore.WHITE)}")
    print(f"  3. Test run:")
    print(f"     {colored(f'launchctl start com.spock.refresh', Fore.WHITE)}")


def setup_schedule_linux():
    """Setup cron schedule for Linux"""
    cron_entry = f"0 9 * * * {sys.executable} {os.path.abspath(__file__)} --quick >> ~/spock_refresh.log 2>&1"

    print(f"\n{colored('📝 Cron entry:', Fore.CYAN)}")
    print(f"  {cron_entry}")
    print(f"\n  Schedule: Daily at 09:00 AM")
    print(f"  Log file: ~/spock_refresh.log")

    print(f"\n{colored('To add this cron job:', Fore.YELLOW)}")
    print(f"  1. Edit crontab:")
    print(f"     {colored('crontab -e', Fore.WHITE)}")
    print(f"  2. Add this line:")
    print(f"     {colored(cron_entry, Fore.WHITE)}")
    print(f"  3. Save and exit")
    print(f"  4. Verify:")
    print(f"     {colored('crontab -l', Fore.WHITE)}")


def setup_schedule_windows():
    """Setup Task Scheduler for Windows"""
    task_name = "SpockDatabaseRefresh"

    print(f"\n{colored('📝 Windows Task Scheduler:', Fore.CYAN)}")
    print(f"  Task Name: {task_name}")
    print(f"  Schedule:  Daily at 09:00 AM")
    print(f"  Action:    {sys.executable} {os.path.abspath(__file__)} --quick")

    print(f"\n{colored('To create this task:', Fore.YELLOW)}")
    print(f"  1. Open Task Scheduler (taskschd.msc)")
    print(f"  2. Create Basic Task...")
    print(f"  3. Name: {task_name}")
    print(f"  4. Trigger: Daily, 09:00 AM")
    print(f"  5. Action: Start a program")
    print(f"     Program: {colored(sys.executable, Fore.WHITE)}")
    print(f"     Arguments: {colored(f'{os.path.abspath(__file__)} --quick', Fore.WHITE)}")
    print(f"  6. Finish")

    # Offer PowerShell command
    print(f"\n{colored('Or use this PowerShell command (Run as Administrator):', Fore.YELLOW)}")
    ps_cmd = f'''$action = New-ScheduledTaskAction -Execute "{sys.executable}" -Argument "{os.path.abspath(__file__)} --quick"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "{task_name}" -Description "Spock Database Daily Refresh"'''
    print(f"{colored(ps_cmd, Fore.WHITE)}")


# ============================================================================
# Macro Data Collection Functions
# ============================================================================

def get_macro_data_status():
    """
    Get macro data (bonds & commodities) coverage status

    Returns:
        dict: {
            'bonds': {
                'total_records': 2150,
                'date_range': ('2024-01-01', '2025-01-12'),
                'symbols': ['US2Y', 'US10Y', 'US30Y'],
                'latest_date': date(2025, 1, 12)
            },
            'commodities': {
                'total_records': 4300,
                'date_range': ('2024-01-01', '2025-01-12'),
                'symbols': ['GC=F', 'SI=F', 'CL=F', 'NG=F', 'HG=F', 'PL=F'],
                'latest_date': date(2025, 1, 12)
            }
        }
        None if database unavailable
    """
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()

        # Bond yields data
        bonds_query = """
        SELECT
            COUNT(*) as total_records,
            MIN(date) as min_date,
            MAX(date) as max_date,
            array_agg(DISTINCT symbol ORDER BY symbol) as symbols
        FROM bond_yields
        """
        bonds_result = db.execute_query(bonds_query)

        if bonds_result and bonds_result[0]['total_records'] > 0:
            bonds_data = {
                'total_records': bonds_result[0]['total_records'],
                'date_range': (bonds_result[0]['min_date'], bonds_result[0]['max_date']),
                'symbols': bonds_result[0]['symbols'],
                'latest_date': bonds_result[0]['max_date']
            }
        else:
            bonds_data = {
                'total_records': 0,
                'date_range': (None, None),
                'symbols': [],
                'latest_date': None
            }

        # Commodities data
        commodities_query = """
        SELECT
            COUNT(*) as total_records,
            MIN(date) as min_date,
            MAX(date) as max_date,
            array_agg(DISTINCT symbol ORDER BY symbol) as symbols
        FROM commodities
        """
        commodities_result = db.execute_query(commodities_query)

        if commodities_result and commodities_result[0]['total_records'] > 0:
            commodities_data = {
                'total_records': commodities_result[0]['total_records'],
                'date_range': (commodities_result[0]['min_date'], commodities_result[0]['max_date']),
                'symbols': commodities_result[0]['symbols'],
                'latest_date': commodities_result[0]['max_date']
            }
        else:
            commodities_data = {
                'total_records': 0,
                'date_range': (None, None),
                'symbols': [],
                'latest_date': None
            }

        db.close_pool()

        return {
            'bonds': bonds_data,
            'commodities': commodities_data
        }

    except Exception as e:
        return None


def print_macro_data_status():
    """Print macro data (bonds & commodities) status with colored output"""
    print(f"\n{colored('📈 Macro Data Collection Status', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 100)

    status = get_macro_data_status()

    if status:
        # Bonds section
        bonds = status['bonds']
        print(f"\n{colored('💵 Bond Yields (US Treasury):', Fore.YELLOW + Style.BRIGHT)}")
        print(f"  Total Records:     {colored(f'{bonds['total_records']:,}', Fore.CYAN)}")

        if bonds['total_records'] > 0:
            print(f"  Symbols:           {', '.join(bonds['symbols'])}")
            print(f"  Date Range:        {bonds['date_range'][0]} → {bonds['date_range'][1]}")
            print(f"  Latest Date:       {colored(str(bonds['latest_date']), Fore.GREEN)}")

            # Check freshness
            if bonds['latest_date']:
                days_old = (datetime.now().date() - bonds['latest_date']).days
                if days_old == 0:
                    print(f"  Freshness:         {colored('✅ Up to date!', Fore.GREEN)}")
                elif days_old <= 3:
                    print(f"  Freshness:         {colored(f'⚠️  {days_old} days old', Fore.YELLOW)}")
                else:
                    print(f"  Freshness:         {colored(f'❌ {days_old} days old - update recommended', Fore.RED)}")
        else:
            print(f"  {colored('⚠️  No data available - run initial backfill', Fore.YELLOW)}")

        # Commodities section
        commodities = status['commodities']
        print(f"\n{colored('🛢️  Commodities (Futures):', Fore.YELLOW + Style.BRIGHT)}")
        print(f"  Total Records:     {colored(f'{commodities['total_records']:,}', Fore.CYAN)}")

        if commodities['total_records'] > 0:
            print(f"  Symbols:           {', '.join(commodities['symbols'])}")
            print(f"  Date Range:        {commodities['date_range'][0]} → {commodities['date_range'][1]}")
            print(f"  Latest Date:       {colored(str(commodities['latest_date']), Fore.GREEN)}")

            # Check freshness
            if commodities['latest_date']:
                days_old = (datetime.now().date() - commodities['latest_date']).days
                if days_old == 0:
                    print(f"  Freshness:         {colored('✅ Up to date!', Fore.GREEN)}")
                elif days_old <= 3:
                    print(f"  Freshness:         {colored(f'⚠️  {days_old} days old', Fore.YELLOW)}")
                else:
                    print(f"  Freshness:         {colored(f'❌ {days_old} days old - update recommended', Fore.RED)}")
        else:
            print(f"  {colored('⚠️  No data available - run initial backfill', Fore.YELLOW)}")

        # Overall summary
        total_records = bonds['total_records'] + commodities['total_records']
        print(f"\n{colored('📊 Overall Summary:', Fore.CYAN + Style.BRIGHT)}")
        print(f"  Total Records:     {colored(f'{total_records:,}', Fore.WHITE)}")
        print(f"  Data Sources:      {colored('yfinance API', Fore.CYAN)}")

    else:
        print(f"  {colored('❌ Cannot connect to database', Fore.RED)}")
        print(f"  {colored('💡 Make sure PostgreSQL is running and .env is configured', Fore.YELLOW)}")

    print("=" * 100)


@with_lock('macro_data_update', timeout=600)
def run_macro_data_update(start_date=None, end_date=None, components=None, dry_run=False):
    """
    Run macro data collection using collect_macro_data.py

    Args:
        start_date: Start date (YYYY-MM-DD) or None for default (7 days ago)
        end_date: End date (YYYY-MM-DD) or None for default (today)
        components: List of components ['bonds', 'commodities'] or None for both
        dry_run: If True, only show what would be done
    """
    print(f"\n{colored('📈 Starting Macro Data Collection', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 70)

    # Set defaults
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    if not components:
        components = ['bonds', 'commodities']

    components_str = ','.join(components)

    # Build command
    cmd = [
        sys.executable,
        'scripts/collect_macro_data.py',
        '--start-date', start_date,
        '--end-date', end_date,
        '--components', components_str
    ]

    # Display plan
    print(f"  Date Range:        {colored(f'{start_date} → {end_date}', Fore.CYAN)}")
    print(f"  Components:        {colored(components_str, Fore.CYAN)}")

    if dry_run:
        print(f"  Mode:              {colored('DRY RUN (preview only)', Fore.YELLOW)}")
        print()
        print(f"  {colored('Command:', Fore.CYAN)} {' '.join(cmd)}")
        print()
        print(f"  {colored('💡 This is a preview. No data will be collected.', Fore.YELLOW)}")
        print("=" * 70)
        return
    else:
        print(f"  Mode:              {colored('PRODUCTION (will write to DB)', Fore.GREEN)}")

    print()
    print(f"  {colored('Command:', Fore.CYAN)} {' '.join(cmd)}")
    print()

    # Confirm
    confirm = input(f"{colored('Continue? [Y/n]:', Fore.CYAN)} ").strip().lower()
    if confirm and confirm != 'y':
        print(f"{colored('❌ Cancelled', Fore.YELLOW)}")
        return

    # Run
    try:
        start_time = datetime.now()
        print(f"\n{colored('🚀 Collecting macro data...', Fore.GREEN)}")
        print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        result = subprocess.run(cmd, check=True)

        elapsed = (datetime.now() - start_time).total_seconds()
        elapsed_str = f"{elapsed:.1f}s"

        print(f"\n{colored('✅ Macro data collection completed successfully!', Fore.GREEN)}")
        print(f"  Duration: {elapsed_str}")
        print()

        # Show updated status
        print(f"{colored('📊 Updated Status:', Fore.CYAN)}")
        print_macro_data_status()

    except subprocess.CalledProcessError as e:
        print(f"\n{colored('❌ Macro data collection failed!', Fore.RED)}")
        print(f"{colored('Error:', Fore.RED)} {e}")

    except KeyboardInterrupt:
        print(f"\n{colored('⚠️  Interrupted by user', Fore.YELLOW)}")
        print(f"{colored('💡 Partial progress may have been saved to database', Fore.CYAN)}")


def setup_macro_data_submenu():
    """Macro data collection submenu"""
    while True:
        print(f"\n{colored('📈 Macro Data Collection', Fore.CYAN + Style.BRIGHT)}")
        print("=" * 100)

        # Current status summary
        status = get_macro_data_status()
        if status:
            total_records = status['bonds']['total_records'] + status['commodities']['total_records']
            bonds_latest = status['bonds']['latest_date']
            commodities_latest = status['commodities']['latest_date']

            # Determine overall freshness
            if bonds_latest and commodities_latest:
                latest_date = max(bonds_latest, commodities_latest)
                days_old = (datetime.now().date() - latest_date).days

                if days_old == 0:
                    freshness = colored('✅ Up to date', Fore.GREEN)
                elif days_old <= 3:
                    freshness = colored(f'⚠️  {days_old} days old', Fore.YELLOW)
                else:
                    freshness = colored(f'❌ {days_old} days old', Fore.RED)
            else:
                freshness = colored('⚠️  No data', Fore.RED)

            print(f"Total Records: {colored(f'{total_records:,}', Fore.CYAN)} | "
                  f"Freshness: {freshness}")
        else:
            print(f"Status: {colored('❌ Database unavailable', Fore.RED)}")
        print()

        # Submenu options
        print(f"{colored('Options:', Fore.CYAN)}")
        print(f"  {colored('1.', Fore.WHITE)} 📊 {colored('Check Current Status', Fore.CYAN)} - 현재 데이터 상태 확인")
        print(f"  {colored('2.', Fore.WHITE)} 🚀 {colored('Quick Update', Fore.GREEN)} (최근 7일)")
        print(f"  {colored('3.', Fore.WHITE)} 📈 {colored('Historical Backfill', Fore.YELLOW)} (사용자 지정 기간)")
        print(f"  {colored('4.', Fore.WHITE)} 🔄 {colored('Full Refresh', Fore.MAGENTA)} (2024-01-01 ~ 현재)")
        print(f"  {colored('5.', Fore.WHITE)} 🧪 {colored('Dry Run Test', Fore.BLUE)} (미리보기)")
        print(f"  {colored('0.', Fore.WHITE)} ◀️  {colored('Back to Main Menu', Fore.RED)}")
        print()

        choice = input(f"{colored('Select (0-5):', Fore.CYAN)} ").strip()

        if choice == '1':
            # Check status
            print_macro_data_status()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '2':
            # Quick update (last 7 days)
            print(f"\n{colored('🚀 Quick Update (최근 7일)', Fore.GREEN)}")
            run_macro_data_update()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '3':
            # Historical backfill (custom date range)
            print(f"\n{colored('📈 Historical Backfill', Fore.YELLOW + Style.BRIGHT)}")
            print("=" * 70)

            start_input = input(f"{colored('Start date [YYYY-MM-DD] (default: 2024-01-01):', Fore.CYAN)} ").strip()
            start_date = start_input if start_input else '2024-01-01'

            end_input = input(f"{colored('End date [YYYY-MM-DD] (default: today):', Fore.CYAN)} ").strip()
            end_date = end_input if end_input else datetime.now().strftime('%Y-%m-%d')

            print(f"\n{colored('Select components:', Fore.CYAN)}")
            print("  1. Bonds only")
            print("  2. Commodities only")
            print("  3. Both (default)")
            comp_choice = input(f"{colored('Choice [1-3]:', Fore.CYAN)} ").strip()

            if comp_choice == '1':
                components = ['bonds']
            elif comp_choice == '2':
                components = ['commodities']
            else:
                components = ['bonds', 'commodities']

            run_macro_data_update(start_date=start_date, end_date=end_date, components=components)
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '4':
            # Full refresh (2024-01-01 to today)
            print(f"\n{colored('🔄 Full Refresh', Fore.MAGENTA + Style.BRIGHT)}")
            print(f"This will collect all data from 2024-01-01 to today")
            print(f"{colored('⚠️  Warning:', Fore.YELLOW)} May take several minutes depending on data volume")
            print()

            confirm = input(f"{colored('Proceed with full refresh? [Y/n]:', Fore.CYAN)} ").strip().lower()
            if confirm != 'n':
                run_macro_data_update(
                    start_date='2024-01-01',
                    end_date=datetime.now().strftime('%Y-%m-%d'),
                    components=['bonds', 'commodities']
                )
            else:
                print(f"{colored('⏭️  Cancelled', Fore.YELLOW)}")

            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '5':
            # Dry run test
            print(f"\n{colored('🧪 Dry Run Test', Fore.BLUE)}")
            print("This will preview the collection without writing to database")
            run_macro_data_update(dry_run=True)
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '0':
            # Back to main menu
            break

        else:
            print(f"{colored('❌ Invalid choice. Please select 0-5.', Fore.RED)}")
            input(f"{colored('Press Enter to continue...', Fore.CYAN)}")


# ============================================================================
# Equity Account Backfill Functions
# ============================================================================

def get_equity_backfill_status():
    """
    Get equity account backfill coverage status

    Returns:
        dict: {
            'total_tickers': 2396,
            'with_equity': 81,
            'without_equity': 2315,
            'coverage_pct': 3.38,
            'last_backfill_date': datetime,
            'estimated_time_hours': 48.0
        }
        None if database unavailable
    """
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()

        # Total KR tickers
        total_query = """
        SELECT COUNT(*) as count
        FROM tickers
        WHERE region = 'KR' AND asset_type = 'STOCK' AND is_active = TRUE
        """
        total_result = db.execute_query(total_query)
        total = total_result[0]['count'] if total_result else 0

        # With equity data (2024 이후 DART 데이터, capital_stock 보유)
        equity_query = """
        SELECT COUNT(DISTINCT ticker) as count
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND data_source = 'DART'
          AND date >= '2024-01-01'
          AND capital_stock IS NOT NULL
        """
        equity_result = db.execute_query(equity_query)
        with_equity = equity_result[0]['count'] if equity_result else 0

        # Last backfill date
        last_query = """
        SELECT MAX(created_at) as last_date
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND data_source = 'DART'
          AND capital_stock IS NOT NULL
        """
        last_result = db.execute_query(last_query)
        last_date = last_result[0]['last_date'] if last_result else None

        db.close_pool()

        # Calculate statistics
        missing = total - with_equity
        coverage = (with_equity / total * 100) if total > 0 else 0

        # Estimate time: 108 sec/ticker * 3 years / 3600 = 0.09 hours/ticker (default)
        # Use REFRESH_CONFIG if available
        time_per_ticker = REFRESH_CONFIG.equity_backfill_time_per_ticker if REFRESH_CONFIG else 0.09
        estimated_hours = round(missing * time_per_ticker, 1)

        return {
            'total_tickers': total,
            'with_equity': with_equity,
            'without_equity': missing,
            'coverage_pct': coverage,
            'last_backfill_date': last_date,
            'estimated_time_hours': estimated_hours
        }

    except Exception as e:
        return None


def print_equity_backfill_status():
    """Print equity account backfill status with colored output"""
    print(f"\n{colored('💰 Equity Account Backfill Status', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 70)

    status = get_equity_backfill_status()

    if status:
        total = status['total_tickers']
        with_equity = status['with_equity']
        without_equity = status['without_equity']
        coverage = status['coverage_pct']
        last_date = status['last_backfill_date']
        estimated_hours = status['estimated_time_hours']

        # Coverage status color
        if coverage >= 95:
            status_text = colored('✅ Excellent', Fore.GREEN)
            cov_color = Fore.GREEN
        elif coverage >= 80:
            status_text = colored('⚠️  Good', Fore.YELLOW)
            cov_color = Fore.YELLOW
        elif coverage >= 50:
            status_text = colored('⚠️  Fair', Fore.YELLOW)
            cov_color = Fore.YELLOW
        elif coverage >= 10:
            status_text = colored('❌ Poor', Fore.RED)
            cov_color = Fore.RED
        else:
            status_text = colored('❌ Critical', Fore.RED + Style.BRIGHT)
            cov_color = Fore.RED

        # Display summary
        print(f"  Total KR Tickers:      {colored(f'{total:,}', Fore.CYAN)}")
        print(f"  With Equity Data:      {colored(f'{with_equity:,}', Fore.GREEN)} "
              f"({colored(f'{coverage:.2f}%', cov_color)})")
        print(f"  Without Equity Data:   {colored(f'{without_equity:,}', Fore.RED)}")

        if last_date:
            print(f"  Last Backfill:         {colored(str(last_date), Fore.CYAN)}")
        else:
            print(f"  Last Backfill:         {colored('Never', Fore.RED)}")

        print(f"  Status:                {status_text}")
        print()

        # Time estimate for remaining
        if without_equity > 0:
            print(f"  {colored('⏱  Estimated Time for Remaining:', Fore.YELLOW)}")
            print(f"     • Full backfill ({without_equity:,} tickers): "
                  f"{colored(f'~{estimated_hours} hours', Fore.YELLOW)}")
            print(f"     • Batch 100 tickers: {colored('~9 hours', Fore.CYAN)}")
            print(f"     • Batch 500 tickers: {colored('~45 hours', Fore.CYAN)}")
            print()

        # Batch recommendations
        if without_equity > 0:
            print(f"  {colored('💡 Recommended Batch Sizes:', Fore.CYAN)}")
            if without_equity >= 500:
                print(f"     • Quick test: 100 tickers (9 hours)")
                print(f"     • Medium batch: 500 tickers (45 hours)")
                print(f"     • Full backfill: {without_equity:,} tickers ({estimated_hours} hours)")
            elif without_equity >= 100:
                print(f"     • Medium batch: 100 tickers (9 hours)")
                print(f"     • Full backfill: {without_equity:,} tickers ({estimated_hours} hours)")
            else:
                print(f"     • Full backfill: {without_equity:,} tickers ({estimated_hours} hours)")

    else:
        print(f"  {colored('❌ Cannot connect to database', Fore.RED)}")
        print(f"  {colored('💡 Make sure PostgreSQL is running and .env is configured', Fore.YELLOW)}")

    print("=" * 70)


def run_equity_backfill(limit=None, dry_run=False, rate_limit=1.0, use_gap_analysis=True):
    """
    Run equity account backfill using backfill_fundamentals_dart.py

    Args:
        limit: Number of tickers to process (None = all remaining)
        dry_run: If True, only show what would be done
        rate_limit: API call rate limit (calls per second)
        use_gap_analysis: If True, use gap-aware backfill (recommended, Phase 3)
    """
    print(f"\n{colored('💰 Starting Equity Account Backfill', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 70)

    # Show current status
    status = get_equity_backfill_status()
    if not status:
        print(f"{colored('❌ Cannot connect to database', Fore.RED)}")
        return

    remaining = status['without_equity']
    if remaining == 0:
        print(f"{colored('✅ All tickers already have equity data!', Fore.GREEN)}")
        return

    # Determine actual limit
    actual_limit = min(limit, remaining) if limit else remaining

    # ========================================================================
    # Phase 3: Gap Analysis Pre-Scan (if enabled)
    # ========================================================================
    if use_gap_analysis:
        print(f"\n{colored('🔍 Pre-Scan: Analyzing data gaps...', Fore.CYAN)}")
        try:
            db = PostgresDatabaseManager()
            analyzer = GapAnalyzer(db)

            gap_result = analyzer.analyze_gaps(
                table='ticker_fundamentals',
                target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
                region='KR',
                asset_type='STOCK',
                backfill_start_date=date(2022, 1, 1),
                limit=actual_limit
            )

            summary = gap_result.get_summary()
            print(f'  Total tickers analyzed:  {colored(f"{summary['total_analyzed']:,}", Fore.CYAN)}')
            print(f"  {colored('✅ Already complete:', Fore.GREEN)}       {summary['complete']} (will skip)")
            print(f"  {colored('⚠️  Need backfill:', Fore.YELLOW)}        {summary['needs_backfill']}")
            print(f"    - Fully missing:       {summary['fully_missing']}")
            print(f"    - Partially missing:   {summary['partially_missing']}")
            print(f'\n  {colored(f"💡 API calls saved: {summary['complete']} ({summary['efficiency_gain_pct']:.1f}%)", Fore.GREEN + Style.BRIGHT)}')
            print()
        except Exception as e:
            print(f"  {colored(f'⚠️  Gap analysis failed: {e}', Fore.YELLOW)}")
            print(f"  Continuing with standard backfill...")
            use_gap_analysis = False  # Fallback to legacy mode

    # Build command
    cmd = [
        sys.executable,
        'scripts/backfill_fundamentals_dart.py',
        '--limit', str(actual_limit),
        '--rate-limit', str(rate_limit)
    ]

    # Add gap analysis flags (Phase 3)
    if use_gap_analysis:
        cmd.append('--use-gap-analysis')
        cmd.extend(['--target-columns', 'capital_stock', 'capital_surplus', 'retained_earnings'])

    if dry_run:
        cmd.append('--dry-run')

    # Display plan
    time_per_ticker = REFRESH_CONFIG.equity_backfill_time_per_ticker if REFRESH_CONFIG else 0.09
    print(f"  Target Tickers:    {colored(f'{actual_limit:,} / {remaining:,} remaining', Fore.CYAN)}")
    print(f"  Rate Limit:        {colored(f'{rate_limit} calls/sec', Fore.CYAN)}")
    print(f"  Estimated Time:    {colored(f'~{actual_limit * time_per_ticker:.1f} hours', Fore.YELLOW)}")

    if dry_run:
        print(f"  Mode:              {colored('DRY RUN (no changes)', Fore.YELLOW)}")
    else:
        print(f"  Mode:              {colored('PRODUCTION (will write to DB)', Fore.GREEN)}")

    print()
    print(f"  Command: {colored(' '.join(cmd), Fore.CYAN)}")
    print()

    # Show monitoring command
    print(f"  {colored('💡 Monitor progress in another terminal:', Fore.CYAN)}")
    print(f"     tail -f logs/{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals.log")
    print()

    # Warnings for long operations
    if actual_limit >= 500:
        time_per_ticker = REFRESH_CONFIG.equity_backfill_time_per_ticker if REFRESH_CONFIG else 0.09
        print(f"  {colored('⚠️  Warning: Large batch operation!', Fore.YELLOW)}")
        print(f"     • Estimated time: ~{actual_limit * time_per_ticker:.1f} hours")
        print(f"     • Consider running in screen/tmux session")
        print(f"     • Use Ctrl+C to safely interrupt")
        print()

    # Confirm
    if not dry_run:
        confirm = input(f"{colored('Continue? [Y/n]:', Fore.CYAN)} ").strip().lower()
        if confirm and confirm != 'y':
            print(f"{colored('❌ Cancelled', Fore.YELLOW)}")
            return

    # Run
    try:
        start_time = datetime.now()
        print(f"\n{colored('🚀 Starting backfill...', Fore.GREEN)}")
        print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        result = subprocess.run(cmd, check=True)

        elapsed = (datetime.now() - start_time).total_seconds()
        elapsed_str = f"{elapsed/3600:.1f}h" if elapsed >= 3600 else f"{elapsed:.1f}s"

        print(f"\n{colored('✅ Backfill completed successfully!', Fore.GREEN)}")
        print(f"  Duration: {elapsed_str}")
        print()

        # Show updated status
        print(f"{colored('📊 Updated Status:', Fore.CYAN)}")
        print_equity_backfill_status()

    except subprocess.CalledProcessError as e:
        print(f"\n{colored('❌ Backfill failed!', Fore.RED)}")
        print(f"{colored('Error:', Fore.RED)} {e}")
        print()
        print(f"{colored('💡 Check the log file for details:', Fore.YELLOW)}")
        print(f"   logs/{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals.log")

    except KeyboardInterrupt:
        print(f"\n{colored('⚠️  Interrupted by user', Fore.YELLOW)}")
        print(f"{colored('💡 Partial progress has been saved to database', Fore.CYAN)}")
        print()
        print(f"{colored('📊 Current Status:', Fore.CYAN)}")
        print_equity_backfill_status()


@with_lock('equity_backfill_submenu', timeout=3600)
def setup_equity_backfill_submenu():
    """Equity account backfill submenu"""
    while True:
        print(f"\n{colored('💰 Equity Account Backfill', Fore.CYAN + Style.BRIGHT)}")
        print("=" * 70)

        # Current status summary
        status = get_equity_backfill_status()
        if status:
            coverage = status['coverage_pct']
            remaining = status['without_equity']
            cov_color = Fore.GREEN if coverage >= 80 else (Fore.YELLOW if coverage >= 50 else Fore.RED)
            print(f"Current Coverage: {colored(f'{coverage:.2f}%', cov_color)} "
                  f"({colored(f'{remaining:,} tickers remaining', Fore.YELLOW)})")
        else:
            print(f"Current Coverage: {colored('❌ Database unavailable', Fore.RED)}")
        print()

        # Submenu options
        print(f"{colored('Options:', Fore.CYAN)}")
        print(f"  {colored('1.', Fore.WHITE)} 📊 {colored('Check Backfill Status', Fore.CYAN)} - 현재 커버리지 확인")
        print(f"  {colored('2.', Fore.WHITE)} 🔍 {colored('Gap Analysis Preview', Fore.CYAN)} (데이터 스캔만 수행)")
        print(f"  {colored('3.', Fore.WHITE)} 🧪 {colored('Dry Run Test', Fore.YELLOW)} (2 tickers, gap-aware)")
        print(f"  {colored('4.', Fore.WHITE)} 🔵 {colored('Quick Batch', Fore.GREEN)} (100 tickers, gap-aware)")
        print(f"  {colored('5.', Fore.WHITE)} 🟠 {colored('Medium Batch', Fore.YELLOW)} (500 tickers, gap-aware)")
        print(f"  {colored('6.', Fore.WHITE)} 🔴 {colored('Full Backfill', Fore.MAGENTA)} (모든 remaining, gap-aware)")
        print(f"  {colored('7.', Fore.WHITE)} 🔧 {colored('Legacy Mode', Fore.BLUE)} (without gap analysis)")
        print(f"  {colored('0.', Fore.WHITE)} ◀️  {colored('Back to Main Menu', Fore.RED)}")
        print()

        choice = input(f"{colored('Select (0-7):', Fore.CYAN)} ").strip()

        if choice == '1':
            # Check status
            print_equity_backfill_status()
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '2':
            # Gap Analysis Preview (read-only scan)
            print(f"\n{colored('🔍 Gap Analysis Preview', Fore.CYAN + Style.BRIGHT)}")
            print("=" * 70)
            print(f"Scanning database for missing equity data (read-only)...")
            print()
            try:
                db = PostgresDatabaseManager()
                analyzer = GapAnalyzer(db)
                gap_result = analyzer.analyze_gaps(
                    table='ticker_fundamentals',
                    target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
                    region='KR',
                    asset_type='STOCK',
                    backfill_start_date=date(2022, 1, 1),
                    limit=None  # Analyze all tickers
                )

                summary = gap_result.get_summary()
                print(f"📊 {colored('Gap Analysis Results:', Fore.CYAN + Style.BRIGHT)}")
                print(f'  Total tickers analyzed:  {colored(f"{summary['total_analyzed']:,}", Fore.CYAN)}')
                print(f"  {colored('✅ Already complete:', Fore.GREEN)}       {summary['complete']} tickers")
                print(f"  {colored('⚠️  Need backfill:', Fore.YELLOW)}        {summary['needs_backfill']} tickers")
                print(f"    - Fully missing:       {summary['fully_missing']} tickers")
                print(f"    - Partially missing:   {summary['partially_missing']} tickers")
                print()
                print(f"  {colored(f'💡 Efficiency Gain:', Fore.GREEN + Style.BRIGHT)}")
                print(f"    API calls saved:       {summary['complete']} ({summary['efficiency_gain_pct']:.1f}%)")
                print()
            except Exception as e:
                print(f"  {colored(f'❌ Gap analysis failed: {e}', Fore.RED)}")
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '3':
            # Dry run test with 2 tickers (gap-aware)
            print(f"\n{colored('🧪 Dry Run Test (Gap-Aware)', Fore.YELLOW)}")
            print(f"This will simulate gap-aware backfill for 2 tickers without writing to database")
            run_equity_backfill(limit=2, dry_run=True, rate_limit=1.0, use_gap_analysis=True)
            input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '4':
            # Quick batch: 100 tickers (gap-aware)
            if not status:
                print(f"{colored('❌ Database unavailable', Fore.RED)}")
                input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
                continue

            actual = min(100, status['without_equity'])
            time_per_ticker = REFRESH_CONFIG.equity_backfill_time_per_ticker if REFRESH_CONFIG else 0.09
            print(f"\n{colored('🔵 Quick Batch - Gap-Aware (100 tickers)', Fore.GREEN)}")
            print(f"Will process {actual:,} tickers (estimated: ~{actual * time_per_ticker:.1f} hours)")
            run_equity_backfill(limit=100, dry_run=False, rate_limit=1.0, use_gap_analysis=True)

        elif choice == '5':
            # Medium batch: 500 tickers (gap-aware)
            if not status:
                print(f"{colored('❌ Database unavailable', Fore.RED)}")
                input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
                continue

            actual = min(500, status['without_equity'])
            time_per_ticker = REFRESH_CONFIG.equity_backfill_time_per_ticker if REFRESH_CONFIG else 0.09
            print(f"\n{colored('🟠 Medium Batch - Gap-Aware (500 tickers)', Fore.YELLOW)}")
            print(f"Will process {actual:,} tickers (estimated: ~{actual * time_per_ticker:.1f} hours)")
            print(f"{colored('⚠️  Recommendation:', Fore.YELLOW)} Run in screen/tmux session for long operations")
            run_equity_backfill(limit=500, dry_run=False, rate_limit=1.0, use_gap_analysis=True)

        elif choice == '6':
            # Full backfill: all remaining (gap-aware)
            if not status:
                print(f"{colored('❌ Database unavailable', Fore.RED)}")
                input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
                continue

            remaining = status['without_equity']
            estimated = status['estimated_time_hours']

            print(f"\n{colored('🔴 Full Backfill - Gap-Aware', Fore.MAGENTA + Style.BRIGHT)}")
            print(f"⚠️  This will process ALL {remaining:,} remaining tickers")
            print(f"⏱  Estimated time: ~{estimated} hours")
            print()
            print(f"{colored('💡 Recommendations:', Fore.CYAN)}")
            print(f"   • Run in screen/tmux session")
            print(f"   • Consider lower --rate-limit for stability")
            print(f"   • Monitor logs for any issues")
            print()

            confirm = input(f"{colored('Proceed with full backfill? [y/N]:', Fore.YELLOW)} ").strip().lower()
            if confirm == 'y':
                run_equity_backfill(limit=None, dry_run=False, rate_limit=1.0, use_gap_analysis=True)
            else:
                print(f"{colored('⏭️  Cancelled', Fore.YELLOW)}")
                input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")

        elif choice == '7':
            # Legacy mode (without gap analysis)
            print(f"\n{colored('🔧 Legacy Mode', Fore.BLUE + Style.BRIGHT)}")
            print("=" * 70)
            print(f"{colored('⚠️  Note:', Fore.YELLOW)} This mode processes all tickers without gap analysis.")
            print(f"Consider using gap-aware mode for better efficiency.")
            print()

            limit_input = input(f"Enter ticker limit (or press Enter for 10): ").strip()
            limit_val = int(limit_input) if limit_input else 10

            run_equity_backfill(limit=limit_val, dry_run=False, rate_limit=1.0, use_gap_analysis=False)

        elif choice == '0':
            # Back to main menu
            break

        else:
            print(f"{colored('❌ Invalid choice. Please select 0-7.', Fore.RED)}")
            input(f"{colored('Press Enter to continue...', Fore.CYAN)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Spock Database Refresh Tool - User-friendly data update utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive menu (recommended)
  python3 spock_refresh.py

  # Quick refresh (last 7 days)
  python3 spock_refresh.py --quick

  # Full refresh (all data)
  python3 spock_refresh.py --full

  # Incremental (missing data only)
  python3 spock_refresh.py --incremental

  # Status check
  python3 spock_refresh.py --status

  # Custom regions
  python3 spock_refresh.py --quick --regions KR US

  # Dry run
  python3 spock_refresh.py --full --dry-run

For more options, see scripts/update_database.py --help
        """
    )

    # Preset modes
    preset_group = parser.add_mutually_exclusive_group()
    preset_group.add_argument(
        '--quick',
        action='store_true',
        help='Quick refresh (last 7 days, ~5 min)'
    )
    preset_group.add_argument(
        '--full',
        action='store_true',
        help='Full refresh (all data, ~30 min)'
    )
    preset_group.add_argument(
        '--incremental',
        action='store_true',
        help='Incremental refresh (missing data only, ~10 min)'
    )
    preset_group.add_argument(
        '--status',
        action='store_true',
        help='Show database status and exit'
    )

    # Options
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['KR', 'US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to update (default: KR)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='자동으로 모든 확인 프롬프트 승인 (자동화/CI/CD용)'
    )

    args = parser.parse_args()

    # Cleanup stale locks on startup (silent, non-blocking)
    try:
        cleanup_stale_locks(max_age_hours=24)
    except Exception:
        pass  # Don't fail if cleanup has issues

    # Create checkpoint directory if it doesn't exist (silent, non-blocking)
    try:
        os.makedirs('data/checkpoints', exist_ok=True)
    except Exception:
        pass  # Don't fail if directory creation has issues

    # If no arguments, show interactive menu
    if len(sys.argv) == 1:
        interactive_menu()
        return

    # Status mode
    if args.status:
        print_banner()
        print_status()
        return

    # CLI mode
    print_banner()

    regions = args.regions or ['KR']

    if args.quick:
        cmd_args = [
            '--regions'] + regions + [
            '--steps', 'ohlcv', 'fundamentals', 'dividend',
            '--incremental'
        ]
        description = 'Quick Refresh'

    elif args.full:
        cmd_args = [
            '--regions'] + regions + [
            '--steps', 'tickers', 'ohlcv', 'fundamentals', 'dividend'
        ]
        description = 'Full Refresh'

    elif args.incremental:
        cmd_args = [
            '--regions'] + regions + [
            '--steps', 'tickers', 'ohlcv', 'fundamentals', 'dividend',
            '--incremental'
        ]
        description = 'Incremental Refresh'
    else:
        parser.print_help()
        return

    # Add optional flags
    if args.dry_run:
        cmd_args.append('--dry-run')
    if args.verbose:
        cmd_args.append('--verbose')

    # Run (with auto-confirm if --yes flag is provided)
    run_update_database(cmd_args, description, auto_confirm=args.yes)


def run_daily_valuation_update():
    """Run daily PER/PBR valuation update (pykrx)"""
    print(f"\n{colored('='*80, Fore.CYAN)}")
    print(f"{colored('💹 Daily PER/PBR Valuation Update', Fore.YELLOW + Style.BRIGHT)}")
    print(f"{colored('='*80, Fore.CYAN)}")
    print()
    print(f"{colored('Data Source:', Fore.WHITE)} pykrx (KRX market data)")
    print(f"{colored('Update Frequency:', Fore.WHITE)} Daily")
    print(f"{colored('Purpose:', Fore.WHITE)} Historical valuation multiple trend analysis")
    print()

    confirm = input(f"{colored('Proceed with daily valuation update? (y/n):', Fore.CYAN)} ").strip().lower()

    if confirm == 'y':
        try:
            from datetime import datetime
            log_file = f"logs/daily_valuation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

            cmd = [
                'python3', 'scripts/update_database.py',
                '--regions', 'KR',
                '--steps', 'daily_valuation',
                '--incremental',
                '--log-file', log_file
            ]

            print(f"\n{colored('⏳ Starting daily valuation update...', Fore.YELLOW)}")
            print(f"{colored(f'Log file: {log_file}', Fore.WHITE)}")
            print()

            result = subprocess.run(cmd, check=False)

            if result.returncode == 0:
                print(f"\n{colored('✅ Daily valuation update completed successfully!', Fore.GREEN + Style.BRIGHT)}")
            else:
                print(f"\n{colored('❌ Daily valuation update failed. Check log file.', Fore.RED + Style.BRIGHT)}")

        except Exception as e:
            print(f"\n{colored(f'❌ Error: {e}', Fore.RED + Style.BRIGHT)}")
    else:
        print(f"{colored('❌ Cancelled', Fore.RED)}")

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def run_technical_indicators_update():
    """Technical Indicators Only - Enhanced multi-region calculation with batch processing"""
    print(f"\n{colored('='*80, Fore.CYAN)}")
    print(f"{colored('📉 Technical Indicators Calculation', Fore.CYAN + Style.BRIGHT)}")
    print(f"{colored('='*80, Fore.CYAN)}")
    print()
    print(f"{colored('Indicators:', Fore.WHITE)} MA(5,20,60,120,200), RSI-14, MACD")
    print(f"{colored('Available Regions:', Fore.WHITE)} KR, HK, US, JP, CN, VN")
    print()

    # Region selection (using helper function)
    regions = select_regions_custom()

    # Calculation mode selection
    print(f"\n{colored('Calculation Mode:', Fore.CYAN)}")
    print(f"  1. Incremental (only calculate missing indicators)")
    print(f"  2. Full (recalculate all indicators)")
    print()

    mode_choice = input(f"{colored('Choice [1]:', Fore.CYAN)} ").strip()
    incremental = True if mode_choice != '2' else False
    mode_name = "Incremental" if incremental else "Full Recalculation"

    # Batch size selection
    print(f"\n{colored('Batch Size:', Fore.CYAN)}")
    print(f"  1. Small (50 tickers/batch) - Safer, slower")
    print(f"  2. Medium (100 tickers/batch) - Balanced (recommended)")
    print(f"  3. Large (200 tickers/batch) - Faster, more memory")
    print()

    batch_choice = input(f"{colored('Choice [2]:', Fore.CYAN)} ").strip()

    if batch_choice == '1':
        batch_size = 50
    elif batch_choice == '3':
        batch_size = 200
    else:
        batch_size = 100  # Default

    # Dry run option
    dry_run_input = input(f"\n{colored('Dry run (preview only)? [y/N]:', Fore.CYAN)} ").strip().lower()
    dry_run = dry_run_input == 'y'

    # Summary and confirmation
    print(f"\n{colored('Configuration Summary:', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)
    print(f"  Regions: {colored(', '.join(regions), Fore.WHITE)}")
    print(f"  Mode: {colored(mode_name, Fore.WHITE)}")
    print(f"  Batch Size: {colored(batch_size, Fore.WHITE)} tickers")
    print(f"  Dry Run: {colored('Yes' if dry_run else 'No', Fore.YELLOW if dry_run else Fore.WHITE)}")
    print("=" * 60)
    print()

    confirm = input(f"{colored('Proceed with technical indicators calculation? [Y/n]:', Fore.CYAN)} ").strip().lower()

    if confirm and confirm != 'y':
        print(f"{colored('⏭️  Cancelled', Fore.YELLOW)}")
        input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
        return

    # Execute calculation
    print(f"\n{colored('Starting Technical Indicators Calculation...', Fore.CYAN + Style.BRIGHT)}")
    print("=" * 60)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=batch_size,
        incremental=incremental,
        dry_run=dry_run
    )

    # Summary
    total_success = sum(r.get('success_count', 0) for r in results.values())
    total_tickers = sum(r.get('total_tickers', 0) for r in results.values())
    total_failed = sum(r.get('failed_count', 0) for r in results.values())
    total_time = sum(r.get('duration_minutes', 0.0) for r in results.values())

    print(f"\n{colored('✅ Technical Indicators Calculation Complete!', Fore.GREEN + Style.BRIGHT)}")
    print("=" * 60)
    print(f"Regions: {', '.join(regions)}")
    print(f"Mode: {mode_name}")
    print(f"Success: {total_success}/{total_tickers} tickers")
    if total_failed > 0:
        print(f"{colored(f'Failed: {total_failed} tickers', Fore.YELLOW)}")
    print(f"Total Time: {total_time:.1f} minutes")
    print("=" * 60)

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def run_data_validation():
    """Run data quality validation for backtesting (Phase 2.1)"""
    print(f"\n{colored('='*80, Fore.CYAN)}")
    print(f"{colored('🔍 Data Quality Validation', Fore.CYAN + Style.BRIGHT)}")
    print(f"{colored('='*80, Fore.CYAN)}")
    print()
    print(f"{colored('Validates:', Fore.WHITE)} Duplicate data, NULL values, data coverage")
    print(f"{colored('Available:', Fore.WHITE)} KR, HK, US")
    print()

    # Region selection
    print(f"{colored('Select region:', Fore.CYAN)}")
    print(f"  1. KR (Korea)")
    print(f"  2. HK (Hong Kong)")
    print(f"  3. US (United States)")

    region_choice = input(f"{colored('Choice (1-3):', Fore.CYAN)} ").strip()

    if region_choice == '1':
        region = 'KR'
    elif region_choice == '2':
        region = 'HK'
    elif region_choice == '3':
        region = 'US'
    else:
        print(f"{colored('❌ Invalid choice', Fore.RED)}")
        input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
        return

    # Ask about fixing duplicates
    fix_choice = input(f"{colored('Automatically fix duplicate data? (y/n):', Fore.CYAN)} ").strip().lower()
    fix_duplicates = (fix_choice == 'y')

    confirm = input(f"{colored(f'Validate {region} data? (y/n):', Fore.CYAN)} ").strip().lower()

    if confirm == 'y':
        try:
            cmd = ['python3', 'scripts/validate_backtest_data.py', '--region', region]
            if fix_duplicates:
                cmd.append('--fix')

            print(f"\n{colored('⏳ Running data validation...', Fore.YELLOW)}")
            print()

            result = subprocess.run(cmd, check=False)

            if result.returncode == 0:
                print(f"\n{colored('✅ Data validation completed!', Fore.GREEN + Style.BRIGHT)}")
            else:
                print(f"\n{colored('⚠️  Data validation found issues. Review output above.', Fore.YELLOW + Style.BRIGHT)}")

        except Exception as e:
            print(f"\n{colored(f'❌ Error: {e}', Fore.RED + Style.BRIGHT)}")
    else:
        print(f"{colored('❌ Cancelled', Fore.RED)}")

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


def run_stock_screening():
    """Run stock screening (Phase 2.2)"""
    print(f"\n{colored('='*80, Fore.CYAN)}")
    print(f"{colored('📊 Stock Screening', Fore.CYAN + Style.BRIGHT)}")
    print(f"{colored('='*80, Fore.CYAN)}")
    print()
    print(f"{colored('Available Filters:', Fore.WHITE)}")
    print(f"  1. Technical (RSI, MACD, MA trends)")
    print(f"  2. Value (PER, PBR, dividend yield)")
    print()

    # Filter type selection
    filter_choice = input(f"{colored('Select filter (1-2):', Fore.CYAN)} ").strip()

    if filter_choice == '1':
        filter_type = 'technical'
    elif filter_choice == '2':
        filter_type = 'value'
    else:
        print(f"{colored('❌ Invalid choice', Fore.RED)}")
        input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")
        return

    # Region selection
    if filter_type == 'technical':
        print(f"\n{colored('Select region:', Fore.CYAN)}")
        print(f"  1. HK (Hong Kong) - Recommended")
        print(f"  2. KR (Korea)")
        region_choice = input(f"{colored('Choice (1-2):', Fore.CYAN)} ").strip()
        region = 'HK' if region_choice == '1' else 'KR'
    else:  # value
        print(f"\n{colored('Select region:', Fore.CYAN)}")
        print(f"  1. US (United States) - Recommended")
        print(f"  2. KR (Korea)")
        region_choice = input(f"{colored('Choice (1-2):', Fore.CYAN)} ").strip()
        region = 'US' if region_choice == '1' else 'KR'

    # Build command
    cmd = ['python3', 'scripts/run_screening.py', filter_type, '--region', region]

    # Filter-specific parameters
    if filter_type == 'technical':
        print(f"\n{colored('RSI threshold (default: 35 for oversold):', Fore.CYAN)}")
        rsi_max = input(f"  RSI max (press Enter for 35): ").strip()
        if rsi_max:
            cmd.extend(['--rsi-max', rsi_max])
    else:  # value
        print(f"\n{colored('Value thresholds (press Enter for defaults):', Fore.CYAN)}")
        per_max = input(f"  PER max (default: 15): ").strip()
        pbr_max = input(f"  PBR max (default: 3): ").strip()
        if per_max:
            cmd.extend(['--per-max', per_max])
        if pbr_max:
            cmd.extend(['--pbr-max', pbr_max])

    # Output file
    save_choice = input(f"\n{colored('Save results to CSV? (y/n):', Fore.CYAN)} ").strip().lower()
    if save_choice == 'y':
        output_file = f"/tmp/{filter_type}_{region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        cmd.extend(['--output', output_file])

    # Confirm
    confirm = input(f"\n{colored(f'Run {filter_type} screening for {region}? (y/n):', Fore.CYAN)} ").strip().lower()

    if confirm == 'y':
        try:
            print(f"\n{colored('⏳ Running stock screening...', Fore.YELLOW)}")
            print()

            result = subprocess.run(cmd, check=False)

            if result.returncode == 0:
                print(f"\n{colored('✅ Screening completed!', Fore.GREEN + Style.BRIGHT)}")
                if save_choice == 'y':
                    print(f"{colored(f'Results saved to: {output_file}', Fore.WHITE)}")
            else:
                print(f"\n{colored('❌ Screening failed. Review output above.', Fore.RED + Style.BRIGHT)}")

        except Exception as e:
            print(f"\n{colored(f'❌ Error: {e}', Fore.RED + Style.BRIGHT)}")
    else:
        print(f"{colored('❌ Cancelled', Fore.RED)}")

    input(f"\n{colored('Press Enter to continue...', Fore.CYAN)}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{colored('⚠️  Interrupted by user', Fore.YELLOW)}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{colored('❌ Fatal error:', Fore.RED)} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
