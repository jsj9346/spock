#!/bin/bash
# Monitor DART Annual Data Backfill Progress
# Usage: ./scripts/monitor_dart_backfill.sh

set -euo pipefail

LOG_FILE="logs/20251102_task9_full_backfill.log"
DB_NAME="quant_platform"

echo "================================================================================"
echo "DART Annual Data Backfill - Progress Monitor"
echo "================================================================================"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

# 1. Current Processing Status
echo "📊 Current Processing Status:"
echo "---"
tail -20 "$LOG_FILE" | grep -E "Processing [0-9]|Collecting 2024" | tail -3
echo ""

# 2. Latest Statistics
echo "📈 Latest Statistics from Log:"
echo "---"
tail -100 "$LOG_FILE" | grep -E "(Tickers Processed|Success|Failed|Records Inserted)" | tail -5
echo ""

# 3. Database Record Count
echo "💾 Database Progress:"
echo "---"
psql -d "$DB_NAME" -c "
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT ticker) as unique_tickers,
    ROUND((COUNT(DISTINCT ticker)::numeric / 2330 * 100)::numeric, 2) as progress_pct,
    2330 - COUNT(DISTINCT ticker) as tickers_remaining
FROM ticker_fundamentals
WHERE fiscal_year = 2024 AND period_type = 'ANNUAL' AND region = 'KR';
" | grep -v "^$"
echo ""

# 4. Recent Errors (if any)
echo "⚠️  Recent Errors (last 10):"
echo "---"
ERROR_COUNT=$(tail -200 "$LOG_FILE" | grep -c "ERROR" || echo "0")
if [ "$ERROR_COUNT" -gt 0 ]; then
    tail -200 "$LOG_FILE" | grep "ERROR" | tail -10
    echo ""
    echo "⚠️  Found $ERROR_COUNT errors in last 200 lines"
else
    echo "✅ No errors detected in recent logs"
fi
echo ""

# 5. Estimated Completion Time
echo "⏱️  Time Estimates:"
echo "---"
CURRENT_COUNT=$(psql -d "$DB_NAME" -t -c "
SELECT COUNT(DISTINCT ticker)
FROM ticker_fundamentals
WHERE fiscal_year = 2024 AND period_type = 'ANNUAL' AND region = 'KR';
" | tr -d ' ')

TOTAL_TICKERS=2330
REMAINING=$((TOTAL_TICKERS - CURRENT_COUNT))
AVG_TIME_PER_TICKER=35  # seconds

if [ "$CURRENT_COUNT" -gt 2 ]; then
    ELAPSED_TIME=$(tail -100 "$LOG_FILE" | grep "Duration:" | tail -1 | awk '{print $4}' || echo "unknown")
    echo "Current progress: $CURRENT_COUNT / $TOTAL_TICKERS tickers ($REMAINING remaining)"
    echo "Average time per ticker: ~$AVG_TIME_PER_TICKER seconds"

    REMAINING_SECONDS=$((REMAINING * AVG_TIME_PER_TICKER))
    REMAINING_HOURS=$((REMAINING_SECONDS / 3600))
    REMAINING_MINUTES=$(((REMAINING_SECONDS % 3600) / 60))

    echo "Estimated remaining time: ${REMAINING_HOURS}h ${REMAINING_MINUTES}m"
    echo "Expected completion: $(date -v+${REMAINING_HOURS}H -v+${REMAINING_MINUTES}M '+%Y-%m-%d %H:%M')"
else
    echo "Not enough data yet for time estimate (only $CURRENT_COUNT tickers processed)"
fi
echo ""

# 6. Background Process Status
echo "🔄 Background Process:"
echo "---"
if pgrep -f "backfill_fundamentals_dart.py.*2024.*2024" > /dev/null; then
    PID=$(pgrep -f "backfill_fundamentals_dart.py.*2024.*2024")
    CPU=$(ps -p "$PID" -o %cpu= || echo "N/A")
    MEM=$(ps -p "$PID" -o %mem= || echo "N/A")
    echo "✅ Process running (PID: $PID)"
    echo "   CPU: ${CPU}% | Memory: ${MEM}%"
else
    echo "❌ Process not running"
    echo "   Last log entry: $(tail -1 "$LOG_FILE")"
fi
echo ""

echo "================================================================================"
echo "Monitor completed at $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================================"
echo ""
echo "💡 Tip: Run this script periodically to track progress"
echo "   Example: watch -n 300 ./scripts/monitor_dart_backfill.sh  # Every 5 minutes"
