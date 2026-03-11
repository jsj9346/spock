#!/usr/bin/env python3
"""
Liquidity Factor Strategy Backtest (vectorbt)

검증된 Liquidity 팩터 기반 롱-온리 전략을 vectorbt로 백테스팅합니다.

전략 로직:
1. 매월 말 Liquidity 팩터 계산 (평균 거래량 / 시가총액)
2. Liquidity가 높은(거래량 많은) 상위 20% 종목 선택
3. 동일 가중 포트폴리오 구성
4. 월간 리밸런싱

IC 검증 결과:
- Pearson IC: -0.0485
- Spearman IC: -0.0441
- t-stat: -2.61
- p-value: 0.0092 ✅ (통계적 유의미)

사용법:
    # 기본 백테스트 (2022-2024, 1억원 초기 자본)
    python3 scripts/backtest_liquidity_strategy.py

    # 커스텀 파라미터
    python3 scripts/backtest_liquidity_strategy.py \
      --start-date 2022-01-01 \
      --end-date 2024-12-31 \
      --capital 100000000 \
      --top-pct 0.2 \
      --rebalance-freq M

Author: Spock Quant Platform
Date: 2025-11-12
"""

import sys
from pathlib import Path
from datetime import datetime
import argparse
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.strategies.liquidity_factor_strategy import LiquidityFactorStrategy
from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def convert_signals_to_vectorbt_format(
    signals_df: pd.DataFrame,
    all_dates: pd.DatetimeIndex
) -> tuple[dict, dict]:
    """
    전략 신호를 vectorbt 형식으로 변환 (entry + exit)

    Args:
        signals_df: LiquidityFactorStrategy.generate_signals() 출력
                   columns: ['date', 'ticker', 'signal', 'liquidity_score', 'rank']
        all_dates: 전체 거래일 인덱스

    Returns:
        (entries, exits) - 둘 다 {ticker: pd.Series(bool)}
        - entries: 리밸런싱 날짜에 True (매수)
        - exits: 다음 리밸런싱 전날에 True (매도)
    """
    entries = {}
    exits = {}

    # 날짜별로 그룹화
    signals_by_date = signals_df.groupby('date')['ticker'].apply(list).to_dict()

    # 리밸런싱 날짜 리스트 추출 (정렬)
    rebalance_dates = sorted([pd.Timestamp(d) for d in signals_by_date.keys()])

    # 모든 티커 추출
    all_tickers = signals_df['ticker'].unique()

    logger.info(f"📊 신호 변환: {len(all_tickers)}개 고유 종목, {len(rebalance_dates)}개 리밸런싱 날짜")

    # 각 티커별로 entry/exit 시리즈 생성
    for ticker in all_tickers:
        # 초기값: 모두 False
        entry_series = pd.Series(False, index=all_dates)
        exit_series = pd.Series(False, index=all_dates)

        # 리밸런싱 날짜별로 신호 설정
        for i, rebal_date in enumerate(rebalance_dates):
            # 해당 리밸런싱에서 이 종목이 선택되었는지 확인
            selected_tickers = signals_by_date.get(rebal_date.date(), [])

            if ticker in selected_tickers:
                # Entry 신호: 리밸런싱 날짜에 매수
                try:
                    entry_idx = all_dates.get_loc(rebal_date)
                    entry_series.iloc[entry_idx] = True
                except KeyError:
                    # 리밸런싱 날짜가 거래일이 아니면 다음 거래일 사용
                    future_dates = all_dates[all_dates >= rebal_date]
                    if len(future_dates) > 0:
                        nearest_date = future_dates[0]
                        entry_idx = all_dates.get_loc(nearest_date)
                        entry_series.iloc[entry_idx] = True

                # Exit 신호: 다음 리밸런싱 직전에 매도
                if i < len(rebalance_dates) - 1:
                    # 다음 리밸런싱 날짜
                    next_rebal_date = rebalance_dates[i + 1]

                    # 다음 리밸런싱 전날 찾기
                    prev_dates = all_dates[all_dates < next_rebal_date]
                    if len(prev_dates) > 0:
                        exit_date = prev_dates[-1]  # 직전 거래일
                        exit_idx = all_dates.get_loc(exit_date)
                        exit_series.iloc[exit_idx] = True
                else:
                    # 마지막 리밸런싱이면 백테스트 종료일에 청산
                    exit_series.iloc[-1] = True

        entries[ticker] = entry_series
        exits[ticker] = exit_series

    logger.info(f"✅ Entry 신호: {sum(s.sum() for s in entries.values())}개")
    logger.info(f"✅ Exit 신호: {sum(s.sum() for s in exits.values())}개")

    return entries, exits


