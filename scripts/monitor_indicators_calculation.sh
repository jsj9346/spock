#!/bin/bash
# Monitor Technical Indicators Calculation Progress

echo "======================================================================"
echo "Technical Indicators Calculation Progress Monitor"
echo "======================================================================"
echo ""
echo "Started: $(date)"
echo ""

# Check running processes
PROCESS_COUNT=$(ps aux | grep "calculate_technical_indicators.py" | grep -v grep | wc -l | tr -d ' ')
echo "Running processes: $PROCESS_COUNT"
echo ""

# Check each region
for region in VN CN JP HK US; do
    LOG_FILE="/tmp/${region}_indicators.log"

    if [ -f "$LOG_FILE" ]; then
        # Count tickers processed
        PROCESSED=$(grep -c "✅" "$LOG_FILE" 2>/dev/null || echo "0")
        FAILED=$(grep -c "❌" "$LOG_FILE" 2>/dev/null || echo "0")

        # Get last progress update
        LAST_PROGRESS=$(grep "📈 Progress:" "$LOG_FILE" 2>/dev/null | tail -1)

        echo "[$region]"
        echo "  Processed: $PROCESSED tickers"
        echo "  Failed: $FAILED tickers"
        if [ -n "$LAST_PROGRESS" ]; then
            echo "  $LAST_PROGRESS"
        fi
        echo ""
    else
        echo "[$region] Log file not found"
        echo ""
    fi
done

echo "======================================================================"
echo ""
echo "To monitor real-time:"
echo "  VN: tail -f /tmp/vn_indicators.log"
echo "  CN: tail -f /tmp/cn_indicators.log"
echo "  JP: tail -f /tmp/jp_indicators.log"
echo "  HK: tail -f /tmp/hk_indicators.log"
echo "  US: tail -f /tmp/us_indicators.log"
echo ""
echo "To check database status:"
echo "  psql -d quant_platform -c \"SELECT region, COUNT(DISTINCT ticker) as total, COUNT(DISTINCT CASE WHEN ma5 IS NOT NULL THEN ticker END) as with_indicators FROM ohlcv_data WHERE timeframe='1d' GROUP BY region ORDER BY region;\""
