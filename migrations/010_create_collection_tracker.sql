-- Migration 010: Create collection_tracker table
-- Purpose: Track data collection operations to prevent duplicate API calls
-- Date: 2025-11-27

-- ============================================================================
-- collection_tracker: 수집 작업 추적 테이블
-- ============================================================================
-- 동일 날짜에 동일 데이터 재수집 방지를 위한 추적 테이블
-- 예: Quick Refresh 후 Full Refresh 실행 시 이미 수집된 데이터 스킵

CREATE TABLE IF NOT EXISTS collection_tracker (
    id SERIAL PRIMARY KEY,

    -- 대상 식별
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(10) NOT NULL,
    data_type VARCHAR(50) NOT NULL,  -- 'dividend', 'ratios', 'cash_backfill', 'technical'

    -- 수집 정보
    last_collected DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'success',  -- 'success', 'failed', 'skipped'
    records_count INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT,

    -- 메타데이터
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 유니크 제약: 같은 날 같은 ticker/region/data_type 조합은 1개만
    UNIQUE (ticker, region, data_type, last_collected)
);

-- ============================================================================
-- 인덱스
-- ============================================================================

-- 배치 조회용 인덱스 (region + data_type + date로 조회)
CREATE INDEX IF NOT EXISTS idx_collection_tracker_lookup
ON collection_tracker (region, data_type, last_collected);

-- 개별 ticker 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_collection_tracker_ticker
ON collection_tracker (ticker, region, data_type);

-- 날짜 기반 정리용 인덱스
CREATE INDEX IF NOT EXISTS idx_collection_tracker_date
ON collection_tracker (last_collected);

-- 상태 필터링용 인덱스
CREATE INDEX IF NOT EXISTS idx_collection_tracker_status
ON collection_tracker (status, last_collected);

-- ============================================================================
-- 코멘트
-- ============================================================================

COMMENT ON TABLE collection_tracker IS '데이터 수집 작업 추적 - 중복 API 호출 방지';
COMMENT ON COLUMN collection_tracker.data_type IS '수집 데이터 유형: dividend, ratios, cash_backfill, technical';
COMMENT ON COLUMN collection_tracker.status IS '수집 상태: success(성공), failed(실패), skipped(스킵)';
COMMENT ON COLUMN collection_tracker.records_count IS '수집된 레코드 수';
COMMENT ON COLUMN collection_tracker.duration_ms IS '수집 소요 시간 (밀리초)';

-- ============================================================================
-- 초기 통계 뷰 (선택사항)
-- ============================================================================

CREATE OR REPLACE VIEW v_collection_stats AS
SELECT
    region,
    data_type,
    last_collected,
    status,
    COUNT(*) as ticker_count,
    SUM(records_count) as total_records,
    AVG(duration_ms)::INTEGER as avg_duration_ms,
    SUM(duration_ms) as total_duration_ms
FROM collection_tracker
GROUP BY region, data_type, last_collected, status
ORDER BY last_collected DESC, region, data_type;

COMMENT ON VIEW v_collection_stats IS '수집 작업 통계 뷰';

-- ============================================================================
-- 완료
-- ============================================================================
-- 실행: psql -d quant_platform -f migrations/010_create_collection_tracker.sql
