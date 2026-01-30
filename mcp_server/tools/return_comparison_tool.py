# mcp_server/tools/return_comparison_tool.py
"""
Return Comparison Tool for MCP Server

Provides compare_stock_returns tool for generating multi-stock return
comparison charts. Returns PNG image as MCP ImageContent with minimal
token usage.

Tool Definition:
    name: compare_stock_returns
    description: Compare returns of multiple stocks with visualization
    input: tickers, region, period, include_benchmark, show_volatility, show_drawdown

Handler:
    Validates input -> Calls ReturnComparisonAdapter -> Returns ImageContent (PNG)

Features:
    - Multi-stock return comparison (up to 5 stocks)
    - Benchmark overlay (KOSPI, S&P500, etc.)
    - Volatility bands and Sharpe Ratio
    - Drawdown visualization
    - Minimal token usage (image + summary only)

Author: Spock MCP Server
Date: 2026-01-20
"""

from typing import Any, Sequence, Union
from datetime import datetime
from pathlib import Path
import base64
import json

from mcp.types import Tool, TextContent, ImageContent
import structlog

logger = structlog.get_logger()

# Period mapping to days
PERIOD_DAYS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
    "5Y": 1825
}

# Benchmark tickers by region
BENCHMARK_TICKERS = {
    "KR": {"ticker": "069500", "name": "KODEX 200 (KOSPI)"},  # KODEX 200 ETF as KOSPI proxy
    "US": {"ticker": "SPY", "name": "S&P 500"},
    "HK": {"ticker": "2800.HK", "name": "Tracker Fund (HSI)"},
    "CN": {"ticker": "510050.SS", "name": "SSE 50 ETF"},
    "JP": {"ticker": "1306", "name": "TOPIX ETF"},
    "VN": {"ticker": "E1VFVN30", "name": "VN30 ETF"}
}


def get_return_comparison_tool_def() -> Tool:
    """
    Get tool definition for compare_stock_returns.

    Returns:
        MCP Tool object with schema
    """
    return Tool(
        name="compare_stock_returns",
        description=(
            "여러 종목의 수익률을 비교하는 시각화 차트를 생성합니다 (Google Finance 스타일). "
            "최대 5개 종목의 누적 수익률을 라인차트로 비교하고, "
            "KOSPI/S&P500 등 벤치마크 대비 성과를 확인할 수 있습니다. "
            "토큰 효율적: 이미지와 요약 메트릭만 반환하여 대용량 데이터 전송을 방지합니다."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 5,
                    "description": (
                        "비교할 종목 코드 (2~5개). 예시: "
                        "KR=['005930','000660'] | "
                        "US=['AAPL','MSFT','GOOGL'] | "
                        "HK=['0700','9988'] | "
                        "CN=['600519','000858']"
                    )
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "HK", "CN", "JP", "VN"],
                    "default": "KR",
                    "description": "시장 지역 (KR=한국, US=미국, HK=홍콩, CN=중국, JP=일본, VN=베트남)"
                },
                "period": {
                    "type": "string",
                    "enum": ["1M", "3M", "6M", "1Y", "2Y", "5Y"],
                    "default": "1Y",
                    "description": "비교 기간 (1M=1개월, 3M=3개월, 6M=6개월, 1Y=1년, 2Y=2년, 5Y=5년)"
                },
                "include_benchmark": {
                    "type": "boolean",
                    "default": True,
                    "description": "벤치마크 지수 포함 여부 (KR=KOSPI, US=S&P500 등)"
                },
                "save_to_file": {
                    "type": "string",
                    "description": (
                        "차트 이미지를 저장할 파일 경로 (선택사항). "
                        "예: '~/Downloads/comparison.png'"
                    )
                }
            },
            "required": ["tickers"]
        }
    )


