# MCP 주식 차트 시각화 도구 설계서

## 1. 개요

### 1.1 목적
Claude Desktop에서 사용자가 특정 종목의 시각화 자료를 요청할 때, 1년치 OHLCV 캔들차트와 기술적 지표를 시각화한 이미지를 생성하여 반환하는 MCP 도구를 설계합니다.

### 1.2 핵심 요구사항
- **입력**: 종목 코드(ticker), 지역(region), 기간, 기술적 지표 옵션
- **출력**: PNG 이미지 (Base64 인코딩, MCP ImageContent 형식)
- **차트 구성**:
  - 메인 패널: OHLCV 캔들스틱 차트
  - 서브 패널: 기술적 지표 (RSI, MACD, 볼린저 밴드 등)
  - 오버레이: 이동평균선 (MA20, MA50, MA200)
  - 거래량 바 차트

### 1.3 지원 시장
| 지역 | 코드 | 예시 |
|------|------|------|
| 한국 | KR | 005930 (삼성전자) |
| 미국 | US | AAPL, MSFT |
| 홍콩 | HK | 0700.HK |
| 중국 | CN | 600519 |
| 일본 | JP | 7203.T |
| 베트남 | VN | VNM |

---

## 2. 시스템 아키텍처

### 2.1 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Desktop                                │
│                    (MCP Client)                                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SpockMCPServer                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  server.py - Tool Registration & Dispatch                    │   │
│  │  - list_tools_handler()                                      │   │
│  │  - call_tool_handler("generate_stock_chart", {...})          │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │  tools/chart_tool.py - Tool Definition & Handler             │   │
│  │  - get_chart_tool_def() → Tool schema                        │   │
│  │  - handle_generate_stock_chart() → ImageContent              │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │  adapters/chart_adapter.py - Business Logic                  │   │
│  │  - generate_chart(ticker, options) → bytes (PNG)             │   │
│  │  - _fetch_ohlcv_data() → DataFrame                           │   │
│  │  - _calculate_indicators() → DataFrame                       │   │
│  │  - _render_chart() → bytes                                   │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │  generators/stock_chart_generator.py - Chart Rendering       │   │
│  │  - StockChartGenerator class                                 │   │
│  │  - create_candlestick_chart() → Figure                       │   │
│  │  - add_volume_panel() → Figure                               │   │
│  │  - add_indicator_panel() → Figure                            │   │
│  │  - export_to_png() → bytes                                   │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │  adapters/data_adapter.py (기존)                             │   │
│  │  - get_ohlcv() → OHLCV data                                  │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL + TimescaleDB                         │
│                     ohlcv_data (hypertable)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
1. Claude Desktop → MCP Request
   {
     "tool": "generate_stock_chart",
     "arguments": {
       "ticker": "005930",
       "region": "KR",
       "period_days": 365,
       "indicators": ["ma", "rsi", "macd", "bollinger"]
     }
   }

2. Tool Handler → Adapter → Generator
   - OHLCV 데이터 조회 (1년치)
   - 기술적 지표 계산
   - 차트 렌더링 (mplfinance)
   - PNG 이미지 생성

3. MCP Response ← ImageContent
   {
     "type": "image",
     "data": "iVBORw0KGgoAAAANSUhEUgAA...",  // Base64 PNG
     "mimeType": "image/png"
   }
```

---

## 3. API 설계

### 3.1 Tool Definition

```python
# mcp_server/tools/chart_tool.py

