#!/usr/bin/env python3
"""
Alpha/Beta Calculation for Three-Factor Strategy

2024년 Three-Factor 전략의 KOSPI 대비 상대 성과 분석:
- Alpha: 벤치마크 초과 수익률
- Beta: 시장 민감도
- Information Ratio: 초과 수익률의 일관성
- Tracking Error: 벤치마크 대비 변동성

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger
import yfinance as yf
from datetime import datetime
from scipy import stats

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Configuration
# ============================================================================

# Analysis period (2024년 전체)
START_DATE = '2024-01-01'
END_DATE = '2024-11-30'

# Portfolio equity curve file
EQUITY_CURVE_FILE = project_root / 'backtest_results' / 'three_factor_equity_curve.csv'

# KOSPI ticker for Yahoo Finance
KOSPI_TICKER = '^KS11'


# ============================================================================
# Helper Functions
# ============================================================================

def fetch_kospi_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch KOSPI index data from Yahoo Finance

    Parameters
    ----------
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)

    Returns
    -------
    pd.DataFrame
        KOSPI daily close prices (index: date)
    """
    logger.info(f"📊 KOSPI 데이터 수집 중... ({start_date} ~ {end_date})")

    try:
        kospi = yf.download(KOSPI_TICKER, start=start_date, end=end_date, progress=False)

        if kospi.empty:
            logger.error("❌ KOSPI 데이터를 가져올 수 없습니다")
            return pd.DataFrame()

        # Extract close prices and flatten if needed
        kospi_close = kospi['Close'].squeeze().copy()
        kospi_close.index = pd.to_datetime(kospi_close.index)

        logger.info(
            f"✅ KOSPI 데이터 수집 완료\n"
            f"   - 기간: {kospi_close.index[0].strftime('%Y-%m-%d')} ~ {kospi_close.index[-1].strftime('%Y-%m-%d')}\n"
            f"   - 데이터 행: {len(kospi_close)}\n"
            f"   - 시작가: {float(kospi_close.iloc[0]):.2f}\n"
            f"   - 종가: {float(kospi_close.iloc[-1]):.2f}"
        )

        return kospi_close

    except Exception as e:
        logger.error(f"❌ KOSPI 데이터 수집 실패: {e}")
        return pd.DataFrame()


