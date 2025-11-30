#!/bin/bash
# ============================================================================
# DART 분기 데이터 백필 모니터링 스크립트
# ============================================================================
# 사용법:
#   ./scripts/monitor_quarterly_backfill.sh [옵션]
#
# 옵션:
#   status    - 현재 수집 상태 확인
#   progress  - 실시간 진행률 모니터링 (watch 모드)
#   logs      - 최근 로그 확인
#   validate  - 데이터 품질 검증
#   all       - 전체 리포트
# ============================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 데이터베이스 연결 설정
PSQL_CMD="/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -U 13ruce -d quant_platform"

# 로그 디렉토리
LOG_DIR="/Users/13ruce/spock/log"
TODAY=$(date +%Y%m%d)

# ============================================================================
# 함수: 데이터 수집 현황 확인
# ============================================================================
check_status() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  📊 DART 분기 데이터 수집 현황${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    echo -e "${YELLOW}▶ Period Type별 레코드 수:${NC}"
    $PSQL_CMD -c "
    SELECT
        period_type,
        COUNT(*) as record_count,
        COUNT(DISTINCT ticker) as ticker_count,
        MIN(date) as min_date,
        MAX(date) as max_date,
        MIN(fiscal_year) as min_year,
        MAX(fiscal_year) as max_year
    FROM ticker_fundamentals
    WHERE region = 'KR'
    GROUP BY period_type
    ORDER BY period_type;
    "

    echo ""
    echo -e "${YELLOW}▶ 연도별 분기 데이터 분포:${NC}"
    $PSQL_CMD -c "
    SELECT
        fiscal_year,
        period_type,
        COUNT(*) as records,
        COUNT(DISTINCT ticker) as tickers
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND period_type IN ('QUARTERLY', 'SEMI-ANNUAL')
    GROUP BY fiscal_year, period_type
    ORDER BY fiscal_year DESC, period_type;
    "
}

# ============================================================================
# 함수: 데이터 품질 검증
# ============================================================================
validate_data() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🔍 데이터 품질 검증${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    echo -e "${YELLOW}▶ TTM 계산 가능한 ticker 수 (4분기 연속 데이터):${NC}"
    $PSQL_CMD -c "
    WITH quarterly_counts AS (
        SELECT
            ticker,
            COUNT(*) as q_count,
            MAX(date) as latest_date
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'QUARTERLY'
          AND date >= CURRENT_DATE - INTERVAL '15 months'
        GROUP BY ticker
        HAVING COUNT(*) >= 4
    )
    SELECT
        COUNT(*) as ttm_ready_tickers,
        MIN(latest_date) as oldest_latest,
        MAX(latest_date) as newest_latest
    FROM quarterly_counts;
    "

    echo ""
    echo -e "${YELLOW}▶ 주요 지표 NULL 비율:${NC}"
    $PSQL_CMD -c "
    SELECT
        period_type,
        COUNT(*) as total,
        ROUND(100.0 * COUNT(revenue) / COUNT(*), 1) as revenue_pct,
        ROUND(100.0 * COUNT(operating_profit) / COUNT(*), 1) as op_profit_pct,
        ROUND(100.0 * COUNT(net_income) / COUNT(*), 1) as net_income_pct,
        ROUND(100.0 * COUNT(total_assets) / COUNT(*), 1) as total_assets_pct,
        ROUND(100.0 * COUNT(total_equity) / COUNT(*), 1) as total_equity_pct
    FROM ticker_fundamentals
    WHERE region = 'KR'
    GROUP BY period_type
    ORDER BY period_type;
    "

    echo ""
    echo -e "${YELLOW}▶ 분기별 연속성 검증 (삼성전자 예시):${NC}"
    $PSQL_CMD -c "
    SELECT
        ticker,
        fiscal_year,
        period_type,
        date,
        revenue / 1000000000000.0 as revenue_조,
        net_income / 1000000000000.0 as net_income_조
    FROM ticker_fundamentals
    WHERE ticker = '005930'
      AND region = 'KR'
      AND period_type IN ('QUARTERLY', 'SEMI-ANNUAL', 'ANNUAL')
    ORDER BY date DESC
    LIMIT 12;
    "
}

# ============================================================================
# 함수: 실시간 진행률 모니터링
# ============================================================================
monitor_progress() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  ⏱️ 실시간 진행률 모니터링 (5초마다 갱신, Ctrl+C로 종료)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    watch -n 5 "
    echo '📊 Period Type별 현황:'
    /opt/homebrew/opt/postgresql@17/bin/psql -h localhost -U 13ruce -d quant_platform -c \"
    SELECT
        period_type,
        COUNT(*) as records,
        COUNT(DISTINCT ticker) as tickers,
        MAX(date) as latest_date
    FROM ticker_fundamentals
    WHERE region = 'KR'
    GROUP BY period_type
    ORDER BY period_type;
    \"

    echo ''
    echo '📝 최근 로그 (마지막 5줄):'
    tail -5 /Users/13ruce/spock/log/${TODAY}_backfill_fundamentals_dart.log 2>/dev/null || echo 'No log file found'
    "
}

# ============================================================================
# 함수: 최근 로그 확인
# ============================================================================
check_logs() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  📝 최근 백필 로그${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    LOG_FILE="${LOG_DIR}/${TODAY}_backfill_fundamentals_dart.log"

    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}▶ 로그 파일: ${LOG_FILE}${NC}"
        echo -e "${YELLOW}▶ 마지막 30줄:${NC}"
        echo ""
        tail -30 "$LOG_FILE"

        echo ""
        echo -e "${YELLOW}▶ 에러 요약:${NC}"
        grep -i "error\|fail\|exception" "$LOG_FILE" | tail -10 || echo "No errors found"

        echo ""
        echo -e "${YELLOW}▶ 성공 통계:${NC}"
        grep -i "success\|inserted\|updated" "$LOG_FILE" | tail -5 || echo "No success messages found"
    else
        echo -e "${RED}로그 파일이 없습니다: ${LOG_FILE}${NC}"
        echo ""
        echo -e "${YELLOW}사용 가능한 로그 파일:${NC}"
        ls -la "${LOG_DIR}"/*backfill_fundamentals_dart*.log 2>/dev/null | tail -5 || echo "No log files found"
    fi
}

# ============================================================================
# 함수: 전체 리포트
# ============================================================================
full_report() {
    check_status
    echo ""
    validate_data
    echo ""
    check_logs
}

# ============================================================================
# 메인 실행
# ============================================================================
case "${1:-status}" in
    status)
        check_status
        ;;
    progress)
        monitor_progress
        ;;
    logs)
        check_logs
        ;;
    validate)
        validate_data
        ;;
    all)
        full_report
        ;;
    *)
        echo "사용법: $0 {status|progress|logs|validate|all}"
        echo ""
        echo "  status    - 현재 수집 상태 확인"
        echo "  progress  - 실시간 진행률 모니터링"
        echo "  logs      - 최근 로그 확인"
        echo "  validate  - 데이터 품질 검증"
        echo "  all       - 전체 리포트"
        exit 1
        ;;
esac