def get_chart_tool_def() -> Tool:
    return Tool(
        name="generate_stock_chart",
        description=(
            "주식 종목의 1년치 OHLCV 캔들차트와 기술적 지표를 시각화한 "
            "PNG 이미지를 생성합니다. 이동평균선, RSI, MACD, 볼린저 밴드 등의 "
            "기술적 지표를 포함할 수 있습니다."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "종목 코드 (예: KR='005930', US='AAPL', HK='0700')"
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "HK", "CN", "JP", "VN"],
                    "default": "KR",
                    "description": "시장 지역"
                },
                "period_days": {
                    "type": "integer",
                    "default": 365,
                    "minimum": 30,
                    "maximum": 730,
                    "description": "조회 기간 (일 단위, 기본 365일 = 1년)"
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
                        "ma=이동평균선(20/50/200), "
                        "rsi=RSI(14), "
                        "macd=MACD(12,26,9), "
                        "bollinger=볼린저밴드(20,2), "
                        "volume=거래량"
                    )
                },
                "chart_style": {
                    "type": "string",
                    "enum": ["default", "dark", "classic"],
                    "default": "default",
                    "description": "차트 스타일 테마"
                },
                "image_width": {
                    "type": "integer",
                    "default": 1200,
                    "minimum": 800,
                    "maximum": 2400,
                    "description": "이미지 너비 (픽셀)"
                },
                "image_height": {
                    "type": "integer",
                    "default": 800,
                    "minimum": 600,
                    "maximum": 1600,
                    "description": "이미지 높이 (픽셀)"
                }
            },
            "required": ["ticker"]
        }
    )
```

### 3.2 Handler Implementation

```python
# mcp_server/tools/chart_tool.py

async def handle_generate_stock_chart(
    chart_adapter: ChartAdapter,
    arguments: dict
) -> Sequence[ImageContent | TextContent]:
    """
    주식 차트 생성 도구 핸들러

    Returns:
        성공 시: [ImageContent(PNG)]
        실패 시: [TextContent(에러 메시지)]
    """
    try:
        # 1. 인자 추출
        ticker = arguments.get("ticker")
        region = arguments.get("region", "KR")
        period_days = arguments.get("period_days", 365)
        indicators = arguments.get("indicators", ["ma", "volume"])
        chart_style = arguments.get("chart_style", "default")
        image_width = arguments.get("image_width", 1200)
        image_height = arguments.get("image_height", 800)

        # 2. 입력 검증
        validate_ticker_format(ticker, region)

        # 3. 차트 생성
        png_bytes = await chart_adapter.generate_chart(
            ticker=ticker,
            region=region,
            period_days=period_days,
            indicators=indicators,
            chart_style=chart_style,
            image_size=(image_width, image_height)
        )

        # 4. Base64 인코딩 및 ImageContent 반환
        import base64
        image_data = base64.standard_b64encode(png_bytes).decode("utf-8")

        return [
            ImageContent(
                type="image",
                data=image_data,
                mimeType="image/png"
            )
        ]

    except DataNotFoundError as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "DATA_NOT_FOUND",
                "message": f"종목 '{ticker}'의 데이터를 찾을 수 없습니다.",
                "hint": "종목 코드와 지역 설정을 확인해주세요."
            }, ensure_ascii=False)
        )]

    except Exception as e:
        logger.error("chart_generation_error", error=str(e), ticker=ticker)
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "CHART_GENERATION_FAILED",
                "message": str(e)
            }, ensure_ascii=False)
        )]
```

---

## 4. 차트 생성기 설계

### 4.1 StockChartGenerator 클래스

```python
# mcp_server/generators/stock_chart_generator.py

from typing import List, Tuple, Optional
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from io import BytesIO

