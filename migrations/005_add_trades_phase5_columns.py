"""
Migration 005: Add Phase 5 columns to trades table

Purpose:
    Support Phase 5 portfolio management features including:
    - Global market support (region field)
    - Entry/Exit price tracking (entry_price, exit_price)
    - Entry/Exit timestamps (entry_timestamp, exit_timestamp)
    - Trade status tracking (trade_status: OPEN, CLOSED)
    - Sector tracking for position limits (sector)
    - Position sizing percentage (position_size_percent)

Changes:
    - Add region column (default 'KR' for backward compatibility)
    - Add entry_price and exit_price columns
    - Add entry_timestamp and exit_timestamp columns
    - Add trade_status column (default 'OPEN')
    - Add sector column for position limit tracking
    - Add position_size_percent column

Usage:
    python migrations/005_add_trades_phase5_columns.py
    python migrations/005_add_trades_phase5_columns.py --db-path custom.db
    python migrations/005_add_trades_phase5_columns.py --verify-only
"""

import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TradesPhase5Migration:
    """trades 테이블 Phase 5 컬럼 추가 마이그레이션"""

    MIGRATION_ID = '005_add_trades_phase5_columns'
    MIGRATION_DATE = '2025-10-15'

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

    def check_column_exists(self, cursor, column_name: str) -> bool:
        """trades 테이블에 특정 컬럼 존재 여부 확인"""
        cursor.execute("PRAGMA table_info(trades)")
        columns = [col[1] for col in cursor.fetchall()]
        return column_name in columns

    def migrate(self) -> bool:
        """마이그레이션 실행"""

        # 데이터베이스 파일 존재 확인
        if not os.path.exists(self.db_path):
            logger.error(f"❌ 데이터베이스 파일 없음: {self.db_path}")
            logger.info("💡 먼저 'python init_db.py'를 실행하여 데이터베이스를 생성하세요")
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            logger.info(f"🔧 마이그레이션 시작: {self.MIGRATION_ID}")
            logger.info(f"📁 대상 DB: {self.db_path}")

            # Step 1: 기존 레코드 수 확인
            cursor.execute("SELECT COUNT(*) FROM trades")
            existing_count = cursor.fetchone()[0]
            logger.info(f"📊 기존 거래 레코드 수: {existing_count}개")

            # Step 2: 각 컬럼 추가 (존재하지 않는 경우만)
            columns_to_add = [
                ('region', "TEXT NOT NULL DEFAULT 'KR'"),
                ('entry_price', "REAL"),
                ('exit_price', "REAL"),
                ('entry_timestamp', "TEXT"),
                ('exit_timestamp', "TEXT"),
                ('trade_status', "TEXT DEFAULT 'OPEN'"),
                ('sector', "TEXT"),
                ('position_size_percent', "REAL"),
            ]

            added_columns = []
            skipped_columns = []

            for col_name, col_definition in columns_to_add:
                if self.check_column_exists(cursor, col_name):
                    logger.info(f"⏭️  {col_name} 컬럼이 이미 존재합니다. 스킵")
                    skipped_columns.append(col_name)
                else:
                    logger.info(f"➕ {col_name} 컬럼 추가 중...")
                    cursor.execute(f"""
                        ALTER TABLE trades
                        ADD COLUMN {col_name} {col_definition}
                    """)
                    added_columns.append(col_name)

            if added_columns:
                logger.info(f"✅ {len(added_columns)}개 컬럼 추가 완료: {', '.join(added_columns)}")
            else:
                logger.info("✅ 모든 컬럼이 이미 존재합니다. 마이그레이션 스킵")

            # Step 3: 기존 레코드 업데이트 (NULL 방지)
            if existing_count > 0 and added_columns:
                logger.info("🔄 기존 레코드 기본값 설정 중...")

                # region: 기본값 'KR'로 설정
                if 'region' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET region = 'KR'
                        WHERE region IS NULL
                    """)

                # trade_status: 기본값 'OPEN'으로 설정
                if 'trade_status' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET trade_status = 'OPEN'
                        WHERE trade_status IS NULL
                    """)

                # entry_price: price 값으로 설정 (BUY 거래인 경우)
                if 'entry_price' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET entry_price = price
                        WHERE side = 'BUY' AND entry_price IS NULL
                    """)

                # exit_price: price 값으로 설정 (SELL 거래인 경우)
                if 'exit_price' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET exit_price = price
                        WHERE side = 'SELL' AND exit_price IS NULL
                    """)

                # entry_timestamp: order_time 값으로 설정 (BUY 거래인 경우)
                if 'entry_timestamp' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET entry_timestamp = order_time
                        WHERE side = 'BUY' AND entry_timestamp IS NULL
                    """)

                # exit_timestamp: execution_time 값으로 설정 (SELL 거래인 경우)
                if 'exit_timestamp' in added_columns:
                    cursor.execute("""
                        UPDATE trades
                        SET exit_timestamp = execution_time
                        WHERE side = 'SELL' AND exit_timestamp IS NULL
                    """)

                logger.info("✅ 기존 레코드 기본값 설정 완료")

            # Step 4: 인덱스 생성 (Phase 5)
            logger.info("🔍 Phase 5 인덱스 생성 중...")

            indexes = [
                ("idx_trades_status", "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(trade_status)"),
                ("idx_trades_ticker_region_status", "CREATE INDEX IF NOT EXISTS idx_trades_ticker_region_status ON trades(ticker, region, trade_status)"),
                ("idx_trades_entry_timestamp", "CREATE INDEX IF NOT EXISTS idx_trades_entry_timestamp ON trades(entry_timestamp DESC)"),
                ("idx_trades_exit_timestamp", "CREATE INDEX IF NOT EXISTS idx_trades_exit_timestamp ON trades(exit_timestamp DESC)"),
            ]

            for idx_name, idx_sql in indexes:
                cursor.execute(idx_sql)
                logger.info(f"  ✅ {idx_name} 생성 완료")

            # Step 5: 검증
            logger.info("🔎 마이그레이션 검증 중...")

            # 모든 컬럼 존재 확인
            for col_name, _ in columns_to_add:
                if not self.check_column_exists(cursor, col_name):
                    raise Exception(f"{col_name} 컬럼 추가 실패")

            # region 필드 NULL 값 확인
            cursor.execute("SELECT COUNT(*) FROM trades WHERE region IS NULL")
            null_region_count = cursor.fetchone()[0]
            if null_region_count > 0:
                raise Exception(f"{null_region_count}개 레코드에 region NULL 값 존재")

            # trade_status 필드 NULL 값 확인
            cursor.execute("SELECT COUNT(*) FROM trades WHERE trade_status IS NULL")
            null_status_count = cursor.fetchone()[0]
            if null_status_count > 0:
                raise Exception(f"{null_status_count}개 레코드에 trade_status NULL 값 존재")

            # 인덱스 확인
            for idx_name, _ in indexes:
                cursor.execute(f"""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='{idx_name}'
                """)
                if not cursor.fetchone():
                    raise Exception(f"{idx_name} 인덱스 생성 실패")

            # Commit
            conn.commit()
            logger.info(f"✅ 마이그레이션 {self.MIGRATION_ID} 성공적으로 완료")

            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ 마이그레이션 실패: {e}")
            return False

        finally:
            conn.close()

    def verify(self) -> bool:
        """마이그레이션 결과 검증"""

        if not os.path.exists(self.db_path):
            logger.error(f"❌ 데이터베이스 파일 없음: {self.db_path}")
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            logger.info(f"🔍 마이그레이션 검증: {self.MIGRATION_ID}")

            # 1. 모든 컬럼 존재 확인
            required_columns = [
                'region', 'entry_price', 'exit_price',
                'entry_timestamp', 'exit_timestamp',
                'trade_status', 'sector', 'position_size_percent'
            ]

            cursor.execute("PRAGMA table_info(trades)")
            existing_columns = [col[1] for col in cursor.fetchall()]

            missing_columns = [col for col in required_columns if col not in existing_columns]

            if missing_columns:
                logger.error(f"❌ 누락된 컬럼: {', '.join(missing_columns)}")
                return False

            logger.info("✅ 모든 필수 컬럼 존재 확인")

            # 2. 데이터 분포 확인
            cursor.execute("SELECT COUNT(*) FROM trades")
            total_count = cursor.fetchone()[0]

            if total_count > 0:
                # region 분포
                cursor.execute("SELECT region, COUNT(*) FROM trades GROUP BY region")
                region_stats = cursor.fetchall()
                logger.info(f"📊 region 분포 (총 {total_count}건):")
                for region, count in region_stats:
                    logger.info(f"  - {region}: {count}건 ({count/total_count*100:.1f}%)")

                # trade_status 분포
                cursor.execute("SELECT trade_status, COUNT(*) FROM trades GROUP BY trade_status")
                status_stats = cursor.fetchall()
                logger.info(f"📊 trade_status 분포:")
                for status, count in status_stats:
                    logger.info(f"  - {status}: {count}건 ({count/total_count*100:.1f}%)")

                # NULL 값 확인
                cursor.execute("SELECT COUNT(*) FROM trades WHERE region IS NULL")
                null_region = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM trades WHERE trade_status IS NULL")
                null_status = cursor.fetchone()[0]

                if null_region > 0 or null_status > 0:
                    logger.error(f"❌ NULL 값 존재: region={null_region}, trade_status={null_status}")
                    return False

                logger.info("✅ 필수 필드 NULL 값 없음")

            else:
                logger.info("ℹ️  거래 레코드 없음 (신규 데이터베이스)")

            # 3. 인덱스 존재 확인
            required_indexes = [
                'idx_trades_status',
                'idx_trades_ticker_region_status',
                'idx_trades_entry_timestamp',
                'idx_trades_exit_timestamp'
            ]

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_trades_%'
            """)
            existing_indexes = [row[0] for row in cursor.fetchall()]

            missing_indexes = [idx for idx in required_indexes if idx not in existing_indexes]

            if missing_indexes:
                logger.error(f"❌ 누락된 인덱스: {', '.join(missing_indexes)}")
                return False

            logger.info("✅ 모든 Phase 5 인덱스 존재 확인")

            logger.info("✅ 마이그레이션 검증 완료 - 모든 검사 통과")
            return True

        except Exception as e:
            logger.error(f"❌ 검증 실패: {e}")
            return False

        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migration 005: Add Phase 5 columns to trades table'
    )
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite DB 경로 (기본값: data/spock_local.db)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='마이그레이션 실행 없이 검증만 수행'
    )

    args = parser.parse_args()

    migration = TradesPhase5Migration(db_path=args.db_path)

    if args.verify_only:
        # 검증 모드
        success = migration.verify()
        sys.exit(0 if success else 1)
    else:
        # 마이그레이션 실행
        success = migration.migrate()

        if success:
            # 자동 검증
            logger.info("\n" + "="*60)
            migration.verify()
            logger.info("="*60)

        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
