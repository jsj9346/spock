"""
Fundamental Data Backfiller Extension (Phase 2.2)

Skeleton implementation for backfilling fundamental data (P/E, ROE, revenue)
from DART and KIS APIs.

Author: Spock Quant Platform
Date: 2025-10-29
Version: 1.0.0
Status: Skeleton Only (Not Implemented)
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, List, Dict, Any
import pandas as pd
from loguru import logger


class FundamentalBackfiller(ABC):
    """
    Fundamental data backfilling interface.

    Skeleton implementation - override methods for DART/KIS integration.

    Future Implementation:
        - DART API integration for Korean stocks (quarterly reports)
        - KIS API fundamental data extraction
        - yfinance fundamental data for global stocks
        - Data normalization and standardization
    """

    def __init__(self, db_manager, config: dict):
        """
        Initialize fundamental backfiller.

        Args:
            db_manager: PostgresDatabaseManager instance
            config: Configuration
                - enabled (bool): Whether fundamental backfill is enabled
                - dart_api_key (str): DART API key
                - kis_api_key (str): KIS API key
                - rate_limit (float): Max requests per second
        """
        self.db = db_manager
        self.config = config
        self.enabled = config.get('enabled', False)

        # API clients (lazy initialization)
        self.dart_client = None
        self.kis_client = None
        self.yfinance_client = None

        # API priority by region
        self.fundamental_priority = {
            'KR': ['dart', 'kis'],
            'US': ['yfinance'],
            'default': ['yfinance']
        }

        if self.enabled:
            logger.warning(
                "⚠️ FundamentalBackfiller is enabled but not implemented. "
                "This is a skeleton - fundamental backfill will not work."
            )

    @abstractmethod
    def backfill_fundamentals(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        metrics: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Backfill fundamental data from external APIs.

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date for backfill
            end_date: End date for backfill
            metrics: List of metrics to fetch
                - 'pe_ratio': Price-to-Earnings ratio
                - 'pb_ratio': Price-to-Book ratio
                - 'roe': Return on Equity
                - 'debt_to_equity': Debt to Equity ratio
                - 'revenue': Total revenue
                - 'net_income': Net income
                - 'operating_margin': Operating margin
                - 'dividend_yield': Dividend yield

        Returns:
            DataFrame with columns: [date, metric1, metric2, ...]
            Returns None if backfill fails or disabled

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            # 1. Try API sources by priority
            priority_list = self.fundamental_priority.get(region, ['yfinance'])

            for api_name in priority_list:
                if api_name == 'dart':
                    df = self._fetch_from_dart(ticker, start_date, end_date)
                elif api_name == 'kis':
                    df = self._fetch_from_kis(ticker, start_date, end_date)
                elif api_name == 'yfinance':
                    df = self._fetch_from_yfinance(ticker, start_date, end_date)

                if df is not None:
                    # 2. Filter requested metrics
                    if metrics:
                        df = df[['date'] + metrics]

                    # 3. Validate and save
                    self._save_to_postgres(df, ticker, region)
                    return df

            return None
            ```
        """
        if not self.enabled:
            logger.debug(f"Fundamental backfill disabled for {ticker}")
            return None

        raise NotImplementedError(
            "FundamentalBackfiller.backfill_fundamentals() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    @abstractmethod
    def _fetch_from_dart(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        Fetch fundamental data from DART API.

        Args:
            ticker: Korean stock ticker (6-digit code)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with quarterly financial statements

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            from modules.dart_api_client import DARTApiClient

            # 1. Convert ticker to corp_code
            corp_code = self._get_corp_code(ticker)

            # 2. Fetch quarterly reports
            dart_client = DARTApiClient()
            reports = dart_client.get_financial_statements(
                corp_code=corp_code,
                start_date=start_date,
                end_date=end_date,
                report_type='quarterly'
            )

            # 3. Parse financial data
            df = self._parse_dart_financials(reports)
            return df
            ```
        """
        if not self.enabled:
            return None

        raise NotImplementedError(
            "FundamentalBackfiller._fetch_from_dart() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    @abstractmethod
    def _fetch_from_kis(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        Fetch fundamental data from KIS API.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with fundamental data

        Raises:
            NotImplementedError: Skeleton method not implemented
        """
        if not self.enabled:
            return None

        raise NotImplementedError(
            "FundamentalBackfiller._fetch_from_kis() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    @abstractmethod
    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        Fetch fundamental data from yfinance.

        Args:
            ticker: Stock ticker symbol (yfinance format)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with fundamental data

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            import yfinance as yf

            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract fundamental metrics
            df = pd.DataFrame([{
                'date': pd.Timestamp.now(),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'roe': info.get('returnOnEquity'),
                'debt_to_equity': info.get('debtToEquity'),
                'revenue': info.get('totalRevenue'),
                'net_income': info.get('netIncomeToCommon'),
                'operating_margin': info.get('operatingMargins'),
                'dividend_yield': info.get('dividendYield')
            }])

            return df
            ```
        """
        if not self.enabled:
            return None

        raise NotImplementedError(
            "FundamentalBackfiller._fetch_from_yfinance() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    def _save_to_postgres(
        self,
        df: pd.DataFrame,
        ticker: str,
        region: str
    ) -> None:
        """
        Save fundamental data to PostgreSQL (future implementation).

        Args:
            df: DataFrame with fundamental data
            ticker: Stock ticker
            region: Market region
        """
        # Future implementation
        pass

    def is_enabled(self) -> bool:
        """
        Check if fundamental backfill is enabled.

        Returns:
            True if fundamental backfill is enabled
        """
        return self.enabled

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"FundamentalBackfiller(enabled={self.enabled}, "
            f"status='skeleton')"
        )
