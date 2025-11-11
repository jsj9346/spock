"""
Query builder for Quant Platform CLI.

Provides fluent API for building SQL queries with filters,
sorting, and column selection.
"""

from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class SortOrder(Enum):
    """Sort order enumeration."""
    ASC = "ASC"
    DESC = "DESC"


class QueryBuilder:
    """
    Fluent query builder for ticker screening and data retrieval.

    Features:
    - Method chaining for intuitive query construction
    - Parameterized queries for SQL injection prevention
    - Support for filters, sorting, limits, and column selection
    - Automatic JOIN detection for related tables

    Usage:
        qb = QueryBuilder()
        query, params = (qb
            .tickers()
            .filter("per < $1", 15.0)
            .filter("pbr < $2", 1.0)
            .top(10)
            .order_by("market_cap", SortOrder.DESC)
            .build()
        )
    """

    def __init__(self):
        """Initialize query builder with default state."""
        self._base_table: str = ""
        self._columns: List[str] = ["*"]
        self._filters: List[str] = []
        self._params: List[Any] = []
        self._order_by: List[Tuple[str, SortOrder]] = []
        self._limit: Optional[int] = None
        self._region: str = "KR"  # Default to Korean market
        self._joins: List[str] = []
        self._param_counter: int = 0

    def tickers(self, region: str = "KR") -> 'QueryBuilder':
        """
        Start query from tickers table.

        Args:
            region: Market region (KR, US, etc.) Default: KR

        Returns:
            Self for method chaining
        """
        self._base_table = "tickers"
        self._region = region
        # Default columns for ticker queries
        self._columns = [
            "t.ticker",
            "t.region",
            "t.name",
            "t.name_eng",
            "t.exchange",
            "t.asset_type",
            "t.is_active"
        ]
        return self

    def select(self, columns: List[str]) -> 'QueryBuilder':
        """
        Specify columns to return.

        Args:
            columns: List of column names (supports table aliases)

        Returns:
            Self for method chaining
        """
        self._columns = columns
        return self

    def filter(self, condition: str, *params: Any) -> 'QueryBuilder':
        """
        Add filter condition with parameters.

        Args:
            condition: WHERE clause condition (use $1, $2 for parameters)
            *params: Parameter values

        Returns:
            Self for method chaining

        Example:
            .filter("per < $1", 15.0)
            .filter("pbr < $1 AND market_cap > $2", 1.5, 1000000000)
        """
        # Re-number parameters to maintain sequence
        adjusted_condition = condition
        for i, param in enumerate(params, start=1):
            self._param_counter += 1
            adjusted_condition = adjusted_condition.replace(f"${i}", f"${self._param_counter}")
            self._params.append(param)

        self._filters.append(adjusted_condition)
        return self

    def filter_dict(self, filters: Dict[str, Any]) -> 'QueryBuilder':
        """
        Add filters from dictionary (key=value format).

        Args:
            filters: Dictionary of column: value pairs

        Returns:
            Self for method chaining

        Example:
            .filter_dict({"region": "KR", "asset_type": "STOCK"})
        """
        for column, value in filters.items():
            self._param_counter += 1
            self._filters.append(f"{column} = ${self._param_counter}")
            self._params.append(value)
        return self

    def with_fundamentals(self) -> 'QueryBuilder':
        """
        Join with ticker_fundamentals table for financial metrics.

        Adds columns: per, pbr, dividend_yield, market_cap, ev_ebitda

        Returns:
            Self for method chaining
        """
        if "ticker_fundamentals" not in " ".join(self._joins):
            self._joins.append("""
                LEFT JOIN LATERAL (
                    SELECT per, pbr, dividend_yield, market_cap, shares_outstanding, ev, ev_ebitda
                    FROM ticker_fundamentals
                    WHERE ticker_fundamentals.ticker = t.ticker
                      AND ticker_fundamentals.region = t.region
                    ORDER BY date DESC
                    LIMIT 1
                ) f ON true
            """)

            # Add fundamental columns to selection
            if self._columns == ["*"] or "t.ticker" in self._columns:
                self._columns.extend([
                    "f.per",
                    "f.pbr",
                    "f.dividend_yield",
                    "f.market_cap",
                    "f.ev_ebitda"
                ])

        return self

    def with_technicals(self) -> 'QueryBuilder':
        """
        Join with ohlcv_data table for technical indicators.

        Adds columns: close, ma20, ma60, rsi_14, macd

        Returns:
            Self for method chaining
        """
        if "ohlcv_data" not in " ".join(self._joins):
            self._joins.append("""
                LEFT JOIN LATERAL (
                    SELECT close, volume, ma5, ma20, ma60, rsi_14, macd, macd_signal, bb_upper, bb_lower
                    FROM ohlcv_data
                    WHERE ohlcv_data.ticker = t.ticker
                      AND ohlcv_data.region = t.region
                      AND ohlcv_data.timeframe = '1d'
                    ORDER BY date DESC
                    LIMIT 1
                ) o ON true
            """)

            # Add technical columns to selection
            if self._columns == ["*"] or "t.ticker" in self._columns:
                self._columns.extend([
                    "o.close",
                    "o.ma20",
                    "o.ma60",
                    "o.rsi_14",
                    "o.macd"
                ])

        return self

    def with_details(self) -> 'QueryBuilder':
        """
        Join with stock_details table for sector/industry info.

        Adds columns: sector, industry

        Returns:
            Self for method chaining
        """
        if "stock_details" not in " ".join(self._joins):
            self._joins.append("""
                LEFT JOIN stock_details sd ON sd.ticker = t.ticker AND sd.region = t.region
            """)

            # Add detail columns to selection
            if self._columns == ["*"] or "t.ticker" in self._columns:
                self._columns.extend([
                    "sd.sector",
                    "sd.industry"
                ])

        return self

    def order_by(self, column: str, order: SortOrder = SortOrder.DESC) -> 'QueryBuilder':
        """
        Add sorting column and order (supports multiple columns).

        Args:
            column: Column name to sort by
            order: Sort direction (ASC or DESC)

        Returns:
            Self for method chaining

        Example:
            .order_by("per", SortOrder.ASC)
            .order_by("pbr", SortOrder.ASC)
        """
        self._order_by.append((column, order))
        return self

    def top(self, n: int) -> 'QueryBuilder':
        """
        Limit results to top N rows.

        Args:
            n: Maximum number of rows to return

        Returns:
            Self for method chaining
        """
        self._limit = n
        return self

    def limit(self, n: int) -> 'QueryBuilder':
        """Alias for top(). Limit results to N rows."""
        return self.top(n)

    def build(self) -> Tuple[str, List[Any]]:
        """
        Build final SQL query and parameters.

        Returns:
            Tuple of (query_string, parameters)

        Raises:
            ValueError: If base table not specified
        """
        if not self._base_table:
            raise ValueError("Base table not specified. Call tickers() first.")

        # Build SELECT clause
        columns_str = ", ".join(self._columns)
        query_parts = [f"SELECT {columns_str}"]

        # FROM clause
        query_parts.append(f"FROM {self._base_table} t")

        # JOIN clauses
        if self._joins:
            query_parts.extend(self._joins)

        # WHERE clause (always filter by region + is_active)
        where_conditions = [f"t.region = ${self._param_counter + 1}", "t.is_active = true"]
        self._params.append(self._region)
        self._param_counter += 1

        # Add user filters
        if self._filters:
            where_conditions.extend(self._filters)

        query_parts.append("WHERE " + " AND ".join(where_conditions))

        # ORDER BY clause (supports multiple columns)
        if self._order_by:
            order_clauses = [f"{column} {order.value}" for column, order in self._order_by]
            query_parts.append("ORDER BY " + ", ".join(order_clauses))

        # LIMIT clause
        if self._limit:
            query_parts.append(f"LIMIT {self._limit}")

        query = "\n".join(query_parts)
        return query, self._params

    def reset(self) -> 'QueryBuilder':
        """Reset builder to initial state."""
        self.__init__()
        return self

    def __str__(self) -> str:
        """String representation showing query and params."""
        try:
            query, params = self.build()
            return f"Query:\n{query}\n\nParams: {params}"
        except ValueError as e:
            return f"QueryBuilder (incomplete): {e}"