class StockChartGenerator:
    """
    주식 캔들차트 생성기

    mplfinance 기반으로 OHLCV 캔들차트와 기술적 지표를 렌더링합니다.

    Features:
    - 캔들스틱 차트 (OHLCV)
    - 이동평균선 오버레이 (MA20, MA50, MA200)
    - RSI 서브 패널 (14일)
    - MACD 서브 패널 (12, 26, 9)
    - 볼린저 밴드 오버레이
    - 거래량 바 차트

    Usage:
        generator = StockChartGenerator()
        png_bytes = generator.generate(
            ohlcv_df=df,
            ticker="005930",
            indicators=["ma", "rsi", "volume"],
            style="default",
            size=(1200, 800)
        )
    """

    # 차트 스타일 정의
    STYLES = {
        "default": {
            "base_mpf_style": "yahoo",
            "up_color": "#26A69A",      # 상승 (청록)
            "down_color": "#EF5350",    # 하락 (빨강)
            "volume_up": "#26A69A80",   # 상승 거래량 (반투명)
            "volume_down": "#EF535080", # 하락 거래량 (반투명)
            "ma_colors": ["#FF9800", "#2196F3", "#9C27B0"],  # MA20, MA50, MA200
            "background": "#FAFAFA",
            "grid_color": "#E0E0E0"
        },
        "dark": {
            "base_mpf_style": "nightclouds",
            "up_color": "#00E676",
            "down_color": "#FF5252",
            "volume_up": "#00E67680",
            "volume_down": "#FF525280",
            "ma_colors": ["#FFD54F", "#4FC3F7", "#BA68C8"],
            "background": "#1E1E1E",
            "grid_color": "#333333"
        },
        "classic": {
            "base_mpf_style": "classic",
            "up_color": "#FFFFFF",
            "down_color": "#000000",
            "volume_up": "#00000040",
            "volume_down": "#00000080",
            "ma_colors": ["#FF0000", "#0000FF", "#00FF00"],
            "background": "#FFFFFF",
            "grid_color": "#CCCCCC"
        }
    }

    def __init__(self):
        self.dpi = 100  # 기본 DPI

    def generate(
        self,
        ohlcv_df: pd.DataFrame,
        ticker: str,
        ticker_name: Optional[str] = None,
        region: str = "KR",
        indicators: List[str] = ["ma", "volume"],
        style: str = "default",
        size: Tuple[int, int] = (1200, 800)
    ) -> bytes:
        """
        차트 이미지 생성

        Args:
            ohlcv_df: OHLCV DataFrame (columns: Open, High, Low, Close, Volume)
                      index: DatetimeIndex
            ticker: 종목 코드
            ticker_name: 종목명 (선택)
            region: 시장 지역
            indicators: 표시할 지표 목록
            style: 차트 스타일
            size: (width, height) 픽셀

        Returns:
            PNG 이미지 바이트
        """
        # 1. 스타일 설정
        style_config = self.STYLES.get(style, self.STYLES["default"])

        # 2. mplfinance 스타일 생성
        mc = mpf.make_marketcolors(
            up=style_config["up_color"],
            down=style_config["down_color"],
            volume={"up": style_config["volume_up"], "down": style_config["volume_down"]},
            edge="inherit",
            wick="inherit"
        )
        s = mpf.make_mpf_style(
            base_mpf_style=style_config["base_mpf_style"],
            marketcolors=mc,
            gridcolor=style_config["grid_color"],
            facecolor=style_config["background"]
        )

        # 3. 추가 플롯 (지표) 구성
        addplots = []
        panel_ratios = [4]  # 메인 캔들차트 비율

        # 이동평균선 (메인 패널 오버레이)
        if "ma" in indicators:
            mas = self._calculate_moving_averages(ohlcv_df)
            for i, (ma_name, ma_data) in enumerate(mas.items()):
                addplots.append(mpf.make_addplot(
                    ma_data,
                    color=style_config["ma_colors"][i % 3],
                    width=1.0,
                    panel=0
                ))

        # 볼린저 밴드 (메인 패널 오버레이)
        if "bollinger" in indicators:
            bb = self._calculate_bollinger_bands(ohlcv_df)
            addplots.append(mpf.make_addplot(bb["upper"], color="#9E9E9E", linestyle="--", width=0.8, panel=0))
            addplots.append(mpf.make_addplot(bb["middle"], color="#9E9E9E", width=0.8, panel=0))
            addplots.append(mpf.make_addplot(bb["lower"], color="#9E9E9E", linestyle="--", width=0.8, panel=0))

        # 거래량 (별도 패널)
        current_panel = 1
        if "volume" in indicators:
            panel_ratios.append(1)  # 거래량 패널 비율
            current_panel += 1

        # RSI (별도 패널)
        if "rsi" in indicators:
            rsi = self._calculate_rsi(ohlcv_df)
            addplots.append(mpf.make_addplot(rsi, panel=current_panel, color="#7B1FA2", ylabel="RSI"))
            # RSI 기준선 (30, 70)
            addplots.append(mpf.make_addplot(
                pd.Series([30] * len(ohlcv_df), index=ohlcv_df.index),
                panel=current_panel, color="#4CAF50", linestyle="--", width=0.5
            ))
            addplots.append(mpf.make_addplot(
                pd.Series([70] * len(ohlcv_df), index=ohlcv_df.index),
                panel=current_panel, color="#F44336", linestyle="--", width=0.5
            ))
            panel_ratios.append(1)
            current_panel += 1

        # MACD (별도 패널)
        if "macd" in indicators:
            macd_data = self._calculate_macd(ohlcv_df)
            addplots.append(mpf.make_addplot(macd_data["macd"], panel=current_panel, color="#2196F3", ylabel="MACD"))
            addplots.append(mpf.make_addplot(macd_data["signal"], panel=current_panel, color="#FF9800"))
            addplots.append(mpf.make_addplot(macd_data["histogram"], panel=current_panel, type="bar", color="#9E9E9E"))
            panel_ratios.append(1)
            current_panel += 1

        # 4. 차트 제목 설정
        title_parts = [ticker]
        if ticker_name:
            title_parts.append(f"({ticker_name})")
        title_parts.append(f"- {region}")
        title_parts.append(f"| {ohlcv_df.index[0].strftime('%Y-%m-%d')} ~ {ohlcv_df.index[-1].strftime('%Y-%m-%d')}")
        title = " ".join(title_parts)

        # 5. Figure 크기 계산
        figsize = (size[0] / self.dpi, size[1] / self.dpi)

        # 6. 차트 렌더링
        buf = BytesIO()

        fig, axes = mpf.plot(
            ohlcv_df,
            type="candle",
            style=s,
            title=title,
            volume="volume" in indicators,
            addplot=addplots if addplots else None,
            panel_ratios=panel_ratios,
            figsize=figsize,
            returnfig=True,
            tight_layout=True
        )

        # 7. PNG 저장
        fig.savefig(buf, format="png", dpi=self.dpi, bbox_inches="tight", facecolor=style_config["background"])
        plt.close(fig)

        buf.seek(0)
        return buf.read()

    def _calculate_moving_averages(self, df: pd.DataFrame) -> dict:
        """이동평균선 계산 (MA20, MA50, MA200)"""
        return {
            "MA20": df["Close"].rolling(window=20).mean(),
            "MA50": df["Close"].rolling(window=50).mean(),
            "MA200": df["Close"].rolling(window=200).mean()
        }

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """MACD 계산"""
        exp1 = df["Close"].ewm(span=fast, adjust=False).mean()
        exp2 = df["Close"].ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return {"macd": macd, "signal": signal_line, "histogram": histogram}

    def _calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> dict:
        """볼린저 밴드 계산"""
        middle = df["Close"].rolling(window=period).mean()
        std = df["Close"].rolling(window=period).std()
        return {
            "upper": middle + (std * std_dev),
            "middle": middle,
            "lower": middle - (std * std_dev)
        }
