# mcp_server/tools/macro_tool.py
"""
Macro Analysis MCP Tool

Provides comprehensive macro environment analysis for AI-powered investment decisions.
Aggregates currencies, indices, bonds, commodities, and sector performance.
"""

from typing import Any, Sequence
import json
import structlog
from datetime import datetime, timedelta
from decimal import Decimal

from mcp.types import Tool, TextContent

from ..adapters.macro_adapter import MacroAdapter
from ..utils.validators import validate_date_range
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def get_macro_tool_def() -> Tool:
    """Get tool definition for analyze_macro_environment."""
    return Tool(
        name="analyze_macro_environment",
        description=(
            "Analyze comprehensive macro economic environment for investment decision-making. "
            "Provides currency valuations, global market indices, bond yields, commodities, "
            "sector performance, and market regime classification (Risk-On/Off/Rotation/Defensive). "
            "Useful for understanding current market conditions and cross-asset correlations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "analysis_date": {
                    "type": "string",
                    "description": (
                        "Analysis date in YYYY-MM-DD format. "
                        "Uses latest available data as of this date. "
                        "Example: '2024-01-05'"
                    ),
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "lookback_days": {
                    "type": "integer",
                    "description": (
                        "Historical lookback period in days for trend analysis. "
                        "Default: 30 days. Range: 1-365 days."
                    ),
                    "minimum": 1,
                    "maximum": 365,
                    "default": 30
                },
                "components": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["all", "currencies", "indices", "bonds", "commodities", "sectors"]
                    },
                    "description": (
                        "Macro components to analyze. "
                        "Options: 'all', 'currencies' (FX rates), 'indices' (equity indices), "
                        "'bonds' (yield curves), 'commodities' (gold, oil, etc.), 'sectors' (sector rotation). "
                        "Default: ['currencies', 'indices']. "
                        "Note: bonds, commodities, sectors available in Phase 3."
                    ),
                    "default": ["currencies", "indices"]
                },
                "regions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["KR", "US", "JP", "HK", "CN", "EU", "UK"]
                    },
                    "description": (
                        "Geographic regions to include. "
                        "Default: ['KR', 'US']. "
                        "Options: KR (Korea), US (United States), JP (Japan), "
                        "HK (Hong Kong), CN (China), EU (Europe), UK (United Kingdom)."
                    ),
                    "default": ["KR", "US"]
                }
            },
            "required": ["analysis_date"]
        }
    )


