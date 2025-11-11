#!/bin/bash
# monitor_backfill_progress.sh - 백필 진행상황 실시간 모니터링

# 최신 로그 파일 찾기
LOG_FILE=$(ls -t logs/backfill_orphaned_tickers_*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "❌ 로그 파일을 찾을 수 없습니다."
    exit 1
fi

echo "📊 백필 진행상황 모니터링"
echo "로그 파일: $LOG_FILE"
echo "========================================"
echo ""

# 실시간 모니터링 루프
while true; do
    clear
    echo "📊 백필 진행상황 ($(date '+%H:%M:%S'))"
    echo "========================================"

    # 현재 진행 중인 티커
    CURRENT=$(tail -50 "$LOG_FILE" | grep "Processing" | tail -1)
    if [ -n "$CURRENT" ]; then
        echo "🔄 현재 처리 중:"
        echo "$CURRENT"
        echo ""
    fi

    # 최근 성공한 티커 5개
    echo "✅ 최근 성공 (5개):"
    tail -100 "$LOG_FILE" | grep "✅" | tail -5
    echo ""

    # 통계 정보
    TOTAL_LINES=$(wc -l < "$LOG_FILE")
    SUCCESS_COUNT=$(grep -c "✅" "$LOG_FILE")
    WARNING_COUNT=$(grep -c "⚠️" "$LOG_FILE")
    ERROR_COUNT=$(grep -c "❌" "$LOG_FILE")
    PRIORITY_COUNT=$(grep -c "PRIORITY" "$LOG_FILE")

    echo "📈 통계:"
    echo "  총 로그 라인: $TOTAL_LINES"
    echo "  ✅ 성공: $SUCCESS_COUNT"
    echo "  🎯 우선순위: $PRIORITY_COUNT"
    echo "  ⚠️  경고: $WARNING_COUNT"
    echo "  ❌ 실패: $ERROR_COUNT"
    echo ""

    # 진행률 계산 (전체 2425개 기준)
    TOTAL_TICKERS=2425
    if [ $SUCCESS_COUNT -gt 0 ]; then
        PROGRESS=$(echo "scale=2; $SUCCESS_COUNT * 100 / $TOTAL_TICKERS" | bc)
        REMAINING=$((TOTAL_TICKERS - SUCCESS_COUNT))
        echo "  진행률: $PROGRESS% ($SUCCESS_COUNT/$TOTAL_TICKERS)"
        echo "  남은 티커: $REMAINING"

        # 예상 완료 시간 (0.5초/티커 기준)
        REMAINING_SECONDS=$((REMAINING / 2))
        REMAINING_MINUTES=$((REMAINING_SECONDS / 60))
        echo "  예상 남은 시간: 약 ${REMAINING_MINUTES}분"
    fi

    echo ""
    echo "========================================"
    echo "Ctrl+C로 종료 | 10초마다 업데이트"

    # 10초 대기
    sleep 10
done
