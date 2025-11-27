# mcp_server/tools/dividend_tool.py
"""
Dividend History MCP Tool

Provides dividend history query and growth analysis for stocks.
Supports multiple regions and includes CAGR, streak analysis, and upcoming dividends.
"""

from typing import Any, Sequence, List, Dict, Optional
from datetime import datetime, date
import json
import structlog

from mcp.types import Tool, TextContent

from ..adapters.data_adapter import DataAdapter
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()

# Currency mapping
CURRENCY_MAP = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "HK": "HKD",
    "CN": "CNY",
    "VN": "VND",
}


def get_dividend_tool_def() -> Tool:
    """Get tool definition for query_dividend_history."""
    return Tool(
        name="query_dividend_history",
        description=(
            "Get dividend payment history for stocks. "
            "Includes dividend amounts, dates, yields, and growth analysis. "
            "Useful for income investing strategy and dividend growth analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of ticker symbols. "
                        "KR format: 6-digit numeric (e.g., 005930). "
                        "US format: 1-5 uppercase letters (e.g., AAPL). "
                        "Maximum 20 tickers per request."
                    ),
                    "minItems": 1,
                    "maxItems": 20
                },
                "years": {
                    "type": "integer",
                    "description": "Number of years of history (1-10). Default: 5",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5
                },
                "include_growth_analysis": {
                    "type": "boolean",
                    "description": "Include dividend growth rate analysis (CAGR, streak). Default: true",
                    "default": True
                },
                "include_upcoming": {
                    "type": "boolean",
                    "description": "Include upcoming dividend dates if available. Default: true",
                    "default": True
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                    "description": "Market region code. Default: KR",
                    "default": "KR"
                }
            },
            "required": ["tickers"]
        }
    )


def calculate_dividend_cagr(dividends: List[Dict], years: int) -> Optional[float]:
    """
    Calculate Compound Annual Growth Rate for dividends.

    Args:
        dividends: List of dividend records sorted by fiscal_year DESC
        years: Number of years to calculate CAGR for

    Returns:
        CAGR as a decimal (e.g., 0.05 for 5%) or None if insufficient data
    """
    if len(dividends) < 2:
        return None

    # Group by fiscal year and sum annual dividends
    annual_dividends = {}
    for div in dividends:
        year = div.get('fiscal_year')
        dps = div.get('dividend_per_share') or 0
        if year:
            annual_dividends[year] = annual_dividends.get(year, 0) + dps

    if len(annual_dividends) < 2:
        return None

    # Get first and last year with dividends
    years_sorted = sorted(annual_dividends.keys())
    first_year = years_sorted[0]
    last_year = years_sorted[-1]

    first_value = annual_dividends[first_year]
    last_value = annual_dividends[last_year]

    if first_value <= 0 or last_value <= 0:
        return None

    # Calculate CAGR
    n_years = last_year - first_year
    if n_years <= 0:
        return None

    cagr = (last_value / first_value) ** (1 / n_years) - 1
    return round(cagr, 4)


def calculate_dividend_streak(dividends: List[Dict]) -> Dict:
    """
    Calculate dividend payment streak.

    Returns:
        Dict with consecutive_years, streak_type, and last_year
    """
    if not dividends:
        return {"consecutive_years": 0, "streak_type": "none", "last_year": None}

    # Get unique fiscal years with dividends
    years_with_dividends = sorted(set(
        d.get('fiscal_year') for d in dividends
        if d.get('fiscal_year') and (d.get('dividend_per_share') or 0) > 0
    ))

    if not years_with_dividends:
        return {"consecutive_years": 0, "streak_type": "none", "last_year": None}

    # Count consecutive years from most recent
    current_year = datetime.now().year
    consecutive = 0
    last_year = years_with_dividends[-1]

    # Check if most recent dividend is within last 2 years
    if last_year >= current_year - 1:
        consecutive = 1
        for i in range(len(years_with_dividends) - 2, -1, -1):
            if years_with_dividends[i + 1] - years_with_dividends[i] == 1:
                consecutive += 1
            else:
                break

    # Determine streak type
    if consecutive >= 25:
        streak_type = "dividend_aristocrat"
    elif consecutive >= 10:
        streak_type = "dividend_achiever"
    elif consecutive >= 5:
        streak_type = "stable"
    elif consecutive > 0:
        streak_type = "maintained"
    else:
        streak_type = "none"

    return {
        "consecutive_years": consecutive,
        "streak_type": streak_type,
        "last_year": last_year
    }


def get_annual_summary(dividends: List[Dict], year: int) -> Dict:
    """Get annual dividend summary for a specific year."""
    year_dividends = [d for d in dividends if d.get('fiscal_year') == year]

    if not year_dividends:
        return {
            "total_dps": 0,
            "payments": 0,
            "types": []
        }

    total_dps = sum(d.get('dividend_per_share') or 0 for d in year_dividends)
    types = list(set(d.get('dividend_type') for d in year_dividends if d.get('dividend_type')))

    return {
        "total_dps": round(total_dps, 4),
        "payments": len(year_dividends),
        "types": types
    }


