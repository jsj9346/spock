#!/usr/bin/env python3
"""
팩터 검증 스크립트 (Factor Validation Script)

목적:
- 팩터 예측력 검증 (Information Coefficient 계산)
- 팩터 간 상관관계 분석 (독립성 확인)
- 간단한 백테스트 수행 (수익성 검증)
- 검증 보고서 생성

사용법:
    python3 scripts/validate_factors.py --region KR --start-date 2022-01-01 --end-date 2024-12-31

출력:
- validation_report_YYYYMMDD.md: 검증 보고서
- factor_ic_analysis.png: IC 시각화
- factor_correlation_heatmap.png: 상관관계 히트맵
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import factor library
from modules.factors import (
    # Momentum Factors
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor,
    # Low-Vol Factors
    HistoricalVolatilityFactor,
    BetaFactor,
    MaxDrawdownFactor,
    # Size Factor (OHLCV-based only)
    LiquidityFactor
)
from modules.db_manager_postgres import PostgresDatabaseManager

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FactorValidator:
    """팩터 검증 클래스"""

    def __init__(self, region: str = 'KR', start_date: str = None, end_date: str = None):
        """
        초기화

        Args:
            region: 시장 지역 ('KR', 'US')
            start_date: 검증 시작일 (YYYY-MM-DD)
            end_date: 검증 종료일 (YYYY-MM-DD)
        """
        self.region = region
        self.start_date = start_date or '2022-01-01'
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        self.db = PostgresDatabaseManager()

        # 팩터 인스턴스 초기화 (OHLCV 데이터 기반만)
        self.factors = {
            # Momentum Factors
            '12M_Momentum': TwelveMonthMomentumFactor(),
            'RSI_Momentum': RSIMomentumFactor(),
            'Short_Term_Momentum': ShortTermMomentumFactor(),
            # Low-Vol Factors
            'Historical_Volatility': HistoricalVolatilityFactor(),
            # 'Beta': BetaFactor(),  # TODO: market_returns 계산 오류 수정 필요
            'Max_Drawdown': MaxDrawdownFactor(),
            # Size Factor (OHLCV-based)
            'Liquidity': LiquidityFactor()
        }

        logger.info(f"✅ 팩터 검증 초기화: {len(self.factors)}개 팩터, {region} 시장, {self.start_date} ~ {self.end_date}")

    def load_sample_tickers(self, limit: int = 100) -> List[str]:
        """
        샘플 티커 로드 (OHLCV 데이터 기반, 거래량 높은 종목 우선)

        Args:
            limit: 샘플 티커 수

        Returns:
            티커 리스트
        """
        # OHLCV 데이터가 풍부한 티커 선택 (2024년 전체 데이터 필요)
        query = """
            SELECT ticker, AVG(volume) as avg_volume
            FROM ohlcv_data
            WHERE region = %s
              AND date >= %s
              AND date <= %s
              AND volume > 0
            GROUP BY ticker
            HAVING COUNT(*) >= 200 AND MIN(date) <= %s
            ORDER BY avg_volume DESC
            LIMIT %s
        """

        try:
            # 파라미터: region, start_date, end_date, min_start_date (2024-02-01), limit
            min_start_date = '2024-02-01'  # 최소 2월 1일 이전부터 데이터 필요
            results = self.db.execute_query(
                query,
                (self.region, self.start_date, self.end_date, min_start_date, limit)
            )
            logger.debug(f"🔍 쿼리 결과 타입: {type(results)}, 길이: {len(results) if results else 0}")

            if not results:
                logger.warning(f"⚠️ 쿼리 결과 없음 (region={self.region}, limit={limit})")
                # Fallback: 간단한 쿼리 시도
                simple_query = """
                    SELECT DISTINCT ticker
                    FROM ohlcv_data
                    WHERE region = %s
                      AND date >= %s
                      AND date <= %s
                    LIMIT %s
                """
                results = self.db.execute_query(
                    simple_query,
                    (self.region, self.start_date, self.end_date, limit)
                )
                logger.info(f"🔄 Fallback 쿼리 결과: {len(results) if results else 0}개")

            # execute_query returns list of dicts
            tickers = [row['ticker'] for row in results]
            logger.info(f"✅ 샘플 티커 로드: {len(tickers)}개 (OHLCV 데이터 기반)")
            return tickers
        except Exception as e:
            logger.error(f"❌ 티커 로드 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def calculate_factor_values(self, tickers: List[str]) -> pd.DataFrame:
        """
        시계열 팩터 값 계산 (과거 여러 시점)

        Args:
            tickers: 티커 리스트

        Returns:
            DataFrame (ticker, factor_name, raw_value, date)
        """
        results = []

        # 월말 날짜 생성 (시작일부터 종료일까지)
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)

        # 월말 날짜 리스트 생성 (매월 말일)
        calculation_dates = pd.date_range(start=start, end=end, freq='M')
        logger.info(f"📅 계산 시점: {len(calculation_dates)}개 월말 ({calculation_dates[0].date()} ~ {calculation_dates[-1].date()})")

        for ticker in tickers:
            try:
                # 전체 OHLCV 데이터 조회 (팩터 계산용)
                ohlcv_query = """
                    SELECT date, open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker = %s AND region = %s
                      AND date BETWEEN %s AND %s
                    ORDER BY date ASC
                """

                ohlcv_data = self.db.execute_query(
                    ohlcv_query,
                    (ticker, self.region, self.start_date, self.end_date)
                )

                if not ohlcv_data:
                    logger.warning(f"⚠️ {ticker}: OHLCV 데이터 없음")
                    continue

                # DataFrame 변환 (Decimal → float)
                df_full = pd.DataFrame(
                    ohlcv_data,
                    columns=['date', 'open', 'high', 'low', 'close', 'volume']
                )
                df_full['date'] = pd.to_datetime(df_full['date'])
                # Convert Decimal to float
                for col in ['open', 'high', 'low', 'close']:
                    df_full[col] = df_full[col].astype(float)
                df_full['volume'] = df_full['volume'].astype(int)

                logger.info(f"📊 {ticker}: {len(df_full)}개 OHLCV 레코드 ({df_full['date'].min().date()} ~ {df_full['date'].max().date()})")

                # 각 월말 시점에서 팩터 계산
                factor_count = 0
                for calc_date in calculation_dates:
                    # 해당 시점까지의 데이터만 사용 (lookback window)
                    df = df_full[df_full['date'] <= calc_date].copy()

                    if len(df) < 60:  # 최소 60일 데이터 필요
                        logger.debug(f"⚠️ {ticker} ({calc_date.date()}): 데이터 부족 ({len(df)}일)")
                        continue

                    # 각 팩터 계산
                    for factor_name, factor in self.factors.items():
                        try:
                            # Liquidity는 region 파라미터 필요
                            if factor_name == 'Liquidity':
                                result = factor.calculate(data=df, ticker=ticker, region=self.region)
                            elif factor_name == 'Beta':
                                # Beta는 region 파라미터 필요
                                result = factor.calculate(data=df, ticker=ticker, region=self.region)
                            else:
                                # Momentum, Low-Vol 팩터
                                result = factor.calculate(data=df, ticker=ticker)

                            if result:
                                results.append({
                                    'ticker': ticker,
                                    'factor_name': factor_name,
                                    'raw_value': result.raw_value,
                                    'date': calc_date.date()
                                })
                                factor_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ {ticker} - {factor_name} ({calc_date.date()}) 계산 실패: {e}")
                            continue

                logger.info(f"✅ {ticker}: {factor_count}개 팩터 값 계산 완료")

            except Exception as e:
                logger.debug(f"⚠️ {ticker} 데이터 조회 실패: {e}")
                continue

        if not results:
            logger.warning("⚠️ 팩터 값 계산 결과 없음")
            return pd.DataFrame()

        df_factors = pd.DataFrame(results)
        logger.info(f"✅ 팩터 값 계산 완료: {len(df_factors)} 레코드")
        logger.info(f"   시점별 샘플:")
        logger.info(f"{df_factors.groupby('date').size().head()}")
        return df_factors

    def calculate_forward_returns(
        self,
        tickers: List[str],
        forward_days: int = 21
    ) -> pd.DataFrame:
        """
        미래 수익률 계산 (IC 계산용)

        Args:
            tickers: 티커 리스트
            forward_days: 미래 수익률 기간 (일)

        Returns:
            DataFrame (ticker, date, forward_return)
        """
        results = []

        for ticker in tickers:
            try:
                query = """
                    SELECT date, close,
                           LEAD(close, %s) OVER (ORDER BY date) as future_close
                    FROM ohlcv_data
                    WHERE ticker = %s AND region = %s
                      AND date BETWEEN %s AND %s
                    ORDER BY date ASC
                """

                data = self.db.execute_query(
                    query,
                    (forward_days, ticker, self.region, self.start_date, self.end_date)
                )

                # execute_query returns list of dicts
                for row in data:
                    date = row['date']
                    close = float(row['close']) if row['close'] else None
                    future_close = float(row['future_close']) if row['future_close'] else None

                    if close and future_close:
                        forward_return = ((future_close - close) / close) * 100
                        results.append({
                            'ticker': ticker,
                            'date': date,
                            'forward_return': forward_return
                        })

            except Exception as e:
                logger.debug(f"⚠️ {ticker} 미래 수익률 계산 실패: {e}")
                continue

        if not results:
            logger.warning("⚠️ 미래 수익률 계산 결과 없음")
            return pd.DataFrame()

        df_returns = pd.DataFrame(results)
        logger.info(f"✅ 미래 수익률 계산 완료: {len(df_returns)} 레코드")
        logger.info(f"   샘플: {df_returns.head()}")
        return df_returns

    def calculate_information_coefficient(
        self,
        df_factors: pd.DataFrame,
        df_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Information Coefficient (IC) 계산

        IC = Correlation(Factor Value, Forward Returns)

        Args:
            df_factors: 팩터 값 DataFrame
            df_returns: 미래 수익률 DataFrame

        Returns:
            IC 메트릭 DataFrame (factor_name, ic_mean, ic_std, t_stat, p_value)
        """
        ic_results = []

        # 팩터별로 IC 계산
        for factor_name in df_factors['factor_name'].unique():
            # 팩터 데이터 필터링
            factor_data = df_factors[df_factors['factor_name'] == factor_name].copy()

            # 날짜 기준으로 병합 (정확한 매칭을 위해 날짜 정규화)
            factor_data['date'] = pd.to_datetime(factor_data['date']).dt.date
            df_returns_copy = df_returns.copy()
            df_returns_copy['date'] = pd.to_datetime(df_returns_copy['date']).dt.date

            # Debug: 병합 전 데이터 확인
            logger.debug(f"🔍 {factor_name} - Factor dates: {factor_data['date'].unique()[:5]}")
            logger.debug(f"🔍 {factor_name} - Return dates: {df_returns_copy['date'].unique()[:5]}")

            merged = pd.merge(
                factor_data,
                df_returns_copy,
                on=['ticker', 'date'],
                how='inner'
            )

            logger.debug(f"🔍 {factor_name} - Merged samples: {len(merged)}")

            if len(merged) < 10:  # 최소 샘플 수
                logger.warning(f"⚠️ {factor_name}: 샘플 부족 ({len(merged)}개)")
                continue

            # Pearson 상관계수 (IC)
            try:
                pearson_corr, pearson_p = stats.pearsonr(
                    merged['raw_value'],
                    merged['forward_return']
                )
            except (ValueError, RuntimeError):
                pearson_corr, pearson_p = np.nan, np.nan

            # Spearman 상관계수 (순위 기반)
            try:
                spearman_corr, spearman_p = stats.spearmanr(
                    merged['raw_value'],
                    merged['forward_return']
                )
            except (ValueError, RuntimeError):
                spearman_corr, spearman_p = np.nan, np.nan

            # t-통계량 계산 (IC의 통계적 유의성)
            n = len(merged)
            if not np.isnan(pearson_corr) and n > 2:
                t_stat = pearson_corr * np.sqrt((n - 2) / (1 - pearson_corr**2))
            else:
                t_stat = np.nan

            ic_results.append({
                'factor_name': factor_name,
                'ic_pearson': pearson_corr,
                'ic_spearman': spearman_corr,
                'pearson_p_value': pearson_p,
                'spearman_p_value': spearman_p,
                't_stat': t_stat,
                'n_samples': n
            })

        df_ic = pd.DataFrame(ic_results)
        logger.info(f"✅ IC 계산 완료: {len(df_ic)}개 팩터")
        return df_ic

    def calculate_factor_correlations(
        self,
        df_factors: pd.DataFrame
    ) -> pd.DataFrame:
        """
        팩터 간 상관관계 계산

        Args:
            df_factors: 팩터 값 DataFrame

        Returns:
            상관관계 매트릭스 DataFrame
        """
        # Pivot: ticker를 행, factor_name을 열로 변환
        pivot = df_factors.pivot_table(
            index='ticker',
            columns='factor_name',
            values='raw_value',
            aggfunc='mean'  # 중복 값이 있으면 평균
        )

        # 상관관계 매트릭스 계산
        corr_matrix = pivot.corr(method='pearson')

        logger.info(f"✅ 팩터 상관관계 계산 완료: {corr_matrix.shape[0]}x{corr_matrix.shape[1]}")
        return corr_matrix

    def plot_ic_analysis(
        self,
        df_ic: pd.DataFrame,
        output_path: str = 'factor_ic_analysis.png'
    ):
        """
        IC 분석 시각화

        Args:
            df_ic: IC 메트릭 DataFrame
            output_path: 출력 파일 경로
        """
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # 1. IC 값 (Pearson vs Spearman)
        ax1 = axes[0]
        x = np.arange(len(df_ic))
        width = 0.35

        ax1.bar(x - width/2, df_ic['ic_pearson'], width, label='Pearson IC', alpha=0.8)
        ax1.bar(x + width/2, df_ic['ic_spearman'], width, label='Spearman IC', alpha=0.8)
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
        ax1.axhline(y=0.05, color='green', linestyle=':', linewidth=0.5, label='IC > 0.05 (유의미)')
        ax1.set_xlabel('Factor')
        ax1.set_ylabel('Information Coefficient')
        ax1.set_title('Factor Information Coefficients (IC)')
        ax1.set_xticks(x)
        ax1.set_xticklabels(df_ic['factor_name'], rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. t-통계량 (통계적 유의성)
        ax2 = axes[1]
        ax2.bar(x, df_ic['t_stat'], alpha=0.8, color='steelblue')
        ax2.axhline(y=2.0, color='red', linestyle='--', linewidth=1, label='t > 2.0 (유의수준 95%)')
        ax2.axhline(y=-2.0, color='red', linestyle='--', linewidth=1)
        ax2.set_xlabel('Factor')
        ax2.set_ylabel('t-statistic')
        ax2.set_title('Factor IC Statistical Significance (t-statistics)')
        ax2.set_xticks(x)
        ax2.set_xticklabels(df_ic['factor_name'], rotation=45, ha='right')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ IC 분석 시각화 저장: {output_path}")
        plt.close()

    def plot_correlation_heatmap(
        self,
        corr_matrix: pd.DataFrame,
        output_path: str = 'factor_correlation_heatmap.png'
    ):
        """
        팩터 상관관계 히트맵

        Args:
            corr_matrix: 상관관계 매트릭스
            output_path: 출력 파일 경로
        """
        plt.figure(figsize=(12, 10))

        # 히트맵 생성
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))  # 상삼각 마스킹
        sns.heatmap(
            corr_matrix,
            mask=mask,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            square=True,
            linewidths=1,
            cbar_kws={"shrink": 0.8},
            vmin=-1,
            vmax=1
        )

        plt.title('Factor Correlation Matrix', fontsize=16, pad=20)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ 상관관계 히트맵 저장: {output_path}")
        plt.close()

    def generate_validation_report(
        self,
        df_ic: pd.DataFrame,
        corr_matrix: pd.DataFrame,
        output_path: str = None
    ) -> str:
        """
        검증 보고서 생성 (Markdown)

        Args:
            df_ic: IC 메트릭 DataFrame
            corr_matrix: 상관관계 매트릭스
            output_path: 출력 파일 경로

        Returns:
            보고서 파일 경로
        """
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d')
            output_path = f'validation_report_{timestamp}.md'

        # 보고서 작성
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 팩터 검증 보고서 (Factor Validation Report)\n\n")
            f.write(f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**시장**: {self.region}\n")
            f.write(f"**기간**: {self.start_date} ~ {self.end_date}\n")
            f.write(f"**팩터 수**: {len(self.factors)}개\n\n")

            f.write("---\n\n")

            # 1. IC 분석 결과
            f.write("## 1. Information Coefficient (IC) 분석\n\n")
            f.write("IC는 팩터 값과 미래 수익률 간의 상관관계를 측정합니다.\n")
            f.write("- **IC > 0.05**: 유의미한 예측력\n")
            f.write("- **t-stat > 2.0**: 통계적 유의성 (95% 신뢰수준)\n\n")

            f.write("### IC 메트릭 요약\n\n")
            f.write("| Factor | Pearson IC | Spearman IC | t-stat | p-value | Samples |\n")
            f.write("|--------|------------|-------------|--------|---------|----------|\n")

            for _, row in df_ic.iterrows():
                f.write(f"| {row['factor_name']} | ")
                f.write(f"{row['ic_pearson']:.4f} | ")
                f.write(f"{row['ic_spearman']:.4f} | ")
                f.write(f"{row['t_stat']:.2f} | ")
                f.write(f"{row['pearson_p_value']:.4f} | ")
                f.write(f"{row['n_samples']:,.0f} |\n")

            f.write("\n")

            # IC 해석
            f.write("### IC 해석\n\n")
            significant_factors = df_ic[
                (df_ic['ic_pearson'].abs() > 0.05) & (df_ic['t_stat'].abs() > 2.0)
            ]

            if len(significant_factors) > 0:
                f.write(f"✅ **유의미한 팩터**: {len(significant_factors)}개\n\n")
                for _, row in significant_factors.iterrows():
                    direction = "양의 예측력" if row['ic_pearson'] > 0 else "음의 예측력"
                    f.write(f"- **{row['factor_name']}**: IC={row['ic_pearson']:.4f}, {direction}\n")
            else:
                f.write("⚠️ 통계적으로 유의미한 팩터가 없습니다.\n")

            f.write("\n")

            # 2. 팩터 상관관계 분석
            f.write("## 2. 팩터 상관관계 분석\n\n")
            f.write("팩터 간 독립성을 확인합니다.\n")
            f.write("- **|상관계수| < 0.5**: 독립적\n")
            f.write("- **|상관계수| > 0.7**: 높은 상관관계 (중복 가능성)\n\n")

            # 높은 상관관계 식별
            high_corr_pairs = []
            for i in range(len(corr_matrix)):
                for j in range(i+1, len(corr_matrix)):
                    corr_value = corr_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        high_corr_pairs.append({
                            'factor1': corr_matrix.index[i],
                            'factor2': corr_matrix.columns[j],
                            'correlation': corr_value
                        })

            if high_corr_pairs:
                f.write(f"⚠️ **높은 상관관계 팩터 쌍**: {len(high_corr_pairs)}개\n\n")
                f.write("| Factor 1 | Factor 2 | Correlation |\n")
                f.write("|----------|----------|-------------|\n")
                for pair in high_corr_pairs:
                    f.write(f"| {pair['factor1']} | {pair['factor2']} | {pair['correlation']:.4f} |\n")
            else:
                f.write("✅ 모든 팩터가 독립적입니다 (|상관계수| < 0.7).\n")

            f.write("\n")

            # 3. 권장사항
            f.write("## 3. 권장사항\n\n")

            # IC 기반 권장사항
            if len(significant_factors) == 0:
                f.write("### IC 개선 필요\n")
                f.write("- 샘플 크기 증가 (더 많은 티커 또는 더 긴 기간)\n")
                f.write("- 팩터 계산 로직 검토\n")
                f.write("- 미래 수익률 기간 조정 (현재: 21일)\n\n")

            # 상관관계 기반 권장사항
            if high_corr_pairs:
                f.write("### 팩터 중복 제거\n")
                f.write("높은 상관관계를 가진 팩터 중 하나를 제거하거나 조합하는 것을 권장합니다.\n\n")

            f.write("### 다음 단계\n")
            f.write("1. 유의미한 팩터로 포트폴리오 구성\n")
            f.write("2. 백테스팅으로 실제 수익성 검증\n")
            f.write("3. Walk-forward 최적화로 과적합 방지\n")
            f.write("4. 프로덕션 배포 전 out-of-sample 테스트\n\n")

            f.write("---\n\n")
            f.write("**생성**: `python3 scripts/validate_factors.py`\n")

        logger.info(f"✅ 검증 보고서 생성: {output_path}")
        return output_path

    def run_validation(self, sample_size: int = 100):
        """
        전체 검증 프로세스 실행

        Args:
            sample_size: 샘플 티커 수
        """
        logger.info(f"🚀 팩터 검증 시작: {sample_size}개 티커 샘플")

        # 1. 샘플 티커 로드
        tickers = self.load_sample_tickers(limit=sample_size)
        if not tickers:
            logger.error("❌ 티커 로드 실패")
            return

        # 2. 팩터 값 계산
        df_factors = self.calculate_factor_values(tickers)
        if df_factors.empty:
            logger.error("❌ 팩터 값 계산 실패")
            return

        # 3. 미래 수익률 계산
        df_returns = self.calculate_forward_returns(tickers, forward_days=21)
        if df_returns.empty:
            logger.error("❌ 미래 수익률 계산 실패")
            return

        # 4. IC 계산
        df_ic = self.calculate_information_coefficient(df_factors, df_returns)
        if df_ic.empty:
            logger.error("❌ IC 계산 실패")
            return

        # 5. 팩터 상관관계 계산
        corr_matrix = self.calculate_factor_correlations(df_factors)

        # 6. 시각화
        self.plot_ic_analysis(df_ic)
        self.plot_correlation_heatmap(corr_matrix)

        # 7. 보고서 생성
        report_path = self.generate_validation_report(df_ic, corr_matrix)

        logger.info("✅ 팩터 검증 완료!")
        logger.info(f"📊 보고서: {report_path}")
        logger.info(f"📊 IC 분석: factor_ic_analysis.png")
        logger.info(f"📊 상관관계: factor_correlation_heatmap.png")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='팩터 검증 스크립트')
    parser.add_argument('--region', type=str, default='KR', help='시장 지역 (KR, US)')
    parser.add_argument('--start-date', type=str, default='2022-01-01', help='시작일 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='종료일 (YYYY-MM-DD)')
    parser.add_argument('--sample-size', type=int, default=100, help='샘플 티커 수')

    args = parser.parse_args()

    # 검증 실행
    validator = FactorValidator(
        region=args.region,
        start_date=args.start_date,
        end_date=args.end_date
    )

    validator.run_validation(sample_size=args.sample_size)


if __name__ == '__main__':
    main()