def backtest_liquidity_strategy(
    start_date: str = '2022-01-01',
    end_date: str = '2024-12-31',
    initial_capital: float = 100_000_000,
    top_pct: float = 0.2,
    rebalance_freq: str = 'M',
    transaction_cost: float = 0.003
) -> dict:
    """
    Liquidity 팩터 전략 백테스트 실행

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        initial_capital: 초기 자본 (KRW)
        top_pct: 상위 선택 비율 (0.2 = 상위 20%)
        rebalance_freq: 리밸런싱 주기 ('M' = 월말, 'Q' = 분기말)
        transaction_cost: 거래 비용 (0.003 = 0.3%)

    Returns:
        백테스트 결과 딕셔너리
    """
    logger.info("=" * 80)
    logger.info("LIQUIDITY FACTOR STRATEGY BACKTEST (vectorbt)")
    logger.info("=" * 80)
    logger.info(f"기간: {start_date} ~ {end_date}")
    logger.info(f"초기 자본: ₩{initial_capital:,.0f}")
    logger.info(f"상위 선택: {top_pct*100:.0f}% (상위 {top_pct*100:.0f}%)")
    logger.info(f"리밸런싱: {rebalance_freq} (M=월말, Q=분기말)")
    logger.info(f"거래 비용: {transaction_cost*100:.2f}% (편도)")
    logger.info("")
    logger.info("팩터 검증 결과:")
    logger.info("  Pearson IC:  -0.0485")
    logger.info("  Spearman IC: -0.0441")
    logger.info("  t-stat:      -2.61")
    logger.info("  p-value:      0.0092 ✅")
    logger.info("=" * 80)
    logger.info("")

    # 1. 전략 초기화 및 신호 생성
    logger.info("🚀 Step 1: 전략 신호 생성")
    strategy = LiquidityFactorStrategy(
        top_pct=top_pct,
        rebalance_freq=rebalance_freq,
        transaction_cost=transaction_cost
    )

    signals_df = strategy.generate_signals(
        region='KR',
        start_date=start_date,
        end_date=end_date
    )

    if signals_df.empty:
        logger.error("❌ 신호 생성 실패")
        return {}

    logger.info(f"✅ 신호 생성 완료: {len(signals_df)}개")
    logger.info(f"   고유 종목: {signals_df['ticker'].nunique()}개")
    logger.info(f"   리밸런싱: {signals_df['date'].nunique()}회")
    logger.info("")

    # 2. 가격 데이터 로드
    logger.info("📊 Step 2: 가격 데이터 로드")
    db = PostgresDatabaseManager()

    # 전체 거래일 인덱스 생성
    date_query = """
        SELECT DISTINCT date
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date BETWEEN %s AND %s
        ORDER BY date
    """
    date_result = db.execute_query(date_query, (start_date, end_date))
    all_dates = pd.DatetimeIndex([row['date'] for row in date_result])

    logger.info(f"✅ 거래일: {len(all_dates)}일 ({all_dates[0].date()} ~ {all_dates[-1].date()})")

    # 선택된 종목의 가격 데이터 로드
    unique_tickers = signals_df['ticker'].unique().tolist()

    vbt_adapter = VectorBTAdapter(
        initial_capital=initial_capital,
        commission=transaction_cost,
        slippage=0.0,  # 이미 transaction_cost에 포함
        freq='1D'
    )

    price_data = vbt_adapter.load_data(
        tickers=unique_tickers,
        region='KR',
        start_date=start_date,
        end_date=end_date,
        columns=['close']
    )

    if not price_data:
        logger.error("❌ 가격 데이터 로드 실패")
        return {}

    logger.info(f"✅ 가격 데이터 로드 완료: {len(price_data)}개 종목")
    logger.info("")

    # 3. 가격 데이터 인덱스 생성 및 정렬
    logger.info("🔄 Step 3: 가격 데이터 인덱스 통합 및 정렬")

    # 모든 가격 데이터의 날짜 인덱스를 통합
    price_dates = set()
    for ticker, df in price_data.items():
        price_dates.update(df.index)

    # 정렬된 DatetimeIndex 생성
    unified_index = pd.DatetimeIndex(sorted(price_dates))
    logger.info(f"✅ 통합 인덱스: {len(unified_index)}일 ({unified_index[0].date()} ~ {unified_index[-1].date()})")

    # 모든 가격 데이터를 통합 인덱스로 재정렬 (누락 날짜는 NaN으로 채움)
    logger.info("🔄 가격 데이터 재정렬 중...")
    for ticker in price_data.keys():
        price_data[ticker] = price_data[ticker].reindex(unified_index)

    logger.info(f"✅ 모든 종목 데이터를 {len(unified_index)}일로 통일")
    logger.info("")

    # 4. 신호를 vectorbt 형식으로 변환 (통합 인덱스 사용)
    logger.info("🔄 Step 4: 신호 형식 변환 (Entry + Exit)")
    entries, exits = convert_signals_to_vectorbt_format(signals_df, unified_index)
    logger.info(f"✅ 변환 완료: {len(entries)}개 종목")
    logger.info("")

    # 5. vectorbt 백테스트 실행
    logger.info("⚡ Step 5: vectorbt 백테스트 실행 (리밸런싱 포함)")

    # Close price 데이터프레임 생성
    import vectorbt as vbt
    close_prices = pd.DataFrame({
        ticker: df['close'] for ticker, df in price_data.items()
    })

    # Entry/Exit 데이터프레임 생성
    entries_df = pd.DataFrame({
        ticker: entries[ticker] for ticker in entries.keys()
    })
    exits_df = pd.DataFrame({
        ticker: exits[ticker] for ticker in exits.keys()
    })

    # 동일 가중 포트폴리오: 각 리밸런싱 시점에 size 계산
    logger.info("🔧 동일 가중 포트폴리오 size 계산 중...")

    # 각 날짜별로 선택된 종목 수를 기반으로 동적 size 계산
    sizes_df = pd.DataFrame(index=unified_index, columns=close_prices.columns, dtype=float)
    sizes_df[:] = 0.0  # 초기값: 모두 0

    # 리밸런싱 날짜마다 동일 가중 계산
    for date in unified_index:
        # 이 날짜에 entry 신호가 있는 종목들
        entries_today = entries_df.loc[date]
        tickers_to_buy = entries_today[entries_today].index.tolist()

        if len(tickers_to_buy) > 0:
            # 동일 가중: 각 종목에 총 자본의 1/N
            target_value_per_stock = initial_capital / len(tickers_to_buy)

            for ticker in tickers_to_buy:
                price = close_prices.loc[date, ticker]
                if pd.notna(price) and price > 0:
                    # 살 수 있는 주식 수 (수수료 고려 전)
                    shares = target_value_per_stock / price
                    sizes_df.loc[date, ticker] = shares

    total_entry_sizes = (sizes_df > 0).sum().sum()
    logger.info(f"✅ 동일 가중 size 계산 완료: {total_entry_sizes}개 매수 신호")

    # 포트폴리오 시뮬레이션 (동일 가중 size 사용)
    portfolio = vbt.Portfolio.from_signals(
        close=close_prices,
        entries=entries_df,
        exits=exits_df,
        size=sizes_df,  # 미리 계산된 주식 수
        size_type='amount',  # 주식 수 직접 지정
        init_cash=initial_capital,
        fees=transaction_cost,
        slippage=0.0,
        freq='1D',
        group_by=True,  # 모든 종목을 하나의 포트폴리오로 그룹화
        cash_sharing=True  # 현금을 공유하여 포트폴리오 레벨 관리
    )

    logger.info("✅ 백테스트 완료")
    logger.info("")

    # 6. 성능 메트릭 계산
    logger.info("📈 Step 6: 성능 메트릭 계산")

    # Get trades for analysis
    trades = portfolio.trades.records_readable

    # Calculate comprehensive metrics (using _extract_scalar for Series values)
    metrics = {
        # Return metrics
        'total_return': _extract_scalar(portfolio.total_return()),
        'annualized_return': _extract_scalar(portfolio.annualized_return()),
        'cumulative_returns': portfolio.cumulative_returns(),

        # Risk metrics
        'sharpe_ratio': _extract_scalar(portfolio.sharpe_ratio()),
        'sortino_ratio': _extract_scalar(portfolio.sortino_ratio()),
        'calmar_ratio': _extract_scalar(portfolio.calmar_ratio()),
        'max_drawdown': _extract_scalar(portfolio.max_drawdown()),
        'volatility': _extract_scalar(portfolio.annualized_volatility()),

        # Trade metrics
        'total_trades': len(trades) if trades is not None else 0,
        'win_rate': (trades['PnL'] > 0).mean() if len(trades) > 0 else 0.0,
        'profit_factor': trades[trades['PnL'] > 0]['PnL'].sum() / abs(trades[trades['PnL'] < 0]['PnL'].sum()) if len(trades[trades['PnL'] < 0]) > 0 else 0.0,
        'avg_trade_return': trades['Return'].mean() if len(trades) > 0 else 0.0,

        # Capital metrics
        'initial_capital': initial_capital,
        'final_value': _extract_scalar(portfolio.final_value()),
    }

    metrics['total_profit'] = metrics['final_value'] - initial_capital

    logger.info("✅ 메트릭 계산 완료")
    logger.info(f"   총 거래: {metrics['total_trades']}개")
    logger.info(f"   최종 가치: ₩{metrics['final_value']:,.0f}")
    logger.info("")

    return {
        'portfolio': portfolio,
        'metrics': metrics,
        'signals': signals_df,
        'strategy': strategy
    }


