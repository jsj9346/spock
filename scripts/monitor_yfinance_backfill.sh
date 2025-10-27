#!/bin/bash
# Monitor yfinance Global Market Backfill (Phase 1.5 - Day 3)
# Usage: ./scripts/monitor_yfinance_backfill.sh

echo "================================================================================"
echo "PHASE 1.5 - DAY 3: YFINANCE GLOBAL MARKET BACKFILL MONITORING"
echo "================================================================================"
echo ""

# Check Process Status
echo "📊 PROCESS STATUS:"
echo "--------------------------------------------------------------------------------"
YFINANCE_PID=$(ps aux | grep "backfill_fundamentals_yfinance.py" | grep -v grep | awk '{print $2}')

if [ -n "$YFINANCE_PID" ]; then
    echo "✅ yfinance Backfill: RUNNING (PID: $YFINANCE_PID)"
    echo "   Started: $(ps -p $YFINANCE_PID -o lstart= 2>/dev/null)"
    echo "   Runtime: $(ps -p $YFINANCE_PID -o etime= 2>/dev/null | xargs)"
else
    echo "❌ yfinance Backfill: STOPPED"
fi
echo ""

# Check Database Records by Region
echo "💾 DATABASE STATUS (by region):"
echo "--------------------------------------------------------------------------------"
psql -d quant_platform -c "
SELECT
    region,
    COUNT(*) as records,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(created_at) as first_inserted,
    MAX(created_at) as last_inserted,
    ROUND(AVG(CASE WHEN per IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as per_fill_rate
FROM ticker_fundamentals
WHERE region IN ('US', 'JP', 'CN', 'HK', 'VN') AND data_source = 'yfinance'
GROUP BY region
ORDER BY region;
" 2>/dev/null

echo ""
echo "📈 TOTAL YFINANCE RECORDS:"
psql -d quant_platform -t -c "
SELECT COUNT(*) || ' total records (' || COUNT(DISTINCT ticker) || ' unique tickers)'
FROM ticker_fundamentals
WHERE data_source = 'yfinance';
" 2>/dev/null

echo ""

# Check Latest Log Entries
echo "📋 LATEST PROGRESS (last 10 lines):"
echo "--------------------------------------------------------------------------------"
tail -10 logs/yfinance_production_backfill.log 2>/dev/null | grep -v "^$" || echo "  No log file found"

echo ""

# Extract progress statistics from log
echo "📊 PROGRESS STATISTICS:"
echo "--------------------------------------------------------------------------------"
if [ -f logs/yfinance_production_backfill.log ]; then
    # Get latest progress line (e.g., "[123/17297] Processing...")
    LATEST_PROGRESS=$(grep -E "^\[.*\] Processing" logs/yfinance_production_backfill.log | tail -1)
    if [ -n "$LATEST_PROGRESS" ]; then
        echo "   $LATEST_PROGRESS"

        # Extract current/total from pattern [123/17297]
        CURRENT=$(echo "$LATEST_PROGRESS" | grep -oE "\[[0-9]+" | tr -d '[')
        TOTAL=$(echo "$LATEST_PROGRESS" | grep -oE "/[0-9]+\]" | tr -d '/]')

        if [ -n "$CURRENT" ] && [ -n "$TOTAL" ]; then
            PERCENT=$(awk "BEGIN {printf \"%.2f\", ($CURRENT / $TOTAL) * 100}")
            echo "   Progress: $CURRENT/$TOTAL tickers ($PERCENT%)"

            # Estimate remaining time
            if [ -n "$YFINANCE_PID" ]; then
                ELAPSED_SEC=$(ps -p $YFINANCE_PID -o etimes= 2>/dev/null | xargs)
                if [ -n "$ELAPSED_SEC" ] && [ "$ELAPSED_SEC" -gt 0 ] && [ "$CURRENT" -gt 0 ]; then
                    SEC_PER_TICKER=$(awk "BEGIN {printf \"%.2f\", $ELAPSED_SEC / $CURRENT}")
                    REMAINING_SEC=$(awk "BEGIN {printf \"%.0f\", ($TOTAL - $CURRENT) * $SEC_PER_TICKER}")
                    REMAINING_MIN=$(awk "BEGIN {printf \"%.1f\", $REMAINING_SEC / 60}")
                    echo "   Estimated remaining: ${REMAINING_MIN} minutes"
                else
                    echo "   Estimated remaining: Calculating..."
                fi
            fi
        fi
    else
        echo "   No progress data available yet"
    fi

    # Count success/warning/error in log
    SUCCESS_COUNT=$(grep -c "✅" logs/yfinance_production_backfill.log 2>/dev/null || echo "0")
    WARNING_COUNT=$(grep -c "⚠️" logs/yfinance_production_backfill.log 2>/dev/null || echo "0")
    ERROR_COUNT=$(grep -c "❌" logs/yfinance_production_backfill.log 2>/dev/null || echo "0")

    echo "   Success: $SUCCESS_COUNT | Warnings: $WARNING_COUNT | Errors: $ERROR_COUNT"
else
    echo "   Log file not found"
fi

echo ""
echo "================================================================================"
echo "Quick Commands:"
echo "  Refresh: watch -n 10 ./scripts/monitor_yfinance_backfill.sh"
echo "  Real-time log: tail -f logs/yfinance_production_backfill.log"
echo "  Stop backfill: kill $YFINANCE_PID"
echo "================================================================================"
