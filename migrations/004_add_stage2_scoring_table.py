"""
Migration 004: Add Stage 2 Scoring Table

Phase 5 - LayeredScoringEngine Integration
Adds filter_cache_stage2 table for 100-point scoring system results

Run after:
- 003_add_filtering_tables.py (Stage 0 and Stage 1 tables)

Usage:
    python migrations/004_add_stage2_scoring_table.py --db-path data/spock_local.db
"""

import sqlite3
import sys
import os
import argparse
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class Stage2ScoringMigration:
    """Migration for Stage 2 scoring table"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def migrate(self):
        """Execute migration"""
        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            logger.info("ℹ️  Run init_db.py first to create the database")
            return False

        logger.info(f"📊 Starting Migration 004: Stage 2 Scoring Table")
        logger.info(f"   Database: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='filter_cache_stage2'
            """)
            if cursor.fetchone():
                logger.warning("⚠️  Table 'filter_cache_stage2' already exists. Skipping migration.")
                return True

            # Create Stage 2 scoring table
            self._create_stage2_table(cursor)

            # Create indexes
            self._create_indexes(cursor)

            # Verify creation
            cursor.execute("SELECT COUNT(*) FROM filter_cache_stage2")
            logger.info(f"✅ Table created successfully (0 rows)")

            conn.commit()
            logger.info("✅ Migration 004 completed successfully")
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Migration failed: {e}")
            return False
        finally:
            conn.close()

    def _create_stage2_table(self, cursor):
        """Create filter_cache_stage2 table for LayeredScoringEngine results"""
        logger.info("  📋 Creating filter_cache_stage2 table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage2 (
                -- ========================================
                -- Primary Key
                -- ========================================
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ========================================
                -- Ticker Identification (Multi-Market Support)
                -- ========================================
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,                 -- 'KR', 'US', 'HK', 'CN', 'JP', 'VN'

                -- ========================================
                -- Scoring Results (100-Point System)
                -- ========================================
                total_score INTEGER NOT NULL,         -- 0-100 total score

                -- Layer 1: Macro Analysis (25 points)
                market_regime_score INTEGER,          -- MarketRegimeModule (5 points)
                volume_profile_score INTEGER,         -- VolumeProfileModule (10 points)
                price_action_score INTEGER,           -- PriceActionModule (10 points)

                -- Layer 2: Structural Analysis (45 points)
                stage_analysis_score INTEGER,         -- StageAnalysisModule (15 points)
                moving_average_score INTEGER,         -- MovingAverageModule (15 points)
                relative_strength_score INTEGER,      -- RelativeStrengthModule (15 points)

                -- Layer 3: Micro Analysis (30 points)
                pattern_recognition_score INTEGER,    -- PatternRecognitionModule (10 points)
                volume_spike_score INTEGER,           -- VolumeSpikeModule (10 points)
                momentum_score INTEGER,               -- MomentumModule (10 points)

                -- ========================================
                -- Trading Recommendation
                -- ========================================
                recommendation TEXT NOT NULL,         -- 'BUY' (≥70), 'WATCH' (50-69), 'AVOID' (<50)

                -- ========================================
                -- Market Context (Adaptive Thresholds)
                -- ========================================
                market_regime TEXT,                   -- 'bull', 'sideways', 'bear'
                volatility_regime TEXT,               -- 'low', 'medium', 'high'

                -- ========================================
                -- Detected Patterns (for Kelly Calculator)
                -- ========================================
                detected_pattern TEXT,                -- Pattern type (e.g., 'VCP', 'Cup-and-Handle', 'Stage 2 Breakout')
                pattern_confidence REAL,              -- Pattern confidence 0.0-1.0

                -- ========================================
                -- Module Explanations (JSON)
                -- ========================================
                score_explanations TEXT,              -- JSON: Detailed reasoning from each module

                -- ========================================
                -- Performance Metadata
                -- ========================================
                execution_time_ms INTEGER,            -- Scoring execution time

                -- ========================================
                -- Timestamps
                -- ========================================
                cache_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- ========================================
                -- Constraints
                -- ========================================
                UNIQUE(ticker, region, cache_timestamp)
            )
        """)

    def _create_indexes(self, cursor):
        """Create indexes for Stage 2 table"""
        logger.info("  🔍 Creating indexes...")

        indexes = [
            # Query by ticker + region
            "CREATE INDEX IF NOT EXISTS idx_stage2_ticker_region ON filter_cache_stage2(ticker, region)",

            # Sort by total score (descending)
            "CREATE INDEX IF NOT EXISTS idx_stage2_score ON filter_cache_stage2(total_score DESC)",

            # Filter by recommendation
            "CREATE INDEX IF NOT EXISTS idx_stage2_recommendation ON filter_cache_stage2(recommendation)",

            # Query by pattern type
            "CREATE INDEX IF NOT EXISTS idx_stage2_pattern ON filter_cache_stage2(detected_pattern)",

            # Time-series queries
            "CREATE INDEX IF NOT EXISTS idx_stage2_timestamp ON filter_cache_stage2(cache_timestamp DESC)",

            # Region-specific queries
            "CREATE INDEX IF NOT EXISTS idx_stage2_region ON filter_cache_stage2(region)",
        ]

        for idx_sql in indexes:
            cursor.execute(idx_sql)

    def rollback(self):
        """Rollback migration"""
        logger.warning(f"⚠️  Rolling back Migration 004...")

        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DROP TABLE IF EXISTS filter_cache_stage2")
            conn.commit()
            logger.info("✅ Rollback completed: filter_cache_stage2 dropped")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Rollback failed: {e}")
            return False
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description='Migration 004: Add Stage 2 Scoring Table')
    parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite database path')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')

    args = parser.parse_args()

    migration = Stage2ScoringMigration(db_path=args.db_path)

    if args.rollback:
        success = migration.rollback()
    else:
        success = migration.migrate()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
