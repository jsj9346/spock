# mcp_server/tools/chart_tool.py
"""
Stock Chart Tool for MCP Server

Provides generate_stock_chart tool for creating OHLCV candlestick charts
with technical indicators. Returns PNG image as MCP ImageContent.

Tool Definition:
    name: generate_stock_chart
    description: Generate stock candlestick chart with technical indicators
    input: ticker, region, period_days, indicators, chart_style, image_width, image_height, save_to_file

Handler:
    Validates input -> Calls ChartAdapter.generate_chart -> Returns ImageContent (PNG)

Features:
    - Base64 encoded PNG image for inline display
    - Optional file saving with suggested filename
    - Download guidance for users

Author: Spock MCP Server
Date: 2026-01-19
"""

from typing import Any, Sequence, Union
from datetime import datetime
from pathlib import Path
import base64
import json
import os

from mcp.types import Tool, TextContent, ImageContent
import structlog

logger = structlog.get_logger()


def get_chart_tool_def() -> Tool:
    """
    Get tool definition for generate_stock_chart.

    Returns:
        MCP Tool object with schema
    """
    return Tool(
        name="generate_stock_chart",
        description=(
            "주식 종목의 OHLCV 캔들차트와 기술적 지표를 시각화한 PNG 이미지를 생성합니다. "
            "이동평균선(MA20/50/200), RSI, MACD, 볼린저 밴드 등의 지표를 포함할 수 있습니다. "
            "기본 1년치 데이터를 조회하며, 30일~2년 범위로 설정 가능합니다."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": (
                        "종목 코드. 예시: "
                        "KR='005930'(삼성전자), '000660'(SK하이닉스) | "
                        "US='AAPL', 'MSFT', 'GOOGL' | "
                        "HK='0700'(텐센트), '9988'(알리바바) | "
                        "JP='7203'(도요타) | "
                        "CN='600519'(마오타이)"
                    )
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "HK", "CN", "JP", "VN"],
                    "default": "KR",
                    "description": "시장 지역 (KR=한국, US=미국, HK=홍콩, CN=중국, JP=일본, VN=베트남)"
                },
                "period_days": {
                    "type": "integer",
                    "default": 365,
                    "minimum": 30,
                    "maximum": 730,
                    "description": "조회 기간 (일 단위). 기본 365일(1년), 최소 30일, 최대 730일(2년)"
                },
                "indicators": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["ma", "rsi", "macd", "bollinger", "volume"]
                    },
                    "default": ["ma", "volume"],
                    "description": (
                        "표시할 기술적 지표: "
                        "ma=이동평균선(20/50/200일), "
                        "rsi=RSI(14일, 30/70 기준선), "
                        "macd=MACD(12,26,9), "
                        "bollinger=볼린저밴드(20일,2표준편차), "
                        "volume=거래량"
                    )
                },
                "chart_style": {
                    "type": "string",
                    "enum": ["default", "dark", "classic"],
                    "default": "default",
                    "description": "차트 스타일. default=밝은 테마, dark=어두운 테마, classic=전통적 흑백"
                },
                "image_width": {
                    "type": "integer",
                    "default": 1200,
                    "minimum": 800,
                    "maximum": 2400,
                    "description": "이미지 너비 (픽셀). 기본 1200px"
                },
                "image_height": {
                    "type": "integer",
                    "default": 800,
                    "minimum": 600,
                    "maximum": 1600,
                    "description": "이미지 높이 (픽셀). 기본 800px"
                },
                "save_to_file": {
                    "type": "string",
                    "description": (
                        "차트 이미지를 저장할 파일 경로 (선택사항). "
                        "예: '/Users/user/Downloads/chart.png' 또는 '~/Desktop/samsung_chart.png'. "
                        "지정하지 않으면 이미지만 반환하고 파일로 저장하지 않습니다."
                    )
                },
                "include_download_info": {
                    "type": "boolean",
                    "default": True,
                    "description": "다운로드 안내 정보 포함 여부. True면 파일명 제안과 저장 방법을 함께 안내합니다."
                }
            },
            "required": ["ticker"]
        }
    )


