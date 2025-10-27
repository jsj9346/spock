#!/usr/bin/env python3
"""
Multi-Factor Analysis & Ranking Report
Demonstrates factor effectiveness through current rankings and composition analysis

This script analyzes factor scores from the database and generates:
1. Top stocks by each factor category (Value, Momentum, Quality)
2. Multi-factor composite rankings
3. Factor correlation matrix
4. Factor distribution statistics
5. Sector diversification analysis
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import date, datetime
from loguru import logger

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.db_manager_postgres import PostgresDatabaseManager


def load_factor_scores(db: PostgresDatabaseManager, analysis_date: date = None) -> pd.DataFrame:
    """
    Load all factor scores for Korean stocks

    Args:
        db: Database manager instance
        analysis_date: Date to analyze (default: today)

    Returns:
        DataFrame with columns: ticker, factor_name, percentile, z_score, raw_value
    """
    if analysis_date is None:
        analysis_date = date.today()

    logger.info(f"📊 Loading factor scores for {analysis_date}...")

    query = """
        SELECT
            ticker,
            factor_name,
            score,
            percentile
        FROM factor_scores
        WHERE region = 'KR'
          AND date = %s
        ORDER BY ticker, factor_name
    """

    results = db.execute_query(query, (analysis_date,))

    if not results:
        logger.error(f"❌ No factor scores found for {analysis_date}")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Convert numeric columns from Decimal to float
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df['percentile'] = pd.to_numeric(df['percentile'], errors='coerce')

    logger.info(f"✅ Loaded {len(df)} factor scores for {df['ticker'].nunique()} stocks")

    return df


def get_stock_info(db: PostgresDatabaseManager, tickers: list) -> pd.DataFrame:
    """
    Get stock names and sectors for given tickers

    Args:
        db: Database manager instance
        tickers: List of ticker codes

    Returns:
        DataFrame with columns: ticker, name, sector
    """
    if not tickers:
        return pd.DataFrame()

    placeholders = ', '.join(['%s'] * len(tickers))
    query = f"""
        SELECT
            t.ticker,
            t.name,
            COALESCE(sd.sector, 'Unknown') as sector
        FROM tickers t
        LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
        WHERE t.ticker IN ({placeholders})
          AND t.region = 'KR'
    """

    results = db.execute_query(query, tuple(tickers))
    return pd.DataFrame(results)


def calculate_factor_category_scores(df: pd.DataFrame, category_factors: dict) -> pd.DataFrame:
    """
    Calculate composite scores for each factor category

    Args:
        df: Factor scores DataFrame
        category_factors: Dict mapping category names to list of factor names

    Returns:
        DataFrame with composite scores for each category
    """
    results = []

    for category, factors in category_factors.items():
        # Filter to category factors
        category_df = df[df['factor_name'].isin(factors)].copy()

        if category_df.empty:
            logger.warning(f"⚠️ No data for {category} category")
            continue

        # Pivot to get one row per ticker
        pivot = category_df.pivot(index='ticker', columns='factor_name', values='percentile')

        # Calculate composite score (equal weight average)
        pivot[f'{category}_score'] = pivot.mean(axis=1)

        # Get tickers with complete data (all factors available)
        complete = pivot.dropna()

        result_df = complete[[f'{category}_score']].reset_index()
        result_df['category'] = category
        result_df['num_factors'] = len(factors)

        # Ensure score column is numeric
        result_df[f'{category}_score'] = pd.to_numeric(result_df[f'{category}_score'], errors='coerce')

        results.append(result_df)

        logger.info(f"✅ {category}: {len(complete)} stocks with complete factor coverage")

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def get_top_stocks_by_category(
    factor_df: pd.DataFrame,
    category_scores: pd.DataFrame,
    stock_info: pd.DataFrame,
    top_n: int = 20
) -> dict:
    """
    Get top N stocks for each factor category

    Args:
        factor_df: Raw factor scores
        category_scores: Composite category scores
        stock_info: Stock information (name, sector)
        top_n: Number of top stocks to return

    Returns:
        Dict mapping category name to DataFrame of top stocks
    """
    top_stocks = {}

    for category in category_scores['category'].unique():
        # Get top stocks by composite score
        cat_df = category_scores[category_scores['category'] == category].copy()
        score_col = f'{category}_score'

        top = cat_df.nlargest(top_n, score_col)

        # Merge with stock info
        top = top.merge(stock_info, on='ticker', how='left')

        # Add individual factor scores
        for _, row in top.iterrows():
            ticker = row['ticker']
            ticker_factors = factor_df[factor_df['ticker'] == ticker][['factor_name', 'percentile']]

            for _, factor_row in ticker_factors.iterrows():
                factor_name = factor_row['factor_name']
                top.loc[top['ticker'] == ticker, factor_name] = factor_row['percentile']

        top_stocks[category] = top

        logger.info(f"✅ Top {len(top)} stocks for {category}")

    return top_stocks


def calculate_factor_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate correlation matrix between all factors

    Args:
        df: Factor scores DataFrame

    Returns:
        Correlation matrix DataFrame
    """
    logger.info("📊 Calculating factor correlations...")

    # Pivot to get factors as columns
    pivot = df.pivot(index='ticker', columns='factor_name', values='percentile')

    # Calculate correlations
    corr = pivot.corr()

    logger.info(f"✅ Correlation matrix: {corr.shape[0]} factors")

    return corr


