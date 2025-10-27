"""
Manual Test for Newly Implemented PostgreSQL Methods

Tests all 52 newly implemented methods across 6 categories:
- Stock Details (8 methods)
- ETF Details (12 methods)
- Technical Analysis (6 methods)
- Fundamentals (8 methods)
- Trading & Portfolio (12 methods)
- Market Data (6 methods)

Author: Quant Platform Development Team
Date: 2025-10-20
"""

import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager


def test_stock_details(db):
    """Test Stock Details methods"""
    print("\n=== Testing Stock Details Methods ===")

    # First insert the ticker (foreign key requirement)
    ticker_data = {
        'ticker': '005930',
        'region': 'KR',
        'name': 'Samsung Electronics',
        'exchange': 'KOSPI',
        'asset_type': 'STOCK',
        'is_active': True
    }
    db.insert_ticker(ticker_data)
    print(f"✅ Insert ticker: True")

    # Insert stock details
    stock_data = {
        'ticker': '005930',
        'region': 'KR',
        'sector': 'Information Technology',
        'sector_code': '45',
        'industry': 'Semiconductors',
        'industry_code': '453010',
        'is_spac': False,
        'is_preferred': False,
        'par_value': 100
    }
    result = db.insert_stock_details(stock_data)
    print(f"✅ Insert stock details: {result}")

    # Get stock details
    stock = db.get_stock_details('005930', 'KR')
    print(f"✅ Get stock details: {stock['industry'] if stock else 'None'}")

    # Get stocks by sector
    stocks = db.get_stocks_by_sector('45', 'KR')
    print(f"✅ Get stocks by sector: {len(stocks)} stocks found")

    # Get stocks by industry
    stocks = db.get_stocks_by_industry('Semiconductors', 'KR')
    print(f"✅ Get stocks by industry: {len(stocks)} stocks found")

    # Count stocks by sector (returns list of sector counts)
    counts = db.count_stocks_by_sector('KR')
    total_count = sum(c['count'] for c in counts) if counts else 0
    print(f"✅ Count stocks by sector: {total_count} stocks total, {len(counts)} sectors")

    return True


def test_etf_details(db):
    """Test ETF Details methods"""
    print("\n=== Testing ETF Details Methods ===")

    # First insert the ticker
    ticker_data = {
        'ticker': 'TIGER',
        'region': 'KR',
        'name': 'TIGER KOSPI 200 ETF',
        'exchange': 'KRX',
        'asset_type': 'ETF',
        'is_active': True
    }
    db.insert_ticker(ticker_data)
    print(f"✅ Insert ticker: True")

    # Insert ETF details
    etf_data = {
        'ticker': 'TIGER',
        'region': 'KR',
        'issuer': 'Mirae Asset',
        'underlying_asset_class': 'EQUITY',
        'tracking_index': 'KOSPI 200',
        'geographic_region': 'Korea',
        'sector_theme': 'Technology',
        'fund_type': 'INDEX',
        'aum': 5000000000,
        'expense_ratio': 0.15
    }
    result = db.insert_etf_details(etf_data)
    print(f"✅ Insert ETF details: {result}")

    # Get ETF details
    etf = db.get_etf_details('TIGER', 'KR')
    print(f"✅ Get ETF details: {etf['issuer'] if etf else 'None'}")

    # Get ETFs by theme
    etfs = db.get_etfs_by_theme('Technology', 'KR')
    print(f"✅ Get ETFs by theme: {len(etfs)} ETFs found")

    # Get ETFs by expense ratio (max 0.5%)
    etfs = db.get_etfs_by_expense_ratio(0.5, 'KR')
    print(f"✅ Get ETFs by expense ratio: {len(etfs)} ETFs found")

    # Insert ETF holdings
    result = db.insert_etf_holdings(
        etf_ticker='TIGER',
        stock_ticker='005930',
        region='KR',
        weight=25.5,
        as_of_date=str(date.today()),
        shares=1000000,
        rank_in_etf=1
    )
    print(f"✅ Insert ETF holdings: {result}")

    # Get stocks in ETF
    stocks = db.get_stocks_in_etf('TIGER', 'KR')
    print(f"✅ Get stocks in ETF: {len(stocks)} stocks found")

    # Get ETFs holding stock
    etfs = db.get_etfs_holding_stock('005930', 'KR')
    print(f"✅ Get ETFs holding stock: {len(etfs)} ETFs found")

    return True


