"""
Example: Using ComparisonAnalyzer with Database

Demonstrates how to:
1. Fetch annual fundamental data from database
2. Analyze YoY growth and CAGR
3. Classify trends and generate summaries
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.fundamentals.comparison_analyzer import ComparisonAnalyzer
from modules.db_manager_postgres import PostgresDatabaseManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_annual_fundamentals(db: PostgresDatabaseManager, ticker: str, region: str) -> list:
    """
    Fetch annual fundamental data from database

    Args:
        db: Database manager instance
        ticker: Ticker symbol (e.g., '005930')
        region: Region code (e.g., 'KR')

    Returns:
        List of annual records sorted by fiscal_year DESC
    """
    query = """
        SELECT
            ticker,
            region,
            fiscal_year,
            date,
            revenue,
            operating_profit,
            net_income,
            ebitda,
            total_assets,
            total_equity,
            total_liabilities,
            per,
            pbr,
            ev_ebitda
        FROM ticker_fundamentals
        WHERE ticker = %s
            AND region = %s
            AND period_type = 'ANNUAL'
            AND fiscal_year IS NOT NULL
        ORDER BY fiscal_year DESC
    """

    results = db.execute_query(query, (ticker, region))

    if not results:
        logger.warning(f"No annual data found for {ticker} ({region})")
        return []

    # Convert to list of dictionaries (results are already dicts from PostgresDatabaseManager)
    annual_data = results
    logger.info(f"Fetched {len(annual_data)} years of data for {ticker}")

    return annual_data


def analyze_ticker(ticker: str, region: str = 'KR'):
    """
    Analyze fundamental trends for a ticker

    Args:
        ticker: Ticker symbol (e.g., '005930' for Samsung Electronics)
        region: Region code (default: 'KR')
    """
    logger.info(f"Analyzing {ticker} ({region})")

    # Initialize components
    db = PostgresDatabaseManager()
    analyzer = ComparisonAnalyzer()

    try:
        # Fetch annual data
        annual_data = fetch_annual_fundamentals(db, ticker, region)

        if not annual_data:
            logger.error(f"No data available for {ticker}")
            return

        # Define metrics to analyze (use only columns that exist in ticker_fundamentals)
        metrics = [
            'revenue',
            'operating_profit',
            'net_income',
            'ebitda',
            'total_assets',
            'total_equity'
        ]

        # Perform analysis
        result = analyzer.analyze_annual_comparison(annual_data, metrics=metrics)

        # Display results
        print(f"\n{'='*80}")
        print(f"Fundamental Analysis: {ticker} ({region})")
        print(f"{'='*80}")

        print(f"\nYears Analyzed: {result['summary']['years_analyzed']}")
        print(f"Overall Trend: {result['summary']['overall_trend']}")
        print(f"Strongest Metric: {result['summary']['strongest_metric']}")
        print(f"Weakest Metric: {result['summary']['weakest_metric']}")

        # Display YoY Growth
        print(f"\n{'-'*80}")
        print("Year-over-Year Growth Rates")
        print(f"{'-'*80}")

        for metric in ['revenue', 'net_income', 'ebitda']:
            if metric in result['yoy'] and result['yoy'][metric]:
                print(f"\n{metric.upper()}:")
                for period, growth in result['yoy'][metric].items():
                    trend_symbol = "+" if growth > 0 else "-" if growth < 0 else "="
                    print(f"  {period}: {growth:>8.2%} {trend_symbol}")

        # Display CAGR
        print(f"\n{'-'*80}")
        print("Compound Annual Growth Rate (CAGR)")
        print(f"{'-'*80}")

        for metric in ['revenue', 'net_income', 'ebitda']:
            if metric in result['cagr'] and result['cagr'][metric]:
                print(f"\n{metric.upper()}:")
                for period, cagr in result['cagr'][metric].items():
                    trend_symbol = "+" if cagr > 0 else "-" if cagr < 0 else "="
                    print(f"  {period}: {cagr:>8.2%} {trend_symbol}")

        # Display Trends
        print(f"\n{'-'*80}")
        print("Trend Classification")
        print(f"{'-'*80}")

        for metric, trend in result['trends'].items():
            if trend == 'improving':
                symbol = "[+] IMPROVING"
            elif trend == 'declining':
                symbol = "[-] DECLINING"
            elif trend == 'stable':
                symbol = "[=] STABLE"
            else:
                symbol = "[?] UNKNOWN"

            print(f"{metric:>25}: {symbol}")

        print(f"\n{'='*80}\n")

    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}", exc_info=True)


def compare_tickers(ticker1: str, ticker2: str, region: str = 'KR'):
    """
    Compare fundamental trends between two tickers

    Args:
        ticker1: First ticker symbol
        ticker2: Second ticker symbol
        region: Region code (default: 'KR')
    """
    logger.info(f"Comparing {ticker1} vs {ticker2} ({region})")

    db = PostgresDatabaseManager()
    analyzer = ComparisonAnalyzer()

    try:
        # Fetch data for both tickers
        data1 = fetch_annual_fundamentals(db, ticker1, region)
        data2 = fetch_annual_fundamentals(db, ticker2, region)

        if not data1 or not data2:
            logger.error("Insufficient data for comparison")
            return

        # Analyze both tickers
        metrics = ['revenue', 'net_income', 'ebitda', 'roe']
        result1 = analyzer.analyze_annual_comparison(data1, metrics=metrics)
        result2 = analyzer.analyze_annual_comparison(data2, metrics=metrics)

        # Display comparison
        print(f"\n{'='*80}")
        print(f"Comparison: {ticker1} vs {ticker2} ({region})")
        print(f"{'='*80}")

        print(f"\n{ticker1:>40} | {ticker2:>40}")
        print(f"{'-'*80}")

        for metric in metrics:
            # Get most recent YoY
            yoy1 = list(result1['yoy'].get(metric, {}).values())[0] if result1['yoy'].get(metric) else None
            yoy2 = list(result2['yoy'].get(metric, {}).values())[0] if result2['yoy'].get(metric) else None

            yoy1_str = f"{yoy1:>8.2%}" if yoy1 is not None else "N/A"
            yoy2_str = f"{yoy2:>8.2%}" if yoy2 is not None else "N/A"

            print(f"{metric:>20}: {yoy1_str:>15} | {yoy2_str:>15}")

        print(f"\n{'-'*80}")
        print(f"Overall Trend: {result1['summary']['overall_trend']:>22} | {result2['summary']['overall_trend']:>15}")
        print(f"{'='*80}\n")

    except Exception as e:
        logger.error(f"Error comparing tickers: {e}", exc_info=True)


if __name__ == "__main__":
    # Example 1: Analyze Samsung Electronics (005930)
    print("\n=== Example 1: Analyze Single Ticker ===")
    analyze_ticker('005930', 'KR')

    # Example 2: Analyze SK Hynix (000660)
    print("\n=== Example 2: Analyze Another Ticker ===")
    analyze_ticker('000660', 'KR')

    # Example 3: Compare Samsung vs SK Hynix
    print("\n=== Example 3: Compare Two Tickers ===")
    compare_tickers('005930', '000660', 'KR')
