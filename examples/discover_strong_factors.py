#!/usr/bin/env python3
"""
Strong Factor Discovery - IC > 0.3 Candidates

Phase 2.4.1: 추가 팩터 후보 발굴

Walk-Forward 검증 결과, 현재 3개 팩터(IC < 0.2)가 너무 약해서 과적합이 발생했습니다.
이 스크립트는 25개 이상의 팩터를 테스트하여 IC > 0.3인 강력한 팩터를 발굴합니다.

테스트 팩터 (28개):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Momentum (4):
  - TwelveMonthMomentumFactor
  - RSIMomentumFactor
  - ShortTermMomentumFactor (기존, IC=0.093)
  - EarningsMomentumFactor

Low-Volatility (3):
  - HistoricalVolatilityFactor
  - BetaFactor
  - MaxDrawdownFactor (기존, IC=-0.166)

Size (3):
  - MarketCapFactor
  - LiquidityFactor (기존, IC=-0.097)
  - FloatFactor

Value (4):
  - DividendYieldFactor
  - EVToEBITDAFactor
  - PERatioFactor
  - PBRatioFactor

Quality (9):
  - ROEFactor
  - ROAFactor
  - OperatingMarginFactor
  - NetProfitMarginFactor
  - CurrentRatioFactor
  - QuickRatioFactor
  - DebtToEquityFactor
  - AccrualsRatioFactor
  - CFToNIRatioFactor

Growth (3):
  - RevenueGrowthFactor
  - OperatingProfitGrowthFactor
  - NetIncomeGrowthFactor

Efficiency (2):
  - AssetTurnoverFactor
  - EquityTurnoverFactor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

필터링 기준:
1. IC > 0.3 (|IC| > 0.3) - 강력한 예측력
2. p-value < 0.05 - 통계적 유의성
3. 기존 팩터 상관관계 < 0.5 - 독립성
4. H1 vs H2 2024 IC 차이 < 50% - 안정성

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from loguru import logger
from typing import Dict, List, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Factor imports
from modules.factors.momentum_factors import (
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor,
    EarningsMomentumFactor
)
from modules.factors.low_vol_factors import (
    HistoricalVolatilityFactor,
    BetaFactor,
    MaxDrawdownFactor
)
from modules.factors.size_factors import (
    MarketCapFactor,
    LiquidityFactor,
    FloatFactor
)
from modules.factors.value_factors import (
    DividendYieldFactorPostgres,
    EVToEBITDAFactorPostgres,
    PERatioFactor,
    PBRatioFactor
)
from modules.factors.quality_factors import (
    ROEFactor,
    ROAFactor,
    OperatingMarginFactor,
    NetProfitMarginFactor,
    CurrentRatioFactor,
    QuickRatioFactor,
    DebtToEquityFactor,
    AccrualsRatioFactor,
    CFToNIRatioFactor
)
from modules.factors.growth_factors import (
    RevenueGrowthFactor,
    OperatingProfitGrowthFactor,
    NetIncomeGrowthFactor
)
from modules.factors.efficiency_factors import (
    AssetTurnoverFactor,
    EquityTurnoverFactor
)

# Database
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# Configuration
# ============================================================================

# Test period
TEST_START = '2024-01-01'
TEST_END = '2024-11-30'

# H1 vs H2 split for stability check
H1_START = '2024-01-01'
H1_END = '2024-06-30'
H2_START = '2024-07-01'
H2_END = '2024-11-30'

# IC threshold
IC_THRESHOLD = 0.3
P_VALUE_THRESHOLD = 0.05
CORRELATION_THRESHOLD = 0.5

# Sample size
MIN_TICKERS = 100
MAX_TICKERS = 200

# Forward return period
FORWARD_RETURN_DAYS = 21  # ~1 month

# Region
REGION = 'KR'


# ============================================================================
# Factor Registry
# ============================================================================

# All factors to test (28 factors)
FACTOR_REGISTRY = {
    # Momentum (4 factors)
    'TwelveMonthMomentum': TwelveMonthMomentumFactor(),
    'RSIMomentum': RSIMomentumFactor(),
    'ShortTermMomentum': ShortTermMomentumFactor(),  # Existing, IC=0.093
    'EarningsMomentum': EarningsMomentumFactor(),

    # Low-Volatility (3 factors)
    'HistoricalVolatility': HistoricalVolatilityFactor(),
    'Beta': BetaFactor(),
    'MaxDrawdown': MaxDrawdownFactor(),  # Existing, IC=-0.166

    # Size (3 factors)
    'MarketCap': MarketCapFactor(),
    'Liquidity': LiquidityFactor(),  # Existing, IC=-0.097
    'Float': FloatFactor(),

    # Value (4 factors)
    'DividendYield': DividendYieldFactorPostgres(),
    'EVToEBITDA': EVToEBITDAFactorPostgres(),
    'PERatio': PERatioFactor(),
    'PBRatio': PBRatioFactor(),

    # Quality (9 factors)
    'ROE': ROEFactor(),
    'ROA': ROAFactor(),
    'OperatingMargin': OperatingMarginFactor(),
    'NetProfitMargin': NetProfitMarginFactor(),
    'CurrentRatio': CurrentRatioFactor(),
    'QuickRatio': QuickRatioFactor(),
    'DebtToEquity': DebtToEquityFactor(),
    'AccrualsRatio': AccrualsRatioFactor(),
    'CFToNIRatio': CFToNIRatioFactor(),

    # Growth (3 factors)
    'RevenueGrowth': RevenueGrowthFactor(),
    'OperatingProfitGrowth': OperatingProfitGrowthFactor(),
    'NetIncomeGrowth': NetIncomeGrowthFactor(),

    # Efficiency (2 factors)
    'AssetTurnover': AssetTurnoverFactor(),
    'EquityTurnover': EquityTurnoverFactor(),
}

# Existing factors (already validated in Phase 1.4)
EXISTING_FACTORS = {
    'ShortTermMomentum': 0.093,
    'MaxDrawdown': -0.166,
    'Liquidity': -0.097
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_test_universe(
    db: PostgresDatabaseManager,
    start_date: str,
    end_date: str,
    min_data_days: int = 200,
    limit: int = 200
) -> List[str]:
    """
    테스트용 투자 유니버스 조회

    Parameters
    ----------
    db : PostgresDatabaseManager
        데이터베이스 매니저
    start_date : str
        시작 날짜
    end_date : str
        종료 날짜
    min_data_days : int
        최소 데이터 일수
    limit : int
        최대 종목 수

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
        LIMIT %s
    """

    result = db.execute_query(
        query,
        (REGION, start_date, end_date, min_data_days, limit)
    )

    tickers = [row['ticker'] for row in result]

    logger.info(
        f"📊 테스트 유니버스: {len(tickers)}개 종목\n"
        f"   - 기간: {start_date} ~ {end_date}\n"
        f"   - 최소 데이터: {min_data_days}일"
    )

    return tickers


def calculate_forward_returns(
    db: PostgresDatabaseManager,
    tickers: List[str],
    calc_date: datetime,
    forward_days: int = 21
) -> pd.DataFrame:
    """
    Forward returns 계산 (future price change from calc_date)

    Parameters
    ----------
    db : PostgresDatabaseManager
        데이터베이스 매니저
    tickers : List[str]
        티커 리스트
    calc_date : datetime
        기준 날짜
    forward_days : int
        Forward 기간 (trading days)

    Returns
    -------
    pd.DataFrame
        columns: ['ticker', 'base_price', 'forward_price', 'forward_return']
    """
    calc_date_str = calc_date.strftime('%Y-%m-%d')
    end_date = (calc_date + timedelta(days=forward_days + 10)).strftime('%Y-%m-%d')

    # Query prices
    query = """
        WITH ranked_prices AS (
            SELECT
                ticker,
                date,
                close,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) as rn_from_start,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn_from_end
            FROM ohlcv_data
            WHERE ticker = ANY(%s)
              AND region = %s
              AND date BETWEEN %s AND %s
        ),
        base_prices AS (
            SELECT ticker, close as base_price
            FROM ranked_prices
            WHERE date = %s
        ),
        forward_prices AS (
            SELECT ticker, close as forward_price
            FROM ranked_prices
            WHERE rn_from_start = (
                SELECT MIN(rn_from_start) + %s
                FROM ranked_prices rp2
                WHERE rp2.ticker = ranked_prices.ticker
                  AND rp2.date >= %s
            )
        )
        SELECT
            bp.ticker,
            bp.base_price,
            fp.forward_price,
            (fp.forward_price - bp.base_price) / bp.base_price AS forward_return
        FROM base_prices bp
        INNER JOIN forward_prices fp ON bp.ticker = fp.ticker
        WHERE fp.forward_price IS NOT NULL
    """

    result = db.execute_query(
        query,
        (tickers, REGION, calc_date_str, end_date, calc_date_str, forward_days, calc_date_str)
    )

    if not result:
        return pd.DataFrame()

    df = pd.DataFrame(
        result,
        columns=['ticker', 'base_price', 'forward_price', 'forward_return']
    )

    # Convert Decimal to float
    for col in ['base_price', 'forward_price', 'forward_return']:
        df[col] = df[col].astype(float)

    return df


def calculate_factor_values(
    factor_name: str,
    factor_instance,
    tickers: List[str],
    calc_date: datetime,
    db: PostgresDatabaseManager
) -> pd.DataFrame:
    """
    특정 시점의 팩터 값 계산

    Parameters
    ----------
    factor_name : str
        팩터 이름
    factor_instance : FactorBase
        팩터 인스턴스
    tickers : List[str]
        티커 리스트
    calc_date : datetime
        계산 시점
    db : PostgresDatabaseManager
        데이터베이스 매니저

    Returns
    -------
    pd.DataFrame
        columns: ['ticker', '{factor_name}_value']
    """
    factor_values = []

    # Lookback period (최대 1년)
    lookback_start = (calc_date - timedelta(days=400)).strftime('%Y-%m-%d')
    calc_date_str = calc_date.strftime('%Y-%m-%d')

    for ticker in tickers:
        # Fetch OHLCV data
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
              AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """

        data = db.execute_query(query, (ticker, REGION, lookback_start, calc_date_str))

        if len(data) < 60:  # Minimum data requirement
            continue

        # Convert to DataFrame
        df = pd.DataFrame(
            data,
            columns=['date', 'open', 'high', 'low', 'close', 'volume']
        )
        df['date'] = pd.to_datetime(df['date'])

        # Convert Decimal to float
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(int)

        # Calculate factor
        try:
            result = factor_instance.calculate(df, ticker, REGION)

            if result and result.raw_value is not None:
                factor_values.append({
                    'ticker': ticker,
                    f'{factor_name}_value': result.raw_value
                })
        except Exception as e:
            logger.debug(f"   ⚠️ {ticker} 팩터 계산 실패: {e}")
            continue

    if not factor_values:
        return pd.DataFrame()

    return pd.DataFrame(factor_values)


