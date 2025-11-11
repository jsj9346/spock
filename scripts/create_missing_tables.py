#!/usr/bin/env python3
"""
Create missing PostgreSQL tables (exchange_rates, fx_signals)
"""

import os
import sys
import psycopg2
from psycopg2 import Error
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def create_exchange_rates_table(cursor):
    """Create exchange_rates hypertable"""
    logger.info("⚙️  Creating exchange_rates hypertable...")

    # Step 1: Create table
    cursor.execute("""
        CREATE TABLE exchange_rates (
            id BIGSERIAL,
            base_currency VARCHAR(3) NOT NULL,
            quote_currency VARCHAR(3) NOT NULL,
            date DATE NOT NULL,
            rate NUMERIC(20, 10) NOT NULL,
            source VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (base_currency, quote_currency, date)
        );
    """)
    logger.info("   ✓ Table created")

    # Step 2: Convert to hypertable
    cursor.execute("""
        SELECT create_hypertable('exchange_rates', 'date',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
    """)
    logger.info("   ✓ Converted to hypertable")

    # Step 3: Create indexes
    cursor.execute("""
        CREATE INDEX idx_exchange_rates_date ON exchange_rates(date DESC);
    """)
    cursor.execute("""
        CREATE INDEX idx_exchange_rates_currency ON exchange_rates(base_currency, quote_currency, date DESC);
    """)
    cursor.execute("""
        CREATE INDEX idx_exchange_rates_base ON exchange_rates(base_currency, date DESC);
    """)
    logger.info("   ✓ Indexes created")

    # Step 4: Enable compression
    cursor.execute("""
        ALTER TABLE exchange_rates SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'base_currency, quote_currency',
            timescaledb.compress_orderby = 'date DESC'
        );
    """)
    logger.info("   ✓ Compression enabled")

    # Step 5: Add compression policy
    cursor.execute("""
        SELECT add_compression_policy('exchange_rates', INTERVAL '90 days');
    """)
    logger.info("   ✓ Compression policy added")

    # Step 6: Add comment
    cursor.execute("""
        COMMENT ON TABLE exchange_rates IS 'Daily FX exchange rates (hypertable, 90-day compression)';
    """)
    logger.info("✅ exchange_rates table created successfully")


def create_fx_signals_table(cursor):
    """Create fx_signals table"""
    logger.info("⚙️  Creating fx_signals table...")

    # Step 1: Create table
    cursor.execute("""
        CREATE TABLE fx_signals (
            id BIGSERIAL PRIMARY KEY,
            currency VARCHAR(3) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            magnitude NUMERIC(10, 4) NOT NULL,
            current_rate NUMERIC(20, 10) NOT NULL,
            previous_rate NUMERIC(20, 10),
            date DATE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    logger.info("   ✓ Table created")

    # Step 2: Create indexes
    cursor.execute("""
        CREATE INDEX idx_fx_signals_currency ON fx_signals(currency, date DESC);
    """)
    cursor.execute("""
        CREATE INDEX idx_fx_signals_date ON fx_signals(date DESC);
    """)
    cursor.execute("""
        CREATE INDEX idx_fx_signals_type ON fx_signals(signal_type, date DESC);
    """)
    logger.info("   ✓ Indexes created")

    # Step 3: Add comment
    cursor.execute("""
        COMMENT ON TABLE fx_signals IS 'FX trading signals generated from exchange rate analysis (regular table)';
    """)
    logger.info("✅ fx_signals table created successfully")


def main():
    """Main execution"""
    # Get database connection parameters
    db_params = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'quant_platform'),
        'user': os.getenv('POSTGRES_USER', os.getenv('USER')),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    logger.info("=" * 60)
    logger.info("📊 Creating Missing PostgreSQL Tables")
    logger.info("=" * 60)
    logger.info(f"Database: {db_params['database']}@{db_params['host']}:{db_params['port']}")

    try:
        # Connect to database
        conn = psycopg2.connect(**db_params)
        conn.autocommit = False
        cursor = conn.cursor()
        logger.info("✅ Connected to PostgreSQL")

        # Create exchange_rates table
        try:
            create_exchange_rates_table(cursor)
            conn.commit()
        except Error as e:
            if 'already exists' in str(e):
                logger.info("⚠️  exchange_rates table already exists (skipping)")
                conn.rollback()
            else:
                raise

        # Create fx_signals table
        try:
            create_fx_signals_table(cursor)
            conn.commit()
        except Error as e:
            if 'already exists' in str(e):
                logger.info("⚠️  fx_signals table already exists (skipping)")
                conn.rollback()
            else:
                raise

        # Close connection
        cursor.close()
        conn.close()

        logger.info("\n" + "=" * 60)
        logger.info("🎉 Missing tables created successfully!")
        logger.info("=" * 60)

        return 0

    except Error as e:
        logger.error(f"❌ Database error: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