def calculate_multi_factor_composite(
    df: pd.DataFrame,
    factors: list,
    weights: dict = None
) -> pd.DataFrame:
    """
    Calculate multi-factor composite score

    Args:
        df: Factor scores DataFrame
        factors: List of factor names to include
        weights: Optional dict mapping factor names to weights (default: equal weight)

    Returns:
        DataFrame with composite scores
    """
    logger.info(f"📊 Calculating multi-factor composite ({len(factors)} factors)...")

    # Filter to specified factors
    multi_df = df[df['factor_name'].isin(factors)].copy()

    # Pivot to get one row per ticker
    pivot = multi_df.pivot(index='ticker', columns='factor_name', values='percentile')

    # Only keep stocks with all factors
    complete = pivot.dropna()

    # Apply weights
    if weights is None:
        # Equal weight
        composite = complete.mean(axis=1)
    else:
        # Weighted average
        weighted_scores = pd.Series(0, index=complete.index)
        total_weight = sum(weights.values())

        for factor, weight in weights.items():
            if factor in complete.columns:
                weighted_scores += complete[factor] * (weight / total_weight)

        composite = weighted_scores

    result = pd.DataFrame({
        'ticker': composite.index,
        'composite_score': composite.values
    })

    logger.info(f"✅ Multi-factor composite: {len(result)} stocks with complete coverage")

    return result