def calculate_ic(
    factor_values: pd.Series,
    forward_returns: pd.Series
) -> Tuple[float, float, float]:
    """
    Information Coefficient (IC) 계산

    IC = Spearman correlation between factor values and forward returns

    Parameters
    ----------
    factor_values : pd.Series
        팩터 값
    forward_returns : pd.Series
        Forward returns

    Returns
    -------
    Tuple[float, float, float]
        (IC, t-statistic, p-value)
    """
    # Remove NaN
    valid_mask = ~(factor_values.isna() | forward_returns.isna())
    factor_clean = factor_values[valid_mask]
    returns_clean = forward_returns[valid_mask]

    if len(factor_clean) < 30:
        return np.nan, np.nan, np.nan

    # Spearman correlation
    ic, p_value = stats.spearmanr(factor_clean, returns_clean)

    # t-statistic
    n = len(factor_clean)
    t_stat = ic * np.sqrt(n - 2) / np.sqrt(1 - ic**2) if abs(ic) < 1 else np.nan

    return ic, t_stat, p_value


def test_factor(
    factor_name: str,
    factor_instance,
    tickers: List[str],
    test_dates: List[datetime],
    db: PostgresDatabaseManager
) -> Dict:
    """
    단일 팩터 테스트 (월별 IC 계산)

    Parameters
    ----------
    factor_name : str
        팩터 이름
    factor_instance : FactorBase
        팩터 인스턴스
    tickers : List[str]
        티커 리스트
    test_dates : List[datetime]
        테스트 날짜 리스트
    db : PostgresDatabaseManager
        데이터베이스 매니저

    Returns
    -------
    Dict
        팩터 테스트 결과
    """
    logger.info(f"🔬 {factor_name} 테스트 중...")

    monthly_ics = []
    total_samples = 0

    for calc_date in test_dates:
        # Calculate factor values
        factor_df = calculate_factor_values(
            factor_name,
            factor_instance,
            tickers,
            calc_date,
            db
        )

        if factor_df.empty:
            logger.debug(f"   ⚠️ {calc_date.strftime('%Y-%m')}: 팩터 값 없음")
            continue

        # Calculate forward returns
        returns_df = calculate_forward_returns(
            db,
            factor_df['ticker'].tolist(),
            calc_date,
            FORWARD_RETURN_DAYS
        )

        if returns_df.empty:
            logger.debug(f"   ⚠️ {calc_date.strftime('%Y-%m')}: Forward returns 없음")
            continue

        # Merge
        merged = pd.merge(
            factor_df,
            returns_df[['ticker', 'forward_return']],
            on='ticker',
            how='inner'
        )

        if len(merged) < 30:
            logger.debug(f"   ⚠️ {calc_date.strftime('%Y-%m')}: 샘플 수 부족 ({len(merged)})")
            continue

        # Calculate IC
        ic, t_stat, p_value = calculate_ic(
            merged[f'{factor_name}_value'],
            merged['forward_return']
        )

        if not np.isnan(ic):
            monthly_ics.append({
                'date': calc_date,
                'ic': ic,
                't_stat': t_stat,
                'p_value': p_value,
                'n_samples': len(merged)
            })
            total_samples += len(merged)

            logger.debug(
                f"   ✅ {calc_date.strftime('%Y-%m')}: "
                f"IC={ic:.3f}, t={t_stat:.2f}, p={p_value:.4f}, n={len(merged)}"
            )

    if not monthly_ics:
        logger.warning(f"   ❌ {factor_name}: 유효한 IC 없음")
        return {
            'factor_name': factor_name,
            'mean_ic': np.nan,
            'mean_t_stat': np.nan,
            'mean_p_value': np.nan,
            'ic_std': np.nan,
            'n_months': 0,
            'total_samples': 0,
            'significant': False,
            'strong': False
        }

    # Aggregate statistics
    ic_values = [x['ic'] for x in monthly_ics]
    t_values = [x['t_stat'] for x in monthly_ics]
    p_values = [x['p_value'] for x in monthly_ics]

    mean_ic = np.mean(ic_values)
    mean_t_stat = np.mean(t_values)
    mean_p_value = np.mean(p_values)
    ic_std = np.std(ic_values)

    # Statistical significance
    significant = mean_p_value < P_VALUE_THRESHOLD

    # Strong factor (|IC| > 0.3)
    strong = abs(mean_ic) > IC_THRESHOLD

    logger.info(
        f"   ✅ {factor_name}: "
        f"IC={mean_ic:.3f}±{ic_std:.3f}, "
        f"t={mean_t_stat:.2f}, "
        f"p={mean_p_value:.4f}, "
        f"n_months={len(monthly_ics)}, "
        f"samples={total_samples}"
    )

    if strong and significant:
        logger.info(f"   🎯 {factor_name}: STRONG CANDIDATE! (IC > {IC_THRESHOLD}, p < {P_VALUE_THRESHOLD})")

    return {
        'factor_name': factor_name,
        'mean_ic': mean_ic,
        'mean_t_stat': mean_t_stat,
        'mean_p_value': mean_p_value,
        'ic_std': ic_std,
        'n_months': len(monthly_ics),
        'total_samples': total_samples,
        'significant': significant,
        'strong': strong,
        'monthly_ics': monthly_ics
    }