def _extract_scalar(value):
    """vectorbt가 반환하는 Series 객체를 스칼라로 변환"""
    if hasattr(value, 'iloc'):
        return float(value.iloc[0])
    elif hasattr(value, 'values'):
        return float(value.values[0]) if len(value.values) > 0 else 0.0
    else:
        return float(value)


def print_performance_report(metrics: dict):
    """성능 보고서 출력"""

    # 모든 메트릭을 스칼라로 변환
    scalar_metrics = {}
    for key, value in metrics.items():
        if key == 'cumulative_returns':
            # cumulative_returns는 시계열이므로 마지막 값만 사용
            continue
        try:
            scalar_metrics[key] = _extract_scalar(value)
        except (AttributeError, ValueError, TypeError):
            scalar_metrics[key] = value

    logger.info("=" * 80)
    logger.info("백테스트 성능 보고서")
    logger.info("=" * 80)
    logger.info("")

    logger.info("📊 포트폴리오 요약:")
    logger.info(f"  초기 자본:         ₩{scalar_metrics['initial_capital']:>15,.0f}")
    logger.info(f"  최종 가치:         ₩{scalar_metrics['final_value']:>15,.0f}")
    logger.info(f"  총 수익:           ₩{scalar_metrics['total_profit']:>15,.0f}")
    logger.info("")

    logger.info("📈 수익률 메트릭:")
    logger.info(f"  총 수익률:         {scalar_metrics['total_return']*100:>10.2f}%")
    logger.info(f"  연환산 수익률:     {scalar_metrics['annualized_return']*100:>10.2f}%")
    logger.info(f"  연환산 변동성:     {scalar_metrics['volatility']*100:>10.2f}%")
    logger.info("")

    logger.info("⚖️ 위험 조정 성과:")
    logger.info(f"  샤프 비율:         {scalar_metrics['sharpe_ratio']:>10.2f}")
    logger.info(f"  소르티노 비율:     {scalar_metrics['sortino_ratio']:>10.2f}")
    logger.info(f"  칼마 비율:         {scalar_metrics['calmar_ratio']:>10.2f}")
    logger.info("")

    logger.info("📉 위험 메트릭:")
    logger.info(f"  최대 낙폭:         {scalar_metrics['max_drawdown']*100:>10.2f}%")
    logger.info("")

    logger.info("💰 거래 분석:")
    logger.info(f"  총 거래 수:        {scalar_metrics['total_trades']:>10.0f}개")
    logger.info(f"  승률:              {scalar_metrics['win_rate']*100:>10.2f}%")
    logger.info(f"  이익 팩터:         {scalar_metrics['profit_factor']:>10.2f}")
    logger.info(f"  평균 거래 수익률:  {scalar_metrics['avg_trade_return']*100:>10.2f}%")
    logger.info("")

    logger.info("=" * 80)
    logger.info("")

    # 성능 평가
    logger.info("🎯 성능 평가:")

    # 샤프 비율
    sharpe = scalar_metrics['sharpe_ratio']
    if sharpe >= 1.5:
        logger.info(f"  ⭐⭐⭐ 우수 - 샤프 비율 {sharpe:.2f} (목표 1.5 초과)")
    elif sharpe >= 1.0:
        logger.info(f"  ⭐⭐ 양호 - 샤프 비율 {sharpe:.2f} (업계 표준 1.0 초과)")
    else:
        logger.info(f"  ⚠️ 미흡 - 샤프 비율 {sharpe:.2f} (1.0 미만)")

    # 최대 낙폭
    max_dd = abs(scalar_metrics['max_drawdown'] * 100)
    if max_dd <= 15:
        logger.info(f"  ✅ 위험 통제 - 최대 낙폭 {max_dd:.1f}% (목표 15% 이내)")
    else:
        logger.info(f"  ⚠️ 고위험 - 최대 낙폭 {max_dd:.1f}% (목표 15% 초과)")

    # 연환산 수익률
    annual_ret = scalar_metrics['annualized_return'] * 100
    if annual_ret >= 15:
        logger.info(f"  ✅ 강한 수익 - 연환산 {annual_ret:.1f}% (목표 15% 초과)")
    elif annual_ret >= 8:
        logger.info(f"  ✅ 시장 초과 - 연환산 {annual_ret:.1f}% (KOSPI ~8% 초과)")
    else:
        logger.info(f"  ⚠️ 저조 - 연환산 {annual_ret:.1f}% (KOSPI 벤치마크 미달)")

    logger.info("=" * 80)


