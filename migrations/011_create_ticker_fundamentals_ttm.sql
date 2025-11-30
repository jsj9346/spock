-- ============================================================================
-- Migration 011: Create ticker_fundamentals_ttm Table
-- ============================================================================
-- Purpose: TTM (Trailing Twelve Months) 재무 지표 저장
--
-- TTM은 최근 4분기 재무 데이터를 집계하여 연환산한 지표입니다.
-- 투자 분석에서 P/E (TTM), ROE (TTM) 등 핵심 지표에 사용됩니다.
--
-- 계산 방식:
--   - 손익계산서 지표: 4분기 합산 (revenue_ttm, net_income_ttm 등)
--   - 재무상태표 지표: 최신 분기 값 사용 (total_assets, total_equity 등)
--   - 파생 비율: TTM 데이터 기반 계산 (ROE, ROA, 마진 등)
--
-- Author: Quant Platform Development Team
-- Date: 2025-11-28
-- ============================================================================

-- Drop table if exists (for idempotent migrations)
DROP TABLE IF EXISTS ticker_fundamentals_ttm CASCADE;

-- Create TTM table
CREATE TABLE ticker_fundamentals_ttm (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Identifiers
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(10) NOT NULL,
    as_of_date DATE NOT NULL,                    -- TTM 계산 기준일

    -- =========================================================================
    -- Income Statement (TTM - 4분기 합산)
    -- =========================================================================
    revenue_ttm NUMERIC(20, 2),                  -- 매출액 TTM
    gross_profit_ttm NUMERIC(20, 2),             -- 매출총이익 TTM
    operating_profit_ttm NUMERIC(20, 2),         -- 영업이익 TTM
    net_income_ttm NUMERIC(20, 2),               -- 순이익 TTM
    ebitda_ttm NUMERIC(20, 2),                   -- EBITDA TTM
    interest_expense_ttm NUMERIC(20, 2),         -- 이자비용 TTM
    interest_income_ttm NUMERIC(20, 2),          -- 이자수익 TTM

    -- =========================================================================
    -- Cash Flow Statement (TTM - 4분기 합산)
    -- =========================================================================
    operating_cash_flow_ttm NUMERIC(20, 2),      -- 영업활동현금흐름 TTM
    investing_cf_ttm NUMERIC(20, 2),             -- 투자활동현금흐름 TTM
    financing_cf_ttm NUMERIC(20, 2),             -- 재무활동현금흐름 TTM
    capex_ttm NUMERIC(20, 2),                    -- 자본적지출 TTM
    fcf_ttm NUMERIC(20, 2),                      -- 잉여현금흐름 TTM

    -- =========================================================================
    -- Balance Sheet (Point-in-Time - 최신 분기 값)
    -- =========================================================================
    total_assets NUMERIC(20, 2),                 -- 총자산
    total_liabilities NUMERIC(20, 2),            -- 총부채
    total_equity NUMERIC(20, 2),                 -- 총자본
    current_assets NUMERIC(20, 2),               -- 유동자산
    current_liabilities NUMERIC(20, 2),          -- 유동부채
    cash_and_equivalents NUMERIC(20, 2),         -- 현금성자산
    total_debt NUMERIC(20, 2),                   -- 총차입금
    inventory NUMERIC(20, 2),                    -- 재고자산
    accounts_receivable NUMERIC(20, 2),          -- 매출채권

    -- =========================================================================
    -- Per Share Data
    -- =========================================================================
    eps_ttm NUMERIC(15, 4),                      -- 주당순이익 TTM
    shares_outstanding BIGINT,                   -- 발행주식수

    -- =========================================================================
    -- Derived Ratios (TTM 기반 계산)
    -- =========================================================================
    roe_ttm NUMERIC(10, 4),                      -- ROE TTM (순이익/평균자본)
    roa_ttm NUMERIC(10, 4),                      -- ROA TTM (순이익/평균자산)
    operating_margin_ttm NUMERIC(10, 4),         -- 영업이익률 TTM
    net_margin_ttm NUMERIC(10, 4),               -- 순이익률 TTM
    gross_margin_ttm NUMERIC(10, 4),             -- 매출총이익률 TTM
    debt_ratio NUMERIC(10, 4),                   -- 부채비율 (총부채/총자본)
    current_ratio NUMERIC(10, 4),                -- 유동비율 (유동자산/유동부채)
    asset_turnover_ttm NUMERIC(10, 4),           -- 총자산회전율 TTM

    -- =========================================================================
    -- Metadata
    -- =========================================================================
    quarters_included TEXT[],                    -- 포함된 분기 목록 ['2024Q3', '2024Q2', ...]
    data_completeness NUMERIC(5, 2),             -- 데이터 완성도 (0.00 ~ 1.00)
    calculation_method VARCHAR(50) DEFAULT 'STANDARD',  -- 계산 방법
    data_source VARCHAR(50),                     -- 원본 데이터 소스 (SEC_EDGAR, DART, EDINET 등)

    -- Timestamps
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- =========================================================================
    -- Constraints
    -- =========================================================================
    CONSTRAINT uq_ttm_ticker_region_date UNIQUE (ticker, region, as_of_date)
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Primary lookup: ticker + region
CREATE INDEX idx_ttm_ticker_region ON ticker_fundamentals_ttm(ticker, region);

-- Date-based queries
CREATE INDEX idx_ttm_as_of_date ON ticker_fundamentals_ttm(as_of_date DESC);

-- Region filtering
CREATE INDEX idx_ttm_region ON ticker_fundamentals_ttm(region);

-- Composite for common query patterns
CREATE INDEX idx_ttm_region_date ON ticker_fundamentals_ttm(region, as_of_date DESC);

-- ROE/ROA screening
CREATE INDEX idx_ttm_roe ON ticker_fundamentals_ttm(roe_ttm DESC NULLS LAST);
CREATE INDEX idx_ttm_roa ON ticker_fundamentals_ttm(roa_ttm DESC NULLS LAST);

-- Data quality filtering
CREATE INDEX idx_ttm_completeness ON ticker_fundamentals_ttm(data_completeness DESC);

-- ============================================================================
-- Update Trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_ttm_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ttm_update_timestamp ON ticker_fundamentals_ttm;
CREATE TRIGGER trg_ttm_update_timestamp
    BEFORE UPDATE ON ticker_fundamentals_ttm
    FOR EACH ROW
    EXECUTE FUNCTION update_ttm_timestamp();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE ticker_fundamentals_ttm IS 'TTM (Trailing Twelve Months) 재무 지표 - 최근 4분기 집계';

COMMENT ON COLUMN ticker_fundamentals_ttm.as_of_date IS 'TTM 계산 기준일 (일반적으로 최신 분기 마감일)';
COMMENT ON COLUMN ticker_fundamentals_ttm.revenue_ttm IS '최근 4분기 매출액 합계';
COMMENT ON COLUMN ticker_fundamentals_ttm.net_income_ttm IS '최근 4분기 순이익 합계';
COMMENT ON COLUMN ticker_fundamentals_ttm.roe_ttm IS 'TTM 순이익 / 평균 자본';
COMMENT ON COLUMN ticker_fundamentals_ttm.quarters_included IS '계산에 포함된 분기 목록';
COMMENT ON COLUMN ticker_fundamentals_ttm.data_completeness IS '0.0 ~ 1.0, 4분기 데이터 완성도';

-- ============================================================================
-- Sample Data Verification Query
-- ============================================================================

-- After running TTM calculation, verify with:
-- SELECT
--     ticker, region, as_of_date,
--     revenue_ttm, net_income_ttm,
--     roe_ttm, operating_margin_ttm,
--     quarters_included, data_completeness
-- FROM ticker_fundamentals_ttm
-- WHERE region = 'KR'
-- ORDER BY as_of_date DESC, ticker
-- LIMIT 20;

-- ============================================================================
-- Grant Permissions (if needed)
-- ============================================================================

-- GRANT SELECT, INSERT, UPDATE ON ticker_fundamentals_ttm TO quant_app;
-- GRANT USAGE, SELECT ON SEQUENCE ticker_fundamentals_ttm_id_seq TO quant_app;
