"""
Spock Trading System - Database Initialization Script

SQLite 데이터베이스 초기화 및 테이블 생성

⚠️  MIGRATION NOTICE: PostgreSQL + TimescaleDB Migration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This SQLite database is LEGACY and maintained for backward compatibility only.

For Quant Investment Platform (production), use PostgreSQL + TimescaleDB:
  Script: scripts/init_postgres_schema.py
  Database: quant_platform
  Host: localhost:5432

PostgreSQL-Specific Enhancements (not available in SQLite):
  1. Hypertables (TimescaleDB): ohlcv_data, factor_scores, exchange_rates, ticker_fundamentals
     - Automatic time-based partitioning (monthly/quarterly chunks)
     - Compression after 90 days - 1 year (10x storage savings)
     - Query optimization for time-series data (10-100x faster)

  2. Continuous Aggregates: ohlcv_monthly, ohlcv_yearly
     - Pre-computed materialized views with automatic refresh
     - Instant monthly/yearly aggregations without scanning raw data

  3. New Tables (PostgreSQL only):
     - exchange_rates: FX exchange rates (hypertable, 90-day compression)
     - fx_signals: FX trading signals (regular table)
     - ticker_fundamentals: Enhanced with region support and hypertable optimization

  4. Performance Benefits:
     - 10-year OHLCV query: <1 second (vs 30+ seconds in SQLite)
     - Unlimited data retention (vs 250-day limit in SQLite)
     - Concurrent reads/writes (vs file-locking in SQLite)

Migration Guide:
  1. Install PostgreSQL + TimescaleDB
  2. Run: python3 scripts/init_postgres_schema.py
  3. Migrate data: python3 scripts/migrate_sqlite_to_postgres.py (if needed)
  4. Update .env: Set POSTGRES_HOST, POSTGRES_DB, etc.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1 테이블 (즉시 사용):
- tickers: 종목 마스터 데이터 (공통 정보)
- stock_details: 주식 전용 정보 (섹터, 산업 등)
- etf_details: ETF 전용 정보 (추종지수, 운용보수 등)
- etfs: ETF 메타데이터
- etf_holdings: ETF 구성 종목 관계
- ticker_fundamentals: 기본 펀더멘털 지표 (시계열)
- ohlcv_data: 일/주/월봉 OHLCV 데이터
- technical_analysis: 기술적 분석 결과
- trades: 거래 내역
- portfolio: 실시간 포지션
- kelly_sizing: 포지션 사이징 계산 (레거시)
- kelly_analysis: Kelly 포지션 사이징 분석 (신규)
- gpt_analysis: GPT 차트 패턴 분석
- market_sentiment: 시장 감정 지표
- global_market_indices: 글로벌 시장 지수
- kis_api_logs: KIS API 호출 로그
- filter_cache_stage0: Stage 0 필터 캐시 (시가총액/거래대금)
- filter_cache_stage1: Stage 1 필터 캐시 (기술적 지표)
- filter_cache_stage2: Stage 2 필터 캐시 (LayeredScoringEngine)
- filter_execution_log: 필터 실행 로그
- risk_limits: 리스크 관리 한도 설정
- circuit_breaker_logs: 서킷 브레이커 트리거 로그
- portfolio_templates: 포트폴리오 템플릿 (리스크 프로파일별)
- asset_class_holdings: 자산 클래스별 보유 현황
- allocation_drift_log: 자산 배분 이탈 로그
- rebalancing_history: 리밸런싱 실행 이력
- rebalancing_orders: 리밸런싱 주문 내역
- exchange_rate_history: 환율 이력 데이터
- migration_history: DB 마이그레이션 이력

Phase 2 테이블 (향후 확장):
- balance_sheet: 재무상태표
- income_statement: 손익계산서
- cash_flow_statement: 현금흐름표
- financial_ratios: 계산된 재무비율

Usage:
    python init_db.py                    # 기본 DB 생성
    python init_db.py --db-path custom.db  # 커스텀 경로
    python init_db.py --reset            # 기존 DB 삭제 후 재생성
    python init_db.py --phase2           # Phase 2 테이블 포함
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


class DatabaseInitializer:
    """SQLite 데이터베이스 초기화"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

    def initialize(self, reset: bool = False, include_phase2: bool = False):
        """
        데이터베이스 초기화

        Args:
            reset: True이면 기존 DB 삭제 후 재생성
            include_phase2: Phase 2 테이블 포함 여부
        """
        # 디렉토리 생성
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Reset 옵션
        if reset and os.path.exists(self.db_path):
            logger.warning(f"🗑️  기존 DB 삭제: {self.db_path}")
            os.remove(self.db_path)

        # DB 연결
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        logger.info(f"📊 데이터베이스 초기화 시작: {self.db_path}")

        # Phase 1 테이블 생성
        logger.info("=== Phase 1 테이블 생성 ===")

        # Core Tables
        self._create_migration_history_table(cursor)
        self._create_tickers_table(cursor)
        self._create_stock_details_table(cursor)
        self._create_etf_details_table(cursor)
        self._create_etf_holdings_tables(cursor)
        self._create_ticker_fundamentals_table(cursor)
        self._create_ohlcv_table(cursor)
        self._create_technical_analysis_table(cursor)

        # Trading & Portfolio Tables
        self._create_trades_table(cursor)
        self._create_portfolio_table(cursor)
        self._create_kelly_sizing_table(cursor)
        self._create_kelly_analysis_table(cursor)
        self._create_gpt_analysis_table(cursor)

        # Market Data Tables
        self._create_global_market_indices_table(cursor)
        self._create_market_sentiment_table(cursor)
        self._create_exchange_rate_history_table(cursor)

        # Filter Cache Tables
        self._create_filter_cache_stage0_table(cursor)
        self._create_filter_cache_stage1_table(cursor)
        self._create_filter_cache_stage2_table(cursor)
        self._create_filter_execution_log_table(cursor)

        # Risk Management Tables
        self._create_risk_limits_table(cursor)
        self._create_circuit_breaker_logs_table(cursor)

        # Portfolio Management Tables
        self._create_portfolio_templates_table(cursor)
        self._create_asset_class_holdings_table(cursor)
        self._create_allocation_drift_log_table(cursor)
        self._create_rebalancing_history_table(cursor)
        self._create_rebalancing_orders_table(cursor)

        # Logging Tables
        self._create_kis_api_logs_table(cursor)

        # Phase 2 테이블 생성 (선택적)
        if include_phase2:
            logger.info("=== Phase 2 테이블 생성 (펀더멘털 분석용) ===")
            self._create_balance_sheet_table(cursor)
            self._create_income_statement_table(cursor)
            self._create_cash_flow_statement_table(cursor)
            self._create_financial_ratios_table(cursor)

        # 인덱스 생성
        self._create_indexes(cursor, include_phase2)

        # 커밋 및 종료
        conn.commit()
        conn.close()

        logger.info(f"✅ 데이터베이스 초기화 완료: {self.db_path}")

    def _create_migration_history_table(self, cursor):
        """마이그레이션 이력 테이블 생성"""
        logger.info("  📝 migration_history 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_version TEXT NOT NULL,           -- 마이그레이션 버전 (예: 20251015_001)
                migration_name TEXT NOT NULL,              -- 마이그레이션 이름
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 실행 시각
            )
        """)

    def _create_tickers_table(self, cursor):
        """종목 마스터 테이블 생성 (정적 정보만)"""
        logger.info("  📋 tickers 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickers (
                -- ========================================
                -- 기본 식별 정보 (Primary Key)
                -- ========================================
                ticker TEXT PRIMARY KEY,              -- 종목코드 (005930, AAPL)

                -- ========================================
                -- 종목 기본 정보 (정적)
                -- ========================================
                name TEXT NOT NULL,                   -- 종목명 (삼성전자)
                name_eng TEXT,                        -- 영문명 (Samsung Electronics)

                exchange TEXT NOT NULL,               -- 거래소 (KOSPI, KOSDAQ, KONEX, NYSE, NASDAQ, AMEX, SEHK, SSE, SZSE, TSE, HOSE, HNX)
                region TEXT NOT NULL,                 -- 국가/지역 (KR, US, HK, JP, CN, VN)
                currency TEXT NOT NULL DEFAULT 'KRW', -- 통화 (KRW, USD, HKD, JPY, CNY, VND)

                asset_type TEXT NOT NULL DEFAULT 'STOCK', -- 자산 유형 (STOCK, ETF, ETN, REIT, PREFERRED)

                listing_date TEXT,                    -- 상장일 (YYYY-MM-DD)

                -- ========================================
                -- 거래 단위 (Lot Size)
                -- ========================================
                lot_size INTEGER DEFAULT 1,           -- 거래 단위 (KR/US: 1주, CN/JP/VN: 100주, HK: 종목별 가변)

                -- ========================================
                -- 섹터 정보 (tickers 테이블에 추가됨)
                -- ========================================
                sector_code TEXT,                     -- 섹터 코드 (GICS 2자리)

                -- ========================================
                -- 관리 정보
                -- ========================================
                is_active BOOLEAN DEFAULT 1,          -- 거래 가능 여부 (1: 가능, 0: 정지/폐지)
                delisting_date TEXT,                  -- 폐지일 (상장폐지 시)

                created_at TEXT NOT NULL,             -- 생성 시각
                last_updated TEXT NOT NULL,           -- 최종 업데이트 시각
                enriched_at TEXT,                     -- 데이터 보강 시각 (섹터/펀더멘털 데이터 추가 시)
                data_source TEXT                      -- 데이터 출처 (KRX Official API, pykrx, KIS Master File)
            )
        """)

    def _create_stock_details_table(self, cursor):
        """주식 전용 정보 테이블 생성 (STOCK, PREFERRED)"""
        logger.info("  📈 stock_details 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_details (
                ticker TEXT PRIMARY KEY,

                -- ========================================
                -- 섹터 및 산업 분류
                -- ========================================
                sector TEXT,                          -- GICS 섹터 (Information Technology, Financials)
                sector_code TEXT,                     -- GICS 섹터 코드 (45, 40)
                industry TEXT,                        -- 산업 분류 (반도체, 자동차, 은행)
                industry_code TEXT,                   -- 산업 코드

                -- ========================================
                -- 주식 특화 정보
                -- ========================================
                is_spac BOOLEAN DEFAULT 0,            -- SPAC 여부
                is_preferred BOOLEAN DEFAULT 0,       -- 우선주 여부
                par_value INTEGER,                    -- 액면가 (원)

                -- ========================================
                -- 메타 정보
                -- ========================================
                region TEXT,                          -- 국가/지역 (KR, US, HK, JP, CN, VN)
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                enriched_at TEXT,                     -- 데이터 보강 시각

                FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
            )
        """)

    def _create_etf_details_table(self, cursor):
        """ETF 전용 정보 테이블 생성"""
        logger.info("  📊 etf_details 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etf_details (
                ticker TEXT PRIMARY KEY,

                -- ========================================
                -- 기본 정보
                -- ========================================
                issuer TEXT,                          -- 운용사 (한국투자신탁운용, BlackRock)
                inception_date TEXT,                  -- 설정일/상장일 (YYYY-MM-DD)
                underlying_asset_class TEXT,          -- 기초자산 분류 (주식, 채권, 원자재, 혼합)

                -- ========================================
                -- 추종 지수 및 분류
                -- ========================================
                tracking_index TEXT NOT NULL,         -- 추종 지수 (KOSPI200, S&P500, Solactive Global Big Pharma Index PR)
                geographic_region TEXT,               -- 투자 지역 (KR, US, CN, VN, EU, GLOBAL)
                sector_theme TEXT,                    -- 섹터/테마 (반도체, 바이오, 2차전지, 금)
                fund_type TEXT,                       -- 펀드 유형 (index, sector, thematic, commodity)

                -- ========================================
                -- 규모 정보
                -- ========================================
                aum BIGINT,                           -- 순자산(AUM) - 운용자산총액 (원/달러)
                listed_shares BIGINT,                 -- 상장주식수
                underlying_asset_count INTEGER,       -- 구성종목수

                -- ========================================
                -- 비용 정보 (중요!)
                -- ========================================
                expense_ratio REAL NOT NULL,          -- 총보수율 (%) - ETF 비교의 핵심 지표
                ter REAL,                             -- TER - Total Expense Ratio (%)

                -- ========================================
                -- 리스크 정보
                -- ========================================
                leverage_ratio TEXT,                  -- 레버리지 배율 (1배, 2배, -1배)
                currency_hedged BOOLEAN,              -- 환헤지 여부 (1: 환헤지, 0: 환노출)

                -- ========================================
                -- 추적 정확도 (괴리율)
                -- ========================================
                tracking_error_20d REAL,              -- 20일 괴리율 평균 (%)
                tracking_error_60d REAL,              -- 60일 괴리율 평균 (%)
                tracking_error_120d REAL,             -- 120일 괴리율 평균 (%)
                tracking_error_250d REAL,             -- 250일 괴리율 평균 (%)

                -- ========================================
                -- 가격 정보
                -- ========================================
                week_52_high INTEGER,                 -- 52주 최고가
                week_52_low INTEGER,                  -- 52주 최저가

                -- ========================================
                -- 기타 정보
                -- ========================================
                pension_eligible BOOLEAN,             -- 연금계좌 투자 가능 여부
                investment_strategy TEXT,             -- 투자전략 설명 (긴 텍스트)

                -- ========================================
                -- 메타 정보
                -- ========================================
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                data_source TEXT DEFAULT 'ETFCheck',  -- 데이터 출처

                FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
            )
        """)

    def _create_etf_holdings_tables(self, cursor):
        """ETF 구성 종목 관계 테이블 생성"""
        logger.info("  🔗 ETF Holdings 테이블 생성 (ETF-Stock Relationship)...")

        # Table 1: etfs (ETF metadata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etfs (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,                   -- ETF 이름
                name_eng TEXT,                        -- ETF 영문명
                region TEXT NOT NULL,                 -- 국가/지역
                exchange TEXT,                        -- 거래소
                category TEXT,                        -- 카테고리
                subcategory TEXT,                     -- 서브카테고리
                tracking_index TEXT,                  -- 추종 지수
                total_assets REAL,                    -- 총 자산
                expense_ratio REAL,                   -- 총보수율
                listed_shares INTEGER,                -- 상장주식수
                issuer TEXT,                          -- 운용사
                inception_date TEXT,                  -- 설정일
                leverage_ratio REAL,                  -- 레버리지 배율
                is_inverse BOOLEAN DEFAULT 0,         -- 인버스 여부
                currency_hedged BOOLEAN DEFAULT 0,    -- 환헤지 여부
                tracking_error_20d REAL,              -- 20일 괴리율
                tracking_error_60d REAL,              -- 60일 괴리율
                tracking_error_120d REAL,             -- 120일 괴리율
                tracking_error_250d REAL,             -- 250일 괴리율
                premium_discount REAL,                -- 프리미엄/디스카운트
                avg_daily_volume REAL,                -- 평균 일거래량
                avg_daily_value REAL,                 -- 평균 일거래대금
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                data_source TEXT,

                FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
            )
        """)

        # Table 2: etf_holdings (Many-to-Many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etf_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                etf_ticker TEXT NOT NULL,             -- ETF 종목코드
                stock_ticker TEXT NOT NULL,           -- 구성 종목코드
                weight REAL NOT NULL,                 -- 비중 (%)
                shares INTEGER,                       -- 보유 주식수
                market_value REAL,                    -- 시가총액
                rank_in_etf INTEGER,                  -- ETF 내 순위
                weight_change_from_prev REAL,         -- 이전 대비 비중 변화
                as_of_date TEXT NOT NULL,             -- 기준일
                created_at TEXT NOT NULL,
                data_source TEXT,

                FOREIGN KEY (etf_ticker) REFERENCES etfs(ticker) ON DELETE CASCADE,
                FOREIGN KEY (stock_ticker) REFERENCES tickers(ticker) ON DELETE CASCADE,

                UNIQUE(etf_ticker, stock_ticker, as_of_date)
            )
        """)

        # Create strategic indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_etfs_region ON etfs(region)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_etfs_category ON etfs(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_etfs_issuer ON etfs(issuer)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_etfs_total_assets ON etfs(total_assets DESC)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_stock_date_weight "
                      "ON etf_holdings(stock_ticker, as_of_date DESC, weight DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_etf_date_weight "
                      "ON etf_holdings(etf_ticker, as_of_date DESC, weight DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_date "
                      "ON etf_holdings(as_of_date DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_weight "
                      "ON etf_holdings(weight DESC)")

        logger.info("    ✓ etfs table created (26 columns)")
        logger.info("    ✓ etf_holdings table created (11 columns)")
        logger.info("    ✓ 8 strategic indexes created")

    def _create_ticker_fundamentals_table(self, cursor):
        """기본 펀더멘털 지표 테이블 생성 (시계열)"""
        logger.info("  📊 ticker_fundamentals 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_fundamentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                date TEXT NOT NULL,                   -- 기준일 (YYYY-MM-DD)
                period_type TEXT NOT NULL,            -- DAILY, QUARTERLY, ANNUAL

                -- ======== 기본 지표 ========
                shares_outstanding BIGINT,            -- 상장주식수
                market_cap BIGINT,                    -- 시가총액 (원/달러 단위)

                close_price REAL,                     -- 종가 (해당일 기준)

                -- ======== 밸류에이션 지표 ========
                per REAL,                             -- Price to Earnings Ratio
                pbr REAL,                             -- Price to Book Ratio
                psr REAL,                             -- Price to Sales Ratio
                pcr REAL,                             -- Price to Cash Flow Ratio

                ev BIGINT,                            -- Enterprise Value (기업가치)
                ev_ebitda REAL,                       -- EV/EBITDA

                -- ======== 배당 지표 ========
                dividend_yield REAL,                  -- 배당수익률 (%)
                dividend_per_share REAL,              -- 주당배당금

                -- ======== 메타 정보 ========
                created_at TEXT NOT NULL,
                data_source TEXT,                     -- KIS API, FnGuide 등

                UNIQUE(ticker, date, period_type),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_ohlcv_table(self, cursor):
        """OHLCV 데이터 테이블 생성"""
        logger.info("  📈 ohlcv_data 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                timeframe TEXT NOT NULL,              -- D, W, M
                date TEXT NOT NULL,                   -- 날짜 (YYYY-MM-DD)
                region TEXT,                          -- 국가/지역 (KR, US, HK, JP, CN, VN)

                -- OHLCV
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume BIGINT NOT NULL,

                -- 기술적 지표 (미리 계산)
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

                atr_14 REAL,                          -- ATR (14일)
                atr REAL,                             -- ATR (범용)

                -- 거래량 분석
                volume_ma20 REAL,                     -- 거래량 20일 이동평균
                volume_ratio REAL,                    -- 거래량 비율 (당일/20일평균)

                -- 메타 정보
                created_at TEXT NOT NULL,

                UNIQUE(ticker, region, timeframe, date),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_technical_analysis_table(self, cursor):
        """기술적 분석 결과 테이블 생성"""
        logger.info("  🔍 technical_analysis 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technical_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                analysis_date TEXT NOT NULL,

                -- Weinstein Stage Analysis
                stage INTEGER,                        -- 1, 2, 3, 4
                stage_confidence REAL,                -- 신뢰도 (0~1)

                -- LayeredScoringEngine (100점 만점)
                layer1_macro_score REAL,
                layer2_structural_score REAL,
                layer3_micro_score REAL,
                total_score REAL,

                -- 신호
                signal TEXT,                          -- BUY, WATCH, AVOID
                signal_strength REAL,

                -- GPT-4 분석 (선택적)
                gpt_pattern TEXT,
                gpt_confidence REAL,
                gpt_analysis TEXT,

                created_at TEXT NOT NULL,

                UNIQUE(ticker, analysis_date),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_trades_table(self, cursor):
        """거래 내역 테이블 생성"""
        logger.info("  💰 trades 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ========================================
                -- 기본 거래 정보
                -- ========================================
                ticker TEXT NOT NULL,
                region TEXT NOT NULL DEFAULT 'KR',    -- 국가/지역

                side TEXT NOT NULL,                   -- BUY, SELL
                order_type TEXT NOT NULL,             -- MARKET, LIMIT

                quantity INTEGER NOT NULL,

                -- 가격 정보
                entry_price REAL,                     -- 매수 진입가
                exit_price REAL,                      -- 매도 청산가
                price REAL NOT NULL,                  -- 실제 체결가 (하위 호환성 유지)

                amount REAL NOT NULL,                 -- 거래 금액

                fee REAL DEFAULT 0,
                tax REAL DEFAULT 0,

                order_no TEXT,
                execution_no TEXT,

                -- ========================================
                -- 진입/청산 시각
                -- ========================================
                entry_timestamp TEXT,                 -- 매수 시각 (YYYY-MM-DD HH:MM:SS)
                exit_timestamp TEXT,                  -- 매도 시각

                order_time TEXT NOT NULL,             -- 주문 시각 (하위 호환성)
                execution_time TEXT,                  -- 체결 시각 (하위 호환성)

                -- ========================================
                -- 포지션 관리
                -- ========================================
                trade_status TEXT DEFAULT 'OPEN',     -- OPEN, CLOSED
                sector TEXT,                          -- 섹터 정보 (포지션 리밋용)
                position_size_percent REAL,           -- 포트폴리오 대비 비중 (%)

                -- ========================================
                -- 거래 이유 및 메타데이터
                -- ========================================
                reason TEXT,                          -- 거래 사유 (Stage 2 Breakout, Stop Loss 등)

                created_at TEXT NOT NULL,

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_portfolio_table(self, cursor):
        """포트폴리오 테이블 생성"""
        logger.info("  💼 portfolio 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                ticker TEXT PRIMARY KEY,

                quantity INTEGER NOT NULL,            -- 보유 수량
                avg_price REAL NOT NULL,              -- 평균 단가
                current_price REAL,                   -- 현재가

                market_value REAL,                    -- 평가 금액
                unrealized_pnl REAL,                  -- 미실현 손익 (금액)
                unrealized_pnl_pct REAL,              -- 미실현 손익률 (%)

                stop_loss_price REAL,                 -- 손절가
                profit_target_price REAL,             -- 목표가

                entry_date TEXT NOT NULL,             -- 진입일
                entry_score REAL,                     -- 진입 당시 점수

                last_updated TEXT NOT NULL,

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_kelly_sizing_table(self, cursor):
        """Kelly 포지션 사이징 테이블 생성 (레거시)"""
        logger.info("  📊 kelly_sizing 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kelly_sizing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                calculation_date TEXT NOT NULL,

                pattern_type TEXT,                    -- 패턴 유형 (Stage 2, VCP, Cup & Handle 등)

                win_rate REAL NOT NULL,               -- 승률
                avg_win_loss REAL NOT NULL,           -- 평균 수익/손실 비율

                kelly_pct REAL NOT NULL,              -- Kelly % (Full Kelly)
                half_kelly_pct REAL NOT NULL,         -- Half Kelly %

                recommended_position_size REAL,       -- 권장 포지션 크기 (금액)
                recommended_quantity INTEGER,         -- 권장 수량

                max_position_pct REAL,                -- 최대 포지션 비율
                max_sector_pct REAL,                  -- 최대 섹터 비율

                created_at TEXT NOT NULL,

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_kelly_analysis_table(self, cursor):
        """Kelly 포지션 사이징 분석 테이블 생성 (신규)"""
        logger.info("  🎯 kelly_analysis 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kelly_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                analysis_date TEXT NOT NULL,          -- 분석 일자

                detected_pattern TEXT NOT NULL,       -- 감지된 패턴 (VCP, Cup & Handle, Stage 2 등)
                quality_score REAL NOT NULL,          -- 패턴 품질 점수 (0~1)

                base_position_pct REAL NOT NULL,      -- 기본 포지션 비율 (패턴별)
                quality_multiplier REAL NOT NULL,     -- 품질 승수 (0.5~1.5)
                technical_position_pct REAL NOT NULL, -- 기술적 포지션 비율 (base × quality)

                gpt_confidence REAL,                  -- GPT 신뢰도 (0~1)
                gpt_recommendation TEXT,              -- GPT 추천 (INCREASE, NEUTRAL, DECREASE)
                gpt_adjustment REAL,                  -- GPT 조정값 (-0.3 ~ +0.3)

                final_position_pct REAL NOT NULL,     -- 최종 포지션 비율
                risk_level TEXT,                      -- 리스크 레벨 (LOW, MEDIUM, HIGH)
                max_portfolio_allocation REAL,        -- 최대 포트폴리오 배분

                reasoning TEXT,                       -- 포지션 사이징 근거

                created_at TEXT,

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_gpt_analysis_table(self, cursor):
        """GPT 차트 패턴 분석 테이블 생성"""
        logger.info("  🤖 gpt_analysis 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gpt_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                analysis_date TEXT NOT NULL,

                -- ========================================
                -- VCP (Volatility Contraction Pattern)
                -- ========================================
                vcp_detected BOOLEAN,                 -- VCP 감지 여부
                vcp_confidence REAL,                  -- VCP 신뢰도 (0~1)
                vcp_stage INTEGER,                    -- VCP 단계 (1, 2, 3)
                vcp_volatility_ratio REAL,            -- 변동성 축소 비율
                vcp_reasoning TEXT,                   -- VCP 근거

                -- ========================================
                -- Cup & Handle
                -- ========================================
                cup_handle_detected BOOLEAN,          -- Cup & Handle 감지 여부
                cup_handle_confidence REAL,           -- Cup & Handle 신뢰도
                cup_depth_ratio REAL,                 -- 컵 깊이 비율
                handle_duration_days INTEGER,         -- 손잡이 기간 (일)
                cup_handle_reasoning TEXT,            -- Cup & Handle 근거

                -- ========================================
                -- GPT 종합 분석
                -- ========================================
                gpt_recommendation TEXT,              -- GPT 추천 (BUY, WATCH, AVOID)
                gpt_confidence REAL,                  -- GPT 신뢰도
                gpt_reasoning TEXT,                   -- GPT 근거

                api_cost_usd REAL,                    -- API 비용 (USD)
                processing_time_ms INTEGER,           -- 처리 시간 (밀리초)

                created_at TEXT,

                -- ========================================
                -- Stage 2 확인 (Weinstein)
                -- ========================================
                stage2_confirmed BOOLEAN,             -- Stage 2 확인 여부
                stage2_confidence REAL,               -- Stage 2 신뢰도
                stage2_ma_alignment BOOLEAN,          -- MA 정렬 확인
                stage2_volume_surge BOOLEAN,          -- 거래량 급증 확인
                stage2_reasoning TEXT,                -- Stage 2 근거

                position_adjustment REAL,             -- 포지션 조정 (±0.3)

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_global_market_indices_table(self, cursor):
        """글로벌 시장 지수 테이블 생성 (S&P 500, NASDAQ, DOW, Hang Seng, Nikkei)"""
        logger.info("  🌐 global_market_indices 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_market_indices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date TEXT NOT NULL,
                symbol TEXT NOT NULL,                 -- 지수 심볼 (^GSPC, ^IXIC, ^DJI, ^HSI, ^N225)
                index_name TEXT NOT NULL,             -- 지수 이름
                region TEXT NOT NULL,                 -- 국가/지역

                close_price REAL NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                volume BIGINT,

                change_percent REAL NOT NULL,         -- 변동률 (%)
                trend_5d TEXT,                        -- 5일 추세 (UP, DOWN, SIDEWAYS)
                consecutive_days INTEGER,             -- 연속 상승/하락 일수

                created_at TEXT NOT NULL,

                UNIQUE(date, symbol)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_global_indices_date
            ON global_market_indices(date DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_global_indices_symbol
            ON global_market_indices(symbol, date DESC)
        """)

    def _create_market_sentiment_table(self, cursor):
        """시장 감정 지표 테이블 생성"""
        logger.info("  📉 market_sentiment 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_sentiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date TEXT NOT NULL UNIQUE,

                vix REAL,                             -- VIX 지수
                fear_greed_index REAL,                -- Fear & Greed Index

                kospi_index REAL,                     -- KOSPI 지수
                kosdaq_index REAL,                    -- KOSDAQ 지수

                foreign_net_buying BIGINT,            -- 외국인 순매수 (원)
                institution_net_buying BIGINT,        -- 기관 순매수 (원)

                usd_krw REAL,                         -- USD/KRW 환율
                jpy_krw REAL,                         -- JPY/KRW 환율

                oil_price REAL,                       -- 유가 (WTI)
                gold_price REAL,                      -- 금 가격

                market_regime TEXT,                   -- 시장 국면 (bull, sideways, bear)
                sentiment_score REAL,                 -- 감정 점수 (0~100)

                created_at TEXT NOT NULL
            )
        """)

    def _create_exchange_rate_history_table(self, cursor):
        """환율 이력 데이터 테이블 생성"""
        logger.info("  💱 exchange_rate_history 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                currency TEXT NOT NULL,               -- 통화 쌍 (USD_KRW, HKD_KRW, JPY_KRW, CNY_KRW, VND_KRW)
                rate REAL NOT NULL,                   -- 환율
                timestamp TEXT NOT NULL,              -- 조회 시각
                rate_date TEXT NOT NULL,              -- 환율 기준일 (YYYY-MM-DD)

                source TEXT,                          -- 데이터 출처 (KIS API, ExchangeRate-API)

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_rate_currency_date
            ON exchange_rate_history(currency, rate_date DESC)
        """)

    def _create_filter_cache_stage0_table(self, cursor):
        """Stage 0 필터 캐시 테이블 생성 (시가총액/거래대금 필터)"""
        logger.info("  🔍 filter_cache_stage0 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT NOT NULL,
                exchange TEXT,

                -- ========================================
                -- KRW 환산 값 (비교 기준)
                -- ========================================
                market_cap_krw BIGINT,                -- 시가총액 (원)
                trading_value_krw BIGINT,             -- 거래대금 (원)
                current_price_krw INTEGER,            -- 현재가 (원)

                -- ========================================
                -- 로컬 통화 값 (원본)
                -- ========================================
                market_cap_local REAL,                -- 시가총액 (로컬 통화)
                trading_value_local REAL,             -- 거래대금 (로컬 통화)
                current_price_local REAL,             -- 현재가 (로컬 통화)

                currency TEXT NOT NULL,               -- 통화 (KRW, USD, HKD, JPY, CNY, VND)

                -- ========================================
                -- 환율 정보
                -- ========================================
                exchange_rate_to_krw REAL,            -- KRW 환산율
                exchange_rate_date DATE,              -- 환율 기준일
                exchange_rate_source TEXT,            -- 환율 출처

                -- ========================================
                -- 필터링 정보
                -- ========================================
                market_warn_code TEXT,                -- 시장 경고 코드 (관리종목, 투자주의 등)
                is_stock_connect BOOLEAN,             -- 선강통/후강통 여부 (중국)
                is_otc BOOLEAN,                       -- OTC 여부
                is_delisting BOOLEAN,                 -- 상장폐지 예정 여부

                filter_date DATE NOT NULL,            -- 필터링 실행 일자
                stage0_passed BOOLEAN,                -- Stage 0 통과 여부
                filter_reason TEXT,                   -- 필터링 사유

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(ticker, region, filter_date)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stage0_region_date
            ON filter_cache_stage0(region, filter_date DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stage0_market_cap_krw
            ON filter_cache_stage0(market_cap_krw DESC)
        """)

    def _create_filter_cache_stage1_table(self, cursor):
        """Stage 1 필터 캐시 테이블 생성 (기술적 지표 필터)"""
        logger.info("  📊 filter_cache_stage1 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,

                -- ========================================
                -- 기술적 지표 (KRW 환산)
                -- ========================================
                ma5 REAL,                             -- 5일 이동평균
                ma20 REAL,                            -- 20일 이동평균
                ma60 REAL,                            -- 60일 이동평균
                rsi_14 REAL,                          -- RSI (14일)

                current_price_krw INTEGER,            -- 현재가 (원)
                week_52_high_krw INTEGER,             -- 52주 최고가 (원)

                -- ========================================
                -- 거래량 분석
                -- ========================================
                volume_3d_avg BIGINT,                 -- 3일 평균 거래량
                volume_10d_avg BIGINT,                -- 10일 평균 거래량

                -- ========================================
                -- 필터링 정보
                -- ========================================
                filter_date DATE NOT NULL,            -- 필터링 실행 일자

                data_start_date DATE,                 -- 데이터 시작일
                data_end_date DATE,                   -- 데이터 종료일

                stage1_passed BOOLEAN,                -- Stage 1 통과 여부
                filter_reason TEXT,                   -- 필터링 사유

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(ticker, region, filter_date)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stage1_region_date
            ON filter_cache_stage1(region, filter_date DESC)
        """)

    def _create_filter_cache_stage2_table(self, cursor):
        """Stage 2 Scoring 캐시 테이블 생성 (LayeredScoringEngine 결과 저장)"""
        logger.info("  🎯 filter_cache_stage2 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ========================================
                -- 기본 식별 정보
                -- ========================================
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,

                -- ========================================
                -- 총점 (100점 만점)
                -- ========================================
                total_score INTEGER NOT NULL,

                -- ========================================
                -- Layer 1: Macro Analysis (25 points)
                -- ========================================
                market_regime_score INTEGER,          -- MarketRegimeModule (5 pts)
                volume_profile_score INTEGER,         -- VolumeProfileModule (10 pts)
                price_action_score INTEGER,           -- PriceActionModule (10 pts)

                -- ========================================
                -- Layer 2: Structural Analysis (45 points)
                -- ========================================
                stage_analysis_score INTEGER,         -- StageAnalysisModule (15 pts)
                moving_average_score INTEGER,         -- MovingAverageModule (15 pts)
                relative_strength_score INTEGER,      -- RelativeStrengthModule (15 pts)

                -- ========================================
                -- Layer 3: Micro Analysis (30 points)
                -- ========================================
                pattern_recognition_score INTEGER,    -- PatternRecognitionModule (10 pts)
                volume_spike_score INTEGER,           -- VolumeSpikeModule (10 pts)
                momentum_score INTEGER,               -- MomentumModule (10 pts)

                -- ========================================
                -- Recommendation (추천)
                -- ========================================
                recommendation TEXT NOT NULL,         -- BUY, WATCH, AVOID

                -- ========================================
                -- Adaptive Context (시장 상황)
                -- ========================================
                market_regime TEXT,                   -- bull/sideways/bear
                volatility_regime TEXT,               -- low/medium/high

                -- ========================================
                -- Pattern Detection (패턴 감지)
                -- ========================================
                detected_pattern TEXT,                -- 감지된 패턴 (VCP, Cup & Handle, Stage 2 등)
                pattern_confidence REAL,              -- 패턴 신뢰도 (0~1)

                -- ========================================
                -- Detailed Explanations (JSON)
                -- ========================================
                score_explanations TEXT,              -- 각 모듈별 점수 설명 (JSON)

                -- ========================================
                -- Performance Metadata
                -- ========================================
                execution_time_ms INTEGER,            -- 실행 시간 (밀리초)

                -- ========================================
                -- Cache Metadata
                -- ========================================
                cache_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 캐시 타임스탬프
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- ========================================
                -- Constraints
                -- ========================================
                UNIQUE(ticker, region, cache_timestamp)
            )
        """)

    def _create_filter_execution_log_table(self, cursor):
        """필터 실행 로그 테이블 생성"""
        logger.info("  📝 filter_execution_log 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                execution_date DATE NOT NULL,         -- 실행 일자
                region TEXT NOT NULL,                 -- 국가/지역

                stage INTEGER NOT NULL,               -- 필터 단계 (0, 1, 2)
                input_count INTEGER,                  -- 입력 종목 수
                output_count INTEGER,                 -- 출력 종목 수
                reduction_rate REAL,                  -- 감소율 (%)

                execution_time_sec REAL,              -- 실행 시간 (초)
                api_calls INTEGER,                    -- API 호출 횟수
                error_count INTEGER,                  -- 에러 발생 횟수

                -- ========================================
                -- Stage 0 전용 통계
                -- ========================================
                total_market_cap_krw BIGINT,          -- 총 시가총액 (원)
                avg_trading_value_krw BIGINT,         -- 평균 거래대금 (원)

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(execution_date, region, stage)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filter_log_date
            ON filter_execution_log(execution_date DESC)
        """)

    def _create_risk_limits_table(self, cursor):
        """리스크 관리 한도 설정 테이블 생성"""
        logger.info("  🛡️ risk_limits 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ========================================
                -- 리스크 한도 설정
                -- ========================================
                daily_loss_limit_percent REAL NOT NULL DEFAULT -3.0,    -- 일일 손실 한도 (%)
                stop_loss_percent REAL NOT NULL DEFAULT -8.0,           -- 개별 포지션 손절 (%)
                take_profit_percent REAL NOT NULL DEFAULT 20.0,         -- 익절 목표 (%)

                max_positions INTEGER NOT NULL DEFAULT 10,              -- 최대 동시 보유 종목 수
                max_sector_exposure_percent REAL NOT NULL DEFAULT 40.0, -- 섹터 집중 한도 (%)

                consecutive_loss_threshold INTEGER NOT NULL DEFAULT 3,  -- 연속 손실 허용 횟수

                -- ========================================
                -- 메타 정보
                -- ========================================
                risk_profile TEXT NOT NULL DEFAULT 'MODERATE',  -- CONSERVATIVE, MODERATE, AGGRESSIVE
                effective_from TEXT NOT NULL,                   -- 적용 시작일 (YYYY-MM-DD)
                effective_to TEXT,                              -- 적용 종료일 (NULL: 현재 설정)

                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system'
            )
        """)

    def _create_circuit_breaker_logs_table(self, cursor):
        """서킷 브레이커 트리거 로그 테이블 생성"""
        logger.info("  🚨 circuit_breaker_logs 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circuit_breaker_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- ========================================
                -- 서킷 브레이커 정보
                -- ========================================
                breaker_type TEXT NOT NULL,           -- DAILY_LOSS_LIMIT, POSITION_COUNT_LIMIT,
                                                      -- SECTOR_EXPOSURE_LIMIT, CONSECUTIVE_LOSSES

                trigger_value REAL NOT NULL,          -- 트리거된 값
                limit_value REAL NOT NULL,            -- 한도 값

                trigger_reason TEXT NOT NULL,         -- 트리거 사유 (상세 설명)

                -- ========================================
                -- 메타데이터 (JSON 형식)
                -- ========================================
                metadata TEXT,                        -- 추가 정보 (JSON string)
                                                      -- 예: {"daily_pnl": -350000, "portfolio_value": 10000000}

                -- ========================================
                -- 시각 정보
                -- ========================================
                timestamp TEXT NOT NULL,              -- 트리거 발생 시각 (YYYY-MM-DD HH:MM:SS)

                -- ========================================
                -- 조치 정보
                -- ========================================
                action_taken TEXT,                    -- 취한 조치 (TRADING_HALTED, MANUAL_REVIEW, etc.)
                resolved_at TEXT,                     -- 해제 시각
                resolved_by TEXT,                     -- 해제 주체 (system, manual)

                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

    def _create_portfolio_templates_table(self, cursor):
        """포트폴리오 템플릿 테이블 생성 (리스크 프로파일별)"""
        logger.info("  📋 portfolio_templates 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,

                template_name TEXT NOT NULL UNIQUE,   -- 템플릿 이름 (CONSERVATIVE, MODERATE, AGGRESSIVE)
                template_name_kr TEXT,                -- 템플릿 이름 (한글)
                risk_level TEXT NOT NULL,             -- 리스크 레벨 (LOW, MEDIUM, HIGH)
                description TEXT,                     -- 템플릿 설명

                -- ========================================
                -- 자산 배분 목표 (%)
                -- ========================================
                bonds_etf_target_percent REAL,        -- 채권 ETF 목표 비중
                commodities_etf_target_percent REAL,  -- 원자재 ETF 목표 비중
                dividend_stocks_target_percent REAL,  -- 배당주 목표 비중
                individual_stocks_target_percent REAL,-- 개별 종목 목표 비중
                cash_target_percent REAL,             -- 현금 목표 비중

                -- ========================================
                -- 리밸런싱 설정
                -- ========================================
                rebalancing_method TEXT,              -- 리밸런싱 방법 (DRIFT, PERIODIC, HYBRID)
                drift_threshold_percent REAL,         -- 이탈 임계값 (%)
                periodic_interval_days INTEGER,       -- 주기적 리밸런싱 간격 (일)
                min_rebalance_interval_days INTEGER,  -- 최소 리밸런싱 간격 (일)

                -- ========================================
                -- 거래 제약 조건
                -- ========================================
                max_trade_size_percent REAL,          -- 최대 거래 규모 (%)
                max_single_position_percent REAL,     -- 최대 단일 포지션 비중 (%)
                max_sector_exposure_percent REAL,     -- 최대 섹터 노출 비중 (%)
                min_cash_reserve_percent REAL,        -- 최소 현금 보유 비중 (%)
                max_concurrent_positions INTEGER,     -- 최대 동시 보유 종목 수

                -- ========================================
                -- 메타 정보
                -- ========================================
                is_active BOOLEAN DEFAULT 1,          -- 활성화 여부
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_asset_class_holdings_table(self, cursor):
        """자산 클래스별 보유 현황 테이블 생성"""
        logger.info("  💼 asset_class_holdings 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_class_holdings (
                holding_id INTEGER PRIMARY KEY AUTOINCREMENT,

                template_name TEXT NOT NULL,          -- 템플릿 이름
                asset_class TEXT NOT NULL,            -- 자산 클래스 (BONDS_ETF, COMMODITIES_ETF, DIVIDEND_STOCKS, INDIVIDUAL_STOCKS, CASH)

                ticker TEXT NOT NULL,                 -- 종목 코드
                region TEXT,                          -- 국가/지역
                category TEXT,                        -- 카테고리 (ETF, STOCK, CASH)

                quantity REAL NOT NULL,               -- 보유 수량
                avg_entry_price REAL NOT NULL,        -- 평균 진입가
                current_price REAL NOT NULL,          -- 현재가
                market_value REAL NOT NULL,           -- 평가 금액

                target_allocation_percent REAL,       -- 목표 배분 비중 (%)
                current_allocation_percent REAL,      -- 현재 배분 비중 (%)
                drift_percent REAL,                   -- 이탈 비중 (%)

                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name) ON DELETE CASCADE
            )
        """)

    def _create_allocation_drift_log_table(self, cursor):
        """자산 배분 이탈 로그 테이블 생성"""
        logger.info("  📊 allocation_drift_log 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allocation_drift_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,

                template_name TEXT NOT NULL,          -- 템플릿 이름
                asset_class TEXT NOT NULL,            -- 자산 클래스

                target_percent REAL NOT NULL,         -- 목표 비중 (%)
                current_percent REAL NOT NULL,        -- 현재 비중 (%)
                drift_percent REAL NOT NULL,          -- 이탈 비중 (%)

                alert_level TEXT,                     -- 경고 레벨 (INFO, WARNING, CRITICAL)
                rebalancing_needed BOOLEAN,           -- 리밸런싱 필요 여부

                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name) ON DELETE CASCADE
            )
        """)

    def _create_rebalancing_history_table(self, cursor):
        """리밸런싱 실행 이력 테이블 생성"""
        logger.info("  🔄 rebalancing_history 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rebalancing_history (
                rebalance_id INTEGER PRIMARY KEY AUTOINCREMENT,

                template_name TEXT NOT NULL,          -- 템플릿 이름

                -- ========================================
                -- 트리거 정보
                -- ========================================
                trigger_type TEXT NOT NULL,           -- 트리거 유형 (DRIFT, PERIODIC, MANUAL)
                trigger_reason TEXT,                  -- 트리거 사유
                max_drift_percent REAL,               -- 최대 이탈 비중

                -- ========================================
                -- 리밸런싱 전 상태
                -- ========================================
                pre_cash_krw REAL,                    -- 리밸런싱 전 현금 (원)
                pre_invested_krw REAL,                -- 리밸런싱 전 투자 금액 (원)
                pre_total_value_krw REAL,             -- 리밸런싱 전 총 자산 (원)
                pre_allocation_json TEXT,             -- 리밸런싱 전 배분 (JSON)

                -- ========================================
                -- 리밸런싱 후 상태
                -- ========================================
                post_cash_krw REAL,                   -- 리밸런싱 후 현금 (원)
                post_invested_krw REAL,               -- 리밸런싱 후 투자 금액 (원)
                post_total_value_krw REAL,            -- 리밸런싱 후 총 자산 (원)
                post_allocation_json TEXT,            -- 리밸런싱 후 배분 (JSON)

                -- ========================================
                -- 실행 결과
                -- ========================================
                orders_generated INTEGER,             -- 생성된 주문 수
                orders_executed INTEGER,              -- 실행된 주문 수
                total_value_traded_krw REAL,          -- 총 거래 금액 (원)
                transaction_costs_krw REAL,           -- 거래 비용 (원)

                status TEXT,                          -- 상태 (COMPLETED, PARTIAL, FAILED)
                error_message TEXT,                   -- 에러 메시지

                -- ========================================
                -- 실행 시간
                -- ========================================
                execution_start_time TIMESTAMP,       -- 실행 시작 시각
                execution_end_time TIMESTAMP,         -- 실행 종료 시각

                FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name) ON DELETE CASCADE
            )
        """)

    def _create_rebalancing_orders_table(self, cursor):
        """리밸런싱 주문 내역 테이블 생성"""
        logger.info("  📝 rebalancing_orders 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rebalancing_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,

                rebalance_id INTEGER NOT NULL,        -- 리밸런싱 ID

                ticker TEXT NOT NULL,                 -- 종목 코드
                region TEXT,                          -- 국가/지역
                asset_class TEXT NOT NULL,            -- 자산 클래스

                side TEXT NOT NULL,                   -- 매수/매도 (BUY, SELL)

                -- ========================================
                -- 목표 조정 값
                -- ========================================
                target_value_krw REAL NOT NULL,       -- 목표 금액 (원)
                current_value_krw REAL NOT NULL,      -- 현재 금액 (원)
                delta_value_krw REAL NOT NULL,        -- 차액 (원)

                -- ========================================
                -- 주문 정보
                -- ========================================
                quantity REAL,                        -- 주문 수량
                order_price REAL,                     -- 주문 가격
                executed_price REAL,                  -- 체결 가격
                executed_quantity REAL,               -- 체결 수량
                execution_fee_krw REAL,               -- 수수료 (원)

                status TEXT,                          -- 주문 상태 (PENDING, EXECUTED, FAILED, CANCELLED)
                error_message TEXT,                   -- 에러 메시지

                -- ========================================
                -- 실행 시간
                -- ========================================
                order_time TIMESTAMP,                 -- 주문 시각
                execution_time TIMESTAMP,             -- 체결 시각

                FOREIGN KEY (rebalance_id) REFERENCES rebalancing_history(rebalance_id) ON DELETE CASCADE
            )
        """)

    def _create_kis_api_logs_table(self, cursor):
        """KIS API 호출 로그 테이블 생성"""
        logger.info("  📝 kis_api_logs 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kis_api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT NOT NULL,              -- 호출 시각

                endpoint TEXT NOT NULL,               -- API 엔드포인트
                method TEXT NOT NULL,                 -- HTTP 메서드 (GET, POST)
                tr_id TEXT,                           -- TR ID (거래 고유 번호)

                status_code INTEGER,                  -- HTTP 상태 코드
                rt_cd TEXT,                           -- 응답 코드 (0: 성공, 그 외: 실패)
                msg_cd TEXT,                          -- 메시지 코드
                msg1 TEXT,                            -- 응답 메시지

                response_time REAL,                   -- 응답 시간 (초)

                error_message TEXT,                   -- 에러 메시지

                created_at TEXT NOT NULL
            )
        """)

    def _create_balance_sheet_table(self, cursor):
        """재무상태표 테이블 생성 (Phase 2)"""
        logger.info("  💼 balance_sheet 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                fiscal_date TEXT NOT NULL,            -- 회계 기준일
                period_type TEXT NOT NULL,            -- QUARTERLY, ANNUAL
                report_type TEXT NOT NULL,            -- CONSOLIDATED, SEPARATE

                -- 자산
                total_assets BIGINT,                  -- 총 자산
                current_assets BIGINT,                -- 유동 자산
                non_current_assets BIGINT,            -- 비유동 자산
                cash_and_equivalents BIGINT,          -- 현금 및 현금성 자산
                accounts_receivable BIGINT,           -- 매출채권
                inventories BIGINT,                   -- 재고 자산

                -- 부채
                total_liabilities BIGINT,             -- 총 부채
                current_liabilities BIGINT,           -- 유동 부채
                non_current_liabilities BIGINT,       -- 비유동 부채
                short_term_debt BIGINT,               -- 단기 차입금
                long_term_debt BIGINT,                -- 장기 차입금

                -- 자본
                total_equity BIGINT,                  -- 총 자본
                paid_in_capital BIGINT,               -- 납입 자본금
                retained_earnings BIGINT,             -- 이익 잉여금

                created_at TEXT NOT NULL,
                data_source TEXT,

                UNIQUE(ticker, fiscal_date, period_type, report_type),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_income_statement_table(self, cursor):
        """손익계산서 테이블 생성 (Phase 2)"""
        logger.info("  💵 income_statement 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS income_statement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                fiscal_date TEXT NOT NULL,
                period_type TEXT NOT NULL,
                report_type TEXT NOT NULL,

                revenue BIGINT,                       -- 매출액
                cost_of_revenue BIGINT,               -- 매출 원가
                gross_profit BIGINT,                  -- 매출 총이익

                operating_expenses BIGINT,            -- 영업 비용
                operating_income BIGINT,              -- 영업 이익

                income_before_tax BIGINT,             -- 세전 이익
                income_tax BIGINT,                    -- 법인세
                net_income BIGINT,                    -- 순이익

                eps REAL,                             -- 주당 순이익 (EPS)
                diluted_eps REAL,                     -- 희석 주당 순이익

                created_at TEXT NOT NULL,
                data_source TEXT,

                UNIQUE(ticker, fiscal_date, period_type, report_type),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_cash_flow_statement_table(self, cursor):
        """현금흐름표 테이블 생성 (Phase 2)"""
        logger.info("  💸 cash_flow_statement 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_flow_statement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                fiscal_date TEXT NOT NULL,
                period_type TEXT NOT NULL,
                report_type TEXT NOT NULL,

                operating_cash_flow BIGINT,           -- 영업 활동 현금 흐름
                investing_cash_flow BIGINT,           -- 투자 활동 현금 흐름
                financing_cash_flow BIGINT,           -- 재무 활동 현금 흐름

                capex BIGINT,                         -- 자본 지출 (CAPEX)
                dividends_paid BIGINT,                -- 배당금 지급

                net_change_in_cash BIGINT,            -- 현금 순증감
                free_cash_flow BIGINT,                -- 잉여 현금 흐름 (FCF)

                created_at TEXT NOT NULL,
                data_source TEXT,

                UNIQUE(ticker, fiscal_date, period_type, report_type),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_financial_ratios_table(self, cursor):
        """재무비율 테이블 생성 (Phase 2)"""
        logger.info("  📊 financial_ratios 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_ratios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                fiscal_date TEXT NOT NULL,
                period_type TEXT NOT NULL,

                -- 수익성
                roe REAL,                             -- 자기자본이익률 (ROE)
                roa REAL,                             -- 총자산이익률 (ROA)
                gross_profit_margin REAL,             -- 매출 총이익률
                operating_profit_margin REAL,         -- 영업 이익률
                net_profit_margin REAL,               -- 순이익률

                -- 성장성
                revenue_growth_qoq REAL,              -- 매출 성장률 (분기)
                revenue_growth_yoy REAL,              -- 매출 성장률 (연간)
                net_income_growth_yoy REAL,           -- 순이익 성장률 (연간)

                -- 안정성
                debt_to_equity REAL,                  -- 부채비율
                current_ratio REAL,                   -- 유동비율
                quick_ratio REAL,                     -- 당좌비율

                -- 활동성
                asset_turnover REAL,                  -- 총자산 회전율

                -- 현금흐름
                free_cash_flow_yield REAL,            -- 잉여 현금 흐름 수익률

                created_at TEXT NOT NULL,

                UNIQUE(ticker, fiscal_date, period_type),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

    def _create_indexes(self, cursor, include_phase2: bool = False):
        """인덱스 생성 (조회 성능 최적화)"""
        logger.info("  🔍 인덱스 생성...")

        # Phase 1 인덱스
        indexes = [
            # tickers
            "CREATE INDEX IF NOT EXISTS idx_tickers_exchange ON tickers(exchange)",
            "CREATE INDEX IF NOT EXISTS idx_tickers_asset_type ON tickers(asset_type)",
            "CREATE INDEX IF NOT EXISTS idx_tickers_region ON tickers(region)",

            # stock_details
            "CREATE INDEX IF NOT EXISTS idx_stock_details_sector ON stock_details(sector)",
            "CREATE INDEX IF NOT EXISTS idx_stock_details_industry ON stock_details(industry)",
            "CREATE INDEX IF NOT EXISTS idx_stock_details_region ON stock_details(region)",

            # etf_details
            "CREATE INDEX IF NOT EXISTS idx_etf_details_geographic_region ON etf_details(geographic_region)",
            "CREATE INDEX IF NOT EXISTS idx_etf_details_sector_theme ON etf_details(sector_theme)",
            "CREATE INDEX IF NOT EXISTS idx_etf_details_fund_type ON etf_details(fund_type)",
            "CREATE INDEX IF NOT EXISTS idx_etf_details_expense_ratio ON etf_details(expense_ratio)",

            # ticker_fundamentals
            "CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date ON ticker_fundamentals(ticker, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_fundamentals_period ON ticker_fundamentals(period_type)",

            # ohlcv_data
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_region_date ON ohlcv_data(ticker, region, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv_data(timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_region ON ohlcv_data(region)",

            # technical_analysis
            "CREATE INDEX IF NOT EXISTS idx_ta_ticker_date ON technical_analysis(ticker, analysis_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ta_signal ON technical_analysis(signal)",
            "CREATE INDEX IF NOT EXISTS idx_ta_score ON technical_analysis(total_score DESC)",

            # trades
            "CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)",
            "CREATE INDEX IF NOT EXISTS idx_trades_execution_time ON trades(execution_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(trade_status)",
            "CREATE INDEX IF NOT EXISTS idx_trades_ticker_region_status ON trades(ticker, region, trade_status)",
            "CREATE INDEX IF NOT EXISTS idx_trades_entry_timestamp ON trades(entry_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trades_exit_timestamp ON trades(exit_timestamp DESC)",

            # market_sentiment
            "CREATE INDEX IF NOT EXISTS idx_sentiment_date ON market_sentiment(date DESC)",

            # kis_api_logs
            "CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp ON kis_api_logs(timestamp DESC)",

            # filter_cache_stage2
            "CREATE INDEX IF NOT EXISTS idx_stage2_ticker_region ON filter_cache_stage2(ticker, region)",
            "CREATE INDEX IF NOT EXISTS idx_stage2_score ON filter_cache_stage2(total_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_stage2_cache_timestamp ON filter_cache_stage2(cache_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_stage2_recommendation ON filter_cache_stage2(recommendation)",

            # risk_limits
            "CREATE INDEX IF NOT EXISTS idx_risk_limits_effective_from ON risk_limits(effective_from DESC)",
            "CREATE INDEX IF NOT EXISTS idx_risk_limits_profile ON risk_limits(risk_profile)",

            # circuit_breaker_logs
            "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_timestamp ON circuit_breaker_logs(timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_type ON circuit_breaker_logs(breaker_type)",
            "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_date ON circuit_breaker_logs(DATE(timestamp))",
        ]

        # Phase 2 인덱스
        if include_phase2:
            indexes.extend([
                "CREATE INDEX IF NOT EXISTS idx_bs_ticker_date ON balance_sheet(ticker, fiscal_date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_is_ticker_date ON income_statement(ticker, fiscal_date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_cf_ticker_date ON cash_flow_statement(ticker, fiscal_date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_ratios_ticker_date ON financial_ratios(ticker, fiscal_date DESC)",
            ])

        for idx_sql in indexes:
            cursor.execute(idx_sql)

    def verify_tables(self):
        """테이블 생성 확인"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()

        logger.info("\n📋 생성된 테이블:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            logger.info(f"  - {table[0]:30s} ({count:>6d} rows)")

        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Spock Trading System - Database Initialization')
    parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite DB 경로')
    parser.add_argument('--reset', action='store_true', help='기존 DB 삭제 후 재생성')
    parser.add_argument('--phase2', action='store_true', help='Phase 2 테이블 포함 (재무제표)')
    parser.add_argument('--verify', action='store_true', help='테이블 생성 확인만')

    args = parser.parse_args()

    initializer = DatabaseInitializer(db_path=args.db_path)

    if args.verify:
        initializer.verify_tables()
    else:
        initializer.initialize(reset=args.reset, include_phase2=args.phase2)
        initializer.verify_tables()

    logger.info(f"\n✅ 완료: {args.db_path}")


if __name__ == '__main__':
    main()
