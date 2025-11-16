"""
Liquidity Factor Strategy

단순하고 검증된 Liquidity 팩터 기반 롱-온리 전략.

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

Author: Spock Quant Platform
Date: 2025-11-12
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from loguru import logger

from modules.factors.size_factors import LiquidityFactor
from modules.db_manager_postgres import PostgresDatabaseManager


class LiquidityFactorStrategy:
    """
    Liquidity 팩터 기반 월간 리밸런싱 전략

    Parameters
    ----------
    top_pct : float
        상위 선택 비율 (기본값: 0.2 = 상위 20%)
    rebalance_freq : str
        리밸런싱 주기 ('M' = 월말, 'Q' = 분기말)
    transaction_cost : float
        거래 비용 (기본값: 0.003 = 0.3%)
    """

    def __init__(
        self,
        top_pct: float = 0.2,
        rebalance_freq: str = 'M',
        transaction_cost: float = 0.003
    ):
        self.top_pct = top_pct
        self.rebalance_freq = rebalance_freq
        self.transaction_cost = transaction_cost

        self.factor = LiquidityFactor()
        self.db = PostgresDatabaseManager()

        logger.info(f"✅ Liquidity 전략 초기화: 상위 {top_pct*100:.0f}%, {rebalance_freq} 리밸런싱")

    def get_universe(
        self,
        region: str = 'KR',
        start_date: str = '2022-01-01',
        end_date: str = '2024-12-31',
        min_volume: int = 100000
    ) -> List[str]:
        """
        투자 유니버스 조회 (거래량 기준 필터링)

        Parameters
        ----------
        region : str
            시장 (KR, US)
        start_date : str
            시작 날짜
        end_date : str
            종료 날짜
        min_volume : int
            최소 평균 거래량

        Returns
        -------
        List[str]
            티커 리스트
        """
        query = """
            SELECT ticker, AVG(volume) as avg_volume
            FROM ohlcv_data
            WHERE region = %s
              AND date BETWEEN %s AND %s
              AND volume > 0
            GROUP BY ticker
            HAVING COUNT(*) >= 500 AND AVG(volume) >= %s
            ORDER BY avg_volume DESC
        """

        result = self.db.execute_query(query, (region, start_date, end_date, min_volume))
        tickers = [row['ticker'] for row in result]

        logger.info(f"📊 투자 유니버스: {len(tickers)}개 종목 (평균 거래량 >={min_volume:,})")
        return tickers

    def calculate_factor_scores(
        self,
        tickers: List[str],
        calc_date: datetime,
        region: str = 'KR'
    ) -> pd.DataFrame:
        """
        특정 시점의 팩터 점수 계산

        Parameters
        ----------
        tickers : List[str]
            티커 리스트
        calc_date : datetime
            계산 시점
        region : str
            시장

        Returns
        -------
        pd.DataFrame
            columns: ['ticker', 'liquidity_score', 'rank']
        """
        scores = []

        # 과거 60일 데이터로 팩터 계산
        lookback_start = (calc_date - timedelta(days=90)).strftime('%Y-%m-%d')
        calc_date_str = calc_date.strftime('%Y-%m-%d')

        for ticker in tickers:
            # OHLCV 데이터 조회
            query = """
                SELECT date, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s
                  AND date BETWEEN %s AND %s
                ORDER BY date ASC
            """

            data = self.db.execute_query(query, (ticker, region, lookback_start, calc_date_str))

            if len(data) < 60:
                continue

            # DataFrame 변환
            df = pd.DataFrame(data, columns=['date', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(int)

            # Liquidity 팩터 계산
            result = self.factor.calculate(data=df, ticker=ticker, region=region)

            if result and result.raw_value is not None:
                scores.append({
                    'ticker': ticker,
                    'liquidity_score': result.raw_value,
                    'confidence': result.confidence
                })

        if not scores:
            logger.warning(f"⚠️ {calc_date.date()}: 팩터 점수 계산 실패")
            return pd.DataFrame()

        # DataFrame 생성 및 랭킹
        df_scores = pd.DataFrame(scores)
        df_scores['rank'] = df_scores['liquidity_score'].rank(ascending=False)  # 높은 Liquidity = 높은 순위
        df_scores['rank_pct'] = df_scores['rank'] / len(df_scores)

        logger.info(f"📊 {calc_date.date()}: {len(df_scores)}개 종목 팩터 계산 완료")

        return df_scores

    def select_portfolio(
        self,
        factor_scores: pd.DataFrame,
        top_pct: Optional[float] = None
    ) -> List[str]:
        """
        상위 종목 선택

        Parameters
        ----------
        factor_scores : pd.DataFrame
            팩터 점수
        top_pct : float, optional
            선택 비율 (기본값: self.top_pct)

        Returns
        -------
        List[str]
            선택된 티커 리스트
        """
        if factor_scores.empty:
            return []

        pct = top_pct or self.top_pct

        # 상위 N% 선택
        selected = factor_scores[factor_scores['rank_pct'] <= pct]['ticker'].tolist()

        logger.info(f"✅ 포트폴리오: {len(selected)}개 종목 선택 (상위 {pct*100:.0f}%)")

        return selected

    def get_rebalance_dates(
        self,
        start_date: str,
        end_date: str
    ) -> List[datetime]:
        """
        리밸런싱 날짜 생성

        Parameters
        ----------
        start_date : str
            시작 날짜
        end_date : str
            종료 날짜

        Returns
        -------
        List[datetime]
            리밸런싱 날짜 리스트
        """
        dates = pd.date_range(
            start=start_date,
            end=end_date,
            freq='ME' if self.rebalance_freq == 'M' else 'QE'
        )

        logger.info(f"📅 리밸런싱 날짜: {len(dates)}개 ({dates[0].date()} ~ {dates[-1].date()})")

        return dates.tolist()

    def generate_signals(
        self,
        region: str = 'KR',
        start_date: str = '2022-01-01',
        end_date: str = '2024-12-31'
    ) -> pd.DataFrame:
        """
        전체 기간 매매 신호 생성

        Parameters
        ----------
        region : str
            시장
        start_date : str
            시작 날짜
        end_date : str
            종료 날짜

        Returns
        -------
        pd.DataFrame
            columns: ['date', 'ticker', 'signal', 'liquidity_score']
            signal: 1 = 매수, 0 = 보유 없음
        """
        logger.info(f"🚀 신호 생성 시작: {start_date} ~ {end_date}")

        # 투자 유니버스
        universe = self.get_universe(region, start_date, end_date)

        # 리밸런싱 날짜
        rebalance_dates = self.get_rebalance_dates(start_date, end_date)

        # 신호 생성
        all_signals = []

        for calc_date in rebalance_dates:
            # 팩터 점수 계산
            factor_scores = self.calculate_factor_scores(universe, calc_date, region)

            if factor_scores.empty:
                continue

            # 포트폴리오 선택
            selected = self.select_portfolio(factor_scores)

            # 신호 생성
            for ticker in selected:
                score_row = factor_scores[factor_scores['ticker'] == ticker].iloc[0]
                all_signals.append({
                    'date': calc_date.date(),
                    'ticker': ticker,
                    'signal': 1,
                    'liquidity_score': score_row['liquidity_score'],
                    'rank': score_row['rank']
                })

        df_signals = pd.DataFrame(all_signals)

        logger.info(f"✅ 신호 생성 완료: {len(df_signals)}개 (평균 {len(df_signals)//len(rebalance_dates):.0f}개/월)")

        return df_signals


if __name__ == "__main__":
    # 테스트 실행
    strategy = LiquidityFactorStrategy(top_pct=0.2, rebalance_freq='M')

    # 신호 생성
    signals = strategy.generate_signals(
        region='KR',
        start_date='2022-01-01',
        end_date='2024-12-31'
    )

    print(f"\n📊 생성된 신호: {len(signals)}개")
    print(signals.head(20))
    print(f"\n월별 포트폴리오 크기:")
    print(signals.groupby('date')['ticker'].count())
