# mcp_server/tools/ratios_tool.py
"""
Financial Ratios MCP Tool

Calculates financial ratios from fundamental data with interpretation.
Supports liquidity, leverage, profitability, efficiency, and dividend ratios.
"""

from typing import Any, Sequence, List, Dict
from datetime import datetime
import json
import structlog

from mcp.types import Tool, TextContent

from ..adapters.data_adapter import DataAdapter
from ..calculators.ratio_calculator import FinancialRatioCalculator, RATIO_DEFINITIONS
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()

# Fields required for ratio calculations
REQUIRED_FIELDS = [
    # Balance Sheet
    "current_assets", "current_liabilities", "inventory",
    "total_assets", "total_liabilities", "total_equity",
    "accounts_receivable",
    # Cash Position (for cash ratio calculations)
    "cash_and_equivalents", "short_term_investments", "marketable_securities",
    # Income Statement
    "revenue", "gross_profit", "operating_profit", "net_income",
    "ebitda", "cogs", "interest_expense",
    # Valuation & Per Share
    "dividend_yield", "dividend_per_share", "shares_outstanding",
]

# Currency mapping
CURRENCY_MAP = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "HK": "HKD",
    "CN": "CNY",
    "VN": "VND",
}


def get_ratios_tool_def() -> Tool:
    """Get tool definition for calculate_financial_ratios."""

    # Build category descriptions
    category_desc = []
    for cat, ratios in RATIO_DEFINITIONS.items():
        ratio_names = ", ".join(ratios.keys())
        category_desc.append(f"  - {cat}: {ratio_names}")

    return Tool(
        name="calculate_financial_ratios",
        description=(
            "Calculate financial ratios from fundamental data with interpretation. "
            "Provides health assessment and insights for investment analysis.\n\n"
            "Available ratio categories:\n" + "\n".join(category_desc)
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
                "ratio_categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["liquidity", "cash_position", "leverage", "profitability", "efficiency", "dividend", "all"]
                    },
                    "description": (
                        "Ratio categories to calculate. "
                        "Options: liquidity, cash_position, leverage, profitability, efficiency, dividend, all. "
                        "cash_position includes cash_ratio, cash_to_assets, and net_cash_position. "
                        "Default: ['all']"
                    ),
                    "default": ["all"]
                },
                "period_type": {
                    "type": "string",
                    "enum": ["ANNUAL", "QUARTERLY"],
                    "description": "Data period type for ratio calculation. Default: ANNUAL",
                    "default": "ANNUAL"
                },
                "include_interpretation": {
                    "type": "boolean",
                    "description": "Include ratio interpretation and health assessment. Default: true",
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


def format_ratios_response(
    results: Dict[str, Dict],
    categories: List[str],
    region: str,
    include_interpretation: bool
) -> Dict:
    """
    Format ratio calculation results for MCP response.

    Args:
        results: Calculated ratios by ticker
        categories: Requested categories
        region: Market region
        include_interpretation: Whether to include interpretation

    Returns:
        Formatted response dict
    """
    formatted_data = {}
    total_ratios = 0

    for ticker, ticker_data in results.items():
        ticker_result = {
            "ticker": ticker,
            "fiscal_year": ticker_data.get("fiscal_year"),
            "period_type": ticker_data.get("period_type"),
            "date": ticker_data.get("date"),
            "ratios": {},
        }

        # Format ratios by category
        for category, category_ratios in ticker_data.get("ratios", {}).items():
            category_result = {}

            for ratio_name, ratio_data in category_ratios.items():
                ratio_result = {
                    "value": ratio_data.get("value"),
                    "unit": ratio_data.get("unit"),
                    "korean": ratio_data.get("korean"),
                }

                if include_interpretation:
                    ratio_result["interpretation"] = ratio_data.get("interpretation")
                    ratio_result["health_status"] = ratio_data.get("health_status")

                category_result[ratio_name] = ratio_result
                total_ratios += 1

            ticker_result["ratios"][category] = category_result

        # Add summary if interpretation is enabled
        if include_interpretation and "summary" in ticker_data:
            ticker_result["summary"] = ticker_data["summary"]

        formatted_data[ticker] = ticker_result

    return {
        "success": True,
        "data": formatted_data,
        "metadata": {
            "ticker_count": len(formatted_data),
            "categories": categories if "all" not in categories else list(RATIO_DEFINITIONS.keys()),
            "ratios_calculated": total_ratios,
            "region": region,
            "include_interpretation": include_interpretation,
            "query_time": datetime.now().isoformat()
        }
    }


async def handle_calculate_financial_ratios(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle calculate_financial_ratios tool execution."""

    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    categories = arguments.get("ratio_categories", ["all"])
    period_type = arguments.get("period_type", "ANNUAL")
    include_interpretation = arguments.get("include_interpretation", True)
    region = arguments.get("region", "KR")

    try:
        logger.info(
            "calculate_financial_ratios_start",
            tickers=tickers,
            categories=categories,
            period_type=period_type,
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

        # Get fundamental data for ratio calculation
        data = await adapter.get_fundamentals(
            tickers=tickers,
            fields=REQUIRED_FIELDS,
            period_type=period_type,
            periods=1,  # Most recent period only
            region=region
        )

        # Calculate ratios for each ticker
        results = {}
        for ticker, records in data.items():
            if not records:
                continue

            # Use most recent record
            fundamentals = records[0]

            # Initialize calculator
            calculator = FinancialRatioCalculator(fundamentals)

            # Calculate requested ratios
            calculated_ratios = calculator.calculate_all(categories)

            ticker_result = {
                "fiscal_year": fundamentals.get("fiscal_year"),
                "period_type": fundamentals.get("period_type"),
                "date": fundamentals.get("date"),
                "ratios": calculated_ratios,
            }

            # Add summary if interpretation is enabled
            if include_interpretation:
                ticker_result["summary"] = calculator.get_summary(calculated_ratios)

            results[ticker] = ticker_result

        # Format response
        response = format_ratios_response(results, categories, region, include_interpretation)

        logger.info(
            "calculate_financial_ratios_success",
            ticker_count=len(results),
            categories=categories
        )

        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

    except ValidationError as e:
        logger.warning("calculate_financial_ratios_validation_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DataNotFoundError as e:
        logger.warning("calculate_financial_ratios_not_found", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DatabaseError as e:
        logger.error("calculate_financial_ratios_database_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except Exception as e:
        logger.error("calculate_financial_ratios_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
