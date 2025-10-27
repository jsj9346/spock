#!/bin/bash
#
# Full Pipeline Execution Script - Stage 1 Pre-Filter
#
# Purpose: Execute full pipeline run (2,663 tickers through Stage 1 filter)
# Expected: ~135 high-quality tickers output (~5% pass rate)
# Runtime: ~5-6 minutes
#
# Usage:
#   bash run_full_pipeline.sh           # Execute with progress display
#   bash run_full_pipeline.sh --silent  # Execute without progress display
#

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Spock Trading System${NC}"
echo -e "${BLUE}Full Pipeline Run - Stage 1${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}[1/4] Pre-flight Checks${NC}"
echo -n "  - Checking date/time... "
CURRENT_DAY=$(date +%u)  # 1=Monday, 7=Sunday
CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_DAY" -ge 6 ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}ERROR: Today is weekend. Market is closed.${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} ($(date '+%Y-%m-%d %A %H:%M KST'))"

echo -n "  - Checking database... "
DB_PATH="data/spock_local.db"
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}ERROR: Database not found at $DB_PATH${NC}"
    exit 1
fi
STAGE0_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM filter_cache_stage0 WHERE region='KR' AND stage0_passed=1;" 2>/dev/null || echo "0")
if [ "$STAGE0_COUNT" -eq 0 ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}ERROR: No Stage 0 data found. Run scanner.py first.${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} ($STAGE0_COUNT Stage 0 tickers)"

echo -n "  - Checking OHLCV data... "
OHLCV_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE timeframe='D';" 2>/dev/null || echo "0")
if [ "$OHLCV_COUNT" -lt 2000 ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}ERROR: Insufficient OHLCV data ($OHLCV_COUNT tickers). Run data collector first.${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} ($OHLCV_COUNT tickers with data)"

echo -n "  - Checking disk space... "
AVAILABLE_MB=$(df -m data/ | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_MB" -lt 500 ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}ERROR: Insufficient disk space (${AVAILABLE_MB}MB available, 500MB required)${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} (${AVAILABLE_MB}MB available)"

echo ""

# Execute pipeline
echo -e "${YELLOW}[2/4] Executing Stage 1 Pipeline${NC}"
echo "  Input: $STAGE0_COUNT tickers"
echo "  Expected Output: ~135 tickers (5% pass rate)"
echo "  Estimated Runtime: ~5-6 minutes"
echo ""

START_TIME=$(date +%s)

if [ "$1" == "--silent" ]; then
    python3 modules/stock_pre_filter.py --force-refresh --region KR > /dev/null 2>&1
    EXIT_CODE=$?
else
    python3 modules/stock_pre_filter.py --force-refresh --region KR
    EXIT_CODE=$?
fi

END_TIME=$(date +%s)
RUNTIME=$((END_TIME - START_TIME))

echo ""

if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}[ERROR] Pipeline execution failed (exit code: $EXIT_CODE)${NC}"
    exit $EXIT_CODE
fi

# Validate results
echo -e "${YELLOW}[3/4] Validating Results${NC}"
echo -n "  - Checking Stage 1 cache... "
STAGE1_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM filter_cache_stage1 WHERE region='KR' AND stage1_passed=1;" 2>/dev/null || echo "0")
if [ "$STAGE1_COUNT" -eq 0 ]; then
    echo -e "${RED}FAIL${NC}"
    echo -e "${RED}WARNING: No tickers passed Stage 1 filter. Check filter thresholds.${NC}"
else
    echo -e "${GREEN}OK${NC} ($STAGE1_COUNT tickers passed)"
fi

echo -n "  - Checking execution log... "
LOG_EXISTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM filter_execution_log WHERE stage=1 AND region='KR' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null || echo "0")
if [ "$LOG_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} (Execution not logged)"
fi

echo ""

# Display summary
echo -e "${YELLOW}[4/4] Execution Summary${NC}"
echo "  ================================================"
echo "  Stage 0 Input:     $STAGE0_COUNT tickers"
echo "  Stage 1 Output:    $STAGE1_COUNT tickers"
PASS_RATE=$(echo "scale=2; $STAGE1_COUNT * 100 / $STAGE0_COUNT" | bc)
echo "  Pass Rate:         ${PASS_RATE}%"
echo "  Runtime:           ${RUNTIME}s (~$((RUNTIME/60))m)"
echo "  ================================================"
echo ""

# Display top 10 tickers
if [ "$STAGE1_COUNT" -gt 0 ]; then
    echo -e "${GREEN}Top 10 Tickers:${NC}"
    python3 -c "
from modules.stock_pre_filter import StockPreFilter
import logging
logging.getLogger().setLevel(logging.WARNING)

pf = StockPreFilter()
results = pf.run_stage1_filter()

print('Ticker Name                 MA5        MA20       RSI    ')
print('='*60)
for i, t in enumerate(results[:10], 1):
    print(f'{t[\"ticker\"]:6s} {t[\"name\"]:20s} {t.get(\"ma5\",0):>10.0f} {t.get(\"ma20\",0):>10.0f} {t.get(\"rsi_14\",0):>6.1f}')
" 2>/dev/null || echo "  (Unable to display top tickers)"
    echo ""
fi

# Final status
if [ "$STAGE1_COUNT" -ge 80 ] && [ "$STAGE1_COUNT" -le 200 ]; then
    echo -e "${GREEN}✅ Pipeline execution completed successfully!${NC}"
    echo -e "${GREEN}✅ Output count within expected range (80-200 tickers)${NC}"
    echo ""
    echo "Next Steps:"
    echo "  1. Review top 20 tickers manually"
    echo "  2. Proceed to Stage 2 (LayeredScoringEngine)"
    echo "  3. Generate comprehensive execution report"
    exit 0
elif [ "$STAGE1_COUNT" -lt 80 ] && [ "$STAGE1_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Pipeline completed with low output count${NC}"
    echo -e "${YELLOW}⚠️  Output: $STAGE1_COUNT tickers (below expected 80-200 range)${NC}"
    echo ""
    echo "Possible Causes:"
    echo "  - Bearish market conditions (majority of stocks in downtrend)"
    echo "  - Strict filter thresholds"
    echo ""
    echo "Recommendations:"
    echo "  1. Manually review output tickers for quality"
    echo "  2. Consider loosening RSI range (currently 30-70)"
    echo "  3. Proceed to Stage 2 if tickers meet quality standards"
    exit 0
elif [ "$STAGE1_COUNT" -gt 200 ]; then
    echo -e "${GREEN}✅ Pipeline completed with high output count${NC}"
    echo -e "${GREEN}✅ Output: $STAGE1_COUNT tickers (above expected 80-200 range)${NC}"
    echo ""
    echo "Market Conditions:"
    echo "  - Strong bullish trend detected"
    echo "  - Many stocks meeting technical criteria"
    echo ""
    echo "Recommendations:"
    echo "  1. Proceed to Stage 2 (scoring will further filter)"
    echo "  2. Consider tightening thresholds for future runs"
    exit 0
else
    echo -e "${RED}❌ Pipeline execution failed or produced no output${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check logs for errors"
    echo "  2. Verify Stage 0 data quality"
    echo "  3. Review filter thresholds in config/market_filters/KR.yml"
    exit 1
fi