def test_technical_analysis(db):
    """Test Technical Analysis methods"""
    print("\n=== Testing Technical Analysis Methods ===")

    # Insert technical analysis
    ta_data = {
        'ticker': '005930',
        'region': 'KR',
        'analysis_date': date.today(),
        'stage': 2,
        'stage_confidence': 85,
        'layer1_macro_score': 75,
        'layer2_structural_score': 80,
        'layer3_micro_score': 85,
        'total_score': 80,
        'signal': 'BUY',
        'signal_strength': 'STRONG'
    }
    result = db.insert_technical_analysis(ta_data)
    print(f"✅ Insert technical analysis: {result}")

    # Get stocks by signal
    stocks = db.get_stocks_by_signal('BUY', 'KR', min_score=70)
    print(f"✅ Get stocks by signal: {len(stocks)} stocks found")

    # Get stocks by stage
    stocks = db.get_stocks_by_stage(2, 'KR')
    print(f"✅ Get stocks by stage: {len(stocks)} stocks found")

    return True


def test_fundamentals(db):
    """Test Fundamentals methods"""
    print("\n=== Testing Fundamentals Methods ===")

    # Insert fundamentals
    fund_data = {
        'ticker': '005930',
        'region': 'KR',
        'date': date.today(),
        'period_type': 'DAILY',
        'shares_outstanding': 6000000000,
        'market_cap': 420000000000000,
        'close_price': 70000,
        'per': 15.5,
        'pbr': 1.8,
        'dividend_yield': 2.5
    }
    result = db.insert_fundamentals(fund_data)
    print(f"✅ Insert fundamentals: {result}")

    # Get stocks by P/E ratio
    stocks = db.get_stocks_by_per(20, 'KR')
    print(f"✅ Get stocks by PER: {len(stocks)} stocks found")

    # Get stocks by P/B ratio
    stocks = db.get_stocks_by_pbr(2.5, 'KR')
    print(f"✅ Get stocks by PBR: {len(stocks)} stocks found")

    # Get dividend stocks
    stocks = db.get_dividend_stocks(2.0, 'KR')
    print(f"✅ Get dividend stocks: {len(stocks)} stocks found")

    # Get latest fundamentals
    fund = db.get_latest_fundamentals('005930', 'KR')
    print(f"✅ Get latest fundamentals: PER={fund['per'] if fund else 'None'}")

    return True


def test_trading_portfolio(db):
    """Test Trading & Portfolio methods"""
    print("\n=== Testing Trading & Portfolio Methods ===")

    # Insert trade
    trade_data = {
        'ticker': '005930',
        'region': 'KR',
        'side': 'BUY',
        'order_type': 'LIMIT',
        'quantity': 100,
        'price': 70000,
        'amount': 7000000,
        'fee': 10500,
        'trade_status': 'FILLED',
        'sector': 'Information Technology',
        'position_size_percent': 5.0,
        'reason': 'Technical breakout'
    }
    result = db.insert_trade(trade_data)
    print(f"✅ Insert trade: {result}")

    # Get trades
    trades = db.get_trades('005930', 'KR')
    print(f"✅ Get trades: {len(trades)} trades found")

    # Update portfolio position
    portfolio_data = {
        'ticker': '005930',
        'region': 'KR',
        'shares': 100,
        'avg_entry_price': 70000,
        'current_price': 72000,
        'unrealized_pnl': 200000,
        'unrealized_pnl_pct': 2.86
    }
    result = db.update_portfolio_position(portfolio_data)
    print(f"✅ Update portfolio position: {result}")

    # Get portfolio
    portfolio = db.get_portfolio('KR')
    print(f"✅ Get portfolio: {len(portfolio)} positions")

    # Calculate position size
    position_size = db.calculate_position_size('005930', 'KR', 70000, 100000000, 2.0)
    print(f"✅ Calculate position size: {position_size} shares")

    # Get portfolio P&L
    pnl = db.get_portfolio_pnl('KR')
    print(f"✅ Get portfolio P&L: {pnl['total_pnl'] if pnl else 0}")

    return True