```

### 4.2 ChartAdapter 클래스

```python
# mcp_server/adapters/chart_adapter.py

from typing import List, Tuple, Optional
import pandas as pd
from datetime import datetime, timedelta
import structlog

from .data_adapter import DataAdapter
from ..generators.stock_chart_generator import StockChartGenerator
from ..utils.errors import DataNotFoundError

logger = structlog.get_logger()


class ChartAdapter:
    """
    차트 생성 어댑터

    데이터 조회와 차트 생성을 연결하는 어댑터 계층입니다.
    """

    def __init__(self, data_adapter: Optional[DataAdapter] = None):
        self.data_adapter = data_adapter or DataAdapter()
        self.chart_generator = StockChartGenerator()

    async def generate_chart(
        self,
        ticker: str,
        region: str = "KR",
        period_days: int = 365,
        indicators: List[str] = ["ma", "volume"],
        chart_style: str = "default",
        image_size: Tuple[int, int] = (1200, 800)
    ) -> bytes:
        """
        주식 차트 생성

        Args:
            ticker: 종목 코드
            region: 시장 지역
            period_days: 조회 기간 (일)
            indicators: 기술적 지표 목록
            chart_style: 차트 스타일
            image_size: 이미지 크기 (width, height)

        Returns:
            PNG 이미지 바이트

        Raises:
            DataNotFoundError: 데이터가 없을 경우
        """
        logger.info("chart_generation_started",
                   ticker=ticker, region=region, period_days=period_days)

        # 1. 날짜 범위 계산
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        # 2. OHLCV 데이터 조회
        ohlcv_result = await self.data_adapter.get_ohlcv(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe="1d"
        )

        if not ohlcv_result.get("success") or ticker not in ohlcv_result.get("data", {}):
            raise DataNotFoundError(
                message=f"OHLCV 데이터를 찾을 수 없습니다: {ticker}",
                details={"ticker": ticker, "region": region, "period": f"{start_date} ~ {end_date}"}
            )

        # 3. DataFrame 변환
        ohlcv_data = ohlcv_result["data"][ticker]
        df = self._to_mplfinance_df(ohlcv_data)

        if df.empty or len(df) < 20:
            raise DataNotFoundError(
                message=f"데이터가 부족합니다. 최소 20개의 거래일 데이터가 필요합니다.",
                details={"ticker": ticker, "available_days": len(df)}
            )

        # 4. 종목명 조회 (선택)
        ticker_name = await self._get_ticker_name(ticker, region)

        # 5. 차트 생성
        png_bytes = self.chart_generator.generate(
            ohlcv_df=df,
            ticker=ticker,
            ticker_name=ticker_name,
            region=region,
            indicators=indicators,
            style=chart_style,
            size=image_size
        )

        logger.info("chart_generation_completed",
                   ticker=ticker, image_size_bytes=len(png_bytes))

        return png_bytes

    def _to_mplfinance_df(self, ohlcv_data: List[dict]) -> pd.DataFrame:
        """
        OHLCV 데이터를 mplfinance 형식으로 변환

        Args:
            ohlcv_data: [{"date": "2024-01-01", "open": 100, ...}, ...]

        Returns:
            mplfinance 호환 DataFrame (DatetimeIndex, columns: Open, High, Low, Close, Volume)
        """
        df = pd.DataFrame(ohlcv_data)

        # 컬럼명 표준화
        column_mapping = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
        df = df.rename(columns=column_mapping)

        # DatetimeIndex 설정
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df = df.sort_index()

        # 필수 컬럼만 선택
        df = df[["Open", "High", "Low", "Close", "Volume"]]

        return df

    async def _get_ticker_name(self, ticker: str, region: str) -> Optional[str]:
        """
        종목명 조회 (DB에서)

        Returns:
            종목명 또는 None
        """
        try:
            # DataAdapter를 통해 종목 정보 조회
            # 실제 구현에서는 tickers 테이블에서 조회
            return None  # TODO: 구현
        except Exception:
            return None
