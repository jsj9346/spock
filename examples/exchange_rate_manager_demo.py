"""
ExchangeRateManager Demo
Demonstrates multi-currency exchange rate management with caching

Features:
- Default rate retrieval
- Currency conversion (to/from KRW)
- Multi-currency batch conversion
- Cache management

Usage:
    python3 examples/exchange_rate_manager_demo.py

Author: Spock Trading System
Created: 2025-10-16
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.exchange_rate_manager import ExchangeRateManager
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_rates():
    """Demo 1: Basic exchange rate retrieval"""
    print("=" * 60)
    print("Demo 1: Basic Exchange Rate Retrieval")
    print("=" * 60)

    # Initialize manager (without database for demo)
    manager = ExchangeRateManager(db_manager=None)

    # Get all exchange rates
    print("\n📊 Current Exchange Rates (to KRW):")
    print("-" * 60)

    rates = manager.get_all_rates()
    for currency, rate in sorted(rates.items()):
        if currency == 'KRW':
            print(f"  {currency}: {rate:.2f} (base currency)")
        else:
            print(f"  {currency}: {rate:.2f} KRW per 1 {currency}")

    print()


def demo_currency_conversion():
    """Demo 2: Currency conversion examples"""
    print("=" * 60)
    print("Demo 2: Currency Conversion Examples")
    print("=" * 60)

    manager = ExchangeRateManager(db_manager=None)

    # Example conversions
    conversions = [
        ("USD", 100, "Investment: $100 → KRW"),
        ("HKD", 1000, "Hong Kong stock: HK$1,000 → KRW"),
        ("CNY", 500, "China stock: ¥500 → KRW"),
        ("JPY", 10000, "Japan stock: ¥10,000 → KRW"),
        ("VND", 1000000, "Vietnam stock: ₫1,000,000 → KRW"),
    ]

    print("\n💱 Currency Conversions:")
    print("-" * 60)

    for currency, amount, description in conversions:
        krw_amount = manager.convert_to_krw(amount, currency)
        print(f"  {description}")
        print(f"    → ₩{krw_amount:,} KRW")
        print()


def demo_reverse_conversion():
    """Demo 3: KRW to foreign currency conversion"""
    print("=" * 60)
    print("Demo 3: KRW to Foreign Currency")
    print("=" * 60)

    manager = ExchangeRateManager(db_manager=None)

    # Portfolio value in KRW
    portfolio_krw = 10000000  # ₩10,000,000 (10 million KRW)

    print(f"\n💼 Portfolio Value: ₩{portfolio_krw:,} KRW")
    print("-" * 60)
    print("  Equivalent in foreign currencies:")

    for currency in ['USD', 'HKD', 'CNY', 'JPY', 'VND']:
        foreign_amount = manager.convert_from_krw(portfolio_krw, currency)

        if currency == 'VND':
            print(f"    {currency}: ₫{foreign_amount:,.0f}")
        elif currency == 'JPY':
            print(f"    {currency}: ¥{foreign_amount:,.0f}")
        elif currency == 'CNY':
            print(f"    {currency}: ¥{foreign_amount:,.2f}")
        elif currency == 'HKD':
            print(f"    {currency}: HK${foreign_amount:,.2f}")
        else:
            print(f"    {currency}: ${foreign_amount:,.2f}")

    print()


def demo_market_cap_filtering():
    """Demo 4: Market cap filtering across markets"""
    print("=" * 60)
    print("Demo 4: Multi-Market Filtering Example")
    print("=" * 60)

    manager = ExchangeRateManager(db_manager=None)

    # Target: ₩1,000억원 (₩100B) market cap threshold
    target_krw = 100000000000

    print(f"\n🎯 Target Market Cap: ₩{target_krw:,} KRW (₩100B)")
    print("-" * 60)
    print("  Equivalent thresholds per market:")

    markets = [
        ('US', 'USD', '$', 0),
        ('HK', 'HKD', 'HK$', 0),
        ('CN', 'CNY', '¥', 0),
        ('JP', 'JPY', '¥', 0),
        ('VN', 'VND', '₫', 0),
    ]

    for region, currency, symbol, _ in markets:
        threshold = manager.convert_from_krw(target_krw, currency)

        if currency == 'VND':
            print(f"    {region} ({currency}): {symbol}{threshold:,.0f}")
        elif currency == 'JPY':
            print(f"    {region} ({currency}): {symbol}{threshold:,.0f}")
        else:
            print(f"    {region} ({currency}): {symbol}{threshold:,.2f}M")

    print()


def demo_cache_management():
    """Demo 5: Cache management"""
    print("=" * 60)
    print("Demo 5: Cache Management")
    print("=" * 60)

    manager = ExchangeRateManager(db_manager=None)

    # Populate cache
    print("\n📥 Populating cache...")
    for currency in ['USD', 'HKD', 'CNY']:
        manager.get_rate(currency)

    # Check cache status
    status = manager.get_cache_status()
    print(f"\n💾 Cache Status:")
    print(f"  Cached currencies: {', '.join(status['cached_currencies'])}")
    print(f"  Cache count: {status['cache_count']}")
    print(f"  Newest cache: {status['newest_cache']}")

    # Clear cache
    print("\n🗑️  Clearing cache...")
    manager.clear_cache()

    # Verify empty
    status_after = manager.get_cache_status()
    print(f"  Cache count after clear: {status_after['cache_count']}")

    print()


def demo_with_database():
    """Demo 6: With database persistence"""
    print("=" * 60)
    print("Demo 6: Database Persistence")
    print("=" * 60)

    try:
        # Initialize with database
        db_manager = SQLiteDatabaseManager(db_path='data/spock_local.db')
        manager = ExchangeRateManager(db_manager=db_manager)

        print("\n💾 Manager initialized with database support")
        print("  Rates will be cached in exchange_rate_history table")

        # Fetch rate (will be saved to database)
        usd_rate = manager.get_rate('USD')
        print(f"\n  USD rate: {usd_rate} KRW (saved to database)")

        # Verify database entry
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM exchange_rate_history
            WHERE currency = 'USD'
        """)
        count = cursor.fetchone()[0]
        conn.close()

        print(f"  Database records: {count} entry for USD")

    except FileNotFoundError:
        print("\n⚠️  Database not found: data/spock_local.db")
        print("  Run database initialization first:")
        print("  python3 migrations/006_add_exchange_rate_history.py")

    except Exception as e:
        print(f"\n❌ Database demo failed: {e}")

    print()


def main():
    """Run all demos"""
    print()
    print("🌐 ExchangeRateManager Demo")
    print("=" * 60)
    print("Multi-currency exchange rate management system")
    print("Supports: KRW, USD, HKD, CNY, JPY, VND")
    print()

    try:
        demo_basic_rates()
        demo_currency_conversion()
        demo_reverse_conversion()
        demo_market_cap_filtering()
        demo_cache_management()
        demo_with_database()

        print("=" * 60)
        print("✅ All demos completed successfully!")
        print("=" * 60)
        print()

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
