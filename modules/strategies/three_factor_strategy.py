#!/usr/bin/env python3
"""
Three-Factor Strategy - Validated Multi-Factor Strategy

검증된 3개 팩터 조합 전략 (Phase 1.4 검증 완료):
1. Max_Drawdown (IC=-0.166, p=0.0002) - 리스크 회피
2. Liquidity (IC=-0.097, p=0.0297) - 유동성 필터
3. Short_Term_Momentum (IC=0.093, p=0.0384) - 모멘텀

전략 로직:
1. 매월 말 3개 팩터 값 계산
2. IC 가중치 기반 복합 점수 산출
3. 복합 점수 상위 N개 종목 선택 (기본 20개)
4. 동일 가중 포트폴리오 구성
5. 월간 리밸런싱

팩터 가중치 (IC 기반):
- Max_Drawdown: |IC| = 0.166 → weight = 0.166 / (0.166 + 0.097 + 0.093) = 46.6%
- Liquidity: |IC| = 0.097 → weight = 0.097 / 0.356 = 27.2%
- Short_Term_Momentum: |IC| = 0.093 → weight = 0.093 / 0.356 = 26.1%

Expected Performance:
- Sharpe Ratio Target: > 1.0
- Max Drawdown Target: < 15%
- Win Rate Target: > 55%

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from loguru import logger

# Factor imports
from modules.factors.momentum_factors import ShortTermMomentumFactor
from modules.factors.low_vol_factors import MaxDrawdownFactor
from modules.factors.size_factors import LiquidityFactor

# Database
from modules.db_manager_postgres import PostgresDatabaseManager


class ThreeFactorStrategy:
    """
    검증된 3개 팩터 조합 전략

    Phase 1.4 검증 결과:
    - Max_Drawdown: IC=-0.166, t=-3.76, p=0.0002 ✅✅ (매우 강력)
    - Liquidity: IC=-0.097, t=-2.18, p=0.0297 ✅ (유의미)
    - Short_Term_Momentum: IC=0.093, t=2.08, p=0.0384 ✅ (유의미)

    Parameters
    ----------
    factor_weights : dict, optional
        팩터 가중치 딕셔너리
        기본값: IC 기반 가중치 {'max_drawdown': 0.466, 'liquidity': 0.272, 'momentum': 0.261}
    top_n : int
        선택할 종목 수 (기본값: 20)
    rebalance_freq : str
        리밸런싱 주기 ('M' = 월말, 'Q' = 분기말)
    transaction_cost : float
        거래 비용 (기본값: 0.003 = 0.3%)
    """

    # IC 기반 기본 가중치 (Phase 1.4 검증 결과)
    DEFAULT_WEIGHTS = {
        'max_drawdown': 0.466,   # |IC| = 0.166
        'liquidity': 0.272,      # |IC| = 0.097
        'momentum': 0.261        # |IC| = 0.093
    }

    def __init__(
        self,
        factor_weights: Optional[Dict[str, float]] = None,
        top_n: int = 20,
        rebalance_freq: str = 'M',
        transaction_cost: float = 0.003
    ):
        """Initialize Three-Factor Strategy"""
        # Factor weights
        self.factor_weights = factor_weights if factor_weights else self.DEFAULT_WEIGHTS.copy()
        self._validate_weights()

        # Strategy parameters
        self.top_n = top_n
        self.rebalance_freq = rebalance_freq
        self.transaction_cost = transaction_cost

        # Initialize factors
        self.momentum_factor = ShortTermMomentumFactor()
        self.max_dd_factor = MaxDrawdownFactor()
        self.liquidity_factor = LiquidityFactor()

        # Database
        self.db = PostgresDatabaseManager()

        logger.info(
            f"✅ Three-Factor 전략 초기화\n"
            f"   - 가중치: MDD={self.factor_weights['max_drawdown']:.3f}, "
            f"Liq={self.factor_weights['liquidity']:.3f}, "
            f"Mom={self.factor_weights['momentum']:.3f}\n"
            f"   - 선택 종목: 상위 {top_n}개\n"
            f"   - 리밸런싱: {rebalance_freq}"
        )

    def _validate_weights(self):
        """팩터 가중치 검증"""
        total = sum(self.factor_weights.values())
        if not np.isclose(total, 1.0, atol=0.01):
            logger.warning(f"⚠️ 가중치 합계가 1.0이 아님: {total:.3f}. 정규화 진행.")
            # Normalize weights
            for key in self.factor_weights:
                self.factor_weights[key] /= total

    def get_universe(
        self,
        region: str = 'KR',
        start_date: str = '2024-01-01',
        end_date: str = '2024-11-30',
        min_data_days: int = 224
    ) -> List[str]:
        """
        투자 유니버스 조회

        Parameters
        ----------
        region : str
            시장 (KR, US)
        start_date : str
            시작 날짜
        end_date : str
            종료 날짜
        min_data_days : int
            최소 데이터 일수 (기본 224일 = 2024년 전체)

        Returns
        -------
        List[str]
            티커 리스트
        """
        query = """
            SELECT ticker, AVG(volume) as avg_volume, COUNT(*) as data_days
            FROM ohlcv_data
            WHERE region = %s
              AND date BETWEEN %s AND %s
              AND volume > 0
            GROUP BY ticker
            HAVING COUNT(*) >= %s
            ORDER BY avg_volume DESC
        """

        # Ensure sufficient data for all factors (Max_Drawdown needs lookback)
        result = self.db.execute_query(
            query,
            (region, start_date, end_date, min_data_days)
        )

        tickers = [row['ticker'] for row in result]

        logger.info(
            f"📊 투자 유니버스: {len(tickers)}개 종목\n"
            f"   - 기간: {start_date} ~ {end_date}\n"
            f"   - 최소 데이터: {min_data_days}일"
        )

        return tickers

    def calculate_factor_scores(
        self,
        tickers: List[str],
        calc_date: datetime,
        region: str = 'KR'
    ) -> pd.DataFrame:
        """
        특정 시점의 3개 팩터 점수 계산

        Parameters
        ----------
        tickers : List[str]
            티커 리스트
        calc_date : datetime
            계산 시점 (월말)
        region : str
            시장

        Returns
        -------
        pd.DataFrame
            columns: ['ticker', 'momentum_score', 'max_dd_score', 'liquidity_score',
                      'composite_score', 'rank']
        """
        scores = []

        # Lookback period for each factor
        # Max_Drawdown: 252 days, Momentum: 60 days, Liquidity: 30 days
        lookback_start = (calc_date - timedelta(days=300)).strftime('%Y-%m-%d')
        calc_date_str = calc_date.strftime('%Y-%m-%d')

        logger.info(f"📅 {calc_date_str} 팩터 계산 중... ({len(tickers)}개 종목)")

        for ticker in tickers:
            # Fetch OHLCV data
            query = """
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s
                  AND date BETWEEN %s AND %s
                ORDER BY date ASC
            """

            data = self.db.execute_query(query, (ticker, region, lookback_start, calc_date_str))

            if len(data) < 60:  # Minimum data requirement
                continue

            # Convert to DataFrame
            df = pd.DataFrame(
                data,
                columns=['date', 'open', 'high', 'low', 'close', 'volume']
            )
            df['date'] = pd.to_datetime(df['date'])

            # Convert Decimal to float (PostgreSQL compatibility)
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df['volume'] = df['volume'].astype(int)

            # Calculate each factor
            momentum_result = self.momentum_factor.calculate(df, ticker)
            max_dd_result = self.max_dd_factor.calculate(df, ticker)
            liquidity_result = self.liquidity_factor.calculate(df, ticker, region)

            # Skip if any factor calculation failed
            if not all([momentum_result, max_dd_result, liquidity_result]):
                continue

            # Extract raw factor values
            momentum_score = momentum_result.raw_value
            max_dd_score = max_dd_result.raw_value
            liquidity_score = liquidity_result.raw_value

            scores.append({
                'ticker': ticker,
                'momentum_score': momentum_score,
                'max_dd_score': max_dd_score,
                'liquidity_score': liquidity_score
            })

        if not scores:
            logger.warning(f"⚠️ {calc_date_str}: 팩터 계산 성공한 종목 없음")
            return pd.DataFrame()

        # Convert to DataFrame
        df_scores = pd.DataFrame(scores)

        # Z-score normalization (cross-sectional)
        for col in ['momentum_score', 'max_dd_score', 'liquidity_score']:
            mean = df_scores[col].mean()
            std = df_scores[col].std()

            if std > 0:
                df_scores[f'{col}_z'] = (df_scores[col] - mean) / std
            else:
                df_scores[f'{col}_z'] = 0.0

        # Calculate composite score (IC-weighted)
        df_scores['composite_score'] = (
            self.factor_weights['momentum'] * df_scores['momentum_score_z'] +
            self.factor_weights['max_drawdown'] * df_scores['max_dd_score_z'] +
            self.factor_weights['liquidity'] * df_scores['liquidity_score_z']
        )

        # Rank by composite score (descending)
        df_scores['rank'] = df_scores['composite_score'].rank(ascending=False, method='first')
        df_scores = df_scores.sort_values('rank').reset_index(drop=True)

        logger.info(
            f"✅ {calc_date_str} 팩터 계산 완료: {len(df_scores)}개 종목\n"
            f"   - Top 1: {df_scores.iloc[0]['ticker']} (점수: {df_scores.iloc[0]['composite_score']:.3f})"
        )

        return df_scores

    def select_portfolio(
        self,
        factor_scores: pd.DataFrame,
        top_n: Optional[int] = None
    ) -> pd.DataFrame:
        """
        복합 점수 기반 포트폴리오 선택

        Parameters
        ----------
        factor_scores : pd.DataFrame
            팩터 점수 데이터
        top_n : int, optional
            선택할 종목 수 (기본값: self.top_n)

        Returns
        -------
        pd.DataFrame
            선택된 종목 (동일 가중)
            columns: ['ticker', 'weight', 'composite_score', 'rank']
        """
        n = top_n if top_n else self.top_n

        # Select top N tickers
        portfolio = factor_scores.head(n).copy()

        # Equal weight
        portfolio['weight'] = 1.0 / len(portfolio)

        logger.info(
            f"📊 포트폴리오 선택: {len(portfolio)}개 종목 (동일 가중 {1.0/len(portfolio):.2%})\n"
            f"   - Top 5: {', '.join(portfolio.head(5)['ticker'].tolist())}"
        )

        return portfolio[['ticker', 'weight', 'composite_score', 'rank']]

    def get_rebalance_dates(
        self,
        start_date: str,
        end_date: str,
        freq: Optional[str] = None
    ) -> List[datetime]:
        """
        리밸런싱 날짜 생성

        Parameters
        ----------
        start_date : str
            시작 날짜 (YYYY-MM-DD)
        end_date : str
            종료 날짜 (YYYY-MM-DD)
        freq : str, optional
            리밸런싱 주기 ('M', 'Q', 기본값: self.rebalance_freq)

        Returns
        -------
        List[datetime]
            리밸런싱 날짜 리스트 (월말)
        """
        freq = freq if freq else self.rebalance_freq

        # Generate month-end dates
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)

        # Convert to month-end
        rebalance_dates = [d + pd.offsets.MonthEnd(0) for d in dates]

        logger.info(
            f"📅 리밸런싱 날짜: {len(rebalance_dates)}개\n"
            f"   - 첫 리밸런싱: {rebalance_dates[0].strftime('%Y-%m-%d')}\n"
            f"   - 마지막 리밸런싱: {rebalance_dates[-1].strftime('%Y-%m-%d')}"
        )

        return rebalance_dates

    def generate_signals(
        self,
        universe: List[str],
        start_date: str,
        end_date: str,
        region: str = 'KR'
    ) -> pd.DataFrame:
        """
        전체 백테스팅 기간 동안의 리밸런싱 신호 생성

        Parameters
        ----------
        universe : List[str]
            투자 유니버스 티커 리스트
        start_date : str
            시작 날짜
        end_date : str
            종료 날짜
        region : str
            시장

        Returns
        -------
        pd.DataFrame
            리밸런싱 신호
            columns: ['date', 'ticker', 'weight', 'composite_score', 'rank']
        """
        # Get rebalance dates
        rebalance_dates = self.get_rebalance_dates(start_date, end_date)

        all_signals = []

        for calc_date in rebalance_dates:
            # Calculate factor scores
            factor_scores = self.calculate_factor_scores(universe, calc_date, region)

            if factor_scores.empty:
                logger.warning(f"⚠️ {calc_date.strftime('%Y-%m-%d')}: 팩터 점수 없음, 스킵")
                continue

            # Select portfolio
            portfolio = self.select_portfolio(factor_scores)
            portfolio['date'] = calc_date

            all_signals.append(portfolio)

        if not all_signals:
            logger.error("❌ 신호 생성 실패: 유효한 리밸런싱 없음")
            return pd.DataFrame()

        # Concatenate all signals
        signals_df = pd.concat(all_signals, ignore_index=True)
        signals_df = signals_df[['date', 'ticker', 'weight', 'composite_score', 'rank']]

        logger.info(
            f"✅ 신호 생성 완료\n"
            f"   - 총 리밸런싱: {len(rebalance_dates)}회\n"
            f"   - 총 신호: {len(signals_df)}개\n"
            f"   - 평균 종목 수: {len(signals_df) / len(rebalance_dates):.1f}개/회"
        )

        return signals_df

    def get_strategy_info(self) -> Dict:
        """전략 정보 반환"""
        return {
            'name': 'Three-Factor Strategy',
            'version': '1.0.0',
            'factors': [
                {'name': 'Max_Drawdown', 'weight': self.factor_weights['max_drawdown'], 'ic': -0.166},
                {'name': 'Liquidity', 'weight': self.factor_weights['liquidity'], 'ic': -0.097},
                {'name': 'Short_Term_Momentum', 'weight': self.factor_weights['momentum'], 'ic': 0.093}
            ],
            'parameters': {
                'top_n': self.top_n,
                'rebalance_freq': self.rebalance_freq,
                'transaction_cost': self.transaction_cost
            },
            'validation': {
                'phase': 'Phase 1.4 Complete',
                'sample_size': 500,
                'statistical_significance': True,
                'min_p_value': 0.0002  # Max_Drawdown
            }
        }


def main():
    """Quick test of Three-Factor Strategy"""
    logger.info("=" * 60)
    logger.info("Three-Factor Strategy - Quick Test")
    logger.info("=" * 60)

    # Initialize strategy
    strategy = ThreeFactorStrategy(
        top_n=20,
        rebalance_freq='M'
    )

    # Get universe
    tickers = strategy.get_universe(
        region='KR',
        start_date='2024-01-01',
        end_date='2024-11-30',
        min_data_days=224
    )

    logger.info(f"📊 투자 유니버스: {len(tickers)}개 종목")

    # Generate signals for one month (test)
    test_date = datetime(2024, 11, 30)
    factor_scores = strategy.calculate_factor_scores(tickers, test_date)

    if not factor_scores.empty:
        logger.info(f"\n📈 2024-11-30 팩터 점수 (Top 10):")
        logger.info(factor_scores.head(10)[['ticker', 'composite_score', 'rank']].to_string(index=False))

        # Select portfolio
        portfolio = strategy.select_portfolio(factor_scores)
        logger.info(f"\n💼 선택된 포트폴리오 ({len(portfolio)}개 종목):")
        logger.info(portfolio.to_string(index=False))

    # Print strategy info
    info = strategy.get_strategy_info()
    logger.info(f"\n📋 전략 정보:")
    logger.info(f"   - 이름: {info['name']} v{info['version']}")
    logger.info(f"   - 팩터:")
    for factor in info['factors']:
        logger.info(f"     • {factor['name']}: weight={factor['weight']:.3f}, IC={factor['ic']:.3f}")
    logger.info(f"   - 검증 상태: {info['validation']['phase']}")
    logger.info(f"   - 통계적 유의성: {info['validation']['statistical_significance']}")

    logger.info("\n✅ Three-Factor Strategy 테스트 완료")


if __name__ == "__main__":
    main()
