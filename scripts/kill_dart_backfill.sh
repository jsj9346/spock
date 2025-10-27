#!/bin/bash
# Safe script to kill DART backfill processes only
# Avoids killing unrelated processes like Claude Code

echo "Searching for DART backfill processes..."

# Method 1: Find only Python processes running the script
PIDS=$(ps aux | grep "python3.*backfill_fundamentals_dart.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "✅ No DART backfill processes found"
    exit 0
fi

echo "Found DART backfill processes:"
ps aux | grep "python3.*backfill_fundamentals_dart.py" | grep -v grep

echo ""
echo "Killing processes: $PIDS"
for pid in $PIDS; do
    kill $pid 2>/dev/null && echo "  ✅ Killed PID $pid" || echo "  ⚠️ Failed to kill PID $pid"
done

# Wait and verify
sleep 2
REMAINING=$(ps aux | grep "python3.*backfill_fundamentals_dart.py" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "✅ All DART backfill processes terminated"
else
    echo "⚠️ Some processes still running:"
    echo "$REMAINING"
    echo ""
    echo "Use 'kill -9' if needed (force kill)"
fi
