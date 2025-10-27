#!/usr/bin/env python3
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()

# Check close out of range
print("Close out of range samples:")
cursor.execute('SELECT ticker, region, date, open, high, low, close FROM ohlcv_data WHERE close < low OR close > high LIMIT 10')
for row in cursor.fetchall():
    ticker, region, date, o, h, l, c = row
    print(f'{ticker} ({region}) {date}: O={o}, H={h}, L={l}, C={c}')
    print(f'  Violation: C={c}, L={l}, H={h}, C-L={c-l:.10f}, H-C={h-c:.10f}')

# Check RSI violations
print("\nRSI violations:")
cursor.execute('SELECT ticker, region, date, rsi_14 FROM ohlcv_data WHERE rsi_14 IS NOT NULL AND (rsi_14 < 0 OR rsi_14 > 100) LIMIT 10')
for row in cursor.fetchall():
    print(f'{row[0]} ({row[1]}) {row[2]}: RSI={row[3]}')

# Check Korean derivative tickers
print("\nKorean derivative tickers (samples):")
cursor.execute("SELECT DISTINCT ticker FROM ohlcv_data WHERE region = 'KR' AND ticker LIKE '%[A-Z]%' LIMIT 20")
for row in cursor.fetchall():
    print(f'  {row[0]}')

conn.close()