async def handle_analyze_macro(adapter: MacroAdapter, arguments: Any) -> Sequence[TextContent]:
    """
    Handle analyze_macro_environment tool execution.

    Args:
        adapter: MacroAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Formatted macro analysis response
    """
    # Extract arguments with defaults
    analysis_date = arguments.get("analysis_date")
    lookback_days = arguments.get("lookback_days", 30)
    components = arguments.get("components", ["currencies", "indices"])
    regions = arguments.get("regions", ["KR", "US"])

    try:
        # Step 1: Validate inputs
        logger.info(
            "analyze_macro_start",
            analysis_date=analysis_date,
            lookback_days=lookback_days,
            components=components,
            regions=regions
        )

        # Calculate start_date from lookback period and validate range
        analysis_dt = datetime.strptime(analysis_date, "%Y-%m-%d")
        start_dt = analysis_dt - timedelta(days=lookback_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        # Validate the actual date range
        validate_date_range(start_date, analysis_date)

        # Validate lookback_days
        if not 1 <= lookback_days <= 365:
            raise ValidationError(f"lookback_days must be between 1 and 365, got {lookback_days}")

        # Step 2: Execute analysis
        result = await adapter.analyze_macro_environment(
            analysis_date=analysis_date,
            lookback_days=lookback_days,
            components=components,
            regions=regions
        )

        # Step 3: Format response
        response_text = format_macro_response(result)

        logger.info(
            "analyze_macro_success",
            analysis_date=analysis_date,
            currencies_count=len(result["currencies"]) if result["currencies"] else 0,
            indices_count=len(result["indices"]) if result["indices"] else 0,
            market_regime=result.get("market_regime")
        )

        return [TextContent(type="text", text=response_text)]

    except ValidationError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.warning("analyze_macro_validation_error", error=str(e))
        return [TextContent(type="text", text=error_msg)]

    except DataNotFoundError as e:
        error_msg = f"Data not found: {str(e)}"
        logger.warning("analyze_macro_data_not_found", error=str(e))
        return [TextContent(type="text", text=error_msg)]

    except DatabaseError as e:
        error_msg = f"Database error: {str(e)}"
        logger.error("analyze_macro_database_error", error=str(e))
        return [TextContent(type="text", text=error_msg)]

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error("analyze_macro_unexpected_error", error=str(e))
        return [TextContent(type="text", text=error_msg)]


def format_macro_response(result: dict) -> str:
    """
    Format macro analysis result for AI consumption.

    Args:
        result: Macro analysis result from adapter

    Returns:
        Formatted text response with structured data
    """
    lines = []

    # Header
    lines.append("=== MACRO ECONOMIC ENVIRONMENT ANALYSIS ===")
    lines.append(f"Analysis Date: {result['analysis_date']}")
    lines.append(f"Lookback Period: {result['lookback_days']} days")
    lines.append(f"Market Regime: {result.get('market_regime', 'N/A')}")
    lines.append("")

    # Currencies section
    if result.get("currencies"):
        lines.append("--- CURRENCIES (FX Valuations) ---")
        for currency, data in result["currencies"].items():
            lines.append(f"\n{currency} ({data['region']}):")
            lines.append(f"  Latest Rate: {data['latest_rate']:.6f}")
            lines.append(f"  Latest Date: {data['latest_date']}")
            lines.append(f"  Changes: 1D={data['change_1d']:+.2f}%, 1W={data['change_1w']:+.2f}%, 1M={data['change_1m']:+.2f}%")
            if data.get('trend_score') is not None:
                lines.append(f"  Trend Score: {data['trend_score']:.1f}/100")
            if data.get('attractiveness_score') is not None:
                lines.append(f"  Attractiveness: {data['attractiveness_score']:.1f}/100")
            lines.append(f"  Data Quality: {data['data_quality']}")
        lines.append("")

    # Indices section
    if result.get("indices"):
        lines.append("--- GLOBAL MARKET INDICES ---")
        for symbol, data in result["indices"].items():
            lines.append(f"\n{data['name']} ({symbol}, {data['region']}):")
            lines.append(f"  Latest Close: {data['latest_close']:,.2f}")
            lines.append(f"  Latest Date: {data['latest_date']}")
            lines.append(f"  Changes: 1D={data['change_1d']:+.2f}%, 1W={data['change_1w']:+.2f}%, 1M={data['change_1m']:+.2f}%")
            lines.append(f"  Trend: {data['trend'].upper()}")
            if data.get('volume'):
                lines.append(f"  Volume: {data['volume']:,}")
        lines.append("")

    # Bonds section
    if result.get("bonds"):
        lines.append("--- BOND YIELDS ---")
        for symbol, data in result["bonds"].items():
            if symbol == "yield_curve":
                continue  # Handle separately below
            lines.append(f"\n{symbol} ({data['country']}, {data['maturity']}):")
            lines.append(f"  Latest Yield: {data['latest_yield']:.2f}%")
            lines.append(f"  Latest Date: {data['latest_date']}")
            lines.append(f"  Changes: 1D={data['change_1d_bps']:+.1f}bps, 1W={data['change_1w_bps']:+.1f}bps, 1M={data['change_1m_bps']:+.1f}bps")

        # Yield curve summary
        if "yield_curve" in result["bonds"]:
            yc = result["bonds"]["yield_curve"]
            lines.append(f"\nYield Curve:")
            lines.append(f"  10Y-2Y Spread: {yc['10Y_2Y_spread']:+.2f}%")
            lines.append(f"  30Y-10Y Spread: {yc['30Y_10Y_spread']:+.2f}%")
            lines.append(f"  Curve Shape: {yc['curve_shape'].upper()}")
        lines.append("")

    # Commodities section
    if result.get("commodities"):
        lines.append("--- COMMODITIES ---")

        # Individual commodities
        for symbol, data in result["commodities"].items():
            if symbol == "by_category":
                continue  # Handle separately below
            lines.append(f"\n{data['name']} ({symbol}, {data['category']}):")
            lines.append(f"  Latest Price: ${data['latest_price']:,.2f}")
            lines.append(f"  Latest Date: {data['latest_date']}")
            lines.append(f"  Changes: 1D={data['change_1d']:+.2f}%, 1W={data['change_1w']:+.2f}%, 1M={data['change_1m']:+.2f}%")

        # Category summary
        if "by_category" in result["commodities"]:
            lines.append("\nBy Category:")
            for category, cat_data in result["commodities"]["by_category"].items():
                lines.append(f"  {category}: {cat_data['avg_change_1m']:+.2f}% (1M), {cat_data['count']} commodities")
        lines.append("")

    # Sectors section
    if result.get("sectors"):
        lines.append("--- SECTOR PERFORMANCE ---")

        for region, region_data in result["sectors"].items():
            lines.append(f"\n{region} Market:")

            # Rotation analysis
            if "rotation" in region_data:
                rotation = region_data["rotation"]
                lines.append(f"  Rotation Pattern: {rotation['pattern']}")
                lines.append(f"  Leaders: {', '.join(rotation['leaders'])}")
                lines.append(f"  Laggards: {', '.join(rotation['laggards'])}")

            # Individual sectors
            lines.append(f"  Sectors:")
            for sector, data in region_data.items():
                if sector == "rotation":
                    continue  # Already handled above
                lines.append(f"    {sector}: 1M={data['avg_return_1m']:+.2f}%, Momentum={data['momentum']}, Stocks={data['num_stocks']}")

        lines.append("")

    # Footer with JSON for programmatic access
    lines.append("--- RAW DATA (JSON) ---")
    lines.append(json.dumps(result, indent=2, ensure_ascii=False, cls=DecimalEncoder))

    return "\n".join(lines)