async def handle_generate_stock_chart(
    chart_adapter,
    arguments: Any
) -> Sequence[Union[ImageContent, TextContent]]:
    """
    Handle generate_stock_chart tool execution.

    Args:
        chart_adapter: ChartAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Success: [ImageContent(PNG), TextContent(download_info)] - Image + download guidance
        Failure: [TextContent(JSON error)] - Error details

    Example Input:
        {
            "ticker": "005930",
            "region": "KR",
            "period_days": 365,
            "indicators": ["ma", "rsi", "macd", "volume"],
            "chart_style": "default",
            "save_to_file": "~/Downloads/chart.png"
        }

    Example Output (Success):
        [
            ImageContent(
                type="image",
                data="iVBORw0KGgoAAAANSUhEUgAA...",  # Base64 PNG
                mimeType="image/png"
            ),
            TextContent(
                type="text",
                text='{"success": true, "download_info": {...}}'
            )
        ]

    Example Output (Error):
        TextContent(
            type="text",
            text='{"success": false, "error": "DATA_NOT_FOUND", ...}'
        )
    """
    try:
        # Extract arguments with defaults
        ticker = arguments.get("ticker", "").strip()
        region = arguments.get("region", "KR")
        period_days = arguments.get("period_days", 365)
        indicators = arguments.get("indicators", ["ma", "volume"])
        chart_style = arguments.get("chart_style", "default")
        image_width = arguments.get("image_width", 1200)
        image_height = arguments.get("image_height", 800)
        save_to_file = arguments.get("save_to_file")
        include_download_info = arguments.get("include_download_info", True)

        # Validate required field
        if not ticker:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "VALIDATION_ERROR",
                    "message": "ticker 파라미터가 필요합니다.",
                    "hint": "종목 코드를 입력해주세요. 예: KR='005930', US='AAPL'"
                }, ensure_ascii=False, indent=2)
            )]

        logger.info(
            "generate_stock_chart_called",
            ticker=ticker,
            region=region,
            period_days=period_days,
            indicators=indicators,
            chart_style=chart_style,
            image_size=f"{image_width}x{image_height}",
            save_to_file=save_to_file
        )

        # Generate chart
        png_bytes = await chart_adapter.generate_chart(
            ticker=ticker,
            region=region,
            period_days=period_days,
            indicators=indicators,
            chart_style=chart_style,
            image_size=(image_width, image_height)
        )

        # Encode to Base64
        image_data = base64.standard_b64encode(png_bytes).decode("utf-8")

        # Generate suggested filename
        suggested_filename = _generate_filename(ticker, region, indicators)

        # Save to file if requested
        saved_path = None
        if save_to_file:
            saved_path = _save_chart_to_file(png_bytes, save_to_file, suggested_filename)

        logger.info(
            "generate_stock_chart_success",
            ticker=ticker,
            region=region,
            image_size_bytes=len(png_bytes),
            saved_path=saved_path
        )

        # Build response
        response: list[Union[ImageContent, TextContent]] = []

        # Always include the image
        response.append(ImageContent(
            type="image",
            data=image_data,
            mimeType="image/png"
        ))

        # Add download info if requested
        if include_download_info:
            download_info = _build_download_info(
                ticker=ticker,
                region=region,
                suggested_filename=suggested_filename,
                saved_path=saved_path,
                image_size_bytes=len(png_bytes),
                indicators=indicators
            )
            response.append(TextContent(
                type="text",
                text=json.dumps(download_info, ensure_ascii=False, indent=2)
            ))

        return response

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)

        logger.error(
            "generate_stock_chart_error",
            ticker=arguments.get("ticker"),
            region=arguments.get("region"),
            error_type=error_type,
            error=error_message
        )

        # Build user-friendly error response
        error_response = _build_error_response(
            error_type=error_type,
            error_message=error_message,
            ticker=arguments.get("ticker"),
            region=arguments.get("region")
        )

        return [TextContent(
            type="text",
            text=json.dumps(error_response, ensure_ascii=False, indent=2)
        )]