def save_results(results: dict, output_dir: str = 'backtest_results'):
    """백테스트 결과 저장"""

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 1. 신호 데이터 저장
    signals_path = output_path / f"liquidity_signals_{timestamp}.csv"
    results['signals'].to_csv(signals_path, index=False)
    logger.info(f"💾 신호 저장: {signals_path}")

    # 2. 포트폴리오 가치 저장
    portfolio_value = results['portfolio'].value()
    value_path = output_path / f"liquidity_portfolio_value_{timestamp}.csv"
    portfolio_value.to_csv(value_path)
    logger.info(f"💾 포트폴리오 가치 저장: {value_path}")

    # 3. 메트릭 저장
    metrics_df = pd.DataFrame([results['metrics']])
    metrics_path = output_path / f"liquidity_metrics_{timestamp}.csv"
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"💾 메트릭 저장: {metrics_path}")

    logger.info("")
    logger.info(f"✅ 모든 결과 저장 완료: {output_dir}/")


def main():
    """메인 실행"""
    parser = argparse.ArgumentParser(
        description='Liquidity Factor Strategy Backtest (vectorbt)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 백테스트
  python3 scripts/backtest_liquidity_strategy.py

  # 커스텀 기간
  python3 scripts/backtest_liquidity_strategy.py --start-date 2023-01-01 --end-date 2024-12-31

  # 커스텀 파라미터
  python3 scripts/backtest_liquidity_strategy.py \\
    --start-date 2022-01-01 \\
    --end-date 2024-12-31 \\
    --capital 100000000 \\
    --top-pct 0.2 \\
    --rebalance-freq M
        """
    )

    parser.add_argument('--start-date', type=str, default='2022-01-01',
                       help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31',
                       help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000,
                       help='초기 자본 (KRW, 기본값: 1억)')
    parser.add_argument('--top-pct', type=float, default=0.2,
                       help='상위 선택 비율 (기본값: 0.2 = 상위 20%%)')
    parser.add_argument('--rebalance-freq', type=str, default='M',
                       help='리밸런싱 주기 (M=월말, Q=분기말)')
    parser.add_argument('--transaction-cost', type=float, default=0.003,
                       help='거래 비용 (기본값: 0.003 = 0.3%%)')

    args = parser.parse_args()

    # 백테스트 실행
    results = backtest_liquidity_strategy(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.capital,
        top_pct=args.top_pct,
        rebalance_freq=args.rebalance_freq,
        transaction_cost=args.transaction_cost
    )

    if not results:
        logger.error("❌ 백테스트 실패")
        return 1

    # 성능 보고서 출력
    print_performance_report(results['metrics'])

    # 결과 저장
    save_results(results)

    logger.info("✅ 백테스트 완료!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
