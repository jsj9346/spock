#!/usr/bin/env python3
"""
Liquidity Factor Reverse Strategy Backtest (vectorbt)

역방향 Liquidity 팩터 전략: 유동성이 낮은 종목(하위 20%)을 선택

전략 로직:
1. 매월 말 Liquidity 팩터 계산 (평균 거래량 / 시가총액)
2. Liquidity가 낮은(거래량 적은) 하위 20% 종목 선택  ← 역방향
3. 동일 가중 포트폴리오 구성
4. 월간 리밸런싱

가설:
- IC=-0.0485 (음수) → 유동성 높은 종목이 낮은 수익
- 역방향 전략 → 유동성 낮은 종목 선택 → 높은 수익 기대

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


def reverse_signals(signals_df: pd.DataFrame, all_tickers: list, rebalance_dates: list, top_pct: float = 0.2) -> pd.DataFrame:
    """
    전략 신호를 역방향으로 변환 (상위 20% → 하위 20%)

    Args:
        signals_df: 원본 신호 (상위 20% 선택)
        all_tickers: 전체 종목 리스트
        rebalance_dates: 리밸런싱 날짜 리스트
        top_pct: 선택 비율 (기본값 0.2)

    Returns:
        pd.DataFrame: 역방향 신호 (하위 20% 선택)
    """
    logger.info(f"🔄 신호 역방향 변환 시작...")

    reverse_signals = []

    # 날짜별로 그룹화
    signals_by_date = signals_df.groupby('date').apply(
        lambda x: x.set_index('ticker')[['liquidity_score', 'rank']].to_dict('index')
    ).to_dict()

    for rebal_date in rebalance_dates:
        date_key = rebal_date.date() if isinstance(rebal_date, pd.Timestamp) else rebal_date

        # 해당 날짜의 팩터 점수
        if date_key not in signals_by_date:
            continue

        ticker_scores = signals_by_date[date_key]

        # 모든 종목의 liquidity_score 추출
        scores_list = [(ticker, data['liquidity_score']) for ticker, data in ticker_scores.items()]

        if not scores_list:
            continue

        # liquidity_score 기준 오름차순 정렬 (낮은 값 = 낮은 유동성)
        scores_list.sort(key=lambda x: x[1])

        # 하위 20% 선택
        n_select = max(1, int(len(scores_list) * top_pct))
        bottom_tickers = [ticker for ticker, _ in scores_list[:n_select]]

        # 역방향 신호 생성
        for ticker in bottom_tickers:
            reverse_signals.append({
                'date': date_key,
                'ticker': ticker,
                'signal': 1,
                'liquidity_score': ticker_scores[ticker]['liquidity_score'],
                'rank': ticker_scores[ticker]['rank']
            })

    df_reverse = pd.DataFrame(reverse_signals)
    logger.info(f"✅ 역방향 신호 생성 완료: {len(df_reverse)}개")

    return df_reverse


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
                # Entry signal: 리밸런싱 날짜에 매수
                try:
                    entry_idx = all_dates.get_loc(rebal_date)
                    entry_series.iloc[entry_idx] = True
                except KeyError:
                    # 리밸런싱 날짜가 거래일이 아닌 경우 다음 거래일 사용
                    future_dates = all_dates[all_dates >= rebal_date]
                    if len(future_dates) > 0:
                        nearest_date = future_dates[0]
                        entry_idx = all_dates.get_loc(nearest_date)
                        entry_series.iloc[entry_idx] = True

                # Exit signal: 다음 리밸런싱 직전에 매도
                if i < len(rebalance_dates) - 1:
                    next_rebal_date = rebalance_dates[i + 1]
                    # 다음 리밸런싱 전날 찾기
                    prev_dates = all_dates[all_dates < next_rebal_date]
                    if len(prev_dates) > 0:
                        exit_date = prev_dates[-1]
                        exit_idx = all_dates.get_loc(exit_date)
                        exit_series.iloc[exit_idx] = True
                else:
                    # 마지막 리밸런싱: 백테스트 종료 시 매도
                    exit_series.iloc[-1] = True

        entries[ticker] = entry_series
        exits[ticker] = exit_series

    # 통계 출력
    total_entries = sum([s.sum() for s in entries.values()])
    total_exits = sum([s.sum() for s in exits.values()])
    logger.info(f"✅ 변환 완료: Entry {total_entries}개, Exit {total_exits}개")

    return entries, exits


def _extract_scalar(value):
    """vectorbt가 반환하는 Series 객체를 스칼라로 변환"""
    if hasattr(value, 'iloc'):
        return float(value.iloc[0])
    elif hasattr(value, 'values'):
        return float(value.values[0]) if len(value.values) > 0 else 0.0
    else:
        return float(value)


def run_backtest(
    start_date: str = '2022-01-01',
    end_date: str = '2024-12-31',
    initial_capital: float = 100_000_000,
    top_pct: float = 0.2,
    rebalance_freq: str = 'M',
    transaction_cost: float = 0.003,
    region: str = 'KR'
):
    """
    역방향 Liquidity 팩터 전략 백테스트 실행

    Args:
        start_date: 백테스트 시작일
        end_date: 백테스트 종료일
        initial_capital: 초기 자본
        top_pct: 선택 비율 (하위 20%)
        rebalance_freq: 리밸런싱 주기
        transaction_cost: 거래 비용
        region: 시장
    """
    logger.info("=" * 80)
    logger.info("🚀 역방향 Liquidity 팩터 전략 백테스트 (vectorbt)")
    logger.info("=" * 80)
    logger.info(f"📅 기간: {start_date} ~ {end_date}")
    logger.info(f"💰 초기 자본: ₩{initial_capital:,.0f}")
    logger.info(f"📊 선택: 하위 {top_pct*100:.0f}% (역방향)")
    logger.info(f"🔄 리밸런싱: {rebalance_freq}")
    logger.info(f"💸 거래 비용: {transaction_cost*100:.2f}%")
    logger.info("")

    # 1. 전략 초기화 및 신호 생성
    logger.info("📈 Step 1: 전략 신호 생성")
    strategy = LiquidityFactorStrategy(
        top_pct=top_pct,
        rebalance_freq=rebalance_freq,
        transaction_cost=transaction_cost
    )

    # 원본 신호 생성 (상위 20%)
    signals_original = strategy.generate_signals(region, start_date, end_date)

    # 역방향 신호 생성 (하위 20%)
    rebalance_dates = strategy.get_rebalance_dates(start_date, end_date)
    universe = strategy.get_universe(region, start_date, end_date)
    signals = reverse_signals(signals_original, universe, rebalance_dates, top_pct)

    logger.info("")

    # 2. OHLCV 데이터 로드
    logger.info("📊 Step 2: OHLCV 데이터 로드")
    db = PostgresDatabaseManager()

    # 모든 티커 추출
    all_tickers = signals['ticker'].unique().tolist()
    logger.info(f"📌 총 {len(all_tickers)}개 고유 종목")

    # 각 ticker별로 OHLCV 조회
    price_data = {}
    for ticker in all_tickers:
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
              AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """

        result = db.execute_query(query, (ticker, region, start_date, end_date))

        if result:
            df = pd.DataFrame(result)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            price_data[ticker] = df

    logger.info(f"✅ {len(price_data)}개 종목 데이터 로드 완료")
    logger.info("")

    # 3. vectorbt 형식으로 변환
    logger.info("🔧 Step 3: vectorbt 형식 변환")

    # 모든 날짜 인덱스 통합 (DatetimeIndex)
    all_dates_set = set()
    for df in price_data.values():
        all_dates_set.update(df.index)

    unified_index = pd.DatetimeIndex(sorted(all_dates_set))
    logger.info(f"📅 통합 인덱스: {len(unified_index)}개 거래일")

    # Close price DataFrame 생성 (모든 종목 × 모든 날짜)
    close_prices = pd.DataFrame(index=unified_index, columns=all_tickers, dtype=np.float64)

    for ticker, df in price_data.items():
        # 해당 ticker의 close 가격을 통합 인덱스에 맞춰 채움
        # Decimal을 float로 명시적 변환
        close_prices[ticker] = df['close'].astype(float).reindex(unified_index)

    # NaN 처리: forward fill (상장 전 데이터는 NaN 유지)
    close_prices = close_prices.ffill()

    # 최종 float64 타입 보장
    close_prices = close_prices.astype(np.float64)

    logger.info(f"📊 Close 가격 매트릭스: {close_prices.shape}")

    # Entry/Exit 신호 변환
    entries, exits = convert_signals_to_vectorbt_format(signals, unified_index)

    # DataFrame으로 변환
    entries_df = pd.DataFrame(entries, index=unified_index)
    exits_df = pd.DataFrame(exits, index=unified_index)

    # NaN을 False로 채움
    entries_df = entries_df.fillna(False)
    exits_df = exits_df.fillna(False)

    logger.info(f"📊 Entry 신호: {entries_df.shape}, Exit 신호: {exits_df.shape}")
    logger.info("")

    # 4. vectorbt 백테스트 실행
    logger.info("🎯 Step 4: vectorbt 백테스트 실행")

    # vectorbt 임포트
    try:
        import vectorbt as vbt
    except ImportError:
        logger.error("❌ vectorbt가 설치되지 않았습니다.")
        logger.info("설치: pip install vectorbt")
        return

    # 동일 가중 포트폴리오: 각 리밸런싱 시점에 size 계산
    logger.info("🔧 동일 가중 포트폴리오 size 계산 중...")

    sizes_df = pd.DataFrame(index=unified_index, columns=close_prices.columns, dtype=np.float64)
    sizes_df[:] = 0.0

    # 리밸런싱 날짜마다 동일 가중 계산
    for date in unified_index:
        entries_today = entries_df.loc[date]
        tickers_to_buy = entries_today[entries_today].index.tolist()

        if len(tickers_to_buy) > 0:
            # 동일 가중: 각 종목에 총 자본의 1/N
            target_value_per_stock = initial_capital / len(tickers_to_buy)

            for ticker in tickers_to_buy:
                price = close_prices.loc[date, ticker]
                if pd.notna(price) and price > 0:
                    shares = target_value_per_stock / float(price)
                    sizes_df.loc[date, ticker] = shares

    total_entry_sizes = (sizes_df > 0).sum().sum()
    logger.info(f"✅ 동일 가중 size 계산 완료: {total_entry_sizes}개 매수 신호")

    # Portfolio.from_signals 실행
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
        group_by=True,
        cash_sharing=True
    )

    logger.info("✅ 백테스트 완료")
    logger.info("")

    # 5. 결과 분석
    logger.info("📊 Step 5: 결과 분석")
    logger.info("=" * 80)

    # 포트폴리오 가치 시계열
    portfolio_value = portfolio.value()

    # 누적 수익률
    cumulative_returns = portfolio.cumulative_returns()

    # 거래 내역
    trades = portfolio.trades.records_readable

    # 성과 메트릭
    metrics = {
        'total_return': _extract_scalar(portfolio.total_return()),
        'annualized_return': _extract_scalar(portfolio.annualized_return()),
        'cumulative_returns': cumulative_returns,
        'sharpe_ratio': _extract_scalar(portfolio.sharpe_ratio()),
        'sortino_ratio': _extract_scalar(portfolio.sortino_ratio()),
        'calmar_ratio': _extract_scalar(portfolio.calmar_ratio()),
        'max_drawdown': _extract_scalar(portfolio.max_drawdown()),
        'volatility': _extract_scalar(portfolio.annualized_volatility()),
        'total_trades': len(trades) if trades is not None else 0,
        'win_rate': (trades['PnL'] > 0).mean() if len(trades) > 0 else 0.0,
        'profit_factor': trades[trades['PnL'] > 0]['PnL'].sum() / abs(trades[trades['PnL'] < 0]['PnL'].sum()) if len(trades[trades['PnL'] < 0]) > 0 else 0.0,
        'avg_trade_return': trades['Return'].mean() if len(trades) > 0 else 0.0,
        'initial_capital': initial_capital,
        'final_value': _extract_scalar(portfolio.final_value()),
        'total_profit': _extract_scalar(portfolio.final_value()) - initial_capital
    }

    # 출력
    logger.info(f"📈 수익률:")
    logger.info(f"  총 수익률:            {metrics['total_return']*100:.2f}%")
    logger.info(f"  연간 수익률:          {metrics['annualized_return']*100:.2f}%")
    logger.info(f"  최종 자산:            ₩{metrics['final_value']:,.0f}")
    logger.info(f"  총 수익:              ₩{metrics['total_profit']:,.0f}")
    logger.info("")

    logger.info(f"📊 리스크 지표:")
    logger.info(f"  샤프 비율:            {metrics['sharpe_ratio']:.2f}")
    logger.info(f"  소르티노 비율:        {metrics['sortino_ratio']:.2f}")
    logger.info(f"  칼마 비율:            {metrics['calmar_ratio']:.2f}")
    logger.info(f"  최대 낙폭:            {metrics['max_drawdown']*100:.2f}%")
    logger.info(f"  변동성 (연간):        {metrics['volatility']*100:.2f}%")
    logger.info("")

    logger.info(f"💰 거래 분석:")
    logger.info(f"  총 거래 수:           {metrics['total_trades']}개")
    logger.info(f"  승률:                 {metrics['win_rate']*100:.2f}%")
    logger.info(f"  이익 팩터:            {metrics['profit_factor']:.2f}")
    logger.info(f"  평균 거래 수익률:     {metrics['avg_trade_return']*100:.2f}%")
    logger.info("")

    logger.info("=" * 80)

    # 6. 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_dir = project_root / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # 메트릭 저장
    metrics_file = results_dir / f'liquidity_reverse_metrics_{timestamp}.csv'
    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(metrics_file, index=False)
    logger.info(f"💾 메트릭 저장: {metrics_file}")

    # 포트폴리오 가치 저장
    portfolio_file = results_dir / f'liquidity_reverse_portfolio_value_{timestamp}.csv'
    portfolio_value.to_csv(portfolio_file)
    logger.info(f"💾 포트폴리오 가치 저장: {portfolio_file}")

    # 거래 내역 저장
    if len(trades) > 0:
        trades_file = results_dir / f'liquidity_reverse_trades_{timestamp}.csv'
        trades.to_csv(trades_file, index=False)
        logger.info(f"💾 거래 내역 저장: {trades_file}")

    logger.info("")
    logger.info("✅ 백테스트 완료!")

    return metrics, portfolio, trades


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='역방향 Liquidity 팩터 전략 백테스트')
    parser.add_argument('--start-date', type=str, default='2022-01-01', help='시작일 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31', help='종료일 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000, help='초기 자본 (원)')
    parser.add_argument('--top-pct', type=float, default=0.2, help='선택 비율 (하위 %)')
    parser.add_argument('--rebalance-freq', type=str, default='M', choices=['M', 'Q'], help='리밸런싱 주기')
    parser.add_argument('--transaction-cost', type=float, default=0.003, help='거래 비용 (%)')
    parser.add_argument('--region', type=str, default='KR', choices=['KR', 'US'], help='시장')

    args = parser.parse_args()

    run_backtest(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.capital,
        top_pct=args.top_pct,
        rebalance_freq=args.rebalance_freq,
        transaction_cost=args.transaction_cost,
        region=args.region
    )
