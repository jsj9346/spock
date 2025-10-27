#!/bin/bash
# Auto-validation script for Phase 2 backfill
# Waits for backfill completion, then runs validation automatically

echo "========================================================================"
echo "🤖 Auto-Validation Monitor Started"
echo "========================================================================"
echo ""
echo "⏳ Waiting for backfill process to complete..."
echo ""

# Wait for backfill process to finish
while ps aux | grep -q "[b]ackfill_phase2_historical.py"; do
    # Get current progress from log
    PROGRESS=$(tail -100 logs/phase2_full_backfill_v4_stocks_only.log | grep "Progress:" | tail -1)
    if [ ! -z "$PROGRESS" ]; then
        echo "[$(date '+%H:%M:%S')] $PROGRESS"
    fi

    # Sleep for 5 minutes between checks
    sleep 300
done

echo ""
echo "✅ Backfill process completed!"
echo ""
echo "⏳ Waiting 5 minutes for log buffer to flush..."
sleep 300

echo ""
echo "========================================================================"
echo "🔍 Running Validation..."
echo "========================================================================"
echo ""

# Run validation script
python3 scripts/validate_phase2_backfill.py \
    --log logs/phase2_full_backfill_v4_stocks_only.log \
    --report logs/phase2_validation_report_v4.md

# Check validation exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ Validation completed successfully!"
    echo "========================================================================"
    echo ""
    echo "📊 Results:"
    echo "   - Validation Report: logs/phase2_validation_report_v4.md"
    echo "   - Backfill Log: logs/phase2_full_backfill_v4_stocks_only.log"
    echo ""

    # Show summary from validation report
    if [ -f logs/phase2_validation_report_v4.md ]; then
        echo "📄 Validation Summary:"
        grep -A 5 "## Executive Summary" logs/phase2_validation_report_v4.md
    fi
else
    echo ""
    echo "========================================================================"
    echo "❌ Validation failed!"
    echo "========================================================================"
    echo ""
    echo "Check logs/phase2_full_backfill_v4_stocks_only.log for errors"
fi

echo ""
echo "🏁 Auto-validation completed at $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
