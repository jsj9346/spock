# mcp_server/tools/ttm_tool.py
"""
TTM (Trailing Twelve Months) Query MCP Tool

Retrieves TTM financial metrics from ticker_fundamentals_ttm table.
TTM values aggregate the last 4 quarters of financial data.

Categories:
- income_statement_ttm: Revenue, Net Income, Operating Profit TTM values
- cash_flow_ttm: Operating Cash Flow, FCF, CapEx TTM values
- balance_sheet: Current balance sheet snapshot (latest quarter)
- ratios_ttm: ROE, ROA, Operating Margin, Net Margin TTM values

Author: Quant Platform Development Team
Date: 2025-11-28
"""

from typing import Any, Sequence, List, Dict, Optional
from datetime import datetime
import json
import structlog

from mcp.types import Tool, TextContent

from ..adapters.data_adapter import DataAdapter
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()

# =============================================================================
# Field Definitions by Category
# =============================================================================

TTM_FIELDS = {
    "income_statement_ttm": {
        "revenue_ttm": {"name": "Revenue TTM", "korean": "매출액 TTM", "unit": "currency"},
        "gross_profit_ttm": {"name": "Gross Profit TTM", "korean": "매출총이익 TTM", "unit": "currency"},
        "operating_profit_ttm": {"name": "Operating Profit TTM", "korean": "영업이익 TTM", "unit": "currency"},
        "net_income_ttm": {"name": "Net Income TTM", "korean": "순이익 TTM", "unit": "currency"},
        "ebitda_ttm": {"name": "EBITDA TTM", "korean": "EBITDA TTM", "unit": "currency"},
        "interest_expense_ttm": {"name": "Interest Expense TTM", "korean": "이자비용 TTM", "unit": "currency"},
    },
    "cash_flow_ttm": {
        "operating_cash_flow_ttm": {"name": "Operating Cash Flow TTM", "korean": "영업현금흐름 TTM", "unit": "currency"},
        "fcf_ttm": {"name": "Free Cash Flow TTM", "korean": "잉여현금흐름 TTM", "unit": "currency"},
        "capex_ttm": {"name": "CapEx TTM", "korean": "자본적지출 TTM", "unit": "currency"},
    },
    "balance_sheet": {
        "total_assets": {"name": "Total Assets", "korean": "총자산", "unit": "currency"},
        "total_liabilities": {"name": "Total Liabilities", "korean": "총부채", "unit": "currency"},
        "total_equity": {"name": "Total Equity", "korean": "총자본", "unit": "currency"},
        "current_assets": {"name": "Current Assets", "korean": "유동자산", "unit": "currency"},
        "current_liabilities": {"name": "Current Liabilities", "korean": "유동부채", "unit": "currency"},
    },
    "ratios_ttm": {
        "roe_ttm": {"name": "ROE TTM", "korean": "자기자본이익률 TTM", "unit": "percent"},
        "roa_ttm": {"name": "ROA TTM", "korean": "총자산이익률 TTM", "unit": "percent"},
        "operating_margin_ttm": {"name": "Operating Margin TTM", "korean": "영업이익률 TTM", "unit": "percent"},
        "net_margin_ttm": {"name": "Net Margin TTM", "korean": "순이익률 TTM", "unit": "percent"},
        "debt_ratio": {"name": "Debt Ratio", "korean": "부채비율", "unit": "ratio"},
    },
    "metadata": {
        "quarters_included": {"name": "Quarters Included", "korean": "포함 분기", "unit": "text"},
        "data_completeness": {"name": "Data Completeness", "korean": "데이터 완성도", "unit": "percent"},
        "calculated_at": {"name": "Calculated At", "korean": "계산 시점", "unit": "datetime"},
    },
}

# Currency mapping by region
CURRENCY_MAP = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "HK": "HKD",
    "CN": "CNY",
    "VN": "VND",
}


