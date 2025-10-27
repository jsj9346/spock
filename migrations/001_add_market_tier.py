"""
Migration 001: Add market_tier field to tickers table

Purpose:
    Support NXT (Next Exchange) - Korea's new secondary stock market launched in 2024

Changes:
    - Add market_tier column to tickers table
    - Set default value 'MAIN' for backward compatibility
    - Create composite index on (exchange, market_tier)

Allowed market_tier values:
    - 'MAIN': Main market (traditional KOSPI, KOSDAQ)
    - 'NXT': Next Exchange (KOSPI NXT, KOSDAQ NXT)
    - 'KONEX': Korea New Exchange (SME market)

Usage:
    python migrations/001_add_market_tier.py
    python migrations/001_add_market_tier.py --db-path custom.db
    python migrations/001_add_market_tier.py --verify-only
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


class MarketTierMigration:
    """market_tier 필드 추가 마이그레이션"""

    MIGRATION_ID = '001_add_market_tier'
    MIGRATION_DATE = '2024-01-XX'  # 실제 실행일로 업데이트 필요

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

    def check_column_exists(self, cursor) -> bool:
        """market_tier 컬럼 존재 여부 확인"""
        cursor.execute("PRAGMA table_info(tickers)")
        columns = [col[1] for col in cursor.fetchall()]
        return 'market_tier' in columns

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

            # Step 1: 컬럼 존재 여부 확인
            if self.check_column_exists(cursor):
                logger.info("✅ market_tier 컬럼이 이미 존재합니다. 마이그레이션 스킵")
                return True

            # Step 2: 기존 레코드 수 확인
            cursor.execute("SELECT COUNT(*) FROM tickers")
            existing_count = cursor.fetchone()[0]
            logger.info(f"📊 기존 레코드 수: {existing_count}개")

            # Step 3: market_tier 컬럼 추가 (DEFAULT 'MAIN' 포함)
            logger.info("➕ market_tier 컬럼 추가 중...")
            cursor.execute("""
                ALTER TABLE tickers
                ADD COLUMN market_tier TEXT DEFAULT 'MAIN'
            """)

            # Step 4: 기존 레코드 업데이트 (NULL 방지)
            logger.info("🔄 기존 레코드 업데이트 중 (market_tier = 'MAIN')...")
            cursor.execute("""
                UPDATE tickers
                SET market_tier = 'MAIN'
                WHERE market_tier IS NULL
            """)
            updated_rows = cursor.rowcount
            logger.info(f"✅ {updated_rows}개 레코드 업데이트 완료")

            # Step 5: 복합 인덱스 생성
            logger.info("🔍 복합 인덱스 생성 중 (exchange, market_tier)...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickers_exchange_tier
                ON tickers(exchange, market_tier)
            """)

            # Step 6: 검증
            logger.info("🔎 마이그레이션 검증 중...")

            # 컬럼 존재 확인
            if not self.check_column_exists(cursor):
                raise Exception("market_tier 컬럼 추가 실패")

            # NULL 값 확인
            cursor.execute("SELECT COUNT(*) FROM tickers WHERE market_tier IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                raise Exception(f"{null_count}개 레코드에 NULL 값 존재")

            # 인덱스 확인
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_tickers_exchange_tier'
            """)
            if not cursor.fetchone():
                raise Exception("인덱스 생성 실패")

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

            # 1. 컬럼 존재 확인
            if not self.check_column_exists(cursor):
                logger.error("❌ market_tier 컬럼이 존재하지 않습니다")
                return False

            logger.info("✅ market_tier 컬럼 존재 확인")

            # 2. NULL 값 확인
            cursor.execute("SELECT COUNT(*) FROM tickers WHERE market_tier IS NULL")
            null_count = cursor.fetchone()[0]

            if null_count > 0:
                logger.error(f"❌ {null_count}개 레코드에 NULL 값 존재")
                return False

            logger.info("✅ NULL 값 없음")

            # 3. 기본값 'MAIN' 확인
            cursor.execute("SELECT COUNT(*) FROM tickers")
            total_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tickers WHERE market_tier = 'MAIN'")
            main_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tickers WHERE market_tier = 'NXT'")
            nxt_count = cursor.fetchone()[0]

            logger.info(f"📊 market_tier 분포:")
            logger.info(f"  - MAIN: {main_count}개 ({main_count/total_count*100:.1f}%)")
            logger.info(f"  - NXT: {nxt_count}개 ({nxt_count/total_count*100:.1f}% if total_count else 0)")
            logger.info(f"  - 전체: {total_count}개")

            # 4. 인덱스 존재 확인
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_tickers_exchange_tier'
            """)

            if not cursor.fetchone():
                logger.error("❌ 복합 인덱스 idx_tickers_exchange_tier 없음")
                return False

            logger.info("✅ 복합 인덱스 존재 확인")

            # 5. 샘플 쿼리 테스트
            logger.info("🧪 샘플 쿼리 테스트...")

            # 쿼리 1: 특정 거래소의 메인 시장
            cursor.execute("""
                SELECT COUNT(*) FROM tickers
                WHERE exchange = 'KOSPI' AND market_tier = 'MAIN'
            """)
            kospi_main_count = cursor.fetchone()[0]
            logger.info(f"  - KOSPI MAIN: {kospi_main_count}개")

            # 쿼리 2: NXT 시장 전체
            cursor.execute("""
                SELECT COUNT(*) FROM tickers
                WHERE market_tier = 'NXT'
            """)
            all_nxt_count = cursor.fetchone()[0]
            logger.info(f"  - NXT 전체: {all_nxt_count}개")

            logger.info("✅ 마이그레이션 검증 완료 - 모든 검사 통과")
            return True

        except Exception as e:
            logger.error(f"❌ 검증 실패: {e}")
            return False

        finally:
            conn.close()

    def rollback(self) -> bool:
        """마이그레이션 롤백 (개발/테스트 전용)"""

        logger.warning("⚠️  롤백 기능은 개발/테스트 환경에서만 사용하세요")
        logger.warning("⚠️  프로덕션 환경에서는 백업에서 복원하는 것을 권장합니다")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            logger.info(f"🔙 마이그레이션 롤백: {self.MIGRATION_ID}")

            # Step 1: 컬럼 존재 확인
            if not self.check_column_exists(cursor):
                logger.info("✅ market_tier 컬럼이 존재하지 않습니다. 롤백 불필요")
                return True

            # Step 2: 인덱스 삭제
            logger.info("🗑️  인덱스 삭제 중...")
            cursor.execute("DROP INDEX IF EXISTS idx_tickers_exchange_tier")

            # Step 3: 컬럼 삭제
            # SQLite는 ALTER TABLE DROP COLUMN을 지원하지 않음 (3.35.0 이전)
            # 대신 테이블 재생성 방식 사용
            logger.info("🗑️  market_tier 컬럼 삭제 중...")

            # 백업 테이블 생성
            cursor.execute("""
                CREATE TABLE tickers_backup AS
                SELECT
                    ticker, name, name_eng, exchange, region, currency,
                    asset_type, listing_date, is_active, delisting_date,
                    created_at, last_updated, data_source
                FROM tickers
            """)

            # 기존 테이블 삭제
            cursor.execute("DROP TABLE tickers")

            # 백업 테이블 이름 변경
            cursor.execute("ALTER TABLE tickers_backup RENAME TO tickers")

            # 기존 인덱스 재생성 (market_tier 제외)
            cursor.execute("CREATE INDEX idx_tickers_exchange ON tickers(exchange)")
            cursor.execute("CREATE INDEX idx_tickers_asset_type ON tickers(asset_type)")
            cursor.execute("CREATE INDEX idx_tickers_region ON tickers(region)")

            conn.commit()
            logger.info("✅ 롤백 완료")

            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ 롤백 실패: {e}")
            return False

        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migration 001: Add market_tier field for NXT support'
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
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='마이그레이션 롤백 (개발/테스트 전용)'
    )

    args = parser.parse_args()

    migration = MarketTierMigration(db_path=args.db_path)

    if args.rollback:
        # 롤백 모드
        success = migration.rollback()
        sys.exit(0 if success else 1)

    elif args.verify_only:
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