```

---

## 5. 파일 구조

### 5.1 신규 파일

```
mcp_server/
├── tools/
│   └── chart_tool.py              # NEW: Tool 정의 및 핸들러
├── adapters/
│   └── chart_adapter.py           # NEW: 차트 생성 어댑터
├── generators/
│   ├── __init__.py                # NEW: 패키지 초기화
│   └── stock_chart_generator.py   # NEW: 차트 렌더링 엔진
└── server.py                      # MODIFY: 도구 등록 추가
```

### 5.2 수정 파일

```python
# mcp_server/server.py 수정 사항

# 1. Import 추가
from .adapters.chart_adapter import ChartAdapter

# 2. __init__에서 어댑터 초기화
self.chart_adapter = ChartAdapter(self.data_adapter)

# 3. list_tools_handler에 추가
from .tools.chart_tool import get_chart_tool_def
tools.append(get_chart_tool_def())

# 4. call_tool_handler에 추가
elif name == "generate_stock_chart":
    from .tools.chart_tool import handle_generate_stock_chart
    return await handle_generate_stock_chart(self.chart_adapter, arguments)
```

---

## 6. 기술적 고려사항

### 6.1 의존성

```python
# requirements_quant.txt (기존에 포함됨)
mplfinance==0.12.10b0     # 금융 차트 라이브러리
matplotlib==3.7.2         # 기본 시각화
pandas==2.0.3             # 데이터 처리
```

### 6.2 성능 최적화

| 항목 | 목표 | 전략 |
|------|------|------|
| 차트 생성 시간 | < 3초 | mplfinance 사용 (vectorized) |
| 이미지 크기 | < 500KB | PNG 압축, DPI 최적화 |
| 메모리 사용 | < 100MB | DataFrame 범위 제한 |
| 데이터 조회 | < 500ms | DataAdapter 캐싱 활용 |

### 6.3 에러 처리

```python
# 에러 유형별 처리