def check_correlation_with_existing(
    new_factor_values: pd.Series,
    existing_factor_values: Dict[str, pd.Series]
) -> Dict[str, float]:
    """
    기존 팩터와의 상관관계 확인

    Parameters
    ----------
    new_factor_values : pd.Series
        신규 팩터 값
    existing_factor_values : Dict[str, pd.Series]
        기존 팩터 값 딕셔너리

    Returns
    -------
    Dict[str, float]
        각 기존 팩터와의 Spearman 상관관계
    """
    correlations = {}

    for existing_name, existing_values in existing_factor_values.items():
        # Align indices
        aligned = pd.DataFrame({
            'new': new_factor_values,
            'existing': existing_values
        }).dropna()

        if len(aligned) < 30:
            correlations[existing_name] = np.nan
            continue

        # Spearman correlation
        corr, _ = stats.spearmanr(aligned['new'], aligned['existing'])
        correlations[existing_name] = corr

    return correlations


def check_stability(
    factor_name: str,
    factor_instance,
    tickers: List[str],
    h1_dates: List[datetime],
    h2_dates: List[datetime],
    db: PostgresDatabaseManager
) -> Dict:
    """
    팩터 안정성 확인 (H1 2024 vs H2 2024)

    Parameters
    ----------
    factor_name : str
        팩터 이름
    factor_instance : FactorBase
        팩터 인스턴스
    tickers : List[str]
        티커 리스트
    h1_dates : List[datetime]
        H1 테스트 날짜
    h2_dates : List[datetime]
        H2 테스트 날짜
    db : PostgresDatabaseManager
        데이터베이스 매니저

    Returns
    -------
    Dict
        안정성 통계
    """
    # H1 IC
    h1_result = test_factor(factor_name, factor_instance, tickers, h1_dates, db)
    h1_ic = h1_result['mean_ic']

    # H2 IC
    h2_result = test_factor(factor_name, factor_instance, tickers, h2_dates, db)
    h2_ic = h2_result['mean_ic']

    # IC change
    if not np.isnan(h1_ic) and not np.isnan(h2_ic) and h1_ic != 0:
        ic_change_pct = abs((h2_ic - h1_ic) / h1_ic) * 100
    else:
        ic_change_pct = np.nan

    # Stability (change < 50%)
    stable = ic_change_pct < 50 if not np.isnan(ic_change_pct) else False

    return {
        'h1_ic': h1_ic,
        'h2_ic': h2_ic,
        'ic_change_pct': ic_change_pct,
        'stable': stable
    }


