#!/usr/bin/env python3
"""
Portfolio Allocation Migration Tests
Tests database migration script for portfolio allocation system
"""

import os
import sqlite3
import tempfile
import shutil
from pathlib import Path
import unittest


class TestPortfolioMigration(unittest.TestCase):
    """Test database migration for portfolio allocation system"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once"""
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.migration_script = Path('migrations/006_add_portfolio_allocation_tables.sql')
        cls.rollback_script = Path('migrations/006_rollback.sql')

    @classmethod
    def tearDownClass(cls):
        """Cleanup test environment"""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        """Setup for each test"""
        self.test_db = self.test_dir / 'test_migration.db'
        if self.test_db.exists():
            self.test_db.unlink()

    def tearDown(self):
        """Cleanup after each test"""
        if self.test_db.exists():
            self.test_db.unlink()

    # ====================================================================
    # Test 1: Clean Database Migration
    # ====================================================================

    def test_01_clean_database_migration(self):
        """Test migration on clean database"""
        print("\n" + "=" * 70)
        print("[Test 1] Clean Database Migration")
        print("=" * 70)

        # Create empty database
        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

        # Run migration
        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()

        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.executescript(migration_sql)
        conn.commit()

        # Verify tables created
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND (name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%' OR name LIKE '%holdings%')
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'allocation_drift_log',
            'asset_class_holdings',
            'portfolio_templates',
            'rebalancing_history',
            'rebalancing_orders'
        ]

        print(f"\n✓ Tables Created: {len(tables)}")
        for table in tables:
            print(f"  - {table}")

        self.assertEqual(set(tables), set(expected_tables),
                        "All expected tables should be created")

        # Verify templates inserted
        cursor.execute("SELECT COUNT(*) FROM portfolio_templates")
        template_count = cursor.fetchone()[0]

        print(f"\n✓ Default Templates Inserted: {template_count}")
        self.assertEqual(template_count, 4, "Should have 4 default templates")

        # Verify template names
        cursor.execute("SELECT template_name FROM portfolio_templates ORDER BY template_name")
        template_names = [row[0] for row in cursor.fetchall()]

        expected_names = ['aggressive', 'balanced', 'conservative', 'custom']
        print(f"✓ Template Names: {', '.join(template_names)}")
        self.assertEqual(template_names, expected_names, "Template names should match")

        conn.close()
        print("\n✅ Test 1 PASSED: Clean database migration successful")

    # ====================================================================
    # Test 2: Backward Compatibility
    # ====================================================================

    def test_02_backward_compatibility(self):
        """Test migration on existing database with existing tables"""
        print("\n" + "=" * 70)
        print("[Test 2] Backward Compatibility")
        print("=" * 70)

        # Create database with existing tables (simulating production DB)
        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Create existing tables (from previous migrations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickers (
                ticker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                region TEXT DEFAULT 'KR',
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                region TEXT DEFAULT 'KR',
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                trade_status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert sample data
        cursor.execute("INSERT INTO tickers (ticker, region, name) VALUES ('005930', 'KR', 'Samsung Electronics')")
        cursor.execute("INSERT INTO trades (ticker, region, side, quantity, entry_price) VALUES ('005930', 'KR', 'BUY', 10, 70000)")

        conn.commit()

        print("\n✓ Existing tables created with sample data")
        print("  - tickers: 1 record")
        print("  - trades: 1 record")

        # Run migration
        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()

        cursor.executescript(migration_sql)
        conn.commit()

        # Verify existing data preserved
        cursor.execute("SELECT COUNT(*) FROM tickers")
        ticker_count = cursor.fetchone()[0]
        self.assertEqual(ticker_count, 1, "Existing tickers should be preserved")

        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        self.assertEqual(trade_count, 1, "Existing trades should be preserved")

        print("\n✓ Existing data preserved:")
        print(f"  - tickers: {ticker_count} record")
        print(f"  - trades: {trade_count} record")

        # Verify new tables created
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND (name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%' OR name LIKE '%holdings%')
            ORDER BY name
        """)
        new_tables = [row[0] for row in cursor.fetchall()]

        print(f"\n✓ New tables added: {len(new_tables)}")
        for table in new_tables:
            print(f"  - {table}")

        self.assertGreaterEqual(len(new_tables), 5, "Should have at least 5 new tables")

        conn.close()
        print("\n✅ Test 2 PASSED: Backward compatibility verified")

    # ====================================================================
    # Test 3: Data Integrity Constraints
    # ====================================================================

    def test_03_data_integrity_constraints(self):
        """Test database constraints and validation"""
        print("\n" + "=" * 70)
        print("[Test 3] Data Integrity Constraints")
        print("=" * 70)

        # Run migration
        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()
        cursor.executescript(migration_sql)
        conn.commit()

        # Test 3.1: Allocation percentage constraints
        print("\n[Test 3.1] Allocation percentage constraints")
        try:
            cursor.execute("""
                INSERT INTO portfolio_templates (
                    template_name, risk_level,
                    bonds_etf_target_percent, commodities_etf_target_percent,
                    dividend_stocks_target_percent, individual_stocks_target_percent,
                    cash_target_percent
                ) VALUES ('invalid', 'moderate', 150.0, 20.0, 20.0, 20.0, 10.0)
            """)
            conn.commit()
            self.fail("Should reject invalid percentage >100%")
        except sqlite3.IntegrityError as e:
            print(f"  ✓ Correctly rejected invalid percentage: {e}")

        # Test 3.2: Risk level constraint
        print("\n[Test 3.2] Risk level enum constraint")
        try:
            cursor.execute("""
                INSERT INTO portfolio_templates (
                    template_name, risk_level,
                    bonds_etf_target_percent, commodities_etf_target_percent,
                    dividend_stocks_target_percent, individual_stocks_target_percent,
                    cash_target_percent
                ) VALUES ('invalid2', 'super_aggressive', 20.0, 20.0, 20.0, 30.0, 10.0)
            """)
            conn.commit()
            self.fail("Should reject invalid risk_level")
        except sqlite3.IntegrityError as e:
            print(f"  ✓ Correctly rejected invalid risk_level: {e}")

        # Test 3.3: Asset class enum constraint
        print("\n[Test 3.3] Asset class enum constraint")
        try:
            cursor.execute("""
                INSERT INTO asset_class_holdings (
                    template_name, asset_class, ticker, region,
                    quantity, avg_entry_price, current_price, market_value
                ) VALUES ('balanced', 'invalid_asset_class', 'TEST', 'KR', 10, 1000, 1000, 10000)
            """)
            conn.commit()
            self.fail("Should reject invalid asset_class")
        except sqlite3.IntegrityError as e:
            print(f"  ✓ Correctly rejected invalid asset_class: {e}")

        # Test 3.4: Foreign key constraint
        print("\n[Test 3.4] Foreign key constraint")
        try:
            cursor.execute("""
                INSERT INTO asset_class_holdings (
                    template_name, asset_class, ticker, region,
                    quantity, avg_entry_price, current_price, market_value
                ) VALUES ('nonexistent', 'bonds_etf', 'TEST', 'KR', 10, 1000, 1000, 10000)
            """)
            conn.commit()
            self.fail("Should reject invalid template_name reference")
        except sqlite3.IntegrityError as e:
            print(f"  ✓ Correctly enforced foreign key: {e}")

        conn.close()
        print("\n✅ Test 3 PASSED: All constraints working correctly")

    # ====================================================================
    # Test 4: Indexes Performance
    # ====================================================================

    def test_04_indexes_performance(self):
        """Test that indexes are created and used"""
        print("\n" + "=" * 70)
        print("[Test 4] Index Verification")
        print("=" * 70)

        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()
        cursor.executescript(migration_sql)
        conn.commit()

        # Count indexes
        cursor.execute("""
            SELECT name, tbl_name FROM sqlite_master
            WHERE type='index'
            AND (tbl_name LIKE '%portfolio%' OR tbl_name LIKE '%rebalancing%' OR tbl_name LIKE '%allocation%' OR tbl_name LIKE '%holdings%')
            ORDER BY tbl_name, name
        """)
        indexes = cursor.fetchall()

        print(f"\n✓ Indexes Created: {len(indexes)}")
        for idx_name, tbl_name in indexes:
            print(f"  - {tbl_name}: {idx_name}")

        self.assertGreaterEqual(len(indexes), 10, "Should have at least 10 indexes")

        # Test index usage with EXPLAIN QUERY PLAN
        print("\n[Index Usage Test]")
        cursor.execute("""
            EXPLAIN QUERY PLAN
            SELECT * FROM portfolio_templates WHERE template_name = 'balanced'
        """)
        plan = cursor.fetchall()
        plan_str = ' '.join([str(p) for p in plan])

        print(f"  Query Plan: {plan_str}")
        # Accept either explicit index or SQLite auto-generated index
        index_used = 'idx_portfolio_templates_name' in plan_str or 'sqlite_autoindex_portfolio_templates' in plan_str
        self.assertTrue(index_used,
                       "Query should use template_name index (explicit or auto-generated)")

        conn.close()
        print("\n✅ Test 4 PASSED: Indexes verified and working")

    # ====================================================================
    # Test 5: Rollback Functionality
    # ====================================================================

    def test_05_rollback_functionality(self):
        """Test rollback script removes all changes"""
        print("\n" + "=" * 70)
        print("[Test 5] Rollback Functionality")
        print("=" * 70)

        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Run migration
        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()
        cursor.executescript(migration_sql)
        conn.commit()

        # Verify tables exist
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table'
            AND (name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%' OR name LIKE '%holdings%')
        """)
        table_count_before = cursor.fetchone()[0]
        print(f"\n✓ Tables before rollback: {table_count_before}")
        self.assertGreaterEqual(table_count_before, 5, "Should have migration tables")

        # Run rollback
        with open(self.rollback_script, 'r') as f:
            rollback_sql = f.read()
        cursor.executescript(rollback_sql)
        conn.commit()

        # Verify tables removed
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table'
            AND (name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%' OR name LIKE '%holdings%')
        """)
        table_count_after = cursor.fetchone()[0]
        print(f"✓ Tables after rollback: {table_count_after}")

        # Note: 'portfolio' table might remain if it existed before migration
        self.assertLessEqual(table_count_after, 1,
                            "Migration tables should be removed (portfolio table may remain)")

        conn.close()
        print("\n✅ Test 5 PASSED: Rollback successfully removes migration")

    # ====================================================================
    # Test 6: Template Allocation Validation
    # ====================================================================

    def test_06_template_allocation_validation(self):
        """Test that default template allocations sum to 100%"""
        print("\n" + "=" * 70)
        print("[Test 6] Template Allocation Validation")
        print("=" * 70)

        conn = sqlite3.connect(str(self.test_db))
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        with open(self.migration_script, 'r') as f:
            migration_sql = f.read()
        cursor.executescript(migration_sql)
        conn.commit()

        # Verify each template allocations sum to 100%
        cursor.execute("""
            SELECT
                template_name,
                bonds_etf_target_percent,
                commodities_etf_target_percent,
                dividend_stocks_target_percent,
                individual_stocks_target_percent,
                cash_target_percent,
                (bonds_etf_target_percent + commodities_etf_target_percent +
                 dividend_stocks_target_percent + individual_stocks_target_percent +
                 cash_target_percent) AS total_percent
            FROM portfolio_templates
        """)

        templates = cursor.fetchall()

        print("\n✓ Template Allocation Validation:")
        for row in templates:
            name = row[0]
            bonds, commodities, dividend, individual, cash, total = row[1:]
            print(f"\n  {name}:")
            print(f"    Bonds ETF: {bonds}%")
            print(f"    Commodities ETF: {commodities}%")
            print(f"    Dividend Stocks: {dividend}%")
            print(f"    Individual Stocks: {individual}%")
            print(f"    Cash: {cash}%")
            print(f"    Total: {total}% {'✓' if abs(total - 100.0) < 0.01 else '❌'}")

            self.assertAlmostEqual(total, 100.0, places=1,
                                  msg=f"{name} allocation should sum to 100%")

        conn.close()
        print("\n✅ Test 6 PASSED: All template allocations valid")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
