# mcp_server/tools/cagr_tool.py
"""
CAGR (Compound Annual Growth Rate) MCP Tool

Calculates CAGR for various financial metrics from ticker_fundamentals table.
Supports revenue, earnings, assets, equity, cash flow, and price metrics.
"""

from typing import Any, Sequence, List, Optional
from datetime import datetime
import json
import structlog

from mcp.types import Tool, TextContent

from ..adapters.data_adapter import DataAdapter
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()

# Available metrics for CAGR calculation
CAGR_METRICS = {
    # Price & Market metrics
    "close_price": {"name": "Stock Price", "category": "Price", "korean": "주가"},
    "market_cap": {"name": "Market Cap", "category": "Price", "korean": "시가총액"},

    # Income Statement metrics
    "revenue": {"name": "Revenue", "category": "Income Statement", "korean": "매출액"},
    "gross_profit": {"name": "Gross Profit", "category": "Income Statement", "korean": "매출총이익"},
    "operating_profit": {"name": "Operating Profit", "category": "Income Statement", "korean": "영업이익"},
    "net_income": {"name": "Net Income", "category": "Income Statement", "korean": "순이익"},
    "ebitda": {"name": "EBITDA", "category": "Income Statement", "korean": "EBITDA"},

    # Balance Sheet metrics
    "total_assets": {"name": "Total Assets", "category": "Balance Sheet", "korean": "총자산"},
    "total_equity": {"name": "Total Equity", "category": "Balance Sheet", "korean": "총자본"},
    "total_liabilities": {"name": "Total Liabilities", "category": "Balance Sheet", "korean": "총부채"},

    # Cash Flow metrics
    "fcf": {"name": "Free Cash Flow", "category": "Cash Flow", "korean": "잉여현금흐름"},
    "operating_cash_flow": {"name": "Operating Cash Flow", "category": "Cash Flow", "korean": "영업현금흐름"},

    # Per Share metrics
    "trailing_eps": {"name": "EPS (Trailing)", "category": "Per Share", "korean": "주당순이익"},
    "dividend_per_share": {"name": "Dividend Per Share", "category": "Per Share", "korean": "주당배당금"},
}


def get_cagr_tool_def() -> Tool:
    """Get tool definition for get_cagr."""
    metric_descriptions = "\n".join([
        f"  - {key}: {info['name']} ({info['korean']})"
        for key, info in CAGR_METRICS.items()
    ])

    return Tool(
        name="get_cagr",
        description=(
            "Calculate CAGR (Compound Annual Growth Rate) for financial metrics. "
            "Analyzes historical growth rates for stocks using fundamental data. "
            "Useful for evaluating long-term growth trends in revenue, earnings, assets, and cash flow.\n\n"
            f"Available metrics:\n{metric_descriptions}"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of ticker symbols. "
                        "KR format: 6-digit numeric (e.g., 005930 for Samsung). "
                        "US format: 1-5 uppercase letters (e.g., AAPL for Apple). "
                        "Maximum 20 tickers per request."
                    ),
                    "minItems": 1,
                    "maxItems": 20
                },
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(CAGR_METRICS.keys())
                    },
                    "description": (
                        "List of metrics to calculate CAGR for. "
                        "Available: revenue, net_income, operating_profit, ebitda, "
                        "total_assets, total_equity, fcf, close_price, market_cap, trailing_eps. "
                        "Default: ['revenue', 'net_income', 'operating_profit']"
                    ),
                    "default": ["revenue", "net_income", "operating_profit"]
                },
                "years": {
                    "type": "integer",
                    "description": "Number of years for CAGR calculation (1-10). Default: 3",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3
                },
                "region": {
                    "type": "string",
                    "description": "Market region code",
                    "enum": ["KR", "US", "HK", "JP", "CN", "VN"],
                    "default": "KR"
                },
                "period_type": {
                    "type": "string",
                    "description": (
                        "Data period type. "
                        "ANNUAL: Yearly data (recommended for CAGR). "
                        "QUARTERLY: Quarterly data. "
                        "DAILY: Daily price data (for close_price, market_cap)."
                    ),
                    "enum": ["ANNUAL", "QUARTERLY", "DAILY"],
                    "default": "ANNUAL"
                }
            },
            "required": ["tickers"]
        }
    )


