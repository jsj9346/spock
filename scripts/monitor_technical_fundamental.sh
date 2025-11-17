#!/bin/bash
# Technical + Fundamental Data Processing Monitor
# Usage: ./scripts/monitor_technical_fundamental.sh

TECH_LOG=$(ls -t logs/technical_indicators_*.log 2>/dev/null | head -1)
FUND_LOG=$(ls -t logs/fundamental_data_*.log 2>/dev/null | head -1)

echo "📊 Technical & Fundamental Data Processing Monitor"
echo "=================================================="
echo ""

while true; do
    clear
    echo "📊 HK Market Data Processing Progress"
    echo "=================================================="
    echo "Updated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Technical Indicators Progress
    echo "🔧 Phase 1: Technical Indicators (MA, RSI, MACD)"
    echo "------------------------------------------------"

    if [ -f "$TECH_LOG" ]; then
        # Get latest progress line
        TECH_PROGRESS=$(grep "Progress:" "$TECH_LOG" | tail -1)

        if [ -n "$TECH_PROGRESS" ]; then
            echo "$TECH_PROGRESS"

            # Extract current ticker
            TECH_CURRENT=$(grep -E '\[[0-9]+/[0-9]+\] Processing' "$TECH_LOG" | tail -1 | grep -oE '[0-9]{4}\.HK')
            if [ -n "$TECH_CURRENT" ]; then
                echo "   Current: $TECH_CURRENT"
            fi

            # Success/Failure count
            TECH_SUCCESS=$(grep -c "✅" "$TECH_LOG" 2>/dev/null || echo "0")
            TECH_FAILED=$(grep -c "❌" "$TECH_LOG" 2>/dev/null || echo "0")
            echo "   Success: $TECH_SUCCESS | Failed: $TECH_FAILED"

            # Check if complete
            if grep -q "Technical Indicators Calculation Complete" "$TECH_LOG"; then
                echo "   Status: ✅ COMPLETE"

                # Show final stats
                DURATION=$(grep "Duration:" "$TECH_LOG" | tail -1)
                RATE=$(grep "Rate:" "$TECH_LOG" | tail -1)
                echo "   $DURATION"
                echo "   $RATE"
            fi
        else
            echo "   Status: Starting..."
        fi
    else
        echo "   Status: Not started"
    fi

    echo ""

    # Fundamental Data Progress
    echo "💰 Phase 2: Fundamental Data (P/E, P/B, Dividend Yield)"
    echo "------------------------------------------------"

    if [ -f "$FUND_LOG" ]; then
        # Get latest progress line
        FUND_PROGRESS=$(grep "Progress:" "$FUND_LOG" | tail -1)

        if [ -n "$FUND_PROGRESS" ]; then
            echo "$FUND_PROGRESS"

            # Extract current ticker
            FUND_CURRENT=$(grep -E '\[[0-9]+/[0-9]+\] Fetching' "$FUND_LOG" | tail -1 | grep -oE '[0-9]{4}\.HK')
            if [ -n "$FUND_CURRENT" ]; then
                echo "   Current: $FUND_CURRENT"
            fi

            # Success/Failure count
            FUND_SUCCESS=$(grep -c "✅.*P/E=" "$FUND_LOG" 2>/dev/null || echo "0")
            FUND_FAILED=$(grep -c "❌" "$FUND_LOG" 2>/dev/null || echo "0")
            echo "   Success: $FUND_SUCCESS | Failed: $FUND_FAILED"

            # Check if complete
            if grep -q "Fundamental Data Collection Complete" "$FUND_LOG"; then
                echo "   Status: ✅ COMPLETE"

                # Show final stats
                DURATION=$(grep "Duration:" "$FUND_LOG" | tail -1)
                RATE=$(grep "Rate:" "$FUND_LOG" | tail -1)
                echo "   $DURATION"
                echo "   $RATE"
            fi
        else
            echo "   Status: Starting..."
        fi
    else
        echo "   Status: Not started (will start after Phase 1)"
    fi

    echo ""
    echo "================================================"
    echo "Press Ctrl+C to exit"
    echo ""

    # Check if both complete
    TECH_DONE=false
    FUND_DONE=false

    if [ -f "$TECH_LOG" ] && grep -q "Technical Indicators Calculation Complete" "$TECH_LOG"; then
        TECH_DONE=true
    fi

    if [ -f "$FUND_LOG" ] && grep -q "Fundamental Data Collection Complete" "$FUND_LOG"; then
        FUND_DONE=true
    fi

    if [ "$TECH_DONE" = true ] && [ "$FUND_DONE" = true ]; then
        echo "🎉 ALL PROCESSING COMPLETE!"
        echo ""
        echo "Next steps:"
        echo "1. Validate data quality"
        echo "2. Check database coverage"
        echo "3. Generate final report"
        echo "4. Proceed to backtesting"
        break
    fi

    sleep 15
done
