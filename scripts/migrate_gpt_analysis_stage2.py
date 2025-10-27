#!/usr/bin/env python3
"""
migrate_gpt_analysis_stage2.py - Database Migration for Stage 2 Analysis

Adds 6 new columns to gpt_analysis table for Weinstein Stage 2 theory:
1. stage2_confirmed (BOOLEAN)
2. stage2_confidence (REAL)
3. stage2_ma_alignment (BOOLEAN)
4. stage2_volume_surge (BOOLEAN)
5. stage2_reasoning (TEXT)
6. position_adjustment (REAL)

Features:
- Backup before migration
- Rollback capability
- Schema validation
- Backward compatibility verification
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.db_manager_sqlite import SQLiteDatabaseManager

class GPTAnalysisStage2Migration:
    """Database migration for Stage 2 analysis columns"""

    def __init__(self, db_path: str = "./data/spock_local.db"):
        self.db_path = db_path
        self.backup_path = None
        self.migration_executed = False

    def create_backup(self) -> str:
        """Create database backup before migration"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = Path(self.db_path).parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        self.backup_path = backup_dir / f"spock_local_before_stage2_migration_{timestamp}.db"

        print(f"📦 Creating backup: {self.backup_path}")
        shutil.copy2(self.db_path, self.backup_path)
        print(f"✅ Backup created successfully")

        return str(self.backup_path)

    def check_table_exists(self, conn: sqlite3.Connection) -> bool:
        """Check if gpt_analysis table exists"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='gpt_analysis'
        """)
        result = cursor.fetchone()
        return result is not None

    def check_column_exists(self, conn: sqlite3.Connection, column_name: str) -> bool:
        """Check if column already exists"""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info(gpt_analysis)")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns

    def execute_migration(self) -> bool:
        """Execute database migration"""
        print("\n🔄 Starting database migration...")

        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            # Verify table exists
            if not self.check_table_exists(conn):
                print("❌ gpt_analysis table does not exist")
                print("💡 Run StockGPTAnalyzer.init_database() first")
                conn.close()
                return False

            # Define new columns
            new_columns = [
                ("stage2_confirmed", "BOOLEAN", "0"),
                ("stage2_confidence", "REAL", "0.0"),
                ("stage2_ma_alignment", "BOOLEAN", "0"),
                ("stage2_volume_surge", "BOOLEAN", "0"),
                ("stage2_reasoning", "TEXT", "''"),
                ("position_adjustment", "REAL", "1.0")
            ]

            # Add columns if they don't exist
            added_columns = []
            skipped_columns = []

            for column_name, column_type, default_value in new_columns:
                if self.check_column_exists(conn, column_name):
                    print(f"⏭️  Column '{column_name}' already exists, skipping")
                    skipped_columns.append(column_name)
                    continue

                print(f"➕ Adding column: {column_name} {column_type} DEFAULT {default_value}")

                alter_sql = f"""
                    ALTER TABLE gpt_analysis
                    ADD COLUMN {column_name} {column_type} DEFAULT {default_value}
                """

                cursor.execute(alter_sql)
                added_columns.append(column_name)
                print(f"✅ Column '{column_name}' added successfully")

            conn.commit()
            conn.close()

            self.migration_executed = True

            # Summary
            print(f"\n📊 Migration Summary:")
            print(f"   Added: {len(added_columns)} columns")
            print(f"   Skipped: {len(skipped_columns)} columns (already exist)")
            print(f"   Total: {len(new_columns)} columns")

            if added_columns:
                print(f"\n✅ Added columns: {', '.join(added_columns)}")
            if skipped_columns:
                print(f"⏭️  Skipped columns: {', '.join(skipped_columns)}")

            return True

        except sqlite3.OperationalError as e:
            print(f"\n❌ Migration failed: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False

    def validate_schema(self) -> bool:
        """Validate new schema after migration"""
        print("\n🔍 Validating schema...")

        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            # Get table schema
            cursor.execute("PRAGMA table_info(gpt_analysis)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            # Required columns
            required_columns = {
                'stage2_confirmed': 'BOOLEAN',
                'stage2_confidence': 'REAL',
                'stage2_ma_alignment': 'BOOLEAN',
                'stage2_volume_surge': 'BOOLEAN',
                'stage2_reasoning': 'TEXT',
                'position_adjustment': 'REAL'
            }

            # Validate presence and type
            all_valid = True
            for col_name, expected_type in required_columns.items():
                if col_name not in columns:
                    print(f"❌ Missing column: {col_name}")
                    all_valid = False
                else:
                    actual_type = columns[col_name]
                    if actual_type.upper() == expected_type.upper():
                        print(f"✅ {col_name}: {actual_type}")
                    else:
                        print(f"⚠️  {col_name}: Expected {expected_type}, got {actual_type}")

            # Get row count
            cursor.execute("SELECT COUNT(*) FROM gpt_analysis")
            row_count = cursor.fetchone()[0]
            print(f"\n📊 Total rows in gpt_analysis: {row_count:,}")

            conn.close()

            if all_valid:
                print("\n✅ Schema validation passed")
            else:
                print("\n❌ Schema validation failed")

            return all_valid

        except Exception as e:
            print(f"\n❌ Validation error: {e}")
            return False

    def test_backward_compatibility(self) -> bool:
        """Test that old code can still read from database"""
        print("\n🧪 Testing backward compatibility...")

        try:
            from modules.stock_gpt_analyzer import StockGPTAnalyzer

            # Initialize analyzer (will use new schema)
            analyzer = StockGPTAnalyzer(
                db_path=self.db_path,
                enable_gpt=False
            )
            print("✅ StockGPTAnalyzer initialized successfully")

            # Test cache manager
            cached = analyzer.cache_manager.get_cached_analysis(
                ticker="TEST_TICKER",
                date="2025-01-01"
            )
            print(f"✅ Cache manager working (result: {cached is not None})")

            print("\n✅ Backward compatibility test passed")
            return True

        except Exception as e:
            print(f"\n❌ Backward compatibility test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def rollback(self) -> bool:
        """Rollback migration by restoring backup"""
        if not self.backup_path or not os.path.exists(self.backup_path):
            print("❌ No backup found for rollback")
            return False

        print(f"\n🔄 Rolling back to backup: {self.backup_path}")

        try:
            shutil.copy2(self.backup_path, self.db_path)
            print("✅ Rollback successful")
            return True
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return False

    def run_full_migration(self, skip_backup: bool = False) -> bool:
        """Execute complete migration workflow"""
        print("=" * 60)
        print("GPT Analysis Stage 2 Migration")
        print("=" * 60)

        # Step 1: Backup
        if not skip_backup:
            try:
                self.create_backup()
            except Exception as e:
                print(f"❌ Backup failed: {e}")
                return False
        else:
            print("⏭️  Skipping backup (--skip-backup flag)")

        # Step 2: Execute migration
        if not self.execute_migration():
            print("\n❌ Migration failed")
            if self.backup_path:
                print("\n💡 Run rollback with: --rollback")
            return False

        # Step 3: Validate schema
        if not self.validate_schema():
            print("\n❌ Schema validation failed")
            return False

        # Step 4: Test backward compatibility
        if not self.test_backward_compatibility():
            print("\n❌ Backward compatibility test failed")
            return False

        # Success
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)

        if self.backup_path:
            print(f"\n📦 Backup saved: {self.backup_path}")
            print("💡 You can delete the backup after verifying the migration")

        return True

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate gpt_analysis table for Stage 2 analysis support"
    )
    parser.add_argument(
        "--db-path",
        default="./data/spock_local.db",
        help="Path to SQLite database (default: ./data/spock_local.db)"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip backup creation (NOT RECOMMENDED)"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to most recent backup"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate schema without migration"
    )

    args = parser.parse_args()

    migration = GPTAnalysisStage2Migration(db_path=args.db_path)

    # Rollback mode
    if args.rollback:
        # Find most recent backup
        backup_dir = Path(args.db_path).parent / "backups"
        if not backup_dir.exists():
            print("❌ No backup directory found")
            sys.exit(1)

        backups = sorted(
            backup_dir.glob("spock_local_before_stage2_migration_*.db"),
            reverse=True
        )

        if not backups:
            print("❌ No Stage 2 migration backups found")
            sys.exit(1)

        migration.backup_path = str(backups[0])
        print(f"📦 Found backup: {migration.backup_path}")

        if migration.rollback():
            print("\n✅ Rollback successful")
            sys.exit(0)
        else:
            print("\n❌ Rollback failed")
            sys.exit(1)

    # Validate-only mode
    if args.validate_only:
        if migration.validate_schema():
            sys.exit(0)
        else:
            sys.exit(1)

    # Full migration
    success = migration.run_full_migration(skip_backup=args.skip_backup)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