def calculate_cagr(
    beginning_value: float,
    ending_value: float,
    years: float
) -> Optional[float]:
    """
    Calculate CAGR (Compound Annual Growth Rate).

    Formula: CAGR = (Ending Value / Beginning Value)^(1/years) - 1

    Args:
        beginning_value: Starting value
        ending_value: Ending value
        years: Number of years between values

    Returns:
        CAGR as decimal (e.g., 0.15 for 15%), or None if calculation not possible
    """
    if beginning_value is None or ending_value is None:
        return None
    if beginning_value <= 0 or years <= 0:
        return None

    try:
        # Handle negative ending value (e.g., loss after profit)
        if ending_value <= 0 and beginning_value > 0:
            return None  # Cannot calculate meaningful CAGR

        cagr = (ending_value / beginning_value) ** (1 / years) - 1
        return round(cagr, 4)  # Round to 4 decimal places (0.01% precision)
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


async def handle_get_cagr(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle get_cagr tool execution."""
    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    metrics = arguments.get("metrics", ["revenue", "net_income", "operating_profit"])
    years = arguments.get("years", 3)
    region = arguments.get("region", "KR")
    period_type = arguments.get("period_type", "ANNUAL")

    try:
        logger.info(
            "get_cagr_start",
            tickers=tickers,
            metrics=metrics,
            years=years,
            region=region,
            period_type=period_type
        )

        # Validate inputs
        if not tickers:
            raise ValidationError("At least one ticker is required", {"tickers": tickers})

        if len(tickers) > 20:
            raise ValidationError(
                f"Maximum 20 tickers allowed, got {len(tickers)}",
                {"ticker_count": len(tickers)}
            )

        invalid_metrics = [m for m in metrics if m not in CAGR_METRICS]
        if invalid_metrics:
            raise ValidationError(
                f"Invalid metrics: {invalid_metrics}",
                {"valid_metrics": list(CAGR_METRICS.keys())}
            )

        # Query fundamental data
        results = await adapter.get_cagr_data(
            tickers=tickers,
            metrics=metrics,
            years=years,
            region=region,
            period_type=period_type
        )

        # Format response
        response = format_cagr_response(results, metrics, years, region, period_type)

        logger.info(
            "get_cagr_success",
            ticker_count=len(results),
            metrics=metrics
        )

        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

    except ValidationError as e:
        logger.warning("get_cagr_validation_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DataNotFoundError as e:
        logger.warning("get_cagr_not_found", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DatabaseError as e:
        logger.error("get_cagr_database_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except Exception as e:
        logger.error("get_cagr_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


def format_cagr_response(
    results: dict,
    metrics: List[str],
    years: int,
    region: str,
    period_type: str
) -> dict:
    """
    Format CAGR results for MCP response.

    Args:
        results: Raw CAGR calculation results
        metrics: Requested metrics
        years: CAGR period in years
        region: Market region
        period_type: Data period type

    Returns:
        Formatted response dictionary
    """
    formatted_results = {}

    for ticker, ticker_data in results.items():
        ticker_result = {
            "cagr_metrics": {},
            "data_quality": ticker_data.get("data_quality", {}),
            "period": ticker_data.get("period", {})
        }

        for metric in metrics:
            if metric in ticker_data.get("cagr", {}):
                cagr_value = ticker_data["cagr"][metric]
                metric_info = CAGR_METRICS.get(metric, {})

                ticker_result["cagr_metrics"][metric] = {
                    "name": metric_info.get("name", metric),
                    "korean": metric_info.get("korean", ""),
                    "category": metric_info.get("category", ""),
                    "cagr": cagr_value,
                    "cagr_pct": f"{cagr_value * 100:.2f}%" if cagr_value is not None else None,
                    "interpretation": interpret_cagr(cagr_value, metric)
                }

        formatted_results[ticker] = ticker_result

    return {
        "success": True,
        "results": formatted_results,
        "summary": {
            "ticker_count": len(formatted_results),
            "metrics_requested": metrics,
            "years": years,
            "region": region,
            "period_type": period_type,
            "calculation_date": datetime.now().isoformat()
        }
    }


def interpret_cagr(cagr: Optional[float], metric: str) -> str:
    """
    Provide interpretation of CAGR value.

    Args:
        cagr: CAGR value as decimal
        metric: Metric name

    Returns:
        Human-readable interpretation
    """
    if cagr is None:
        return "Insufficient data for calculation"

    pct = cagr * 100

    # Growth interpretation thresholds
    if pct >= 25:
        growth_level = "exceptional_growth"
        description = "Exceptional growth"
    elif pct >= 15:
        growth_level = "strong_growth"
        description = "Strong growth"
    elif pct >= 8:
        growth_level = "moderate_growth"
        description = "Moderate growth"
    elif pct >= 0:
        growth_level = "slow_growth"
        description = "Slow growth"
    elif pct >= -5:
        growth_level = "slight_decline"
        description = "Slight decline"
    elif pct >= -15:
        growth_level = "moderate_decline"
        description = "Moderate decline"
    else:
        growth_level = "significant_decline"
        description = "Significant decline"

    return f"{description} ({pct:+.1f}% annually)"
