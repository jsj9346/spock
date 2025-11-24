#!/usr/bin/env python3
"""
포트폴리오 가치 시계열 분석

Phase 2.2c-2: 월간 리밸런싱이 제대로 작동하는지 확인
"""

import pandas as pd
import numpy as np
from pathlib import Path

# 최신 결과 파일 경로
results_dir = Path("data/backtest_results")
portfolio_file = list(results_dir.glob("liquidity_portfolio_value_*.csv"))[-1]

print(f"📁 분석 파일: {portfolio_file.name}\n")

# 포트폴리오 가치 로드
df = pd.read_csv(portfolio_file, index_col=0, parse_dates=True)

print("=" * 80)
print("포트폴리오 가치 시계열 분석")
print("=" * 80)
print()

# 1. 기본 정보
print("📊 기본 정보:")
print(f"  기간: {df.index[0].date()} ~ {df.index[-1].date()}")
print(f"  거래일: {len(df)}일")
print(f"  종목 수: {df.shape[1]}개")
print()

# 2. 포트폴리오 총 가치 (모든 종목 합계)
total_value = df.sum(axis=1)
print("📈 포트폴리오 총 가치:")
print(f"  초기: ₩{total_value.iloc[0]:,.0f}")
print(f"  최종: ₩{total_value.iloc[-1]:,.0f}")
print(f"  변화: {(total_value.iloc[-1] / total_value.iloc[0] - 1) * 100:.2f}%")
print(f"  최대: ₩{total_value.max():,.0f} ({total_value.idxmax().date()})")
print(f"  최소: ₩{total_value.min():,.0f} ({total_value.idxmin().date()})")
print()

# 3. 일일 변화율
daily_returns = total_value.pct_change().dropna()
print("📊 일일 수익률 통계:")
print(f"  평균: {daily_returns.mean() * 100:.4f}%")
print(f"  표준편차: {daily_returns.std() * 100:.4f}%")
print(f"  최대 상승: {daily_returns.max() * 100:.2f}% ({daily_returns.idxmax().date()})")
print(f"  최대 하락: {daily_returns.min() * 100:.2f}% ({daily_returns.idxmin().date()})")
print()

# 4. 월별 리밸런싱 검증
# 월말 날짜 추출
month_ends = df.resample('ME').last().index

print("🔄 월간 리밸런싱 검증:")
print(f"  총 리밸런싱 횟수: {len(month_ends)}회")
print()

# 각 월말에 포트폴리오 구성 확인
print("  월말 포트폴리오 구성:")
for i, month_end in enumerate(month_ends[:5]):  # 처음 5개월만
    # 해당 월말의 포지션 개수 (가치 > 0인 종목)
    positions = df.loc[month_end]
    active_positions = (positions > 0).sum()

    print(f"  - {month_end.date()}: {active_positions}개 종목 보유, 총 가치 ₩{positions.sum():,.0f}")

if len(month_ends) > 5:
    print(f"  ... ({len(month_ends) - 5}개월 생략)")
print()

# 5. 종목별 보유 기간 분석
print("📊 종목별 보유 패턴:")
# 각 종목이 보유된 일수
holding_days = (df > 0).sum()
print(f"  평균 보유 일수: {holding_days.mean():.0f}일")
print(f"  최장 보유: {holding_days.max()}일 ({holding_days.idxmax()})")
print(f"  최단 보유: {holding_days.min()}일 ({holding_days.idxmin()})")
print()

# 6. 리밸런싱 전후 변화 확인
print("🔍 리밸런싱 전후 변화 분석:")
rebalance_changes = []
for i in range(len(month_ends) - 1):
    before = month_ends[i]
    after_idx = df.index.get_indexer([month_ends[i]], method='ffill')[0] + 1

    if after_idx < len(df):
        after = df.index[after_idx]

        positions_before = (df.loc[before] > 0).sum()
        positions_after = (df.loc[after] > 0).sum()
        change = positions_after - positions_before

        rebalance_changes.append({
            'date': before.date(),
            'before': positions_before,
            'after': positions_after,
            'change': change
        })

if rebalance_changes:
    changes_df = pd.DataFrame(rebalance_changes)
    print(f"  평균 변화: {changes_df['change'].mean():.1f}개 종목")
    print(f"  최대 증가: +{changes_df['change'].max()}개 ({changes_df.loc[changes_df['change'].idxmax(), 'date']})")
    print(f"  최대 감소: {changes_df['change'].min()}개 ({changes_df.loc[changes_df['change'].idxmin(), 'date']})")
    print()

    # 처음 5회 리밸런싱 상세 정보
    print("  처음 5회 리밸런싱:")
    for _, row in changes_df.head(5).iterrows():
        print(f"  - {row['date']}: {row['before']}개 → {row['after']}개 ({row['change']:+d})")
else:
    print("  리밸런싱 정보 없음")

print()
print("=" * 80)
print("✅ 분석 완료")
