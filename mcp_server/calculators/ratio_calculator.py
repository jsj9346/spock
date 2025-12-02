# mcp_server/calculators/ratio_calculator.py
"""
Financial Ratio Calculator

Calculates and interprets financial ratios from fundamental data.
Supports liquidity, leverage, profitability, efficiency, and dividend ratios.
"""

from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


# =============================================================================
# Ratio Definitions
# =============================================================================

RATIO_DEFINITIONS = {
    "liquidity": {
        "current_ratio": {
            "name": "Current Ratio",
            "korean": "유동비율",
            "formula": "current_assets / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 1.5, "max": 3.0},
            "interpretation": {
                "low": "단기 채무 상환 능력 부족 위험",
                "normal": "적정 유동성 보유",
                "high": "유동자산 과다 보유 (비효율 가능성)"
            }
        },
        "quick_ratio": {
            "name": "Quick Ratio",
            "korean": "당좌비율",
            "formula": "(current_assets - inventory) / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 1.0, "max": 2.0},
            "interpretation": {
                "low": "단기 지급 능력 취약",
                "normal": "적정 당좌자산 보유",
                "high": "과도한 유동성"
            }
        },
        "cash_ratio": {
            "name": "Cash Ratio",
            "korean": "현금비율",
            "formula": "cash_and_equivalents / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 0.2, "max": 0.5},
            "interpretation": {
                "low": "즉시 가용 현금 부족",
                "normal": "적정 현금 보유",
                "high": "과도한 현금 보유 (기회비용 발생)"
            }
        },
    },
    "cash_position": {
        "cash_to_assets": {
            "name": "Cash to Assets",
            "korean": "현금자산비율",
            "formula": "cash_and_equivalents / total_assets * 100",
            "unit": "percent",
            "healthy_range": {"min": 5, "max": 30},
            "interpretation": {
                "low": "현금 비중 낮음",
                "normal": "적정 현금 비중",
                "high": "높은 현금 비중 (투자 여력)"
            }
        },
        "net_cash_position": {
            "name": "Net Cash Position",
            "korean": "순현금포지션",
            "formula": "(cash_and_equivalents + short_term_investments) - total_liabilities",
            "unit": "currency",
            "healthy_range": {"min": 0, "max": None},
            "interpretation": {
                "low": "순부채 상태",
                "normal": "적정 현금 포지션",
                "high": "무차입 경영 (Net Cash)"
            }
        },
    },
    "leverage": {
        "debt_ratio": {
            "name": "Debt Ratio",
            "korean": "부채비율",
            "formula": "total_liabilities / total_equity * 100",
            "unit": "percent",
            "healthy_range": {"min": 0, "max": 200},
            "interpretation": {
                "low": "보수적 재무구조",
                "normal": "적정 레버리지",
                "high": "재무위험 증가"
            }
        },
        "debt_to_assets": {
            "name": "Debt to Assets",
            "korean": "자산대비부채비율",
            "formula": "total_liabilities / total_assets * 100",
            "unit": "percent",
            "healthy_range": {"min": 0, "max": 60},
            "interpretation": {
                "low": "자산 대비 부채 적음",
                "normal": "적정 수준",
                "high": "자산 대비 부채 과다"
            }
        },
        "interest_coverage": {
            "name": "Interest Coverage Ratio",
            "korean": "이자보상배율",
            "formula": "operating_profit / interest_expense",
            "unit": "times",
            "healthy_range": {"min": 3.0, "max": None},
            "interpretation": {
                "low": "이자 지급 능력 부족 (3배 미만 위험)",
                "normal": "안정적 이자 지급 능력",
                "high": "우수한 이자 지급 여력"
            }
        },
    },
    "profitability": {
        "gross_margin": {
            "name": "Gross Profit Margin",
            "korean": "매출총이익률",
            "formula": "gross_profit / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 20, "max": None},
            "interpretation": {
                "low": "원가 경쟁력 부족",
                "normal": "적정 매출총이익률",
                "high": "우수한 원가 경쟁력"
            }
        },
        "operating_margin": {
            "name": "Operating Profit Margin",
            "korean": "영업이익률",
            "formula": "operating_profit / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 5, "max": None},
            "interpretation": {
                "low": "영업 효율성 낮음",
                "normal": "적정 영업이익률",
                "high": "우수한 영업 효율성"
            }
        },
        "net_margin": {
            "name": "Net Profit Margin",
            "korean": "순이익률",
            "formula": "net_income / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 3, "max": None},
            "interpretation": {
                "low": "수익성 낮음",
                "normal": "적정 순이익률",
                "high": "우수한 수익성"
            }
        },
        "roe": {
            "name": "Return on Equity",
            "korean": "자기자본이익률",
            "formula": "net_income / total_equity * 100",
            "unit": "percent",
            "healthy_range": {"min": 10, "max": None},
            "interpretation": {
                "low": "자본 활용 효율 낮음",
                "normal": "적정 ROE",
                "high": "우수한 자본 수익률"
            }
        },
        "roa": {
            "name": "Return on Assets",
            "korean": "총자산이익률",
            "formula": "net_income / total_assets * 100",
            "unit": "percent",
            "healthy_range": {"min": 5, "max": None},
            "interpretation": {
                "low": "자산 활용 효율 낮음",
                "normal": "적정 ROA",
                "high": "우수한 자산 수익률"
            }
        },
        "ebitda_margin": {
            "name": "EBITDA Margin",
            "korean": "EBITDA마진",
            "formula": "ebitda / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 10, "max": None},
            "interpretation": {
                "low": "현금창출력 부족",
                "normal": "적정 EBITDA마진",
                "high": "우수한 현금창출력"
            }
        },
    },
    "efficiency": {
        "asset_turnover": {
            "name": "Asset Turnover",
            "korean": "자산회전율",
            "formula": "revenue / total_assets",
            "unit": "times",
            "healthy_range": {"min": 0.5, "max": None},
            "interpretation": {
                "low": "자산 활용도 낮음",
                "normal": "적정 자산 회전",
                "high": "우수한 자산 활용"
            }
        },
        "inventory_turnover": {
            "name": "Inventory Turnover",
            "korean": "재고회전율",
            "formula": "cogs / inventory",
            "unit": "times",
            "healthy_range": {"min": 4, "max": None},
            "interpretation": {
                "low": "재고 회전 느림 (과잉 재고)",
                "normal": "적정 재고 회전",
                "high": "빠른 재고 회전"
            }
        },
        "receivables_turnover": {
            "name": "Receivables Turnover",
            "korean": "매출채권회전율",
            "formula": "revenue / accounts_receivable",
            "unit": "times",
            "healthy_range": {"min": 6, "max": None},
            "interpretation": {
                "low": "채권 회수 느림",
                "normal": "적정 채권 회수",
                "high": "빠른 채권 회수"
            }
        },
        "inventory_days": {
            "name": "Inventory Turnover Days",
            "korean": "재고자산회전일수",
            "formula": "365 / inventory_turnover",
            "unit": "days",
            "healthy_range": {"min": None, "max": 90},
            "interpretation": {
                "low": "빠른 재고 회전 (효율적)",
                "normal": "적정 재고 회전 기간",
                "high": "재고 보유 기간 길음 (과잉 재고 위험)"
            }
        },
        "receivables_days": {
            "name": "Receivables Turnover Days",
            "korean": "매출채권회전일수",
            "formula": "365 / receivables_turnover",
            "unit": "days",
            "healthy_range": {"min": None, "max": 60},
            "interpretation": {
                "low": "빠른 채권 회수 (현금흐름 양호)",
                "normal": "적정 채권 회수 기간",
                "high": "채권 회수 기간 길음 (유동성 위험)"
            }
        },
    },
    "dividend": {
        "dividend_yield": {
            "name": "Dividend Yield",
            "korean": "배당수익률",
            "formula": "dividend_per_share / close_price * 100",
            "unit": "percent",
            "healthy_range": {"min": 1, "max": 10},
            "interpretation": {
                "low": "배당 수익 낮음",
                "normal": "적정 배당 수익",
                "high": "높은 배당 수익 (지속성 확인 필요)"
            }
        },
        "dividend_payout_ratio": {
            "name": "Dividend Payout Ratio",
            "korean": "배당성향",
            "formula": "(dividend_per_share * shares_outstanding) / net_income * 100",
            "unit": "percent",
            "healthy_range": {"min": 20, "max": 60},
            "interpretation": {
                "low": "배당 여력 높음 (성장 재투자)",
                "normal": "적정 배당 정책",
                "high": "높은 배당 성향 (지속성 확인 필요)"
            }
        },
    },
}