def generate_factor_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate summary statistics for each factor

    Args:
        df: Factor scores DataFrame

    Returns:
        DataFrame with statistics by factor
    """
    logger.info("📊 Generating factor statistics...")

    stats = []

    for factor in df['factor_name'].unique():
        factor_data = df[df['factor_name'] == factor]['percentile']

        stats.append({
            'factor_name': factor,
            'count': len(factor_data),
            'mean': factor_data.mean(),
            'std': factor_data.std(),
            'min': factor_data.min(),
            'q25': factor_data.quantile(0.25),
            'median': factor_data.median(),
            'q75': factor_data.quantile(0.75),
            'max': factor_data.max()
        })

    stats_df = pd.DataFrame(stats)

    logger.info(f"✅ Statistics calculated for {len(stats_df)} factors")

    return stats_df


def analyze_sector_diversification(
    top_stocks: dict,
    stock_info: pd.DataFrame
) -> pd.DataFrame:
    """
    Analyze sector diversification of top stocks by category

    Args:
        top_stocks: Dict of top stocks by category
        stock_info: Stock information with sectors

    Returns:
        DataFrame with sector distribution by category
    """
    logger.info("📊 Analyzing sector diversification...")

    diversification = []

    for category, stocks in top_stocks.items():
        sector_counts = stocks['sector'].value_counts()

        for sector, count in sector_counts.items():
            diversification.append({
                'category': category,
                'sector': sector,
                'count': count,
                'percentage': (count / len(stocks)) * 100
            })

    div_df = pd.DataFrame(diversification)

    logger.info(f"✅ Sector diversification analyzed for {len(top_stocks)} categories")

    return div_df


def print_report(
    factor_df: pd.DataFrame,
    category_scores: pd.DataFrame,
    top_stocks: dict,
    multi_factor_top: pd.DataFrame,
    correlations: pd.DataFrame,
    statistics: pd.DataFrame,
    diversification: pd.DataFrame,
    analysis_date: date
):
    """
    Print comprehensive factor analysis report
    """
    print("\n" + "="*80)
    print(f"📊 MULTI-FACTOR ANALYSIS REPORT - {analysis_date}")
    print("="*80)

    # 1. Overview
    print("\n" + "─"*80)
    print("1️⃣ OVERVIEW")
    print("─"*80)
    print(f"Analysis Date: {analysis_date}")
    print(f"Total Stocks Analyzed: {factor_df['ticker'].nunique()}")
    print(f"Total Factors: {factor_df['factor_name'].nunique()}")
    print(f"Factor Categories: {category_scores['category'].nunique()}")
    print("\nFactors by Category:")

    factor_categories = {
        'Value': ['PE_Ratio', 'PB_Ratio'],
        'Momentum': ['12M_Momentum', 'RSI_Momentum', '1M_Momentum'],
        'Quality': ['Earnings_Quality', 'Book_Value_Quality', 'Dividend_Stability']
    }

    for category, factors in factor_categories.items():
        available = [f for f in factors if f in factor_df['factor_name'].values]
        print(f"  • {category}: {', '.join(available)}")

    # 2. Factor Statistics
    print("\n" + "─"*80)
    print("2️⃣ FACTOR STATISTICS")
    print("─"*80)
    print(statistics.to_string(index=False))

    # 3. Factor Correlations
    print("\n" + "─"*80)
    print("3️⃣ FACTOR CORRELATIONS")
    print("─"*80)
    print("(Values range from -1 to +1, where 0 = no correlation)")
    print(correlations.round(3).to_string())

    # 4. Top Stocks by Category
    print("\n" + "─"*80)
    print("4️⃣ TOP 20 STOCKS BY FACTOR CATEGORY")
    print("─"*80)

    for category, stocks in top_stocks.items():
        print(f"\n🏆 {category.upper()} (Top 20)")
        print("─"*80)

        score_col = f'{category}_score'
        display_cols = ['ticker', 'name', 'sector', score_col]

        # Add available factor columns
        factor_cols = [col for col in stocks.columns if col in factor_df['factor_name'].values]
        display_cols.extend(factor_cols)

        print(stocks[display_cols].head(20).to_string(index=False))

    # 5. Multi-Factor Composite Rankings
    print("\n" + "─"*80)
    print("5️⃣ MULTI-FACTOR COMPOSITE RANKINGS (Top 20)")
    print("─"*80)
    print("(Combined all 8 factors with equal weighting)")
    print(multi_factor_top.head(20).to_string(index=False))

    # 6. Sector Diversification
    print("\n" + "─"*80)
    print("6️⃣ SECTOR DIVERSIFICATION")
    print("─"*80)
    print(diversification.to_string(index=False))

    # 7. Key Insights
    print("\n" + "─"*80)
    print("7️⃣ KEY INSIGHTS")
    print("─"*80)

    # Correlation insights
    high_corr = []
    low_corr = []
    for i in range(len(correlations.columns)):
        for j in range(i+1, len(correlations.columns)):
            factor1 = correlations.columns[i]
            factor2 = correlations.columns[j]
            corr_val = correlations.iloc[i, j]

            if abs(corr_val) > 0.7:
                high_corr.append((factor1, factor2, corr_val))
            elif abs(corr_val) < 0.2:
                low_corr.append((factor1, factor2, corr_val))

    print("\n📈 Highly Correlated Factors (|r| > 0.7):")
    if high_corr:
        for f1, f2, r in high_corr:
            print(f"  • {f1} ↔ {f2}: {r:.3f}")
    else:
        print("  • None found (good factor independence)")

    print("\n🎯 Independent Factors (|r| < 0.2):")
    if low_corr:
        for f1, f2, r in low_corr[:5]:  # Show top 5
            print(f"  • {f1} ↔ {f2}: {r:.3f}")
    else:
        print("  • None found")

    # Sector concentration insights
    print("\n🏢 Sector Concentration:")
    for category in diversification['category'].unique():
        cat_div = diversification[diversification['category'] == category]
        top_sector = cat_div.nlargest(1, 'percentage').iloc[0]
        print(f"  • {category}: {top_sector['sector']} ({top_sector['percentage']:.1f}%)")

    print("\n" + "="*80)
    print("✅ REPORT GENERATION COMPLETE")
    print("="*80 + "\n")


def save_report_to_file(
    factor_df: pd.DataFrame,
    top_stocks: dict,
    multi_factor_top: pd.DataFrame,
    correlations: pd.DataFrame,
    statistics: pd.DataFrame,
    analysis_date: date,
    output_dir: str = "reports"
):
    """
    Save analysis results to CSV files
    """
    logger.info(f"💾 Saving report files to {output_dir}/...")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    date_str = analysis_date.strftime("%Y%m%d")

    # Save statistics
    stats_file = f"{output_dir}/{date_str}_factor_statistics.csv"
    statistics.to_csv(stats_file, index=False, encoding='utf-8-sig')
    logger.info(f"✅ Saved: {stats_file}")

    # Save correlations
    corr_file = f"{output_dir}/{date_str}_factor_correlations.csv"
    correlations.to_csv(corr_file, encoding='utf-8-sig')
    logger.info(f"✅ Saved: {corr_file}")

    # Save top stocks by category
    for category, stocks in top_stocks.items():
        stocks_file = f"{output_dir}/{date_str}_top_stocks_{category.lower()}.csv"
        stocks.to_csv(stocks_file, index=False, encoding='utf-8-sig')
        logger.info(f"✅ Saved: {stocks_file}")

    # Save multi-factor composite
    multi_file = f"{output_dir}/{date_str}_multifactor_composite.csv"
    multi_factor_top.to_csv(multi_file, index=False, encoding='utf-8-sig')
    logger.info(f"✅ Saved: {multi_file}")

    logger.info(f"✅ All report files saved to {output_dir}/")


def main():
    """Main execution"""
    logger.info("="*80)
    logger.info("📊 MULTI-FACTOR ANALYSIS & RANKING REPORT")
    logger.info("="*80)

    # Initialize database
    db = PostgresDatabaseManager()

    # Load factor scores
    analysis_date = date.today()
    factor_df = load_factor_scores(db, analysis_date)

    if factor_df.empty:
        logger.error("❌ No factor scores available. Run factor calculation scripts first.")
        return

    # Define factor categories
    factor_categories = {
        'Value': ['PE_Ratio', 'PB_Ratio'],
        'Momentum': ['12M_Momentum', 'RSI_Momentum', '1M_Momentum'],
        'Quality': ['Earnings_Quality', 'Book_Value_Quality', 'Dividend_Stability']
    }

    # Calculate category composite scores
    category_scores = calculate_factor_category_scores(factor_df, factor_categories)

    # Get stock information
    all_tickers = factor_df['ticker'].unique().tolist()
    stock_info = get_stock_info(db, all_tickers)

    # Get top stocks by category
    top_stocks = get_top_stocks_by_category(factor_df, category_scores, stock_info, top_n=20)

    # Calculate multi-factor composite
    all_factors = [f for factors in factor_categories.values() for f in factors]
    multi_composite = calculate_multi_factor_composite(factor_df, all_factors)
    multi_factor_top = multi_composite.merge(stock_info, on='ticker', how='left')
    multi_factor_top = multi_factor_top.sort_values('composite_score', ascending=False)

    # Calculate factor correlations
    correlations = calculate_factor_correlations(factor_df)

    # Generate factor statistics
    statistics = generate_factor_statistics(factor_df)

    # Analyze sector diversification
    diversification = analyze_sector_diversification(top_stocks, stock_info)

    # Print report
    print_report(
        factor_df,
        category_scores,
        top_stocks,
        multi_factor_top,
        correlations,
        statistics,
        diversification,
        analysis_date
    )

    # Save to files
    save_report_to_file(
        factor_df,
        top_stocks,
        multi_factor_top,
        correlations,
        statistics,
        analysis_date
    )

    logger.info("✅ Multi-factor analysis complete!")


if __name__ == "__main__":
    main()