async def handle_compare_stock_returns(
    adapter,  # ReturnComparisonAdapter
    arguments: Any
) -> Sequence[Union[ImageContent, TextContent]]:
    """
    Handle compare_stock_returns tool execution.

    Args:
        adapter: ReturnComparisonAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Success: [ImageContent(PNG), TextContent(summary JSON)]
        Failure: [TextContent(error JSON)]
    """
    try:
        # Extract arguments with defaults
        tickers = arguments.get("tickers", [])
        region = arguments.get("region", "KR")
        period = arguments.get("period", "1Y")
        include_benchmark = arguments.get("include_benchmark", True)
        save_to_file = arguments.get("save_to_file")

        # Validate required fields
        if not tickers or len(tickers) < 2:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "VALIDATION_ERROR",
                    "message": "최소 2개 이상의 종목이 필요합니다.",
                    "hint": "tickers 배열에 비교할 종목 코드를 2~5개 입력해주세요."
                }, ensure_ascii=False, indent=2)
            )]

        if len(tickers) > 5:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "VALIDATION_ERROR",
                    "message": f"최대 5개 종목까지 비교 가능합니다. (입력: {len(tickers)}개)",
                    "hint": "종목 수를 5개 이하로 줄여주세요."
                }, ensure_ascii=False, indent=2)
            )]

        logger.info(
            "compare_stock_returns_called",
            tickers=tickers,
            region=region,
            period=period,
            include_benchmark=include_benchmark
        )

        # Get period days
        period_days = PERIOD_DAYS.get(period, 365)

        # Get benchmark info
        benchmark_info = None
        if include_benchmark:
            benchmark_info = BENCHMARK_TICKERS.get(region)

        # Generate comparison chart
        png_bytes, metrics, ticker_names = await adapter.generate_comparison(
            tickers=tickers,
            region=region,
            period_days=period_days,
            include_benchmark=include_benchmark,
            benchmark_info=benchmark_info
        )

        # Encode to Base64
        image_data = base64.standard_b64encode(png_bytes).decode("utf-8")

        # Generate suggested filename
        suggested_filename = _generate_filename(tickers, region, period)

        # Save to file if requested
        saved_path = None
        if save_to_file:
            saved_path = _save_chart_to_file(png_bytes, save_to_file, suggested_filename)

        logger.info(
            "compare_stock_returns_success",
            tickers=tickers,
            region=region,
            image_size_bytes=len(png_bytes),
            saved_path=saved_path
        )

        # Build response
        response: list[Union[ImageContent, TextContent]] = []

        # Add the image
        response.append(ImageContent(
            type="image",
            data=image_data,
            mimeType="image/png"
        ))

        # Add summary JSON (minimal tokens)
        summary = _build_summary(
            tickers=tickers,
            ticker_names=ticker_names,
            region=region,
            period=period,
            metrics=metrics,
            benchmark_info=benchmark_info,
            suggested_filename=suggested_filename,
            saved_path=saved_path,
            image_size_bytes=len(png_bytes)
        )

        response.append(TextContent(
            type="text",
            text=json.dumps(summary, ensure_ascii=False, indent=2)
        ))

        return response

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)

        logger.error(
            "compare_stock_returns_error",
            tickers=arguments.get("tickers"),
            region=arguments.get("region"),
            error_type=error_type,
            error=error_message
        )

        error_response = _build_error_response(
            error_type=error_type,
            error_message=error_message,
            tickers=arguments.get("tickers"),
            region=arguments.get("region")
        )

        return [TextContent(
            type="text",
            text=json.dumps(error_response, ensure_ascii=False, indent=2)
        )]


def _generate_filename(tickers: list, region: str, period: str) -> str:
    """Generate suggested filename for the chart."""
    date_str = datetime.now().strftime("%Y%m%d")
    ticker_str = "_".join(tickers[:3])  # First 3 tickers
    if len(tickers) > 3:
        ticker_str += f"_etc{len(tickers)-3}"
    return f"return_comparison_{region}_{period}_{ticker_str}_{date_str}.png"


