#!/usr/bin/env python3
"""
collect_full_kr_250days.py - Full Historical Data Collection for All KR Tickers

Purpose:
- Collect 250 days of OHLCV data for ALL 3,745 KR tickers
- Uses pagination-enabled _custom_kis_get_ohlcv() method
- Overcomes KIS API 100-row limit with 3-chunk pagination
"""

import sys
import os
import sqlite3
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.kis_data_collector import KISDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

def main():
    print("=" * 80)
    print("KR Market Full Historical Data Collection (250 Days)")
    print("=" * 80)

    # Initialize
    collector = KISDataCollector(db_path='data/spock_local.db', region='KR')
    db = SQLiteDatabaseManager(db_path='data/spock_local.db')

    # Get all KR tickers from database
    conn = sqlite3.connect('data/spock_local.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT ticker FROM ohlcv_data WHERE region = "KR" ORDER BY ticker')
    all_tickers = [row[0] for row in cursor.fetchall()]
    conn.close()

    total_tickers = len(all_tickers)
    print(f"\n📊 총 {total_tickers:,}개 종목 처리 시작...")
    print(f"⏱️  예상 소요 시간: ~{total_tickers * 0.45 / 60:.0f}분")
    print(f"🎯 목표: 종목당 250일 데이터 수집\n")

    # Statistics
    success_count = 0
    failed_count = 0
    insufficient_count = 0
    start_time = time.time()

    # Process each ticker
    for idx, ticker in enumerate(all_tickers, 1):
        try:
            # Use pagination-enabled method
            df = collector._custom_kis_get_ohlcv(ticker=ticker, timeframe='D', count=250)

            if df is not None:
                rows = len(df)

                if rows >= 200:  # Acceptable threshold (200-250 rows)
                    # Calculate technical indicators
                    try:
                        df_with_indicators = collector.calculate_technical_indicators(df, ticker)

                        # Save to database
                        collector.save_to_db(ticker, df_with_indicators, timeframe='D')

                        success_count += 1
                        print(f"✅ [{idx}/{total_tickers}] {ticker}: {rows}행 수집 완료")

                    except Exception as e:
                        failed_count += 1
                        print(f"❌ [{idx}/{total_tickers}] {ticker}: 지표 계산 오류 - {e}")

                else:
                    insufficient_count += 1
                    print(f"⚠️  [{idx}/{total_tickers}] {ticker}: 데이터 부족 ({rows}행)")

            else:
                failed_count += 1
                print(f"❌ [{idx}/{total_tickers}] {ticker}: 데이터 없음")

        except Exception as e:
            failed_count += 1
            print(f"❌ [{idx}/{total_tickers}] {ticker}: 오류 - {e}")

        # Progress logging every 100 tickers
        if idx % 100 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = (total_tickers - idx) * avg_time

            print(f"\n{'='*80}")
            print(f"진행률: {idx}/{total_tickers} ({idx/total_tickers*100:.1f}%)")
            print(f"성공: {success_count}, 부족: {insufficient_count}, 실패: {failed_count}")
            print(f"경과 시간: {elapsed/60:.1f}분, 예상 남은 시간: {remaining/60:.1f}분")
            print(f"{'='*80}\n")

    # Final summary
    total_time = time.time() - start_time

    print("\n" + "=" * 80)
    print("수집 완료!")
    print("=" * 80)
    print(f"총 처리: {total_tickers:,}개")
    print(f"✅ 성공: {success_count:,}개 ({success_count/total_tickers*100:.1f}%)")
    print(f"⚠️  데이터 부족: {insufficient_count:,}개 ({insufficient_count/total_tickers*100:.1f}%)")
    print(f"❌ 실패: {failed_count:,}개 ({failed_count/total_tickers*100:.1f}%)")
    print(f"⏱️  총 소요 시간: {total_time/60:.1f}분")
    print("=" * 80)

    # Database statistics
    print("\n데이터베이스 통계 확인 중...")
    conn = sqlite3.connect('data/spock_local.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region = "KR"')
    total_rows = cursor.fetchone()[0]

    cursor.execute('''
        SELECT AVG(day_count) as avg_days, MIN(day_count) as min_days, MAX(day_count) as max_days
        FROM (
            SELECT COUNT(*) as day_count
            FROM ohlcv_data
            WHERE region = 'KR'
            GROUP BY ticker
        )
    ''')
    avg_days, min_days, max_days = cursor.fetchone()

    cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region = "KR" AND ma200 IS NULL')
    ma200_null = cursor.fetchone()[0]

    conn.close()

    print(f"\n📊 데이터베이스 통계:")
    print(f"  총 OHLCV 행: {total_rows:,}개")
    print(f"  평균 데이터 기간: {avg_days:.1f}일")
    print(f"  최소/최대: {min_days}일 / {max_days}일")
    print(f"  MA200 NULL: {ma200_null:,}개 ({ma200_null/total_rows*100:.2f}%)")

    if avg_days >= 240 and ma200_null / total_rows < 0.01:
        print(f"\n✅ 데이터 품질: EXCELLENT (LayeredScoringEngine 실행 가능)")
    elif avg_days >= 200:
        print(f"\n⚠️  데이터 품질: GOOD (MA 재계산 필요)")
    else:
        print(f"\n❌ 데이터 품질: INSUFFICIENT (추가 수집 필요)")

if __name__ == '__main__':
    main()