1. DataNotFoundError
   - 원인: 종목 코드 오류, 데이터 미존재
   - 응답: 사용자 친화적 메시지 + 힌트

2. ValidationError
   - 원인: 잘못된 파라미터
   - 응답: 파라미터 검증 오류 상세

3. ChartGenerationError (신규)
   - 원인: 렌더링 실패
   - 응답: 기술적 상세 + 재시도 권장
```

### 6.4 이미지 크기 가이드라인

| 용도 | 해상도 | 예상 크기 |
|------|--------|-----------|
| Claude Desktop 기본 | 1200x800 | ~200KB |
| 고해상도 | 1600x1000 | ~350KB |
| 모바일 | 800x600 | ~100KB |

---

## 7. 사용 예시

### 7.1 Claude Desktop에서의 사용

**사용자 요청:**
```
삼성전자(005930) 1년치 주가 차트를 보여줘. RSI랑 MACD도 포함해서.
```

**Claude의 MCP 호출:**
```json
{
  "tool": "generate_stock_chart",
  "arguments": {
    "ticker": "005930",
    "region": "KR",
    "period_days": 365,
    "indicators": ["ma", "rsi", "macd", "volume"],
    "chart_style": "default"
  }
}
```

**결과:**
- Claude Desktop에 캔들차트 이미지가 표시됨
- 이동평균선, RSI, MACD, 거래량 패널 포함

### 7.2 다양한 지역 예시

```json
// 미국 주식
{"ticker": "AAPL", "region": "US", "indicators": ["ma", "bollinger"]}

// 홍콩 주식
{"ticker": "0700", "region": "HK", "indicators": ["ma", "rsi"]}

// 일본 주식
{"ticker": "7203", "region": "JP", "indicators": ["ma", "macd"]}
```

---

## 8. 테스트 계획

### 8.1 단위 테스트

```python
# tests/unit/test_chart_generator.py

class TestStockChartGenerator:
    """차트 생성기 단위 테스트"""

    def test_generate_basic_chart(self):
        """기본 캔들차트 생성"""

    def test_generate_with_indicators(self):
        """지표 포함 차트 생성"""

    def test_different_styles(self):
        """다양한 스타일 테스트"""

    def test_empty_data_handling(self):
        """빈 데이터 예외 처리"""

    def test_image_size_constraints(self):
        """이미지 크기 제한 테스트"""
```

### 8.2 통합 테스트

```python
# tests/integration/test_chart_tool.py

class TestChartToolIntegration:
    """차트 도구 통합 테스트"""

    async def test_kr_stock_chart(self):
        """KR 주식 차트 생성"""

    async def test_us_stock_chart(self):
        """US 주식 차트 생성"""

    async def test_invalid_ticker(self):
        """잘못된 종목 코드 처리"""

    async def test_data_not_found(self):
        """데이터 없음 처리"""
```

---

## 9. 구현 우선순위

### Phase 1: 핵심 기능 (1-2일)
1. [ ] `stock_chart_generator.py` 구현
2. [ ] `chart_adapter.py` 구현
3. [ ] `chart_tool.py` 구현
4. [ ] `server.py` 통합

### Phase 2: 기능 확장 (1일)
5. [ ] 추가 스타일 테마
6. [ ] 종목명 표시 기능
7. [ ] 에러 처리 강화

### Phase 3: 테스트 및 문서화 (1일)
8. [ ] 단위 테스트 작성
9. [ ] 통합 테스트 작성
10. [ ] 사용자 문서 작성

---

## 10. 참고 자료

- [mplfinance Documentation](https://github.com/matplotlib/mplfinance)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- 기존 코드: `cli/utils/chart_generator.py`, `modules/visualization/ic_charts.py`

---

**작성일**: 2026-01-19
**작성자**: Spock Quant Platform
**버전**: 1.0.0
