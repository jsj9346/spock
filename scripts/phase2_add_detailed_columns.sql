-- Phase 2: Detailed Financial Statement Columns
-- Adds 18 new columns to ticker_fundamentals table
-- for industry-specific factor calculations
--
-- Author: Quant Investment Platform - Phase 2
-- Date: 2025-10-24
--
-- Usage:
--   psql -d quant_platform -f scripts/phase2_add_detailed_columns.sql

-- ============================================================
-- 1. Manufacturing Industry Indicators (5 columns)
-- ============================================================

-- Cost of Goods Sold (매출원가)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS cogs NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.cogs IS 'Cost of Goods Sold (매출원가)';

-- Gross Profit (매출총이익)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS gross_profit NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.gross_profit IS 'Gross Profit = Revenue - COGS (매출총이익)';

-- Property, Plant & Equipment (유형자산)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS pp_e NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.pp_e IS 'Property, Plant & Equipment (유형자산)';

-- Depreciation Expense (감가상각비)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS depreciation NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.depreciation IS 'Depreciation Expense (감가상각비)';

-- Accounts Receivable (매출채권)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS accounts_receivable NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.accounts_receivable IS 'Accounts Receivable (매출채권)';

-- Accumulated Depreciation (감가상각누계액)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS accumulated_depreciation NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.accumulated_depreciation IS 'Accumulated Depreciation (감가상각누계액)';

-- ============================================================
-- 2. Retail/E-Commerce Industry Indicators (3 columns)
-- ============================================================

-- Selling, General & Administrative Expense (판매비와관리비)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS sga_expense NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.sga_expense IS 'Selling, General & Administrative Expense (판매비와관리비)';

-- Research & Development Expense (연구개발비)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS rd_expense NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.rd_expense IS 'Research & Development Expense (연구개발비)';

-- Operating Expense (영업비용)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS operating_expense NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.operating_expense IS 'Operating Expense = SG&A + R&D (영업비용)';

-- ============================================================
-- 3. Financial Industry Indicators (5 columns)
-- ============================================================

-- Interest Income (이자수익)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS interest_income NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.interest_income IS 'Interest Income (이자수익)';

-- Interest Expense (이자비용)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS interest_expense NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.interest_expense IS 'Interest Expense (이자비용)';

-- Loan Portfolio (대출금)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS loan_portfolio NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.loan_portfolio IS 'Loan Portfolio (대출금)';

-- Non-Performing Loans (부실채권)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS npl_amount NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.npl_amount IS 'Non-Performing Loans (부실채권)';

-- Net Interest Margin (순이자마진)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS nim NUMERIC(10,4);
COMMENT ON COLUMN ticker_fundamentals.nim IS 'Net Interest Margin (%) = (Interest Income - Interest Expense) / Loan Portfolio * 100';

-- ============================================================
-- 4. Common Indicators (All Industries) (5 columns)
-- ============================================================

-- Investing Cash Flow (투자활동현금흐름)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS investing_cf NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.investing_cf IS 'Investing Cash Flow (투자활동현금흐름)';

-- Financing Cash Flow (재무활동현금흐름)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS financing_cf NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.financing_cf IS 'Financing Cash Flow (재무활동현금흐름)';

-- EBITDA (상각전영업이익)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS ebitda NUMERIC(20,2);
COMMENT ON COLUMN ticker_fundamentals.ebitda IS 'EBITDA = Operating Profit + Depreciation (상각전영업이익)';

-- EBITDA Margin (EBITDA 마진)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS ebitda_margin NUMERIC(10,4);
COMMENT ON COLUMN ticker_fundamentals.ebitda_margin IS 'EBITDA Margin (%) = EBITDA / Revenue * 100';

-- ============================================================
-- 5. Indexes for Performance Optimization
-- ============================================================

-- Index for COGS (manufacturing analysis)
CREATE INDEX IF NOT EXISTS idx_fundamentals_cogs
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE cogs IS NOT NULL;

-- Index for R&D Expense (innovation analysis)
CREATE INDEX IF NOT EXISTS idx_fundamentals_rd_expense
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE rd_expense IS NOT NULL;

-- Index for EBITDA (profitability analysis)
CREATE INDEX IF NOT EXISTS idx_fundamentals_ebitda
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE ebitda IS NOT NULL;

-- Index for NIM (financial sector analysis)
CREATE INDEX IF NOT EXISTS idx_fundamentals_nim
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE nim IS NOT NULL;

-- Index for PP&E (asset-intensive analysis)
CREATE INDEX IF NOT EXISTS idx_fundamentals_pp_e
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE pp_e IS NOT NULL;

-- ============================================================
-- 6. Verification Queries
-- ============================================================

-- Check new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'ticker_fundamentals'
  AND column_name IN (
    'cogs', 'gross_profit', 'pp_e', 'depreciation', 'accounts_receivable', 'accumulated_depreciation',
    'sga_expense', 'rd_expense', 'operating_expense',
    'interest_income', 'interest_expense', 'loan_portfolio', 'npl_amount', 'nim',
    'investing_cf', 'financing_cf', 'ebitda', 'ebitda_margin'
  )
ORDER BY column_name;

-- Check indexes created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'ticker_fundamentals'
  AND indexname LIKE '%cogs%'
   OR indexname LIKE '%rd_expense%'
   OR indexname LIKE '%ebitda%'
   OR indexname LIKE '%nim%'
   OR indexname LIKE '%pp_e%'
ORDER BY indexname;

-- Summary
\echo '✅ Phase 2: Added 18 detailed financial statement columns'
\echo ''
\echo 'Manufacturing (6): cogs, gross_profit, pp_e, depreciation, accounts_receivable, accumulated_depreciation'
\echo 'Retail/E-commerce (3): sga_expense, rd_expense, operating_expense'
\echo 'Financial (5): interest_income, interest_expense, loan_portfolio, npl_amount, nim'
\echo 'Common (4): investing_cf, financing_cf, ebitda, ebitda_margin'
\echo ''
\echo 'Total columns: 54 (36 existing + 18 new)'
\echo '✅ Schema extension complete!'
