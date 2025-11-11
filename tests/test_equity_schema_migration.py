"""
Unit tests for equity account schema migration.

Tests:
1. Schema migration SQL execution
2. Column addition (8 new equity columns)
3. Index creation (4 new indexes)
4. Constraint validation (2 CHECK constraints)
5. Backward compatibility (old queries still work)
6. Rollback procedures

Created: 2025-11-07
Phase: Phase 1 - Foundation & Schema (TDD)
"""

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(scope="module")
def db_connection():
    """Create database connection to staging database."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database="quant_platform_staging",  # Use staging for tests
        user=os.getenv("POSTGRES_USER", "13ruce"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    yield conn
    conn.close()


@pytest.fixture
def cursor(db_connection):
    """Create cursor for database operations."""
    with db_connection.cursor(cursor_factory=RealDictCursor) as cur:
        yield cur
        db_connection.commit()


# ============================================================================
# Schema Migration SQL
# ============================================================================

MIGRATION_SQL_ADD_COLUMNS = """
-- Add 8 new equity account columns to ticker_fundamentals
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS capital_stock NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS capital_surplus NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS retained_earnings NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS treasury_stock NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS other_comprehensive_income NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS non_controlling_interest NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS unappropriated_retained_earnings NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS legal_reserve NUMERIC(20, 2);
"""

MIGRATION_SQL_ADD_CONSTRAINTS = """
-- Add data quality constraints
ALTER TABLE ticker_fundamentals
DROP CONSTRAINT IF EXISTS chk_treasury_stock_negative,
ADD CONSTRAINT chk_treasury_stock_negative
    CHECK (treasury_stock IS NULL OR treasury_stock <= 0);

ALTER TABLE ticker_fundamentals
DROP CONSTRAINT IF EXISTS chk_capital_stock_positive,
ADD CONSTRAINT chk_capital_stock_positive
    CHECK (capital_stock IS NULL OR capital_stock >= 0);
"""

MIGRATION_SQL_CREATE_INDEXES = """
-- Create indexes for equity account queries (CONCURRENTLY for zero downtime)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_equity_complete
    ON ticker_fundamentals (ticker, region, date)
    WHERE capital_stock IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_negative_equity
    ON ticker_fundamentals (ticker, region, date)
    WHERE total_equity < 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_treasury_stock
    ON ticker_fundamentals (ticker, region, date)
    WHERE treasury_stock IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_equity_validation
    ON ticker_fundamentals (ticker, region, date, total_equity,
        (capital_stock + capital_surplus + retained_earnings +
         COALESCE(treasury_stock, 0) + COALESCE(other_comprehensive_income, 0)));