def format_dividend_response(
    results: Dict[str, List[Dict]],
    region: str,
    include_growth_analysis: bool,
    include_upcoming: bool
) -> Dict:
    """
    Format dividend history results for MCP response.

    Args:
        results: Dividend records by ticker
        region: Market region
        include_growth_analysis: Whether to include CAGR and streak
        include_upcoming: Whether to include upcoming dividends

    Returns:
        Formatted response dict
    """
    formatted_data = {}
    current_year = datetime.now().year
    today = date.today()

    for ticker, dividends in results.items():
        if not dividends:
            formatted_data[ticker] = {
                "ticker": ticker,
                "region": region,
                "has_dividends": False,
                "message": "No dividend history found"
            }
            continue

        # Sort by fiscal year and ex-dividend date
        dividends_sorted = sorted(
            dividends,
            key=lambda x: (x.get('fiscal_year', 0), x.get('ex_dividend_date') or ''),
            reverse=True
        )

        ticker_result = {
            "ticker": ticker,
            "region": region,
            "currency": dividends_sorted[0].get('currency') or CURRENCY_MAP.get(region, "USD"),
            "has_dividends": True,
            "dividend_history": []
        }

        # Format individual dividend records
        for div in dividends_sorted:
            div_record = {
                "fiscal_year": div.get('fiscal_year'),
                "dividend_type": div.get('dividend_type'),
                "dividend_per_share": div.get('dividend_per_share'),
                "dividend_yield": div.get('dividend_yield'),
            }

            # Add dates if available
            if div.get('ex_dividend_date'):
                div_record["ex_dividend_date"] = str(div.get('ex_dividend_date'))
            if div.get('payment_date'):
                div_record["payment_date"] = str(div.get('payment_date'))
            if div.get('payout_ratio'):
                div_record["payout_ratio"] = div.get('payout_ratio')

            ticker_result["dividend_history"].append(div_record)

        # Add growth analysis if requested
        if include_growth_analysis:
            cagr_3y = calculate_dividend_cagr(
                [d for d in dividends if d.get('fiscal_year', 0) >= current_year - 3],
                3
            )
            cagr_5y = calculate_dividend_cagr(
                [d for d in dividends if d.get('fiscal_year', 0) >= current_year - 5],
                5
            )
            streak = calculate_dividend_streak(dividends)

            # Calculate average payout ratio
            payout_ratios = [d.get('payout_ratio') for d in dividends if d.get('payout_ratio')]
            avg_payout = round(sum(payout_ratios) / len(payout_ratios), 2) if payout_ratios else None

            ticker_result["growth_analysis"] = {
                "dividend_cagr_3y": cagr_3y,
                "dividend_cagr_5y": cagr_5y,
                "consecutive_years": streak["consecutive_years"],
                "dividend_streak": streak["streak_type"],
                "average_payout_ratio": avg_payout,
            }

        # Add upcoming dividends if requested
        if include_upcoming:
            # Find future ex-dividend dates
            upcoming = []
            for d in dividends:
                ex_date = d.get('ex_dividend_date')
                if ex_date:
                    # Convert string to date if needed
                    if isinstance(ex_date, str):
                        try:
                            ex_date_obj = datetime.strptime(ex_date, '%Y-%m-%d').date()
                        except ValueError:
                            continue
                    else:
                        ex_date_obj = ex_date
                    if ex_date_obj > today:
                        upcoming.append((ex_date_obj, d))

            if upcoming:
                # Sort by date and get the next one
                upcoming.sort(key=lambda x: x[0])
                next_div = upcoming[0][1]
                ticker_result["upcoming"] = {
                    "next_ex_date": str(next_div.get('ex_dividend_date')),
                    "expected_dps": next_div.get('dividend_per_share'),
                    "dividend_type": next_div.get('dividend_type')
                }

        # Add summary
        current_year_summary = get_annual_summary(dividends, current_year)
        last_year_summary = get_annual_summary(dividends, current_year - 1)

        ticker_result["summary"] = {
            "annual_dividend_current": current_year_summary["total_dps"],
            "annual_dividend_last_year": last_year_summary["total_dps"],
            "payments_current_year": current_year_summary["payments"],
            "dividend_types": current_year_summary["types"] or last_year_summary["types"]
        }

        formatted_data[ticker] = ticker_result

    return {
        "success": True,
        "data": formatted_data,
        "metadata": {
            "ticker_count": len(formatted_data),
            "region": region,
            "include_growth_analysis": include_growth_analysis,
            "include_upcoming": include_upcoming,
            "query_time": datetime.now().isoformat()
        }
    }


async def handle_query_dividend_history(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle query_dividend_history tool execution."""

    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    years = arguments.get("years", 5)
    include_growth_analysis = arguments.get("include_growth_analysis", True)
    include_upcoming = arguments.get("include_upcoming", True)
    region = arguments.get("region", "KR")

    try:
        logger.info(
            "query_dividend_history_start",
            tickers=tickers,
            years=years,
            region=region
        )

        # Validate inputs
        if not tickers:
            raise ValidationError("At least one ticker is required", {"tickers": tickers})

        if len(tickers) > 20:
            raise ValidationError(
                f"Maximum 20 tickers allowed, got {len(tickers)}",
                {"ticker_count": len(tickers)}
            )

        # Get dividend history for each ticker
        results = await adapter.get_dividend_history(
            tickers=tickers,
            region=region,
            years=years
        )

        # Format response
        response = format_dividend_response(
            results,
            region,
            include_growth_analysis,
            include_upcoming
        )

        logger.info(
            "query_dividend_history_success",
            ticker_count=len(results),
            region=region
        )

        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False, default=str))]

    except ValidationError as e:
        logger.warning("query_dividend_history_validation_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DataNotFoundError as e:
        logger.warning("query_dividend_history_not_found", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DatabaseError as e:
        logger.error("query_dividend_history_database_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except Exception as e:
        logger.error("query_dividend_history_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