@dataclass
class RatioResult:
    """Financial ratio calculation result"""
    name: str
    korean: str
    value: Optional[float]
    unit: str
    formula: str
    interpretation: Optional[str] = None
    health_status: Optional[str] = None  # "healthy", "caution", "warning"


class FinancialRatioCalculator:
    """
    Financial Ratio Calculator

    Calculates financial ratios from fundamental data and provides
    interpretation and health assessment.

    Supports sector-aware calculations to skip irrelevant ratios for
    certain industries (e.g., financial, service companies).
    """

    # Sectors that don't have typical manufacturing metrics
    FINANCIAL_SECTORS = ['금융', '은행', '보험', '증권', '카드', '캐피탈', 'Finance', 'Banking', 'Insurance']
    SERVICE_SECTORS = ['서비스', '소프트웨어', 'IT', '인터넷', '플랫폼', 'Software', 'Internet', 'Services']

    # Ratios to skip for financial companies
    SKIP_FOR_FINANCIAL = ['inventory_turnover', 'inventory_days', 'gross_margin']

    # Ratios to skip for service companies
    SKIP_FOR_SERVICE = ['inventory_turnover', 'inventory_days']

    def __init__(self, fundamentals: Dict[str, Any], sector: str = None):
        """
        Initialize calculator with fundamental data.

        Args:
            fundamentals: Dict containing fundamental data fields
                e.g., {"current_assets": 100, "current_liabilities": 50, ...}
            sector: Optional sector/industry classification for context-aware calculations
        """
        self.data = fundamentals
        self.sector = sector or fundamentals.get('sector', '')
        self._skip_ratios = self._get_skip_ratios()

    def _get_skip_ratios(self) -> set:
        """Determine which ratios to skip based on sector."""
        skip = set()

        sector_upper = self.sector.upper() if self.sector else ''

        # Check if financial sector
        for fin_sector in self.FINANCIAL_SECTORS:
            if fin_sector.upper() in sector_upper:
                skip.update(self.SKIP_FOR_FINANCIAL)
                break

        # Check if service sector
        for svc_sector in self.SERVICE_SECTORS:
            if svc_sector.upper() in sector_upper:
                skip.update(self.SKIP_FOR_SERVICE)
                break

        return skip

    def should_skip_ratio(self, ratio_name: str) -> bool:
        """Check if a ratio should be skipped for this sector."""
        return ratio_name in self._skip_ratios

    def _safe_divide(self, numerator: Any, denominator: Any, multiplier: float = 1.0) -> Optional[float]:
        """Safe division with None and zero handling"""
        if numerator is None or denominator is None:
            return None
        try:
            num = float(numerator)
            den = float(denominator)
            if den == 0:
                return None
            return round(num / den * multiplier, 4)
        except (TypeError, ValueError):
            return None

    def _interpret_ratio(self, value: Optional[float], ratio_def: Dict) -> tuple:
        """
        Interpret ratio value and determine health status.

        Returns:
            (interpretation_text, health_status)
        """
        if value is None:
            return ("데이터 부족으로 계산 불가", None)

        healthy_range = ratio_def.get("healthy_range", {})
        min_val = healthy_range.get("min")
        max_val = healthy_range.get("max")
        interpretations = ratio_def.get("interpretation", {})

        # Determine health status
        if min_val is not None and value < min_val:
            return (interpretations.get("low", "낮은 수준"), "warning")
        elif max_val is not None and value > max_val:
            return (interpretations.get("high", "높은 수준"), "caution")
        else:
            return (interpretations.get("normal", "정상 수준"), "healthy")

    # =========================================================================
    # Liquidity Ratios
    # =========================================================================

    def calculate_current_ratio(self) -> Optional[float]:
        """유동비율 = 유동자산 / 유동부채"""
        return self._safe_divide(
            self.data.get("current_assets"),
            self.data.get("current_liabilities")
        )

    def calculate_quick_ratio(self) -> Optional[float]:
        """당좌비율 = (유동자산 - 재고) / 유동부채"""
        ca = self.data.get("current_assets")
        inv = self.data.get("inventory") or 0
        cl = self.data.get("current_liabilities")

        if ca is None or cl is None:
            return None

        try:
            numerator = float(ca) - float(inv)
            return self._safe_divide(numerator, cl)
        except (TypeError, ValueError):
            return None

    def calculate_cash_ratio(self) -> Optional[float]:
        """현금비율 = 현금성자산 / 유동부채"""
        return self._safe_divide(
            self.data.get("cash_and_equivalents"),
            self.data.get("current_liabilities")
        )

    # =========================================================================
    # Cash Position Ratios
    # =========================================================================

    def calculate_cash_to_assets(self) -> Optional[float]:
        """현금자산비율 = 현금성자산 / 총자산 * 100"""
        return self._safe_divide(
            self.data.get("cash_and_equivalents"),
            self.data.get("total_assets"),
            multiplier=100
        )

    def calculate_net_cash_position(self) -> Optional[float]:
        """순현금포지션 = (현금성자산 + 단기금융상품) - 총부채"""
        cash = self.data.get("cash_and_equivalents")
        short_term = self.data.get("short_term_investments") or 0
        total_liabilities = self.data.get("total_liabilities")

        if cash is None or total_liabilities is None:
            return None

        try:
            return round(float(cash) + float(short_term) - float(total_liabilities), 2)
        except (TypeError, ValueError):
            return None

    # =========================================================================
    # Leverage Ratios
    # =========================================================================

    def calculate_debt_ratio(self) -> Optional[float]:
        """부채비율 = 총부채 / 총자본 * 100"""
        return self._safe_divide(
            self.data.get("total_liabilities"),
            self.data.get("total_equity"),
            multiplier=100
        )

    def calculate_debt_to_assets(self) -> Optional[float]:
        """자산대비부채비율 = 총부채 / 총자산 * 100"""
        return self._safe_divide(
            self.data.get("total_liabilities"),
            self.data.get("total_assets"),
            multiplier=100
        )

    def calculate_interest_coverage(self) -> Optional[float]:
        """이자보상배율 = 영업이익 / 이자비용"""
        return self._safe_divide(
            self.data.get("operating_profit"),
            self.data.get("interest_expense")
        )

    # =========================================================================
    # Profitability Ratios
    # =========================================================================

    def calculate_gross_margin(self) -> Optional[float]:
        """매출총이익률 = 매출총이익 / 매출 * 100"""
        return self._safe_divide(
            self.data.get("gross_profit"),
            self.data.get("revenue"),
            multiplier=100
        )

    def calculate_operating_margin(self) -> Optional[float]:
        """영업이익률 = 영업이익 / 매출 * 100"""
        return self._safe_divide(
            self.data.get("operating_profit"),
            self.data.get("revenue"),
            multiplier=100
        )

    def calculate_net_margin(self) -> Optional[float]:
        """순이익률 = 순이익 / 매출 * 100"""
        return self._safe_divide(
            self.data.get("net_income"),
            self.data.get("revenue"),
            multiplier=100
        )

    def calculate_roe(self) -> Optional[float]:
        """ROE = 순이익 / 자기자본 * 100"""
        return self._safe_divide(
            self.data.get("net_income"),
            self.data.get("total_equity"),
            multiplier=100
        )

    def calculate_roa(self) -> Optional[float]:
        """ROA = 순이익 / 총자산 * 100"""
        return self._safe_divide(
            self.data.get("net_income"),
            self.data.get("total_assets"),
            multiplier=100
        )

    def calculate_ebitda_margin(self) -> Optional[float]:
        """EBITDA마진 = EBITDA / 매출 * 100"""
        return self._safe_divide(
            self.data.get("ebitda"),
            self.data.get("revenue"),
            multiplier=100
        )

    # =========================================================================
    # Efficiency Ratios
    # =========================================================================

    def calculate_asset_turnover(self) -> Optional[float]:
        """자산회전율 = 매출 / 총자산"""
        return self._safe_divide(
            self.data.get("revenue"),
            self.data.get("total_assets")
        )

    def calculate_inventory_turnover(self) -> Optional[float]:
        """재고회전율 = 매출원가 / 재고"""
        return self._safe_divide(
            self.data.get("cogs"),
            self.data.get("inventory")
        )

    def calculate_receivables_turnover(self) -> Optional[float]:
        """매출채권회전율 = 매출 / 매출채권"""
        return self._safe_divide(
            self.data.get("revenue"),
            self.data.get("accounts_receivable")
        )

    def calculate_inventory_days(self) -> Optional[float]:
        """재고자산회전일수 = 365 / 재고회전율"""
        turnover = self.calculate_inventory_turnover()
        if turnover is None or turnover == 0:
            return None
        return 365.0 / turnover

    def calculate_receivables_days(self) -> Optional[float]:
        """매출채권회전일수 = 365 / 매출채권회전율"""
        turnover = self.calculate_receivables_turnover()
        if turnover is None or turnover == 0:
            return None
        return 365.0 / turnover

    # =========================================================================
    # Dividend Ratios
    # =========================================================================

    def calculate_dividend_payout_ratio(self) -> Optional[float]:
        """배당성향 = (DPS * 주식수) / 순이익 * 100"""
        dps = self.data.get("dividend_per_share")
        shares = self.data.get("shares_outstanding")
        ni = self.data.get("net_income")

        if dps is None or shares is None or ni is None:
            return None

        try:
            total_dividend = float(dps) * float(shares)
            return self._safe_divide(total_dividend, ni, multiplier=100)
        except (TypeError, ValueError):
            return None

    # =========================================================================
    # Batch Calculation
    # =========================================================================

    def calculate_category(self, category: str) -> Dict[str, Dict]:
        """
        Calculate all ratios for a specific category.

        Args:
            category: One of 'liquidity', 'leverage', 'profitability', 'efficiency', 'dividend'

        Returns:
            Dict of ratio results with interpretation
        """
        if category not in RATIO_DEFINITIONS:
            return {}

        calculation_methods = {
            # Liquidity
            "current_ratio": self.calculate_current_ratio,
            "quick_ratio": self.calculate_quick_ratio,
            "cash_ratio": self.calculate_cash_ratio,
            # Cash Position
            "cash_to_assets": self.calculate_cash_to_assets,
            "net_cash_position": self.calculate_net_cash_position,
            # Leverage
            "debt_ratio": self.calculate_debt_ratio,
            "debt_to_assets": self.calculate_debt_to_assets,
            "interest_coverage": self.calculate_interest_coverage,
            # Profitability
            "gross_margin": self.calculate_gross_margin,
            "operating_margin": self.calculate_operating_margin,
            "net_margin": self.calculate_net_margin,
            "roe": self.calculate_roe,
            "roa": self.calculate_roa,
            "ebitda_margin": self.calculate_ebitda_margin,
            # Efficiency
            "asset_turnover": self.calculate_asset_turnover,
            "inventory_turnover": self.calculate_inventory_turnover,
            "receivables_turnover": self.calculate_receivables_turnover,
            "inventory_days": self.calculate_inventory_days,
            "receivables_days": self.calculate_receivables_days,
            # Dividend
            "dividend_payout_ratio": self.calculate_dividend_payout_ratio,
        }

        results = {}
        for ratio_name, ratio_def in RATIO_DEFINITIONS[category].items():
            # Skip ratios not applicable to this sector
            if self.should_skip_ratio(ratio_name):
                results[ratio_name] = {
                    "value": None,
                    "name": ratio_def["name"],
                    "korean": ratio_def["korean"],
                    "unit": ratio_def["unit"],
                    "formula": ratio_def["formula"],
                    "interpretation": f"업종 특성상 해당 없음 ({self.sector})",
                    "health_status": None,
                    "skipped": True,
                    "skip_reason": "sector_not_applicable"
                }
                continue

            calc_method = calculation_methods.get(ratio_name)

            # Handle dividend_yield separately (direct from DB)
            if ratio_name == "dividend_yield":
                value = self.data.get("dividend_yield")
                if value is not None:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = None
            elif calc_method:
                value = calc_method()
            else:
                value = None

            interpretation, health_status = self._interpret_ratio(value, ratio_def)

            results[ratio_name] = {
                "value": value,
                "name": ratio_def["name"],
                "korean": ratio_def["korean"],
                "unit": ratio_def["unit"],
                "formula": ratio_def["formula"],
                "interpretation": interpretation,
                "health_status": health_status
            }

        return results

    def calculate_all(self, categories: List[str] = None) -> Dict[str, Dict]:
        """
        Calculate all ratios for specified categories.

        Args:
            categories: List of categories to calculate.
                        If None or contains 'all', calculates all categories.

        Returns:
            Dict with category as key and ratio results as value
        """
        if categories is None or "all" in categories:
            categories = list(RATIO_DEFINITIONS.keys())

        results = {}
        for category in categories:
            if category in RATIO_DEFINITIONS:
                results[category] = self.calculate_category(category)

        return results

    def get_summary(self, ratios: Dict[str, Dict]) -> Dict:
        """
        Generate summary assessment from calculated ratios.

        Args:
            ratios: Output from calculate_all()

        Returns:
            Summary dict with overall health and key insights
        """
        strengths = []
        concerns = []
        health_counts = {"healthy": 0, "caution": 0, "warning": 0}

        for category, category_ratios in ratios.items():
            for ratio_name, ratio_data in category_ratios.items():
                health = ratio_data.get("health_status")
                if health:
                    health_counts[health] = health_counts.get(health, 0) + 1

                    korean_name = ratio_data.get("korean", ratio_name)
                    if health == "healthy":
                        value = ratio_data.get("value")
                        if value is not None:
                            strengths.append(f"{korean_name} 양호")
                    elif health == "warning":
                        strengths.append(f"{korean_name} 주의 필요")
                        concerns.append(ratio_data.get("interpretation", ""))

        # Determine overall health
        total = sum(health_counts.values())
        if total == 0:
            overall_health = "unknown"
        elif health_counts["warning"] > total * 0.3:
            overall_health = "warning"
        elif health_counts["caution"] > total * 0.3:
            overall_health = "caution"
        else:
            overall_health = "healthy"

        return {
            "overall_health": overall_health,
            "health_breakdown": health_counts,
            "strengths": strengths[:5],  # Top 5
            "concerns": concerns[:5],  # Top 5
        }
