# yfinance Global Market Backfill - Monitoring Commands

## 📊 Overview
- **Target**: ~17,297 global stocks (US, JP, CN, HK, VN)
- **Expected Coverage**: ~50% per region (~8,500 stocks)
- **Estimated Time**: ~1-2 hours (0.5s rate limit)
- **Started**: 2025-10-22 10:49
- **PID**: 82636

---

## 🎯 Quick Start Commands

### 1️⃣ **전체 상황 확인 (추천 - All backfills)**
```bash
./scripts/monitor_backfills.sh
```
Shows unified dashboard for DART, pykrx, and yfinance backfills

### 2️⃣ **yfinance 상세 진행률 확인 (yfinance details)**
```bash
./scripts/monitor_yfinance_backfill.sh
```
Shows detailed yfinance progress with region breakdown and ETA

### 3️⃣ **실시간 자동 갱신 (Auto-refresh every 10 seconds)**
```bash
watch -n 10 ./scripts/monitor_yfinance_backfill.sh
```
Automatically refreshes yfinance dashboard every 10 seconds

---

## 📋 Log Monitoring Commands

### 4️⃣ **실시간 로그 보기 (Real-time log tail)**
```bash
tail -f log/yfinance_production_backfill.log
```
Follow log in real-time (Ctrl+C to exit)

### 5️⃣ **최근 진행 상황 (Last 20 lines)**
```bash
tail -20 log/yfinance_production_backfill.log
```
Show last 20 log entries

### 6️⃣ **진행률만 추출 (Extract progress lines)**
```bash
grep -E "^\[.*\] Processing" log/yfinance_production_backfill.log | tail -5
```
Show last 5 progress indicators (e.g., [123/17297] Processing...)

### 7️⃣ **에러/경고 확인 (Check for errors/warnings)**
```bash
grep -E "(ERROR|❌|WARNING|⚠️)" log/yfinance_production_backfill.log | tail -10
```
Show last 10 errors or warnings

---

## 💾 Database Query Commands

### 8️⃣ **지역별 데이터 현황 (Records by region)**
```bash
psql -d quant_platform -c "
SELECT
    region,
    COUNT(*) as records,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(created_at) as first_inserted,
    MAX(created_at) as last_inserted
FROM ticker_fundamentals
WHERE data_source = 'yfinance'
GROUP BY region
ORDER BY region;
"
```

### 9️⃣ **총 레코드 수 확인 (Total record count)**
```bash
psql -d quant_platform -c "
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(created_at) as started_at,
    MAX(created_at) as latest_at
FROM ticker_fundamentals
WHERE data_source = 'yfinance';
"
```

### 🔟 **데이터 품질 확인 (Data quality check)**
```bash
psql -d quant_platform -c "
SELECT
    region,
    COUNT(*) as records,
    ROUND(AVG(CASE WHEN per IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as per_fill_rate,
    ROUND(AVG(CASE WHEN pbr IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as pbr_fill_rate,
    ROUND(AVG(CASE WHEN market_cap IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as market_cap_fill_rate
FROM ticker_fundamentals
WHERE data_source = 'yfinance'
GROUP BY region
ORDER BY region;
"
```

---

## ⚙️ Process Management Commands

### 1️⃣1️⃣ **프로세스 상태 확인 (Check if running)**
```bash
ps aux | grep backfill_fundamentals_yfinance | grep -v grep
```
Shows yfinance backfill process details (PID, runtime, memory usage)

### 1️⃣2️⃣ **백필 중단 (Stop backfill - if needed)**
```bash
pkill -f "backfill_fundamentals_yfinance"
```
⚠️ **Use only if necessary** - Will stop the backfill process

### 1️⃣3️⃣ **백필 재시작 (Restart backfill - if stopped)**
```bash
nohup python3 scripts/backfill_fundamentals_yfinance.py --rate-limit 0.5 > log/yfinance_production_backfill_RESTART.log 2>&1 & echo $!
```
Restart from where it left off (yfinance script has built-in resume capability)

---

## 📊 Progress Calculation (Manual)

### Extract current progress from log:
```bash
# Get latest progress line
grep -E "^\[.*\] Processing" log/yfinance_production_backfill.log | tail -1

# Example output: [123/17297] Processing US:AAPL...
# Means: 123 tickers processed out of 17,297 total
# Progress: 123/17297 = 0.71% complete
```

### Calculate remaining time:
```bash
# If process started at 10:49 and current time is 11:00 (11 min elapsed)
# And 123 tickers processed
# Speed: 123 tickers / 11 min = 11.2 tickers/min
# Remaining: (17297 - 123) / 11.2 = 1533 minutes ≈ 25.5 hours

# But actual rate limit is 0.5s per ticker = 2 tickers/sec = 120 tickers/min
# So expected time: 17297 tickers / 120 tickers/min = 144 min ≈ 2.4 hours
```

---

## 🎯 Expected Results

### Target Coverage (50% of each market):
| Region | Total Tickers | Target Coverage (50%) | Expected Records |
|--------|---------------|----------------------|------------------|
| US     | 6,532         | 3,266                | 3,266            |
| JP     | 4,036         | 2,018                | 2,018            |
| CN     | 3,450         | 1,725                | 1,725            |
| HK     | 2,722         | 1,361                | 1,361            |
| VN     | 557           | 167 (30%)            | 167              |
| **Total** | **17,297** | **~8,537**           | **~8,537**       |

### Success Metrics:
- **Target Coverage**: ≥50% per region (≥30% for VN)
- **Data Quality**: ≥70% fill rate for PER, PBR, market_cap
- **Error Rate**: <10% (yfinance data availability varies by market)
- **Expected Time**: 1-2 hours

---

## 🚨 Troubleshooting

### If backfill seems slow:
1. Check process is running: `ps aux | grep yfinance`
2. Check CPU usage: `top -p <PID>`
3. Check network: `ping finance.yahoo.com`
4. Review recent errors: `grep ERROR log/yfinance_production_backfill.log | tail -20`

### If backfill stopped unexpectedly:
1. Check exit code in log: `tail -50 log/yfinance_production_backfill.log`
2. Check database connection: `psql -d quant_platform -c "SELECT 1;"`
3. Restart with: `nohup python3 scripts/backfill_fundamentals_yfinance.py --rate-limit 0.5 > log/yfinance_production_backfill_RESTART.log 2>&1 &`

### If seeing many 404 errors:
- **Normal behavior** - Not all tickers in our database have yfinance data
- Expected error rate: 20-40% for CN market, 10-20% for others
- Script will skip these and continue with next ticker

---

## 📝 Notes

1. **Rate Limiting**: 0.5s delay between requests (2 req/sec) - yfinance recommended limit
2. **Data Source**: Yahoo Finance API via yfinance library
3. **Resume Capability**: Script automatically skips already-processed tickers
4. **Metrics Collected**: P/E, P/B, P/S, EV/EBITDA, Market Cap, Dividend Yield, etc.
5. **Data Freshness**: Real-time data from Yahoo Finance (as of today)

---

**Last Updated**: 2025-10-22 10:50
**Status**: Running (PID: 82636)
