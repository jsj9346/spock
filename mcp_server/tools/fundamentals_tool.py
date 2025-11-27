# mcp_server/tools/fundamentals_tool.py
"""
Fundamentals Query MCP Tool

Retrieves fundamental financial data from ticker_fundamentals table.
Supports balance sheet, income statement, cash flow, and valuation data.

Categories:
- balance_sheet: Assets, Liabilities, Equity items
- income_statement: Revenue, Expenses, Profit items
- cash_flow: Operating, Investing, Financing cash flows
- valuation: P/E, P/B, EV/EBITDA, Dividend yield
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

FUNDAMENTALS_FIELDS = {
    "balance_sheet": {
        # Assets
        "total_assets": {"name": "Total Assets", "korean": "총자산", "unit": "currency"},
        "current_assets": {"name": "Current Assets", "korean": "유동자산", "unit": "currency"},
        "accounts_receivable": {"name": "Accounts Receivable", "korean": "매출채권", "unit": "currency"},
        "inventory": {"name": "Inventory", "korean": "재고자산", "unit": "currency"},
        "pp_e": {"name": "PP&E", "korean": "유형자산", "unit": "currency"},
        # Liabilities
        "total_liabilities": {"name": "Total Liabilities", "korean": "총부채", "unit": "currency"},
        "current_liabilities": {"name": "Current Liabilities", "korean": "유동부채", "unit": "currency"},
        # Equity
        "total_equity": {"name": "Total Equity", "korean": "총자본", "unit": "currency"},
        "retained_earnings": {"name": "Retained Earnings", "korean": "이익잉여금", "unit": "currency"},
        "capital_stock": {"name": "Capital Stock", "korean": "자본금", "unit": "currency"},
    },
    "income_statement": {
        "revenue": {"name": "Revenue", "korean": "매출액", "unit": "currency"},
        "cogs": {"name": "Cost of Goods Sold", "korean": "매출원가", "unit": "currency"},
        "gross_profit": {"name": "Gross Profit", "korean": "매출총이익", "unit": "currency"},
        "sga_expense": {"name": "SG&A Expense", "korean": "판관비", "unit": "currency"},
        "rd_expense": {"name": "R&D Expense", "korean": "연구개발비", "unit": "currency"},
        "operating_profit": {"name": "Operating Profit", "korean": "영업이익", "unit": "currency"},
        "interest_expense": {"name": "Interest Expense", "korean": "이자비용", "unit": "currency"},
        "interest_income": {"name": "Interest Income", "korean": "이자수익", "unit": "currency"},
        "net_income": {"name": "Net Income", "korean": "순이익", "unit": "currency"},
        "ebitda": {"name": "EBITDA", "korean": "EBITDA", "unit": "currency"},
        "trailing_eps": {"name": "EPS (Trailing)", "korean": "주당순이익", "unit": "currency_per_share"},
    },
    "cash_flow": {
        "operating_cash_flow": {"name": "Operating Cash Flow", "korean": "영업활동현금흐름", "unit": "currency"},
        "investing_cf": {"name": "Investing Cash Flow", "korean": "투자활동현금흐름", "unit": "currency"},
        "financing_cf": {"name": "Financing Cash Flow", "korean": "재무활동현금흐름", "unit": "currency"},
        "fcf": {"name": "Free Cash Flow", "korean": "잉여현금흐름", "unit": "currency"},
        "capex": {"name": "Capital Expenditure", "korean": "자본적지출", "unit": "currency"},
    },
    "valuation": {
        "market_cap": {"name": "Market Cap", "korean": "시가총액", "unit": "currency"},
        "per": {"name": "P/E Ratio", "korean": "PER", "unit": "ratio"},
        "pbr": {"name": "P/B Ratio", "korean": "PBR", "unit": "ratio"},
        "psr": {"name": "P/S Ratio", "korean": "PSR", "unit": "ratio"},
        "ev": {"name": "Enterprise Value", "korean": "기업가치", "unit": "currency"},
        "ev_ebitda": {"name": "EV/EBITDA", "korean": "EV/EBITDA", "unit": "ratio"},
        "dividend_yield": {"name": "Dividend Yield", "korean": "배당수익률", "unit": "percent"},
        "dividend_per_share": {"name": "DPS", "korean": "주당배당금", "unit": "currency_per_share"},
        "fcf_yield": {"name": "FCF Yield", "korean": "FCF수익률", "unit": "percent"},
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


def get_fundamentals_tool_def() -> Tool:
    """Get tool definition for query_fundamentals."""

    # Build category descriptions
    category_desc = []
    for cat, fields in FUNDAMENTALS_FIELDS.items():
        field_names = ", ".join(fields.keys())
        category_desc.append(f"  - {cat}: {field_names}")

    return Tool(
        name="query_fundamentals",
        description=(
            "Get fundamental financial data for stocks including balance sheet, "
            "income statement, cash flow statement, and valuation metrics. "
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
                        "enum": ["balance_sheet", "income_statement", "cash_flow", "valuation", "all"]
                    },
                    "description": (
                        "Financial statement categories to retrieve. "
                        "Options: balance_sheet, income_statement, cash_flow, valuation, all. "
                        "Default: ['all']"
                    ),
                    "default": ["all"]
                },
                "period_type": {
                    "type": "string",
                    "enum": ["ANNUAL", "QUARTERLY", "DAILY"],
                    "description": (
                        "Reporting period type. "
                        "ANNUAL: Yearly financial statements. "
                        "QUARTERLY: Quarterly reports. "
                        "DAILY: Latest daily valuation metrics. "
                        "Default: ANNUAL"
                    ),
                    "default": "ANNUAL"
                },
                "periods": {
                    "type": "integer",
                    "description": "Number of periods to retrieve (1-10). Default: 1",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 1
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


def get_fields_for_categories(categories: List[str]) -> List[str]:
    """Get list of DB column names for requested categories."""
    if "all" in categories:
        categories = list(FUNDAMENTALS_FIELDS.keys())

    fields = set()
    for category in categories:
        if category in FUNDAMENTALS_FIELDS:
            fields.update(FUNDAMENTALS_FIELDS[category].keys())

    return list(fields)


def format_fundamentals_response(
    data: Dict[str, List[Dict]],
    categories: List[str],
    region: str
) -> Dict:
    """
    Format fundamentals data for MCP response.

    Args:
        data: Raw data from database {ticker: [records]}
        categories: Requested categories
        region: Market region

    Returns:
        Formatted response dict
    """
    if "all" in categories:
        categories = list(FUNDAMENTALS_FIELDS.keys())

    currency = CURRENCY_MAP.get(region, "USD")
    formatted_data = {}

    for ticker, records in data.items():
        ticker_data = {
            "ticker": ticker,
            "region": region,
            "currency": currency,
            "periods": []
        }

        for record in records:
            period_data = {
                "fiscal_year": record.get("fiscal_year"),
                "period_type": record.get("period_type"),
                "date": str(record.get("date")) if record.get("date") else None,
            }

            # Group fields by category
            for category in categories:
                if category not in FUNDAMENTALS_FIELDS:
                    continue

                category_data = {}
                for field_name, field_info in FUNDAMENTALS_FIELDS[category].items():
                    value = record.get(field_name)
                    if value is not None:
                        # Convert Decimal to float for JSON serialization
                        try:
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
                    period_data[category] = category_data

            ticker_data["periods"].append(period_data)

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


async def handle_query_fundamentals(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle query_fundamentals tool execution."""

    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    categories = arguments.get("categories", ["all"])
    period_type = arguments.get("period_type", "ANNUAL")
    periods = arguments.get("periods", 1)
    region = arguments.get("region", "KR")

    try:
        logger.info(
            "query_fundamentals_start",
            tickers=tickers,
            categories=categories,
            period_type=period_type,
            periods=periods,
            region=region
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

        # Query data
        data = await adapter.get_fundamentals(
            tickers=tickers,
            fields=fields,
            period_type=period_type,
            periods=periods,
            region=region
        )

        # Format response
        response = format_fundamentals_response(data, categories, region)

        logger.info(
            "query_fundamentals_success",
            ticker_count=len(data),
            categories=categories
        )

        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

    except ValidationError as e:
        logger.warning("query_fundamentals_validation_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DataNotFoundError as e:
        logger.warning("query_fundamentals_not_found", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except DatabaseError as e:
        logger.error("query_fundamentals_database_error", error=str(e))
        return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

    except Exception as e:
        logger.error("query_fundamentals_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