def get_ttm_tool_def() -> Tool:
    """Get tool definition for query_ttm."""

    # Build category descriptions
    category_desc = []
    for cat, fields in TTM_FIELDS.items():
        field_names = ", ".join(fields.keys())
        category_desc.append(f"  - {cat}: {field_names}")

    return Tool(
        name="query_ttm",
        description=(
            "Get TTM (Trailing Twelve Months) financial metrics for stocks. "
            "TTM values aggregate the last 4 quarters of financial data, providing "
            "annualized metrics for better comparison across companies. "
            "Supports KR, US, JP, HK, CN, VN markets.\n\n"
            "Available categories:\n" + "\n".join(category_desc)
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
                        "Maximum 50 tickers per request."
                    ),
                    "minItems": 1,
                    "maxItems": 50
                },
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["income_statement_ttm", "cash_flow_ttm", "balance_sheet", "ratios_ttm", "metadata", "all"]
                    },
                    "description": (
                        "TTM data categories to retrieve. "
                        "Options: income_statement_ttm, cash_flow_ttm, balance_sheet, ratios_ttm, metadata, all. "
                        "Default: ['all']"
                    ),
                    "default": ["all"]
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                    "description": "Market region code. Default: KR",
                    "default": "KR"
                },
                "as_of_date": {
                    "type": "string",
                    "description": (
                        "TTM calculation date (YYYY-MM-DD format). "
                        "If not specified, returns the most recent TTM data. "
                        "Example: 2024-09-30"
                    ),
                }
            },
            "required": ["tickers"]
        }
    )


def get_fields_for_categories(categories: List[str]) -> List[str]:
    """Get list of DB column names for requested categories."""
    if "all" in categories:
        categories = list(TTM_FIELDS.keys())

    fields = set()
    for category in categories:
        if category in TTM_FIELDS:
            fields.update(TTM_FIELDS[category].keys())

    return list(fields)


def format_ttm_response(
    data: Dict[str, List[Dict]],
    categories: List[str],
    region: str
) -> Dict:
    """
    Format TTM data for MCP response.

    Args:
        data: Raw data from database {ticker: [records]}
        categories: Requested categories
        region: Market region

    Returns:
        Formatted response dict
    """
    if "all" in categories:
        categories = list(TTM_FIELDS.keys())

    currency = CURRENCY_MAP.get(region, "USD")
    formatted_data = {}

    for ticker, records in data.items():
        ticker_data = {
            "ticker": ticker,
            "region": region,
            "currency": currency,
            "ttm_records": []
        }

        for record in records:
            ttm_record = {
                "as_of_date": str(record.get("as_of_date")) if record.get("as_of_date") else None,
            }

            # Group fields by category
            for category in categories:
                if category not in TTM_FIELDS:
                    continue

                category_data = {}
                for field_name, field_info in TTM_FIELDS[category].items():
                    value = record.get(field_name)
                    if value is not None:
                        # Convert Decimal to float for JSON serialization
                        try:
                            if field_info["unit"] == "text":
                                pass  # Keep as-is
                            elif field_info["unit"] == "datetime":
                                value = str(value) if value else None
                            else:
                                value = float(value)
                        except (TypeError, ValueError):
                            pass

                        category_data[field_name] = {
                            "value": value,
                            "name": field_info["name"],
                            "korean": field_info["korean"],
                            "unit": field_info["unit"]
                        }

                if category_data:
                    ttm_record[category] = category_data

            ticker_data["ttm_records"].append(ttm_record)

        formatted_data[ticker] = ticker_data

    return {
        "success": True,
        "data": formatted_data,
        "metadata": {
            "ticker_count": len(formatted_data),
            "categories": categories,
            "region": region,
            "currency": currency,
            "query_time": datetime.now().isoformat()
        }
    }


async def handle_query_ttm(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle query_ttm tool execution."""

    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    categories = arguments.get("categories", ["all"])
    region = arguments.get("region", "KR")
    as_of_date = arguments.get("as_of_date")

    try:
        logger.info(
            "query_ttm_start",
            tickers=tickers,
            categories=categories,
            region=region,
            as_of_date=as_of_date
        )

        # Validate inputs
        if not tickers:
            raise ValidationError("At least one ticker is required", {"tickers": tickers})

        if len(tickers) > 50:
            raise ValidationError(
                f"Maximum 50 tickers allowed, got {len(tickers)}",
                {"ticker_count": len(tickers)}
            )

        # Get field list for query
        fields = get_fields_for_categories(categories)

        # Query data using adapter
        data = await adapter.get_ttm_data(
            tickers=tickers,
            fields=fields,
            region=region,
            as_of_date=as_of_date
        )

        # Format response
        response = format_ttm_response(data, categories, region)

        logger.info(
            "query_ttm_success",
            ticker_count=len(data),
            categories=categories
        )

        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

    except ValidationError as e:
        logger.warning("query_ttm_validation_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DataNotFoundError as e:
        logger.warning("query_ttm_not_found", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DatabaseError as e:
        logger.error("query_ttm_database_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except Exception as e:
        logger.error("query_ttm_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