def _build_error_response(
    error_type: str,
    error_message: str,
    ticker: str,
    region: str
) -> dict:
    """Build user-friendly error response."""

    # Map error types to user-friendly codes and hints
    error_mapping = {
        "DataNotFoundError": {
            "code": "DATA_NOT_FOUND",
            "friendly_message": f"종목 '{ticker}'의 데이터를 찾을 수 없습니다.",
            "hint": "종목 코드와 지역 설정을 확인해주세요. 상장폐지 또는 휴장일 데이터는 조회되지 않습니다."
        },
        "ValidationError": {
            "code": "VALIDATION_ERROR",
            "friendly_message": "입력 파라미터가 올바르지 않습니다.",
            "hint": "ticker, region, indicators 등의 값을 확인해주세요."
        },
        "ValueError": {
            "code": "VALUE_ERROR",
            "friendly_message": "데이터 처리 중 오류가 발생했습니다.",
            "hint": "데이터 형식이 올바르지 않을 수 있습니다."
        }
    }

    error_info = error_mapping.get(error_type, {
        "code": "CHART_GENERATION_FAILED",
        "friendly_message": "차트 생성 중 오류가 발생했습니다.",
        "hint": "잠시 후 다시 시도해주세요."
    })

    return {
        "success": False,
        "error": error_info["code"],
        "message": error_info["friendly_message"],
        "details": {
            "ticker": ticker,
            "region": region,
            "technical_error": error_message
        },
        "hint": error_info["hint"]
    }


def _generate_filename(ticker: str, region: str, indicators: list) -> str:
    """
    Generate a suggested filename for the chart image.

    Format: {ticker}_{region}_{date}_{indicators}_chart.png
    Example: 005930_KR_20260119_ma_rsi_volume_chart.png
    """
    date_str = datetime.now().strftime("%Y%m%d")
    indicators_str = "_".join(sorted(indicators)) if indicators else "basic"

    # Clean ticker for filename (remove special characters)
    clean_ticker = "".join(c for c in ticker if c.isalnum())

    return f"{clean_ticker}_{region}_{date_str}_{indicators_str}_chart.png"


def _save_chart_to_file(
    png_bytes: bytes,
    save_path: str,
    suggested_filename: str
) -> str | None:
    """
    Save chart PNG to file.

    Args:
        png_bytes: PNG image bytes
        save_path: User-specified path (can be directory or full file path)
        suggested_filename: Fallback filename if path is directory

    Returns:
        Absolute path where file was saved, or None if save failed
    """
    try:
        # Expand user path (e.g., ~/Downloads -> /Users/user/Downloads)
        expanded_path = Path(save_path).expanduser()

        # If path is a directory, append suggested filename
        if expanded_path.is_dir():
            file_path = expanded_path / suggested_filename
        else:
            file_path = expanded_path

            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write PNG bytes to file
        file_path.write_bytes(png_bytes)

        logger.info(
            "chart_saved_to_file",
            path=str(file_path),
            size_bytes=len(png_bytes)
        )

        return str(file_path.absolute())

    except Exception as e:
        logger.error(
            "chart_save_failed",
            path=save_path,
            error=str(e)
        )
        return None


def _build_download_info(
    ticker: str,
    region: str,
    suggested_filename: str,
    saved_path: str | None,
    image_size_bytes: int,
    indicators: list
) -> dict:
    """
    Build download information for user guidance.

    Returns:
        Dict with download info, suggested filename, and save status
    """
    # Format file size
    if image_size_bytes < 1024:
        size_str = f"{image_size_bytes} bytes"
    elif image_size_bytes < 1024 * 1024:
        size_str = f"{image_size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{image_size_bytes / (1024 * 1024):.2f} MB"

    # Build indicator description
    indicator_names = {
        "ma": "이동평균선(MA20/50/200)",
        "rsi": "RSI(14)",
        "macd": "MACD(12,26,9)",
        "bollinger": "볼린저밴드",
        "volume": "거래량"
    }
    indicators_desc = ", ".join(
        indicator_names.get(ind, ind) for ind in indicators
    )

    info = {
        "success": True,
        "chart_info": {
            "ticker": ticker,
            "region": region,
            "indicators": indicators_desc,
            "image_size": size_str
        },
        "download": {
            "suggested_filename": suggested_filename,
            "tip": "이미지를 우클릭하여 '이미지 저장' 또는 '다른 이름으로 저장'을 선택하세요."
        }
    }

    # Add save info if file was saved
    if saved_path:
        info["saved_file"] = {
            "path": saved_path,
            "message": f"차트가 '{saved_path}'에 저장되었습니다."
        }
    else:
        # Add save suggestion
        info["download"]["save_example"] = (
            "파일로 저장하려면 save_to_file 파라미터를 사용하세요. "
            "예: save_to_file='~/Downloads/chart.png'"
        )

    return info
