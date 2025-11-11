#!/bin/bash
# test_full_integration.sh
# 전체 프로젝트 통합 테스트 스크립트

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Quant Platform CLI - Full Integration Test Suite        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test function
run_test() {
  local test_name=$1
  local test_command=$2

  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "Running: $test_name ... "

  if eval "$test_command" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
  else
    echo -e "${RED}✗ FAIL${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
  fi
}

echo "═══════════════════════════════════════════════════════════"
echo "Sprint 1: Foundation + Quick Win"
echo "═══════════════════════════════════════════════════════════"

run_test "Database Connection" "python3 -c 'import asyncio; from cli.utils.database import DatabaseManager; asyncio.run(DatabaseManager().connect())'"

run_test "Query Builder" "python3 -c 'import asyncio; from cli.utils.database import DatabaseManager; from cli.utils.query_builder import QueryBuilder; asyncio.run(QueryBuilder(DatabaseManager()).tickers(\"KR\").execute())'"

run_test "CLI Query" "python3 quant_platform.py query --region KR --top 5"

run_test "Rich Formatting" "python3 quant_platform.py query --region KR --top 5 | grep -q '┏━━━'"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 2: Enhanced Screening"
echo "═══════════════════════════════════════════════════════════"

run_test "Advanced Filters" "python3 quant_platform.py query --region KR --filter 'market_cap > 1000000000' --top 10"

run_test "CSV Export" "python3 quant_platform.py query --region KR --output test_export.csv && rm test_export.csv"

run_test "Multiple Metrics" "python3 quant_platform.py query --region KR --with-technicals rsi_14 --top 5"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 3: Backtest Foundation"
echo "═══════════════════════════════════════════════════════════"

run_test "vectorbt Installation" "python3 -c 'import vectorbt as vbt'"

run_test "Simple Backtest" "python3 quant_platform.py backtest 005930 --start 2020-01-01 --end 2021-12-31"

run_test "Strategy Selection" "python3 quant_platform.py backtest 005930 --strategy momentum --start 2020-01-01 --end 2021-12-31"

run_test "Metrics Calculation" "python3 quant_platform.py backtest 005930 --metrics all --start 2020-01-01 --end 2021-12-31"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 4: HTML Reports"
echo "═══════════════════════════════════════════════════════════"

run_test "Template Rendering" "python3 -c 'from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader(\"cli/templates\")); env.get_template(\"backtest_report.html\")'"

run_test "Plotly Charts" "python3 -c 'import vectorbt as vbt; import pandas as pd; from cli.utils.charts import create_equity_curve; price = pd.Series([100, 105], index=pd.date_range(\"2020-01-01\", periods=2)); portfolio = vbt.Portfolio.from_holding(price, init_cash=100_000_000); create_equity_curve(portfolio)'"

run_test "HTML Report Generation" "python3 quant_platform.py backtest 005930 --strategy momentum --start 2020-01-01 --end 2021-12-31 --html --output test_report.html && rm test_report.html"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 5: Interactive Shell"
echo "═══════════════════════════════════════════════════════════"

run_test "Shell Startup" "python3 -c 'from cli.shell import QuantShell; QuantShell()'"

run_test "Session Management" "python3 -c 'from cli.shell import QuantShell; import pickle; shell = QuantShell(); shell.current_filters = [\"test\"]; import os; os.makedirs(\"sessions\", exist_ok=True); pickle.dump({\"filters\": shell.current_filters}, open(\"sessions/test.pkl\", \"wb\"))'"

run_test "Command Execution" "echo 'query --region KR --top 5\nexit' | python3 quant_platform.py shell"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 6: Final Polish"
echo "═══════════════════════════════════════════════════════════"

run_test "Query Performance (<100ms)" "python3 -c 'import asyncio, time; from cli.utils.database import DatabaseManager; from cli.utils.query_builder import QueryBuilder; asyncio.run(QueryBuilder(DatabaseManager()).tickers(\"KR\").execute()); assert time.time() < 0.1'"

run_test "Error Handling" "python3 quant_platform.py query --region INVALID 2>&1 | grep -q 'Invalid region'"

run_test "Documentation" "python3 quant_platform.py --help | grep -q 'Quant Platform'"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Test Summary"
echo "═══════════════════════════════════════════════════════════"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo "Success Rate: $((PASSED_TESTS * 100 / TOTAL_TESTS))%"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
  echo -e "${GREEN}🎉 All tests passed! Project is ready for deployment.${NC}"
  exit 0
else
  echo -e "${RED}❌ Some tests failed. Please fix the issues before deploying.${NC}"
  exit 1
fi