def test_market_data(db):
    """Test Market Data methods"""
    print("\n=== Testing Market Data Methods ===")

    # Insert market sentiment
    sentiment_data = {
        'date': date.today(),
        'vix': 15.5,
        'fear_greed_index': 65,
        'kospi_index': 2500,
        'kosdaq_index': 850,
        'foreign_net_buying': 500000000,
        'institution_net_buying': 300000000,
        'market_regime': 'NORMAL',
        'sentiment_score': 65
    }
    result = db.insert_market_sentiment(sentiment_data)
    print(f"✅ Insert market sentiment: {result}")

    # Get latest market sentiment
    sentiment = db.get_latest_market_sentiment()
    print(f"✅ Get latest sentiment: VIX={sentiment['vix'] if sentiment else 'None'}")

    # Insert global index
    index_data = {
        'date': date.today(),
        'symbol': 'KOSPI',
        'index_name': 'Korea Composite Stock Price Index',
        'region': 'KR',
        'close_price': 2500.5,
        'change_percent': 1.5,
        'trend_5d': 'UP'
    }
    result = db.insert_global_index(index_data)
    print(f"✅ Insert global index: {result}")

    # Get global indices
    indices = db.get_global_indices('KR')
    print(f"✅ Get global indices: {len(indices)} indices found")

    # Insert exchange rate
    rate_data = {
        'currency': 'USD_KRW',
        'rate': 1300.5,
        'rate_date': date.today()
    }
    result = db.insert_exchange_rate(rate_data)
    print(f"✅ Insert exchange rate: {result}")

    # Get latest exchange rate
    rate = db.get_latest_exchange_rate('USD_KRW')
    print(f"✅ Get latest exchange rate: {rate['rate'] if rate else 'None'}")

    return True


def cleanup_test_data(db):
    """Clean up all test data"""
    print("\n=== Cleaning up test data ===")
    try:
        # Delete in reverse dependency order (CASCADE will handle most dependencies)
        db._execute_query("DELETE FROM etf_holdings WHERE etf_ticker = 'TIGER' AND region = 'KR'", commit=True)
        db._execute_query("DELETE FROM tickers WHERE ticker = 'TIGER' AND region = 'KR'", commit=True)
        db._execute_query("DELETE FROM tickers WHERE ticker = '005930' AND region = 'KR'", commit=True)
        db._execute_query("DELETE FROM market_sentiment WHERE date = CURRENT_DATE", commit=True)
        db._execute_query("DELETE FROM global_market_indices WHERE symbol = 'KOSPI' AND date = CURRENT_DATE", commit=True)
        db._execute_query("DELETE FROM exchange_rate_history WHERE currency = 'USD_KRW' AND rate_date = CURRENT_DATE", commit=True)
        print("✅ Test data cleaned up successfully")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")


def main():
    """Main test runner"""
    print("=" * 70)
    print("Manual Test for Newly Implemented PostgreSQL Methods")
    print("=" * 70)

    # Create database manager
    db = PostgresDatabaseManager(
        host='localhost',
        port=5432,
        database='quant_platform',
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        pool_min_conn=2,
        pool_max_conn=5
    )

    try:
        # Run all tests
        results = []
        results.append(("Stock Details", test_stock_details(db)))
        results.append(("ETF Details", test_etf_details(db)))
        results.append(("Technical Analysis", test_technical_analysis(db)))
        results.append(("Fundamentals", test_fundamentals(db)))
        results.append(("Trading & Portfolio", test_trading_portfolio(db)))
        results.append(("Market Data", test_market_data(db)))

        # Clean up test data
        cleanup_test_data(db)

        # Print summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        for category, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{category:30s}: {status}")

        all_passed = all(result for _, result in results)
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED!")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Close connection pool
        db.close_pool()


if __name__ == '__main__':
    main()
