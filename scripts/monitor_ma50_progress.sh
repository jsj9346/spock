#!/bin/bash
# Monitor MA50 Full Recalculation Progress
# Usage: ./scripts/monitor_ma50_progress.sh

echo "========================================="
echo "📊 MA50 Calculation Progress Monitor"
echo "========================================="
echo ""

# Find the most recent log file
LATEST_LOG=$(ls -t /Users/13ruce/spock/logs/ma50_full_recalc_*.log 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "❌ No MA50 calculation log found"
    exit 1
fi

echo "📄 Log file: $(basename $LATEST_LOG)"
echo ""

# Check if process is still running
if ps aux | grep -q "[c]alculate_all_ma50.sh"; then
    echo "✅ Process status: RUNNING"
else
    echo "⏹️  Process status: COMPLETED or STOPPED"
fi

echo ""
echo "========================================="
echo "📈 Progress Summary"
echo "========================================="

# Extract region completions
grep "completed in" "$LATEST_LOG" | tail -6

echo ""
echo "========================================="
echo "🔄 Current Activity (last 15 lines)"
echo "========================================="

# Show last 15 lines of activity
tail -15 "$LATEST_LOG" | grep -E "(Processing|completed|failed|✅|❌)" || echo "No recent activity"

echo ""
echo "========================================="
echo "💡 Commands"
echo "========================================="
echo "  View full log:   tail -f $LATEST_LOG"
echo "  View last 50:    tail -50 $LATEST_LOG"
echo "  Search region:   grep 'KR' $LATEST_LOG"
echo "  Kill process:    pkill -f calculate_all_ma50"
echo "========================================="
