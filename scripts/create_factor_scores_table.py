#!/usr/bin/env python3
"""
Create factor_scores table in PostgreSQL database
"""

import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def main():
    """Main execution function"""
    logger.info("=== Factor Scores Table Creation Script ===")

    # Initialize database connection
    db = PostgresDatabaseManager()

    try:
        # Create table
        logger.info("Creating factor_scores table...")
        db.execute_update("""
            CREATE TABLE IF NOT EXISTS factor_scores (
                ticker VARCHAR(20) NOT NULL,
                region VARCHAR(2) NOT NULL,
                date DATE NOT NULL,
                factor_name VARCHAR(50) NOT NULL,
                score NUMERIC(10,4),
                percentile NUMERIC(5,2),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (ticker, region, date, factor_name)
            )
        """)

        # Create indexes
        logger.info("Creating indexes...")
        
        db.execute_update("""
            CREATE INDEX IF NOT EXISTS idx_factor_scores_date
            ON factor_scores(date DESC)
        """)
        
        db.execute_update("""
            CREATE INDEX IF NOT EXISTS idx_factor_scores_factor
            ON factor_scores(factor_name)
        """)
        
        db.execute_update("""
            CREATE INDEX IF NOT EXISTS idx_factor_scores_region_factor
            ON factor_scores(region, factor_name, date DESC)
        """)

        logger.info("✅ Successfully created factor_scores table!")
        
        # Verify
        result = db.execute_query("""
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_name = 'factor_scores'
        """)
        
        if result and result[0]['cnt'] > 0:
            logger.info("✅ Table verified successfully!")
        else:
            logger.error("❌ Table verification failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
