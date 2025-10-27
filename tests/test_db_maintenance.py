"""
Test Database Maintenance Operations

Tests for cleanup_old_ohlcv_data(), vacuum_database(), analyze_database(), and get_database_stats()

Author: Spock Trading System
Created: 2025-10-19
"""

import os
import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
import pandas as pd
from modules.db_manager_sqlite import SQLiteDatabaseManager


@pytest.fixture
def temp_db():
    """Create temporary test database"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_spock.db')

    # Initialize database schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tickers table
    cursor.execute("""
        CREATE TABLE tickers (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_eng TEXT,
            exchange TEXT NOT NULL,
            region TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'KRW',
            asset_type TEXT NOT NULL DEFAULT 'STOCK',
            listing_date TEXT,
            lot_size INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            delisting_date TEXT,
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            data_source TEXT
        )
    """)

    # Create ohlcv_data table
    cursor.execute("""
        CREATE TABLE ohlcv_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            date TEXT NOT NULL,
            region TEXT,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume BIGINT NOT NULL,
            ma5 REAL,
            ma20 REAL,
            ma60 REAL,
            ma120 REAL,
            ma200 REAL,
            rsi_14 REAL,
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            bb_upper REAL,
            bb_middle REAL,
            bb_lower REAL,
            atr_14 REAL,
            created_at TEXT NOT NULL,
            UNIQUE(ticker, region, timeframe, date)
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    os.rmdir(temp_dir)