# ============================================================================
# Main Discovery Workflow
# ============================================================================

def main():
    """Execute Strong Factor Discovery"""

    logger.info("=" * 80)
    logger.info("Strong Factor Discovery - IC > 0.3 Candidates")
    logger.info("=" * 80)

    logger.info(
        f"\n📋 발굴 설정:\n"
        f"   - 테스트 기간: {TEST_START} ~ {TEST_END}\n"
        f"   - IC 기준: |IC| > {IC_THRESHOLD}\n"
        f"   - p-value 기준: < {P_VALUE_THRESHOLD}\n"
        f"   - 상관관계 기준: < {CORRELATION_THRESHOLD}\n"
        f"   - 테스트 팩터: {len(FACTOR_REGISTRY)}개"
    )

    db = PostgresDatabaseManager()

    # Get universe
    tickers = get_test_universe(
        db,
        TEST_START,
        TEST_END,
        min_data_days=200,
        limit=MAX_TICKERS
    )

    if len(tickers) < MIN_TICKERS:
        logger.error(f"❌ 테스트 유니버스 부족: {len(tickers)} < {MIN_TICKERS}")
        return

    # Generate test dates (month-end)
    test_dates = pd.date_range(start=TEST_START, end=TEST_END, freq='M')
    test_dates = [d + pd.offsets.MonthEnd(0) for d in test_dates]

    logger.info(f"\n📅 테스트 날짜: {len(test_dates)}개 월말")

    # H1 vs H2 dates
    h1_dates = [d for d in test_dates if H1_START <= d.strftime('%Y-%m-%d') <= H1_END]
    h2_dates = [d for d in test_dates if H2_START <= d.strftime('%Y-%m-%d') <= H2_END]

    logger.info(f"   - H1 2024: {len(h1_dates)}개 월 ({H1_START} ~ {H1_END})")
    logger.info(f"   - H2 2024: {len(h2_dates)}개 월 ({H2_START} ~ {H2_END})")

    # Test all factors
    logger.info(f"\n{'='*80}")
    logger.info("팩터 테스트 시작 (28개 팩터)")
    logger.info(f"{'='*80}\n")

    results = []

    for factor_name, factor_instance in FACTOR_REGISTRY.items():
        try:
            result = test_factor(
                factor_name,
                factor_instance,
                tickers,
                test_dates,
                db
            )

            results.append(result)

        except Exception as e:
            logger.error(f"❌ {factor_name} 테스트 실패: {e}")
            continue

    # Create results DataFrame
    df_results = pd.DataFrame(results)

    # Sort by |IC| descending
    df_results['abs_ic'] = df_results['mean_ic'].abs()
    df_results = df_results.sort_values('abs_ic', ascending=False).reset_index(drop=True)

    # Filter strong candidates (|IC| > 0.3 and p < 0.05)
    strong_candidates = df_results[
        (df_results['strong']) &
        (df_results['significant'])
    ].copy()

    logger.info(f"\n{'='*80}")
    logger.info("발굴 결과")
    logger.info(f"{'='*80}\n")

    logger.info(f"📊 전체 팩터: {len(df_results)}개")
    logger.info(f"   - 통계적 유의: {df_results['significant'].sum()}개 (p < {P_VALUE_THRESHOLD})")
    logger.info(f"   - 강력한 팩터: {len(strong_candidates)}개 (|IC| > {IC_THRESHOLD})")

    # Print all results
    logger.info(f"\n📈 전체 팩터 IC 랭킹 (상위 15개):")
    print("\n" + df_results.head(15)[['factor_name', 'mean_ic', 'mean_t_stat', 'mean_p_value', 'ic_std', 'n_months', 'significant', 'strong']].to_string(index=False))

    if len(strong_candidates) > 0:
        logger.info(f"\n🎯 강력한 팩터 후보 ({len(strong_candidates)}개):")
        print("\n" + strong_candidates[['factor_name', 'mean_ic', 'mean_t_stat', 'mean_p_value', 'ic_std', 'n_months']].to_string(index=False))

        # Save results
        results_dir = project_root / 'backtest_results'
        results_dir.mkdir(exist_ok=True)

        # Save all results
        all_results_file = results_dir / 'factor_discovery_all_results.csv'
        df_results.to_csv(all_results_file, index=False)
        logger.info(f"\n💾 전체 결과 저장: {all_results_file}")

        # Save strong candidates
        strong_results_file = results_dir / 'factor_discovery_strong_candidates.csv'
        strong_candidates.to_csv(strong_results_file, index=False)
        logger.info(f"💾 강력한 후보 저장: {strong_results_file}")

        # Next steps
        logger.info(f"\n{'='*80}")
        logger.info("다음 단계")
        logger.info(f"{'='*80}\n")

        logger.info(
            f"✅ {len(strong_candidates)}개 강력한 팩터 발굴 완료!\n\n"
            f"다음 작업:\n"
            f"1. 기존 팩터와의 상관관계 확인 (독립성 검증)\n"
            f"2. H1 vs H2 안정성 테스트 (과적합 방지)\n"
            f"3. 최종 후보 선정 및 백테스팅 검증"
        )
    else:
        logger.warning(
            f"\n⚠️ IC > {IC_THRESHOLD}인 강력한 팩터 없음\n\n"
            f"권장사항:\n"
            f"1. IC 기준 완화 (0.2 ~ 0.3 범위 검토)\n"
            f"2. 추가 팩터 개발 (복합 팩터, 비선형 팩터)\n"
            f"3. 다른 시장 데이터 활용 (해외 시장)"
        )

    logger.info(f"\n{'='*80}")
    logger.info("팩터 발굴 완료")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
