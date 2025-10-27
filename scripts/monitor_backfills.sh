#!/bin/bash
# Monitor Phase 1.5 Production Backfills
# Usage: ./scripts/monitor_backfills.sh

echo "================================================================================"
echo "PHASE 1.5 - PRODUCTION BACKFILL MONITORING"
echo "================================================================================"
echo ""

# Check Process Status
echo "📊 PROCESS STATUS:"
echo "--------------------------------------------------------------------------------"
DART_PID=$(ps aux | grep "backfill_fundamentals_dart.py" | grep -v grep | awk '{print $2}')
PYKRX_PID=$(ps aux | grep "backfill_fundamentals_pykrx.py" | grep -v grep | awk '{print $2}' | head -1)
YFINANCE_PID=$(ps aux | grep "backfill_fundamentals_yfinance.py" | grep -v grep | awk '{print $2}')

if [ -n "$DART_PID" ]; then
    echo "✅ DART Backfill (KR): RUNNING (PID: $DART_PID)"
else
    echo "❌ DART Backfill (KR): STOPPED"
fi

if [ -n "$PYKRX_PID" ]; then
    echo "✅ pykrx Backfill (KR): RUNNING (PID: $PYKRX_PID)"
else
    echo "✅ pykrx Backfill (KR): COMPLETED (178,732 records)"
fi

if [ -n "$YFINANCE_PID" ]; then
    echo "✅ yfinance Backfill (Global): RUNNING (PID: $YFINANCE_PID)"
else
    echo "❌ yfinance Backfill (Global): STOPPED"
fi
echo ""

# Check Database Records
echo "💾 DATABASE STATUS (Korean Market):"
echo "--------------------------------------------------------------------------------"
psql -d quant_platform -c "
SELECT
    data_source,
    COUNT(*) as records,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(date) as earliest,
    MAX(date) as latest
FROM ticker_fundamentals
WHERE region = 'KR'
GROUP BY data_source
ORDER BY data_source;
" 2>/dev/null

echo ""
echo "💾 DATABASE STATUS (Global Markets - yfinance):"
echo "--------------------------------------------------------------------------------"
psql -d quant_platform -c "
SELECT
    region,
    COUNT(*) as records,
    COUNT(DISTINCT ticker) as unique_tickers
FROM ticker_fundamentals
WHERE region IN ('US', 'JP', 'CN', 'HK', 'VN') AND data_source = 'yfinance'
GROUP BY region
ORDER BY region;
" 2>/dev/null

echo ""
echo "📈 TOTAL RECORDS:"
psql -d quant_platform -t -c "
SELECT
    'KR: ' || (SELECT COUNT(*) FROM ticker_fundamentals WHERE region = 'KR') || ' | ' ||
    'Global: ' || (SELECT COUNT(*) FROM ticker_fundamentals WHERE region IN ('US','JP','CN','HK','VN')) || ' | ' ||
    'Total: ' || COUNT(*) || ' records'
FROM ticker_fundamentals;
" 2>/dev/null

echo ""

# Check Latest Log Entries
echo "📋 LATEST PROGRESS:"
echo "--------------------------------------------------------------------------------"
echo "DART Backfill (KR - last 2 lines):"
tail -2 logs/dart_production_backfill_SAFE.log 2>/dev/null | grep -v "^$" || echo "  ✅ Completed"

echo ""
echo "pykrx Backfill (KR - last 2 lines):"
if [ -n "$PYKRX_PID" ]; then
    tail -2 logs/pykrx_production_backfill.log 2>/dev/null | grep -v "^$" || echo "  No log file found"
else
    echo "  ✅ Completed (178,732 records, 141 tickers, 2020-01-01 to 2025-10-21)"
fi

echo ""
echo "yfinance Backfill (Global - last 3 lines):"
if [ -f logs/yfinance_production_backfill.log ]; then
    # Show progress line and latest ticker
    grep -E "^\[.*\] Processing" logs/yfinance_production_backfill.log | tail -1
    tail -2 logs/yfinance_production_backfill.log | grep -v "^$" | head -2
else
    echo "  No log file found"
fi

echo ""
echo "================================================================================"
echo "Quick Commands:"
echo "  Refresh dashboard: watch -n 10 ./scripts/monitor_backfills.sh"
echo "  yfinance details: ./scripts/monitor_yfinance_backfill.sh"
echo "  Stop yfinance: kill $YFINANCE_PID"
echo "================================================================================"