def test_cleanup_old_ohlcv_data(temp_db):
    """Test cleanup_old_ohlcv_data() method"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Insert test ticker
    ticker_data = {
        'ticker': '005930',
        'name': '삼성전자',
        'exchange': 'KOSPI',
        'region': 'KR',
        'currency': 'KRW',
        'asset_type': 'STOCK',
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    db.insert_ticker(ticker_data)

    # Insert OHLCV data with different dates
    base_date = datetime.now()

    # Recent data (should be kept)
    recent_dates = [
        base_date - timedelta(days=i) for i in range(0, 100)
    ]

    # Old data (should be deleted)
    old_dates = [
        base_date - timedelta(days=i) for i in range(250, 350)
    ]

    all_dates = recent_dates + old_dates

    # Create DataFrame
    ohlcv_data = pd.DataFrame({
        'date': all_dates,
        'open': [1000.0] * len(all_dates),
        'high': [1100.0] * len(all_dates),
        'low': [900.0] * len(all_dates),
        'close': [1050.0] * len(all_dates),
        'volume': [1000000] * len(all_dates)
    })

    # Insert OHLCV data
    inserted = db.insert_ohlcv_bulk(
        ticker='005930',
        ohlcv_df=ohlcv_data,
        timeframe='D',
        region='KR'
    )

    assert inserted == 200, "Should insert 200 rows"

    # Run cleanup with 250-day retention
    deleted = db.cleanup_old_ohlcv_data(retention_days=250)

    # Should delete approximately 100 old rows (99-100 due to boundary)
    assert 99 <= deleted <= 100, f"Should delete ~100 old rows, got {deleted}"

    # Verify remaining data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM ohlcv_data")
    remaining = cursor.fetchone()[0]
    conn.close()

    assert 100 <= remaining <= 101, f"Should have ~100 rows remaining, got {remaining}"


def test_vacuum_database(temp_db):
    """Test vacuum_database() method"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Insert and delete data to create fragmentation
    ticker_data = {
        'ticker': '005930',
        'name': '삼성전자',
        'exchange': 'KOSPI',
        'region': 'KR',
        'currency': 'KRW',
        'asset_type': 'STOCK',
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    db.insert_ticker(ticker_data)

    # Insert large OHLCV dataset
    dates = [datetime.now() - timedelta(days=i) for i in range(500)]
    ohlcv_data = pd.DataFrame({
        'date': dates,
        'open': [1000.0] * 500,
        'high': [1100.0] * 500,
        'low': [900.0] * 500,
        'close': [1050.0] * 500,
        'volume': [1000000] * 500
    })

    db.insert_ohlcv_bulk(
        ticker='005930',
        ohlcv_df=ohlcv_data,
        timeframe='D',
        region='KR'
    )

    # Delete old data to create fragmentation
    db.cleanup_old_ohlcv_data(retention_days=250)

    # Get size before VACUUM
    size_before = os.path.getsize(temp_db)

    # Run VACUUM
    result = db.vacuum_database()

    # Verify result structure
    assert 'size_before_mb' in result
    assert 'size_after_mb' in result
    assert 'space_reclaimed_mb' in result
    assert 'space_reclaimed_pct' in result
    assert 'duration_seconds' in result

    # Size after should be <= size before
    assert result['size_after_mb'] <= result['size_before_mb']

    # Space reclaimed should be non-negative
    assert result['space_reclaimed_mb'] >= 0


def test_analyze_database(temp_db):
    """Test analyze_database() method"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Run ANALYZE
    success = db.analyze_database()

    assert success is True, "ANALYZE should succeed"


def test_get_database_stats(temp_db):
    """Test get_database_stats() method"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Insert test data
    ticker_data = {
        'ticker': '005930',
        'name': '삼성전자',
        'exchange': 'KOSPI',
        'region': 'KR',
        'currency': 'KRW',
        'asset_type': 'STOCK',
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    db.insert_ticker(ticker_data)

    # Insert OHLCV data
    dates = [datetime.now() - timedelta(days=i) for i in range(250)]
    ohlcv_data = pd.DataFrame({
        'date': dates,
        'open': [1000.0] * 250,
        'high': [1100.0] * 250,
        'low': [900.0] * 250,
        'close': [1050.0] * 250,
        'volume': [1000000] * 250
    })

    db.insert_ohlcv_bulk(
        ticker='005930',
        ohlcv_df=ohlcv_data,
        timeframe='D',
        region='KR'
    )

    # Get stats
    stats = db.get_database_stats()

    # Verify stats structure
    assert 'db_path' in stats
    assert 'db_size_mb' in stats
    assert 'table_count' in stats
    assert 'ohlcv_rows' in stats
    assert 'unique_tickers' in stats
    assert 'unique_regions' in stats
    assert 'regions' in stats
    assert 'oldest_ohlcv_date' in stats
    assert 'newest_ohlcv_date' in stats
    assert 'data_retention_days' in stats
    assert 'ticker_count' in stats

    # Verify stats values
    assert stats['db_path'] == temp_db
    assert stats['db_size_mb'] > 0
    assert stats['table_count'] >= 2  # tickers + ohlcv_data
    assert stats['ohlcv_rows'] == 250
    assert stats['unique_tickers'] == 1
    assert stats['unique_regions'] == 1
    assert stats['regions'] == ['KR']
    assert stats['data_retention_days'] == 249  # 250 days - 1
    assert stats['ticker_count'] == 1


def test_cleanup_with_no_old_data(temp_db):
    """Test cleanup when there is no old data"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Insert test ticker
    ticker_data = {
        'ticker': '005930',
        'name': '삼성전자',
        'exchange': 'KOSPI',
        'region': 'KR',
        'currency': 'KRW',
        'asset_type': 'STOCK',
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    db.insert_ticker(ticker_data)

    # Insert recent data only
    dates = [datetime.now() - timedelta(days=i) for i in range(100)]
    ohlcv_data = pd.DataFrame({
        'date': dates,
        'open': [1000.0] * 100,
        'high': [1100.0] * 100,
        'low': [900.0] * 100,
        'close': [1050.0] * 100,
        'volume': [1000000] * 100
    })

    db.insert_ohlcv_bulk(
        ticker='005930',
        ohlcv_df=ohlcv_data,
        timeframe='D',
        region='KR'
    )

    # Run cleanup
    deleted = db.cleanup_old_ohlcv_data(retention_days=250)

    assert deleted == 0, "Should delete 0 rows when all data is recent"


def test_empty_database_stats(temp_db):
    """Test get_database_stats() on empty database"""

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path=temp_db)

    # Get stats on empty database
    stats = db.get_database_stats()

    # Verify empty stats
    assert stats['ohlcv_rows'] == 0
    assert stats['unique_tickers'] == 0
    assert stats['unique_regions'] == 0
    assert stats['regions'] == []
    assert stats['oldest_ohlcv_date'] is None
    assert stats['newest_ohlcv_date'] is None
    assert stats['data_retention_days'] == 0
    assert stats['ticker_count'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
