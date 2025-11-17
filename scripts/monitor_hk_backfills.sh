#!/bin/bash
# HK Backfill Monitoring Script
# Usage: ./scripts/monitor_hk_backfills.sh

TIER2_LOG="logs/hk_tier2_backfill.log"
ETF_LOG="logs/hk_etf_backfill.log"

echo "🇭🇰 HK Market Backfill Monitor"
echo "================================"
echo ""

while true; do
    clear
    echo "🇭🇰 HK Market Backfill Progress"
    echo "================================"
    echo "Updated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Tier 2 Progress
    if [ -f "$TIER2_LOG" ]; then
        TIER2_CURRENT=$(grep -oE '\[[0-9]+/500\]' "$TIER2_LOG" | tail -1 | grep -oE '[0-9]+' | head -1)
        TIER2_TOTAL=500
        if [ -n "$TIER2_CURRENT" ]; then
            TIER2_PCT=$((TIER2_CURRENT * 100 / TIER2_TOTAL))
            echo "📈 Tier 2 (Stocks): $TIER2_CURRENT/$TIER2_TOTAL ($TIER2_PCT%)"

            # Latest ticker
            TIER2_LATEST=$(grep -E '\[[0-9]+/500\] Backfilling' "$TIER2_LOG" | tail -1 | grep -oE '[0-9]{4}\.HK')
            if [ -n "$TIER2_LATEST" ]; then
                echo "   Current: $TIER2_LATEST"
            fi

            # Success/Failure count
            TIER2_SUCCESS=$(grep -c "✅.*records saved" "$TIER2_LOG")
            TIER2_FAILED=$(grep -c "⚠️.*No data collected" "$TIER2_LOG")
            echo "   Success: $TIER2_SUCCESS | Failed: $TIER2_FAILED"

            # Check if complete
            if grep -q "Tier 2 Backfill Complete" "$TIER2_LOG"; then
                echo "   Status: ✅ COMPLETE"
            else
                # Estimate time remaining
                if [ "$TIER2_CURRENT" -gt 0 ]; then
                    REMAINING=$((TIER2_TOTAL - TIER2_CURRENT))
                    EST_MINS=$((REMAINING / 60))  # ~1 ticker/sec
                    echo "   ETA: ~$EST_MINS minutes"
                fi
            fi
        else
            echo "📈 Tier 2 (Stocks): Starting..."
        fi
    else
        echo "📈 Tier 2 (Stocks): Not started"
    fi

    echo ""

    # ETF Progress
    if [ -f "$ETF_LOG" ]; then
        ETF_CURRENT=$(grep -oE '\[[0-9]+/51\]' "$ETF_LOG" | tail -1 | grep -oE '[0-9]+' | head -1)
        ETF_TOTAL=51
        if [ -n "$ETF_CURRENT" ]; then
            ETF_PCT=$((ETF_CURRENT * 100 / ETF_TOTAL))
            echo "💰 ETF Backfill: $ETF_CURRENT/$ETF_TOTAL ($ETF_PCT%)"

            # Latest ticker
            ETF_LATEST=$(grep -E '\[[0-9]+/51\] Backfilling' "$ETF_LOG" | tail -1 | grep -oE '[0-9]{4}\.HK')
            if [ -n "$ETF_LATEST" ]; then
                echo "   Current: $ETF_LATEST"
            fi

            # Success/Failure count
            ETF_SUCCESS=$(grep -c "✅.*records saved" "$ETF_LOG")
            ETF_FAILED=$(grep -c "⚠️.*No data collected" "$ETF_LOG")
            echo "   Success: $ETF_SUCCESS | Failed: $ETF_FAILED"

            # Check if complete
            if grep -q "Tier 1 Backfill Complete" "$ETF_LOG"; then
                echo "   Status: ✅ COMPLETE"
            else
                # Estimate time remaining
                if [ "$ETF_CURRENT" -gt 0 ]; then
                    REMAINING=$((ETF_TOTAL - ETF_CURRENT))
                    EST_SECS=$((REMAINING))  # ~1 ticker/sec
                    echo "   ETA: ~$EST_SECS seconds"
                fi
            fi
        else
            echo "💰 ETF Backfill: Starting..."
        fi
    else
        echo "💰 ETF Backfill: Not started"
    fi

    echo ""
    echo "================================"
    echo "Press Ctrl+C to exit"
    echo ""

    # Check if both complete
    TIER2_DONE=false
    ETF_DONE=false

    if [ -f "$TIER2_LOG" ] && grep -q "Tier 2 Backfill Complete" "$TIER2_LOG"; then
        TIER2_DONE=true
    fi

    if [ -f "$ETF_LOG" ] && grep -q "Tier 1 Backfill Complete" "$ETF_LOG"; then
        ETF_DONE=true
    fi

    if [ "$TIER2_DONE" = true ] && [ "$ETF_DONE" = true ]; then
        echo "🎉 ALL BACKFILLS COMPLETE!"
        echo ""
        echo "Next steps:"
        echo "1. Check results: cat reports/hk_tier2_backfill_results_*.json"
        echo "2. Check results: cat reports/hk_tier1_backfill_results_*.json"
        echo "3. Validate data quality"
        echo "4. Generate comprehensive report"
        break
    fi

    sleep 30
done