def load_portfolio_equity_curve(filepath: Path) -> pd.DataFrame:
    """
    Load portfolio equity curve from CSV

    Parameters
    ----------
    filepath : Path
        Path to equity curve CSV file

    Returns
    -------
    pd.DataFrame
        Portfolio daily values (index: date)
    """
    logger.info(f"📊 포트폴리오 equity curve 로드 중...")

    try:
        equity_df = pd.read_csv(filepath, index_col=0, parse_dates=True)

        # Extract portfolio value column (should be 'group' for grouped portfolio)
        if 'group' in equity_df.columns:
            portfolio_value = equity_df['group'].copy()
        else:
            # If single column, use it
            portfolio_value = equity_df.iloc[:, 0].copy()

        logger.info(
            f"✅ 포트폴리오 데이터 로드 완료\n"
            f"   - 기간: {portfolio_value.index[0].strftime('%Y-%m-%d')} ~ {portfolio_value.index[-1].strftime('%Y-%m-%d')}\n"
            f"   - 데이터 행: {len(portfolio_value)}\n"
            f"   - 초기 자본: {portfolio_value.iloc[0]:,.0f}원\n"
            f"   - 최종 자산: {portfolio_value.iloc[-1]:,.0f}원"
        )

        return portfolio_value

    except Exception as e:
        logger.error(f"❌ Equity curve 로드 실패: {e}")
        return pd.DataFrame()


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate daily returns from price series

    Parameters
    ----------
    prices : pd.Series
        Daily price series

    Returns
    -------
    pd.Series
        Daily returns (percentage change)
    """
    returns = prices.pct_change().dropna()
    return returns


def calculate_alpha_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.035
) -> dict:
    """
    Calculate Alpha and Beta using linear regression

    Parameters
    ----------
    portfolio_returns : pd.Series
        Portfolio daily returns
    benchmark_returns : pd.Series
        Benchmark daily returns
    risk_free_rate : float
        Annual risk-free rate (default: 3.5% for 2024 KR)

    Returns
    -------
    dict
        Alpha, Beta, and related metrics
    """
    # Align dates
    aligned_data = pd.DataFrame({
        'portfolio': portfolio_returns,
        'benchmark': benchmark_returns
    }).dropna()

    if len(aligned_data) < 2:
        logger.error("❌ 충분한 데이터가 없습니다")
        return {}

    portfolio_ret = aligned_data['portfolio'].values
    benchmark_ret = aligned_data['benchmark'].values

    # Calculate daily risk-free rate
    daily_rf = (1 + risk_free_rate) ** (1/252) - 1

    # Excess returns
    portfolio_excess = portfolio_ret - daily_rf
    benchmark_excess = benchmark_ret - daily_rf

    # Linear regression: portfolio_excess = alpha + beta * benchmark_excess
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        benchmark_excess, portfolio_excess
    )

    # Annualize alpha (daily to annual)
    alpha_daily = intercept
    alpha_annual = (1 + alpha_daily) ** 252 - 1

    # Beta is the slope
    beta = slope

    # R-squared
    r_squared = r_value ** 2

    # Calculate tracking error (annualized)
    tracking_diff = portfolio_ret - benchmark_ret
    tracking_error = tracking_diff.std() * np.sqrt(252)

    # Information Ratio = Alpha / Tracking Error
    if tracking_error > 0:
        information_ratio = alpha_annual / tracking_error
    else:
        information_ratio = np.nan

    # Calculate Sharpe ratios for comparison
    portfolio_sharpe = (portfolio_excess.mean() * 252) / (portfolio_ret.std() * np.sqrt(252))
    benchmark_sharpe = (benchmark_excess.mean() * 252) / (benchmark_ret.std() * np.sqrt(252))

    # Total returns
    portfolio_total = (1 + portfolio_ret).prod() - 1
    benchmark_total = (1 + benchmark_ret).prod() - 1

    return {
        'alpha_annual': alpha_annual,
        'beta': beta,
        'r_squared': r_squared,
        'tracking_error': tracking_error,
        'information_ratio': information_ratio,
        'portfolio_sharpe': portfolio_sharpe,
        'benchmark_sharpe': benchmark_sharpe,
        'portfolio_return': portfolio_total,
        'benchmark_return': benchmark_total,
        'excess_return': portfolio_total - benchmark_total,
        'observations': len(aligned_data)
    }


# ============================================================================
# Main Analysis
# ============================================================================

def main():
    """Run Alpha/Beta Analysis"""

    logger.info("=" * 80)
    logger.info("Three-Factor Strategy - KOSPI 벤치마크 비교 분석")
    logger.info("=" * 80)

    # ========================================================================
    # Step 1: Load Portfolio Data
    # ========================================================================

    logger.info("\n[1/3] 포트폴리오 데이터 로드...")

    portfolio_value = load_portfolio_equity_curve(EQUITY_CURVE_FILE)

    if portfolio_value.empty:
        logger.error("❌ 포트폴리오 데이터를 로드할 수 없습니다. 먼저 백테스트를 실행하세요.")
        return

    # Calculate portfolio returns
    portfolio_returns = calculate_returns(portfolio_value)

    # ========================================================================
    # Step 2: Fetch KOSPI Data
    # ========================================================================

    logger.info("\n[2/3] KOSPI 벤치마크 데이터 수집...")

    kospi_prices = fetch_kospi_data(START_DATE, END_DATE)

    if kospi_prices.empty:
        logger.error("❌ KOSPI 데이터를 가져올 수 없습니다")
        return

    # Calculate KOSPI returns
    kospi_returns = calculate_returns(kospi_prices)

    # ========================================================================
    # Step 3: Calculate Alpha/Beta
    # ========================================================================

    logger.info("\n[3/3] Alpha/Beta 계산...")

    metrics = calculate_alpha_beta(portfolio_returns, kospi_returns)

    if not metrics:
        logger.error("❌ Alpha/Beta 계산 실패")
        return

    # ========================================================================
    # Display Results
    # ========================================================================

    logger.info("\n📊 성과 분석 결과:")
    logger.info("=" * 80)

    logger.info(f"\n📈 수익률 비교:")
    logger.info(f"   - 포트폴리오: {metrics['portfolio_return']*100:+.2f}%")
    logger.info(f"   - KOSPI:      {metrics['benchmark_return']*100:+.2f}%")
    logger.info(f"   - 초과 수익률: {metrics['excess_return']*100:+.2f}%p")

    logger.info(f"\n🎯 Alpha/Beta:")
    logger.info(f"   - Alpha (연환산): {metrics['alpha_annual']*100:+.2f}%")
    logger.info(f"   - Beta:           {metrics['beta']:.3f}")
    logger.info(f"   - R²:             {metrics['r_squared']:.3f}")

    logger.info(f"\n📊 리스크 조정 지표:")
    logger.info(f"   - 포트폴리오 Sharpe: {metrics['portfolio_sharpe']:.3f}")
    logger.info(f"   - KOSPI Sharpe:      {metrics['benchmark_sharpe']:.3f}")
    logger.info(f"   - Information Ratio: {metrics['information_ratio']:.3f}")
    logger.info(f"   - Tracking Error:    {metrics['tracking_error']*100:.2f}%")

    logger.info(f"\n📋 데이터 품질:")
    logger.info(f"   - 관측치: {metrics['observations']}일")

    # ========================================================================
    # Interpretation
    # ========================================================================

    logger.info("\n📋 해석:")
    logger.info("=" * 80)

    # Alpha interpretation
    if metrics['alpha_annual'] > 0.05:
        logger.info(f"✅ 강한 양의 알파 ({metrics['alpha_annual']*100:+.2f}%): 벤치마크를 크게 초과하는 성과")
    elif metrics['alpha_annual'] > 0:
        logger.info(f"👍 양의 알파 ({metrics['alpha_annual']*100:+.2f}%): 벤치마크를 초과하는 성과")
    else:
        logger.info(f"⚠️ 음의 알파 ({metrics['alpha_annual']*100:+.2f}%): 벤치마크 대비 저조한 성과")

    # Beta interpretation
    if metrics['beta'] > 1.2:
        logger.info(f"⚠️ 높은 베타 ({metrics['beta']:.3f}): 시장 대비 높은 변동성 (공격적)")
    elif metrics['beta'] > 0.8:
        logger.info(f"✅ 적정 베타 ({metrics['beta']:.3f}): 시장과 유사한 변동성")
    else:
        logger.info(f"👍 낮은 베타 ({metrics['beta']:.3f}): 시장 대비 낮은 변동성 (방어적)")

    # Information Ratio interpretation
    if metrics['information_ratio'] > 0.5:
        logger.info(f"✅ 높은 정보 비율 ({metrics['information_ratio']:.3f}): 일관된 초과 수익")
    elif metrics['information_ratio'] > 0:
        logger.info(f"👍 양의 정보 비율 ({metrics['information_ratio']:.3f}): 초과 수익 존재")
    else:
        logger.info(f"⚠️ 음의 정보 비율 ({metrics['information_ratio']:.3f}): 초과 수익 부족")

    logger.info("\n" + "=" * 80)
    logger.info("분석 완료")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
