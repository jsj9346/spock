#!/bin/bash
# Monitor Day 4 DART Backfill (2022-2023) Progress
# Usage: ./scripts/monitor_day4_backfill.sh

set -euo pipefail

LOG_FILE="logs/20251104_day4_backfill_2022_2023_restart.log"
DB_NAME="quant_platform"

echo "================================================================================"
echo "Day 4 DART Backfill (2022-2023) - Progress Monitor"
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
tail -20 "$LOG_FILE" | grep -E "Processing [0-9]|Collecting 202[23]" | tail -3
echo ""

# 2. Latest Statistics
echo "📈 Latest Statistics from Log:"
echo "---"
tail -100 "$LOG_FILE" | grep -E "(Tickers Processed|Success|Failed|Records Inserted)" | tail -5
echo ""

# 3. Multi-Year Database Progress
echo "💾 Database Progress (Multi-Year):"
echo "---"
psql -d "$DB_NAME" -c "
SELECT
    fiscal_year,
    COUNT(*) as records,
    COUNT(DISTINCT ticker) as unique_tickers,
    ROUND((COUNT(DISTINCT ticker)::numeric / 2330 * 100)::numeric, 2) as progress_pct
FROM ticker_fundamentals
WHERE period_type = 'ANNUAL' AND region = 'KR'
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
" | grep -v "^$"
echo ""

echo "📊 Total Multi-Year Progress:"
psql -d "$DB_NAME" -c "
SELECT
    COUNT(DISTINCT ticker) as tickers_with_data,
    SUM(CASE WHEN fiscal_year = 2024 THEN 1 ELSE 0 END) as records_2024,
    SUM(CASE WHEN fiscal_year = 2023 THEN 1 ELSE 0 END) as records_2023,
    SUM(CASE WHEN fiscal_year = 2022 THEN 1 ELSE 0 END) as records_2022,
    COUNT(*) as total_records
FROM ticker_fundamentals
WHERE period_type = 'ANNUAL' AND region = 'KR';
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
CURRENT_2023=$(psql -d "$DB_NAME" -t -c "SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals WHERE fiscal_year = 2023 AND period_type = 'ANNUAL' AND region = 'KR';" | tr -d ' ')
CURRENT_2022=$(psql -d "$DB_NAME" -t -c "SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals WHERE fiscal_year = 2022 AND period_type = 'ANNUAL' AND region = 'KR';" | tr -d ' ')

TOTAL_TICKERS=2330
AVG_TIME_PER_TICKER=40  # seconds (from Day 3 metrics)

TOTAL_CURRENT=$((CURRENT_2023 + CURRENT_2022))
TOTAL_TARGET=$((TOTAL_TICKERS * 2))  # 2 years
REMAINING=$((TOTAL_TARGET - TOTAL_CURRENT))

echo "Current progress:"
echo "  2023: $CURRENT_2023 / $TOTAL_TICKERS tickers"
echo "  2022: $CURRENT_2022 / $TOTAL_TICKERS tickers"
echo "  Total: $TOTAL_CURRENT / $TOTAL_TARGET records"
echo "  Remaining: $REMAINING records"
echo ""

if [ "$TOTAL_CURRENT" -gt 2 ]; then
    REMAINING_TICKERS=$((TOTAL_TICKERS - (CURRENT_2023 > CURRENT_2022 ? CURRENT_2023 : CURRENT_2022)))
    REMAINING_SECONDS=$((REMAINING_TICKERS * AVG_TIME_PER_TICKER))
    REMAINING_HOURS=$((REMAINING_SECONDS / 3600))
    REMAINING_MINUTES=$(((REMAINING_SECONDS % 3600) / 60))

    echo "Estimated remaining time: ${REMAINING_HOURS}h ${REMAINING_MINUTES}m"
    echo "Expected completion: $(date -v+${REMAINING_HOURS}H -v+${REMAINING_MINUTES}M '+%Y-%m-%d %H:%M' 2>/dev/null || date -d "+${REMAINING_HOURS} hours +${REMAINING_MINUTES} minutes" '+%Y-%m-%d %H:%M' 2>/dev/null || echo 'N/A')"
else
    echo "Not enough data yet for time estimate"
fi
echo ""

# 6. Background Process Status
echo "🔄 Background Process:"
echo "---"
if pgrep -f "backfill_fundamentals_dart.py.*2022.*2023" > /dev/null; then
    PID=$(pgrep -f "backfill_fundamentals_dart.py.*2022.*2023")
    CPU=$(ps -p "$PID" -o %cpu= 2>/dev/null || echo "N/A")
    MEM=$(ps -p "$PID" -o %mem= 2>/dev/null || echo "N/A")
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
echo "   Example: watch -n 300 ./scripts/monitor_day4_backfill.sh  # Every 5 minutes"