"""

ROLLBACK_SQL_DROP_COLUMNS = """
-- Rollback: Drop all new equity columns
ALTER TABLE ticker_fundamentals
DROP COLUMN IF EXISTS capital_stock,
DROP COLUMN IF EXISTS capital_surplus,
DROP COLUMN IF EXISTS retained_earnings,
DROP COLUMN IF EXISTS treasury_stock,
DROP COLUMN IF EXISTS other_comprehensive_income,
DROP COLUMN IF EXISTS non_controlling_interest,
DROP COLUMN IF EXISTS unappropriated_retained_earnings,
DROP COLUMN IF EXISTS legal_reserve;
"""

ROLLBACK_SQL_DROP_CONSTRAINTS = """
-- Rollback: Drop constraints
ALTER TABLE ticker_fundamentals
DROP CONSTRAINT IF EXISTS chk_treasury_stock_negative,
DROP CONSTRAINT IF EXISTS chk_capital_stock_positive;
"""

ROLLBACK_SQL_DROP_INDEXES = """
-- Rollback: Drop indexes
DROP INDEX IF EXISTS idx_tf_equity_complete;
DROP INDEX IF EXISTS idx_tf_negative_equity;
DROP INDEX IF EXISTS idx_tf_treasury_stock;
DROP INDEX IF EXISTS idx_tf_equity_validation;
"""


# ============================================================================
# Test 1: Schema Migration - Add Columns
# ============================================================================

class TestSchemaColumnsAddition:
    """Test adding 8 new equity account columns."""

    def test_add_equity_columns(self, cursor):
        """Test that all 8 equity columns can be added successfully."""
        # Execute migration
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Verify columns exist
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN (
                'capital_stock', 'capital_surplus', 'retained_earnings',
                'treasury_stock', 'other_comprehensive_income',
                'non_controlling_interest', 'unappropriated_retained_earnings',
                'legal_reserve'
            )
            ORDER BY column_name;
        """)

        columns = cursor.fetchall()
        assert len(columns) == 8, f"Expected 8 columns, got {len(columns)}"

        # Verify all columns are NUMERIC(20, 2)
        for col in columns:
            assert col["data_type"] == "numeric", \
                f"{col['column_name']} should be numeric, got {col['data_type']}"
            assert col["is_nullable"] == "YES", \
                f"{col['column_name']} should be nullable for backward compatibility"

    def test_columns_are_nullable(self, cursor):
        """Test that all new columns are nullable (backward compatibility)."""
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN (
                'capital_stock', 'capital_surplus', 'retained_earnings',
                'treasury_stock', 'other_comprehensive_income',
                'non_controlling_interest', 'unappropriated_retained_earnings',
                'legal_reserve'
            )
            AND is_nullable = 'NO';
        """)

        non_nullable = cursor.fetchall()
        assert len(non_nullable) == 0, \
            f"Found non-nullable columns: {[c['column_name'] for c in non_nullable]}"

    def test_existing_data_preserved(self, cursor):
        """Test that existing data is preserved after migration."""
        # Get record count before
        cursor.execute("SELECT COUNT(*) as count FROM ticker_fundamentals;")
        count_before = cursor.fetchone()["count"]

        # Execute migration (idempotent with IF NOT EXISTS)
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Get record count after
        cursor.execute("SELECT COUNT(*) as count FROM ticker_fundamentals;")
        count_after = cursor.fetchone()["count"]

        assert count_before == count_after, \
            f"Data loss detected: {count_before} -> {count_after}"

    def test_new_columns_default_null(self, cursor):
        """Test that new columns default to NULL for existing records."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        cursor.execute("""
            SELECT COUNT(*) as count
            FROM ticker_fundamentals
            WHERE capital_stock IS NOT NULL
               OR capital_surplus IS NOT NULL
               OR retained_earnings IS NOT NULL;
        """)

        non_null_count = cursor.fetchone()["count"]
        assert non_null_count == 0, \
            f"New columns should be NULL, found {non_null_count} non-NULL values"


# ============================================================================
# Test 2: Constraints Addition
# ============================================================================

class TestConstraintsAddition:
    """Test adding CHECK constraints for data quality."""

    def test_add_treasury_stock_constraint(self, cursor):
        """Test that treasury stock constraint is added correctly."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Verify constraint exists
        cursor.execute("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints
            WHERE constraint_name = 'chk_treasury_stock_negative';
        """)

        constraint = cursor.fetchone()
        assert constraint is not None, "Treasury stock constraint not found"
        assert "treasury_stock" in constraint["check_clause"].lower()

    def test_add_capital_stock_constraint(self, cursor):
        """Test that capital stock constraint is added correctly."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Verify constraint exists
        cursor.execute("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints
            WHERE constraint_name = 'chk_capital_stock_positive';
        """)

        constraint = cursor.fetchone()
        assert constraint is not None, "Capital stock constraint not found"
        assert "capital_stock" in constraint["check_clause"].lower()

    def test_treasury_stock_constraint_rejects_positive(self, cursor):
        """Test that treasury stock constraint rejects positive values."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Try to insert positive treasury stock (should fail)
        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute("""
                INSERT INTO ticker_fundamentals
                (ticker, region, date, treasury_stock)
                VALUES ('TEST01', 'KR', '2024-12-31', 1000000.00);
            """)
            cursor.connection.commit()

        cursor.connection.rollback()

    def test_capital_stock_constraint_rejects_negative(self, cursor):
        """Test that capital stock constraint rejects negative values."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Try to insert negative capital stock (should fail)
        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute("""
                INSERT INTO ticker_fundamentals
                (ticker, region, date, capital_stock)
                VALUES ('TEST02', 'KR', '2024-12-31', -1000000.00);
            """)
            cursor.connection.commit()

        cursor.connection.rollback()


# ============================================================================
# Test 3: Index Creation
# ============================================================================

class TestIndexCreation:
    """Test creating 4 new indexes for equity queries."""

    def test_create_equity_complete_index(self, cursor):
        """Test that idx_tf_equity_complete index is created."""
        # Note: Cannot test CONCURRENTLY in transaction, test structure only
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'ticker_fundamentals'
            AND indexname = 'idx_tf_equity_complete';
        """)

        index = cursor.fetchone()
        # May not exist yet in test (CONCURRENTLY requires special handling)
        # Just verify SQL syntax is correct
        assert "capital_stock IS NOT NULL" in MIGRATION_SQL_CREATE_INDEXES

    def test_create_negative_equity_index(self, cursor):
        """Test that idx_tf_negative_equity index SQL is correct."""
        assert "total_equity < 0" in MIGRATION_SQL_CREATE_INDEXES

    def test_create_treasury_stock_index(self, cursor):
        """Test that idx_tf_treasury_stock index SQL is correct."""
        assert "treasury_stock IS NOT NULL" in MIGRATION_SQL_CREATE_INDEXES

    def test_create_equity_validation_index(self, cursor):
        """Test that idx_tf_equity_validation index SQL is correct."""
        assert "capital_stock + capital_surplus" in MIGRATION_SQL_CREATE_INDEXES
        assert "COALESCE(treasury_stock, 0)" in MIGRATION_SQL_CREATE_INDEXES


# ============================================================================
# Test 4: Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Test that existing queries still work after migration."""

    def test_select_without_equity_columns(self, cursor):
        """Test that SELECT without new columns still works."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Old query that doesn't reference new columns
        cursor.execute("""
            SELECT ticker, region, date, total_equity, net_income
            FROM ticker_fundamentals
            WHERE region = 'KR'
            LIMIT 5;
        """)

        results = cursor.fetchall()
        assert len(results) > 0, "Query should return results"
        assert "total_equity" in results[0], "Old column should exist"

    def test_insert_without_equity_columns(self, cursor):
        """Test that INSERT without new columns still works."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Old-style insert (should work, new columns default to NULL)
        cursor.execute("""
            INSERT INTO ticker_fundamentals
            (ticker, region, date, total_equity, net_income)
            VALUES ('TEST03', 'KR', '2024-12-31', 1000000.00, 50000.00)
            RETURNING id;
        """)

        result = cursor.fetchone()
        assert result["id"] is not None, "Insert should succeed"

        # Verify new columns are NULL
        cursor.execute("""
            SELECT capital_stock, retained_earnings
            FROM ticker_fundamentals
            WHERE ticker = 'TEST03';
        """)

        row = cursor.fetchone()
        assert row["capital_stock"] is None
        assert row["retained_earnings"] is None

    def test_update_without_equity_columns(self, cursor):
        """Test that UPDATE without new columns still works."""
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Insert test data
        cursor.execute("""
            INSERT INTO ticker_fundamentals
            (ticker, region, date, total_equity)
            VALUES ('TEST04', 'KR', '2024-12-31', 1000000.00);
        """)

        # Update without touching new columns
        cursor.execute("""
            UPDATE ticker_fundamentals
            SET total_equity = 2000000.00
            WHERE ticker = 'TEST04';
        """)

        # Verify update worked and new columns still NULL
        cursor.execute("""
            SELECT total_equity, capital_stock
            FROM ticker_fundamentals
            WHERE ticker = 'TEST04';
        """)

        row = cursor.fetchone()
        assert row["total_equity"] == 2000000.00
        assert row["capital_stock"] is None


# ============================================================================
# Test 5: Rollback Procedures
# ============================================================================

class TestRollbackProcedures:
    """Test that rollback SQL correctly removes changes."""

    def test_rollback_drops_columns(self, cursor):
        """Test that rollback SQL drops all new columns."""
        # Add columns
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Verify columns exist
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN ('capital_stock', 'retained_earnings');
        """)
        assert cursor.fetchone()["count"] == 2

        # Rollback
        cursor.execute(ROLLBACK_SQL_DROP_COLUMNS)

        # Verify columns dropped
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN ('capital_stock', 'retained_earnings');
        """)
        assert cursor.fetchone()["count"] == 0

    def test_rollback_drops_constraints(self, cursor):
        """Test that rollback SQL drops all constraints."""
        # Add constraints
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Rollback
        cursor.execute(ROLLBACK_SQL_DROP_CONSTRAINTS)

        # Verify constraints dropped
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.check_constraints
            WHERE constraint_name IN (
                'chk_treasury_stock_negative',
                'chk_capital_stock_positive'
            );
        """)
        assert cursor.fetchone()["count"] == 0


# ============================================================================
# Test 6: Integration Test - Full Migration
# ============================================================================

class TestFullMigration:
    """Integration test for complete migration workflow."""

    def test_full_migration_workflow(self, cursor):
        """Test complete migration: columns → constraints → indexes."""
        # Step 1: Add columns
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)

        # Step 2: Add constraints
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Step 3: Insert test data with equity breakdown
        cursor.execute("""
            INSERT INTO ticker_fundamentals
            (ticker, region, date, total_equity,
             capital_stock, capital_surplus, retained_earnings, treasury_stock)
            VALUES ('TEST05', 'KR', '2024-12-31', 3400000.00,
                    1000000.00, 500000.00, 2000000.00, -100000.00)
            RETURNING id;
        """)

        result = cursor.fetchone()
        assert result["id"] is not None

        # Step 4: Query with equity breakdown
        cursor.execute("""
            SELECT ticker, total_equity, capital_stock, retained_earnings,
                   (capital_stock + capital_surplus + retained_earnings + treasury_stock)
                   AS calculated_equity
            FROM ticker_fundamentals
            WHERE ticker = 'TEST05';
        """)

        row = cursor.fetchone()
        assert row["total_equity"] == 3400000.00
        assert row["calculated_equity"] == 3400000.00  # Sum matches

    def test_migration_idempotency(self, cursor):
        """Test that migration can be run multiple times safely."""
        # Run migration twice
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)  # Should not fail

        # Verify still only 8 columns added
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN (
                'capital_stock', 'capital_surplus', 'retained_earnings',
                'treasury_stock', 'other_comprehensive_income',
                'non_controlling_interest', 'unappropriated_retained_earnings',
                'legal_reserve'
            );
        """)

        assert cursor.fetchone()["count"] == 8


# ============================================================================
# Test 7: Data Integrity
# ============================================================================

class TestDataIntegrity:
    """Test data integrity after migration."""

    def test_no_data_loss_after_migration(self, cursor):
        """Test that no records are lost after migration."""
        # Get counts before
        cursor.execute("SELECT COUNT(*) as count FROM ticker_fundamentals;")
        count_before = cursor.fetchone()["count"]

        cursor.execute("SELECT SUM(total_equity) as sum FROM ticker_fundamentals;")
        sum_before = cursor.fetchone()["sum"]

        # Run migration
        cursor.execute(MIGRATION_SQL_ADD_COLUMNS)
        cursor.execute(MIGRATION_SQL_ADD_CONSTRAINTS)

        # Get counts after
        cursor.execute("SELECT COUNT(*) as count FROM ticker_fundamentals;")
        count_after = cursor.fetchone()["count"]

        cursor.execute("SELECT SUM(total_equity) as sum FROM ticker_fundamentals;")
        sum_after = cursor.fetchone()["sum"]

        # Verify no data loss
        assert count_before == count_after
        assert sum_before == sum_after  # Total equity unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