def _save_chart_to_file(
    png_bytes: bytes,
    save_path: str,
    suggested_filename: str
) -> str | None:
    """Save chart PNG to file."""
    try:
        expanded_path = Path(save_path).expanduser()

        if expanded_path.is_dir():
            file_path = expanded_path / suggested_filename
        else:
            file_path = expanded_path
            file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_bytes(png_bytes)

        logger.info(
            "comparison_chart_saved",
            path=str(file_path),
            size_bytes=len(png_bytes)
        )

        return str(file_path.absolute())

    except Exception as e:
        logger.error(
            "comparison_chart_save_failed",
            path=save_path,
            error=str(e)
        )
        return None


def _build_summary(
    tickers: list,
    ticker_names: dict,
    region: str,
    period: str,
    metrics: dict,
    benchmark_info: dict | None,
    suggested_filename: str,
    saved_path: str | None,
    image_size_bytes: int
) -> dict:
    """Build summary response with minimal tokens (Google Finance style)."""
    # Format file size
    if image_size_bytes < 1024:
        size_str = f"{image_size_bytes} bytes"
    elif image_size_bytes < 1024 * 1024:
        size_str = f"{image_size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{image_size_bytes / (1024 * 1024):.2f} MB"

    # Build stock comparison data (simplified - return only)
    stocks_data = []
    stock_metrics = metrics.get("stocks", {})

    for ticker in tickers:
        m = stock_metrics.get(ticker, {})
        stocks_data.append({
            "ticker": ticker,
            "name": ticker_names.get(ticker, ticker),
            "return_pct": m.get("total_return_pct"),
            "start_price": m.get("start_price"),
            "end_price": m.get("end_price")
        })

    # Sort by return for rankings
    sorted_by_return = sorted(
        [s for s in stocks_data if s["return_pct"] is not None],
        key=lambda x: x["return_pct"],
        reverse=True
    )

    summary = {
        "success": True,
        "comparison": {
            "region": region,
            "period": period,
            "trading_days": stock_metrics.get(tickers[0], {}).get("trading_days"),
            "date_range": {
                "start": stock_metrics.get(tickers[0], {}).get("start_date"),
                "end": stock_metrics.get(tickers[0], {}).get("end_date")
            },
            "stocks": stocks_data,
            "ranking_by_return": [s["ticker"] for s in sorted_by_return]
        },
        "chart_info": {
            "suggested_filename": suggested_filename,
            "image_size": size_str
        }
    }

    # Add benchmark if included
    benchmark_metrics = metrics.get("benchmark")
    if benchmark_metrics and benchmark_info:
        summary["comparison"]["benchmark"] = {
            "ticker": benchmark_info["ticker"],
            "name": benchmark_info["name"],
            "return_pct": benchmark_metrics.get("total_return_pct")
        }

    # Add save info if file was saved
    if saved_path:
        summary["saved_file"] = {
            "path": saved_path,
            "message": f"차트가 '{saved_path}'에 저장되었습니다."
        }

    return summary


def _build_error_response(
    error_type: str,
    error_message: str,
    tickers: list | None,
    region: str | None
) -> dict:
    """Build user-friendly error response."""
    error_mapping = {
        "DataNotFoundError": {
            "code": "DATA_NOT_FOUND",
            "friendly_message": "요청한 종목의 데이터를 찾을 수 없습니다.",
            "hint": "종목 코드와 지역 설정을 확인해주세요."
        },
        "ValidationError": {
            "code": "VALIDATION_ERROR",
            "friendly_message": "입력 파라미터가 올바르지 않습니다.",
            "hint": "종목 코드, 지역, 기간 등을 확인해주세요."
        },
        "ValueError": {
            "code": "VALUE_ERROR",
            "friendly_message": "데이터 처리 중 오류가 발생했습니다.",
            "hint": "일부 종목의 데이터가 불충분할 수 있습니다."
        }
    }

    error_info = error_mapping.get(error_type, {
        "code": "COMPARISON_FAILED",
        "friendly_message": "수익률 비교 차트 생성 중 오류가 발생했습니다.",
        "hint": "잠시 후 다시 시도해주세요."
    })

    return {
        "success": False,
        "error": error_info["code"],
        "message": error_info["friendly_message"],
        "details": {
            "tickers": tickers,
            "region": region,
            "technical_error": error_message
        },
        "hint": error_info["hint"]
    }
