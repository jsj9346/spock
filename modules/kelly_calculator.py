#!/usr/bin/env python3
"""
kelly_calculator.py - Kelly Criterion 기반 포지션 사이징 계산기

🎯 핵심 철학:
- "확률적 우위가 클수록 베팅 사이즈를 크게" - Kelly Formula 기본 아이디어
- 백테스트 대신 역사적으로 검증된 패턴의 성공률 활용
- 2단계 포지션 사이징: Technical Filter → GPT Analysis 조정

📊 Kelly 공식 변형:
- 전통적 Kelly: f = (bp - q) / b
- Makenaide 적용: Position% = Pattern_Base% × Quality_Multiplier × GPT_Adjustment

🎲 역사적 패턴 성공률 (Historical Evidence):
- Stage 1→2 전환: 65-70% (스탠 와인스타인)
- VCP 돌파: 60-65% (마크 미너비니)
- Cup & Handle: 60-65% (윌리엄 오닐)
- 60일 고점 돌파: 55-60%
- 단순 MA200 돌파: 50-55%

💰 포지션 사이징 전략:
- 최대 포지션: 8% (극단적 강세 신호)
- 기본 포지션: 2-5% (일반적 신호)
- 최소 포지션: 1% (약한 신호)
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import json
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# TYPE_CHECKING을 사용한 순환 import 방지
if TYPE_CHECKING:
    from modules.stock_gpt_analyzer import StockGPTAnalyzer, GPTAnalysisResult

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PatternType(Enum):
    """차트 패턴 타입"""
    STAGE_1_TO_2 = "stage_1_to_2"
    VCP_BREAKOUT = "vcp_breakout"
    CUP_HANDLE = "cup_handle"
    HIGH_60D_BREAKOUT = "high_60d_breakout"
    MA200_BREAKOUT = "ma200_breakout"
    STAGE_2_CONTINUATION = "stage_2_continuation"
    UNKNOWN = "unknown"

class RiskLevel(Enum):
    """리스크 레벨"""
    CONSERVATIVE = "conservative"  # 보수적
    MODERATE = "moderate"         # 중도
    AGGRESSIVE = "aggressive"     # 공격적

@dataclass
class PatternProbability:
    """패턴별 확률 정보"""
    pattern_type: PatternType
    win_rate: float  # 승률 (0.0-1.0)
    avg_win: float   # 평균 수익률
    avg_loss: float  # 평균 손실률
    base_position: float  # 기본 포지션 크기 (%)

@dataclass
class QualityScoreAdjustment:
    """품질 점수 조정자"""
    score_range: Tuple[float, float]  # 점수 범위
    multiplier: float  # 조정 배수
    description: str

@dataclass
class KellyResult:
    """Kelly 계산 결과"""
    ticker: str
    analysis_date: str

    # Stage 1: Technical Filter 단계
    detected_pattern: PatternType
    quality_score: float
    base_position_pct: float
    quality_multiplier: float
    technical_position_pct: float

    # Stage 2: GPT 조정 단계 (선택적)
    gpt_confidence: Optional[float] = None
    gpt_recommendation: Optional[str] = None
    gpt_adjustment: float = 1.0
    final_position_pct: float = None

    # 메타 정보
    risk_level: RiskLevel = RiskLevel.MODERATE
    max_portfolio_allocation: float = 25.0  # 최대 포트폴리오 할당 %
    reasoning: str = ""

class KellyCalculator:
    """
    Kelly Criterion 기반 포지션 사이징 계산기
    역사적 패턴 성공률을 활용한 확률적 포지션 결정
    """

    def __init__(self,
                 db_path: str = "./data/spock_local.db",
                 risk_level: RiskLevel = RiskLevel.MODERATE,
                 max_single_position: float = 8.0,
                 max_total_allocation: float = 25.0):

        self.db_path = db_path
        self.risk_level = risk_level
        self.max_single_position = max_single_position  # 개별 포지션 최대 %
        self.max_total_allocation = max_total_allocation  # 전체 할당 최대 %

        # 패턴별 확률 정보 초기화
        self.pattern_probabilities = self._initialize_pattern_probabilities()

        # 품질 점수 조정자 초기화
        self.quality_adjustments = self._initialize_quality_adjustments()

        # GPT Analysis integration (optional)
        self.gpt_analyzer: Optional['StockGPTAnalyzer'] = None

        self.init_database()
        logger.info("🎲 KellyCalculator 초기화 완료")

    def _initialize_pattern_probabilities(self) -> Dict[PatternType, PatternProbability]:
        """패턴별 확률 정보 초기화 (역사적 검증 데이터)"""
        return {
            # 스탠 와인스타인 Stage 1→2 전환 (최강 신호)
            PatternType.STAGE_1_TO_2: PatternProbability(
                pattern_type=PatternType.STAGE_1_TO_2,
                win_rate=0.675,  # 67.5% 승률 (65-70% 중간값)
                avg_win=0.25,    # 평균 25% 수익
                avg_loss=0.08,   # 평균 8% 손실 (미너비니 규칙)
                base_position=5.0  # 5% 기본 포지션
            ),

            # 마크 미너비니 VCP 돌파
            PatternType.VCP_BREAKOUT: PatternProbability(
                pattern_type=PatternType.VCP_BREAKOUT,
                win_rate=0.625,  # 62.5% 승률 (60-65% 중간값)
                avg_win=0.22,    # 평균 22% 수익
                avg_loss=0.08,   # 평균 8% 손실
                base_position=4.0  # 4% 기본 포지션
            ),

            # 윌리엄 오닐 Cup & Handle
            PatternType.CUP_HANDLE: PatternProbability(
                pattern_type=PatternType.CUP_HANDLE,
                win_rate=0.625,  # 62.5% 승률 (60-65% 중간값)
                avg_win=0.20,    # 평균 20% 수익
                avg_loss=0.08,   # 평균 8% 손실
                base_position=4.0  # 4% 기본 포지션
            ),

            # 60일 고점 돌파 + 거래량
            PatternType.HIGH_60D_BREAKOUT: PatternProbability(
                pattern_type=PatternType.HIGH_60D_BREAKOUT,
                win_rate=0.575,  # 57.5% 승률 (55-60% 중간값)
                avg_win=0.18,    # 평균 18% 수익
                avg_loss=0.08,   # 평균 8% 손실
                base_position=3.0  # 3% 기본 포지션
            ),

            # Stage 2 지속 (추가 매수)
            PatternType.STAGE_2_CONTINUATION: PatternProbability(
                pattern_type=PatternType.STAGE_2_CONTINUATION,
                win_rate=0.55,   # 55% 승률
                avg_win=0.15,    # 평균 15% 수익
                avg_loss=0.08,   # 평균 8% 손실
                base_position=2.0  # 2% 기본 포지션
            ),

            # 단순 MA200 돌파
            PatternType.MA200_BREAKOUT: PatternProbability(
                pattern_type=PatternType.MA200_BREAKOUT,
                win_rate=0.525,  # 52.5% 승률 (50-55% 중간값)
                avg_win=0.12,    # 평균 12% 수익
                avg_loss=0.08,   # 평균 8% 손실
                base_position=1.5  # 1.5% 기본 포지션
            ),

            # 알 수 없는 패턴 (보수적 접근)
            PatternType.UNKNOWN: PatternProbability(
                pattern_type=PatternType.UNKNOWN,
                win_rate=0.500,  # 50% 승률 (중립적)
                avg_win=0.10,    # 평균 10% 수익 (보수적)
                avg_loss=0.08,   # 평균 8% 손실
                base_position=1.5  # 1.5% 기본 포지션 (최소 수준)
            ),
        }

    def _initialize_quality_adjustments(self) -> List[QualityScoreAdjustment]:
        """품질 점수 조정자 초기화"""
        return [
            QualityScoreAdjustment((20.0, 25.0), 1.4, "Exceptional (20+ 점)"),
            QualityScoreAdjustment((18.0, 20.0), 1.3, "Excellent (18-20 점)"),
            QualityScoreAdjustment((15.0, 18.0), 1.2, "Strong (15-18 점)"),
            QualityScoreAdjustment((12.0, 15.0), 1.0, "Good (12-15 점)"),
            QualityScoreAdjustment((10.0, 12.0), 0.8, "Weak (10-12 점)"),
            QualityScoreAdjustment((0.0, 10.0), 0.6, "Poor (< 10 점)"),
        ]

    def init_database(self):
        """kelly_analysis 테이블 생성"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            create_table_sql = """
            CREATE TABLE IF NOT EXISTS kelly_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                analysis_date TEXT NOT NULL,

                -- Technical Filter 단계
                detected_pattern TEXT NOT NULL,
                quality_score REAL NOT NULL,
                base_position_pct REAL NOT NULL,
                quality_multiplier REAL NOT NULL,
                technical_position_pct REAL NOT NULL,

                -- GPT 조정 단계 (선택적)
                gpt_confidence REAL DEFAULT NULL,
                gpt_recommendation TEXT DEFAULT NULL,
                gpt_adjustment REAL DEFAULT 1.0,
                final_position_pct REAL NOT NULL,

                -- 메타 정보
                risk_level TEXT DEFAULT 'moderate',
                max_portfolio_allocation REAL DEFAULT 25.0,
                reasoning TEXT DEFAULT '',

                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(ticker, analysis_date)
            );
            """

            cursor.execute(create_table_sql)

            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kelly_ticker ON kelly_analysis(ticker);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kelly_date ON kelly_analysis(analysis_date);")

            conn.commit()
            conn.close()

            logger.info("✅ kelly_analysis 테이블 초기화 완료")

        except Exception as e:
            logger.warning(f"⚠️ kelly_analysis 테이블 생성 스킵: {e}")

    def enable_gpt_analysis(self,
                           enable: bool = True,
                           api_key: Optional[str] = None,
                           daily_cost_limit: float = 0.50):
        """Enable GPT-based position adjustment

        GPT 분석을 활성화하여 Kelly 계산에 Stage 2 검증과 position_adjustment를 적용합니다.

        Args:
            enable: GPT 분석 활성화/비활성화
            api_key: OpenAI API key (optional, .env 파일에서 자동 로드)
            daily_cost_limit: 일일 GPT API 예산 ($0.50 기본값)

        Example:
            >>> kelly_calc = KellyCalculator()
            >>> kelly_calc.enable_gpt_analysis(enable=True)
            >>> result = kelly_calc.calculate_position_with_gpt(
            ...     ticker="005930",
            ...     detected_pattern=PatternType.STAGE_1_TO_2,
            ...     quality_score=75.0
            ... )
        """
        if enable:
            try:
                from modules.stock_gpt_analyzer import StockGPTAnalyzer

                self.gpt_analyzer = StockGPTAnalyzer(
                    db_path=self.db_path,
                    api_key=api_key,
                    enable_gpt=True,
                    daily_cost_limit=daily_cost_limit
                )
                logger.info("✅ GPT analysis enabled for Kelly Calculator")
                logger.info(f"💰 Daily GPT budget: ${daily_cost_limit:.2f}")
            except Exception as e:
                logger.error(f"❌ Failed to enable GPT analysis: {e}")
                self.gpt_analyzer = None
                raise
        else:
            self.gpt_analyzer = None
            logger.info("ℹ️ GPT analysis disabled")

    def _calculate_technical_position(self,
                                     ticker: str,
                                     detected_pattern: PatternType,
                                     quality_score: float,
                                     risk_level: RiskLevel) -> KellyResult:
        """Calculate position size based on technical analysis only (Stage 1)

        기술적 분석만으로 포지션 크기를 계산합니다. GPT 조정 전 단계입니다.

        Args:
            ticker: 종목 코드
            detected_pattern: 탐지된 패턴 타입
            quality_score: LayeredScoringEngine 품질 점수 (0-100)
            risk_level: 리스크 레벨 (CONSERVATIVE, MODERATE, AGGRESSIVE)

        Returns:
            KellyResult with technical_position_pct set, final_position_pct as None

        Example:
            >>> result = kelly_calc._calculate_technical_position(
            ...     ticker="005930",
            ...     detected_pattern=PatternType.STAGE_1_TO_2,
            ...     quality_score=75.0,
            ...     risk_level=RiskLevel.MODERATE
            ... )
            >>> print(result.technical_position_pct)  # e.g., 12.5
            >>> print(result.final_position_pct)      # None (awaiting GPT)
        """
        # Step 1: Get pattern probability and risk/reward
        if detected_pattern not in self.pattern_probabilities:
            logger.warning(f"⚠️ {ticker}: Unknown pattern {detected_pattern.value}, using default")
            prob = self.pattern_probabilities[PatternType.STAGE_2_CONTINUATION]
        else:
            prob = self.pattern_probabilities[detected_pattern]

        win_rate = prob.win_rate
        avg_win = prob.avg_win
        avg_loss = prob.avg_loss
        avg_win_loss = avg_win / avg_loss  # Calculate win/loss ratio

        # Step 2: Calculate Kelly percentage
        kelly_pct = self._calculate_kelly_percentage(win_rate, avg_win_loss)

        # Step 3: Apply Half-Kelly adjustment for safety
        adjusted_kelly_pct = kelly_pct * 0.5

        # Step 4: Apply quality score multiplier (0-100 → 0.5-1.5x)
        # Quality 70+ → 1.0x, Quality 90+ → 1.3x, Quality 50-70 → 0.7-1.0x
        quality_multiplier = 0.5 + (quality_score / 100.0)  # 0.5-1.5 range
        quality_adjusted_pct = adjusted_kelly_pct * quality_multiplier

        # Step 5: Apply risk level adjustment
        risk_multipliers = {
            RiskLevel.CONSERVATIVE: 0.5,  # 50% of calculated position
            RiskLevel.MODERATE: 1.0,      # 100% of calculated position
            RiskLevel.AGGRESSIVE: 1.5     # 150% of calculated position
        }
        risk_multiplier = risk_multipliers.get(risk_level, 1.0)
        technical_position_pct = quality_adjusted_pct * risk_multiplier

        # Step 6: Apply position limits
        max_position = self.max_single_position
        technical_position_pct = min(technical_position_pct, max_position)
        technical_position_pct = max(technical_position_pct, 0.0)

        # Step 7: Create KellyResult (final_position_pct = None, awaiting GPT)
        from datetime import datetime
        result = KellyResult(
            ticker=ticker,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            detected_pattern=detected_pattern,  # Keep as PatternType enum
            quality_score=quality_score,
            base_position_pct=kelly_pct,  # Use Kelly % as base_position
            quality_multiplier=quality_multiplier,
            technical_position_pct=technical_position_pct,
            gpt_confidence=None,
            gpt_recommendation=None,
            gpt_adjustment=1.0,
            final_position_pct=None,  # Will be set by _apply_gpt_adjustment() or default to technical_position_pct
            risk_level=risk_level,  # Keep as RiskLevel enum
            max_portfolio_allocation=self.max_total_allocation,
            reasoning=""  # Will be filled later if needed
        )

        logger.info(f"📊 {ticker} Technical Position: {technical_position_pct:.2f}% "
                   f"(Kelly: {kelly_pct:.2f}% → Half: {adjusted_kelly_pct:.2f}% "
                   f"× Quality: {quality_multiplier:.2f} × Risk: {risk_multiplier:.2f})")

        return result

    def _calculate_kelly_percentage(self, win_rate: float, avg_win_loss: float) -> float:
        """Calculate Kelly percentage using Kelly Criterion formula

        Kelly Formula: f = (p × b - (1-p)) / b
        Where:
        - f = fraction of capital to bet (Kelly percentage)
        - p = probability of winning (win_rate)
        - b = ratio of average win to average loss (avg_win_loss)

        Args:
            win_rate: Probability of winning (0.0-1.0)
            avg_win_loss: Ratio of average win to average loss

        Returns:
            Kelly percentage (0.0-1.0, can be negative if edge is negative)

        Example:
            >>> # Win rate 65%, avg_win/avg_loss = 3.125 (25% win / 8% loss)
            >>> kelly_pct = self._calculate_kelly_percentage(0.65, 3.125)
            >>> print(kelly_pct)  # 0.543 (54.3% of capital)
        """
        # Kelly Formula: f = (p × b - (1-p)) / b
        kelly_pct = (win_rate * avg_win_loss - (1 - win_rate)) / avg_win_loss

        # Ensure non-negative (if negative, no edge exists)
        kelly_pct = max(0.0, kelly_pct)

        # Convert to percentage (0.543 → 54.3%)
        kelly_pct = kelly_pct * 100

        return kelly_pct

    def _apply_gpt_adjustment(self,
                             kelly_result: KellyResult,
                             gpt_result: 'GPTAnalysisResult') -> KellyResult:
        """Apply GPT position adjustment to technical position (Stage 2)

        GPT의 Stage 2 검증 결과와 position_adjustment를 적용하여 최종 포지션을 계산합니다.

        Args:
            kelly_result: Technical-based KellyResult (from _calculate_technical_position)
            gpt_result: GPT analysis result from StockGPTAnalyzer

        Returns:
            Updated KellyResult with GPT fields and final_position_pct set

        Example:
            >>> # After technical calculation
            >>> kelly_result.technical_position_pct  # 12.5%
            >>> # After GPT adjustment (1.2x multiplier)
            >>> kelly_result = self._apply_gpt_adjustment(kelly_result, gpt_result)
            >>> kelly_result.final_position_pct  # 15.0% (12.5 × 1.2)
        """
        ticker = kelly_result.ticker

        # Extract GPT fields from gpt_result
        stage2_analysis = gpt_result.stage2_analysis
        position_adjustment = gpt_result.position_adjustment

        # Update KellyResult with GPT data
        kelly_result.gpt_confidence = stage2_analysis.confidence
        kelly_result.gpt_recommendation = gpt_result.recommendation.value
        kelly_result.gpt_adjustment = position_adjustment

        # Calculate final position: technical × GPT adjustment
        technical_pct = kelly_result.technical_position_pct
        final_pct = technical_pct * position_adjustment

        # Apply max position limit
        max_position = self.max_single_position
        final_pct = min(final_pct, max_position)
        final_pct = max(final_pct, 0.0)

        kelly_result.final_position_pct = final_pct

        # Log GPT adjustment details
        logger.info(f"🤖 {ticker} GPT Adjustment Details:")
        logger.info(f"   Stage 2 Confirmed: {stage2_analysis.confirmed}")
        logger.info(f"   GPT Confidence: {stage2_analysis.confidence:.2f}")
        logger.info(f"   MA Alignment: {stage2_analysis.ma_alignment}")
        logger.info(f"   Volume Surge: {stage2_analysis.volume_surge}")
        logger.info(f"   Recommendation: {gpt_result.recommendation.value}")
        logger.info(f"   Position Adjustment: {position_adjustment:.2f}x")
        logger.info(f"   Technical → Final: {technical_pct:.2f}% → {final_pct:.2f}%")

        return kelly_result

    def calculate_position_with_gpt(self,
                                   ticker: str,
                                   detected_pattern: PatternType,
                                   quality_score: float,
                                   risk_level: RiskLevel = RiskLevel.MODERATE,
                                   use_gpt: bool = True) -> KellyResult:
        """Calculate position size with 2-stage process: Technical → GPT adjustment

        2단계 포지션 사이징:
        - Stage 1: 기술적 분석 기반 Kelly 계산
        - Stage 2: GPT Stage 2 검증 + position_adjustment 적용 (선택적)

        Args:
            ticker: 종목 코드
            detected_pattern: 탐지된 패턴 타입
            quality_score: LayeredScoringEngine 품질 점수 (0-100)
            risk_level: 리스크 레벨 (default: MODERATE)
            use_gpt: GPT 분석 사용 여부 (default: True)

        Returns:
            KellyResult with final_position_pct calculated

        Raises:
            ValueError: quality_score가 0-100 범위를 벗어날 경우

        Example:
            >>> kelly_calc = KellyCalculator()
            >>> kelly_calc.enable_gpt_analysis(enable=True)
            >>> result = kelly_calc.calculate_position_with_gpt(
            ...     ticker="005930",
            ...     detected_pattern=PatternType.STAGE_1_TO_2,
            ...     quality_score=75.0,
            ...     use_gpt=True
            ... )
            >>> print(f"Technical: {result.technical_position_pct:.2f}%")
            >>> print(f"GPT Adjustment: {result.gpt_adjustment:.2f}x")
            >>> print(f"Final: {result.final_position_pct:.2f}%")
        """
        # Validation
        if not 0 <= quality_score <= 100:
            raise ValueError(f"quality_score must be 0-100, got {quality_score}")

        # Stage 1: Technical-based position sizing
        logger.info(f"🎯 {ticker} Starting 2-stage position sizing (Quality: {quality_score:.1f})")
        kelly_result = self._calculate_technical_position(
            ticker=ticker,
            detected_pattern=detected_pattern,
            quality_score=quality_score,
            risk_level=risk_level
        )

        # Stage 2: GPT adjustment (optional)
        if use_gpt and self.gpt_analyzer:
            # Quality threshold check: only analyze stocks with quality ≥70
            if quality_score >= 70.0:
                try:
                    logger.info(f"🤖 {ticker} Running GPT Stage 2 analysis (Quality ≥70)")

                    # Get GPT analysis result
                    if TYPE_CHECKING:
                        from modules.stock_gpt_analyzer import GPTAnalysisResult

                    gpt_result = self.gpt_analyzer.analyze_ticker(ticker)

                    if gpt_result:
                        # Apply GPT adjustment
                        kelly_result = self._apply_gpt_adjustment(kelly_result, gpt_result)
                        logger.info(f"✅ {ticker} GPT adjustment applied: "
                                  f"{kelly_result.gpt_adjustment:.2f}x → "
                                  f"Final: {kelly_result.final_position_pct:.2f}%")
                    else:
                        # GPT analysis failed, use technical position as final
                        kelly_result.final_position_pct = kelly_result.technical_position_pct
                        logger.warning(f"⚠️ {ticker} GPT analysis returned None, using technical position")

                except Exception as e:
                    # GPT analysis error, fallback to technical position
                    kelly_result.final_position_pct = kelly_result.technical_position_pct
                    logger.error(f"❌ {ticker} GPT analysis error: {e}, using technical position")
            else:
                # Quality too low for GPT analysis
                kelly_result.final_position_pct = kelly_result.technical_position_pct
                logger.info(f"⏭️ {ticker} Quality {quality_score:.1f} < 70, skipping GPT analysis")
        else:
            # GPT disabled or not available
            kelly_result.final_position_pct = kelly_result.technical_position_pct
            if use_gpt:
                logger.info(f"ℹ️ {ticker} GPT analyzer not enabled, using technical position")
            else:
                logger.info(f"ℹ️ {ticker} GPT disabled by user, using technical position")

        # Save to database
        self._save_kelly_result(kelly_result)

        logger.info(f"💰 {ticker} Position Sizing Complete: {kelly_result.final_position_pct:.2f}% "
                   f"(Technical: {kelly_result.technical_position_pct:.2f}% "
                   f"× GPT: {kelly_result.gpt_adjustment:.2f})")

        return kelly_result

    def detect_pattern_type(self, technical_result: Dict) -> PatternType:
        """기술적 분석 결과에서 패턴 타입 감지"""

        # 🔧 실제 데이터 구조에 맞게 매핑된 결과 사용
        mapped_result = self._map_technical_data(technical_result)

        # Stage 1→2 전환 감지 (최우선)
        if self._is_stage_1_to_2_transition(mapped_result):
            return PatternType.STAGE_1_TO_2

        # VCP 패턴 감지
        if self._is_vcp_pattern(mapped_result):
            return PatternType.VCP_BREAKOUT

        # Cup & Handle 패턴 감지
        if self._is_cup_handle_pattern(mapped_result):
            return PatternType.CUP_HANDLE

        # 60일 고점 돌파 감지
        if self._is_60d_high_breakout(mapped_result):
            return PatternType.HIGH_60D_BREAKOUT

        # Stage 2 지속 감지
        if self._is_stage_2_continuation(mapped_result):
            return PatternType.STAGE_2_CONTINUATION

        # 단순 MA200 돌파
        if self._is_ma200_breakout(mapped_result):
            return PatternType.MA200_BREAKOUT

        # 🔍 디버깅: 어떤 패턴도 감지되지 않은 경우 로깅
        logger.debug(f"⚠️ 패턴 감지 실패 - 매핑된 데이터: {mapped_result}")

        # 🎯 강화된 fallback 패턴 감지 (관대한 조건으로 UNKNOWN 방지)

        # 1차 fallback: 기존 최소 조건
        if mapped_result.get('price_above_ma20') and mapped_result.get('ma_trend_strength', 0) > 0.1:
            logger.info("🎯 기존 fallback: MA20 위 + 약한 트렌드 → STAGE_2_CONTINUATION")
            return PatternType.STAGE_2_CONTINUATION

        # 2차 fallback: Stage 기반 패턴 감지
        if mapped_result.get('stage_2_entry') or mapped_result.get('stage_2_continuation'):
            logger.info("✅ Stage 기반 fallback: STAGE_2_CONTINUATION")
            return PatternType.STAGE_2_CONTINUATION

        # 3차 fallback: 추천 등급 기반 패턴 결정
        raw_recommendation = str(mapped_result.get('recommendation', '')).upper()
        if 'STRONG_BUY' in raw_recommendation or 'BUY' in raw_recommendation:
            logger.info("✅ 추천 등급 기반 fallback: MA200_BREAKOUT")
            return PatternType.MA200_BREAKOUT

        # 4차 fallback: 볼륨이나 트렌드 지표 기반
        if (mapped_result.get('volume_breakout') or
            mapped_result.get('ma20_uptrend') or
            mapped_result.get('price_above_ma200')):
            logger.info("✅ 기술적 지표 기반 fallback: MA200_BREAKOUT")
            return PatternType.MA200_BREAKOUT

        # 최종 fallback: UNKNOWN 완전 방지
        logger.warning("⚠️ 모든 패턴 감지 실패 - 보수적 MA200 돌파 패턴 적용")
        return PatternType.MA200_BREAKOUT  # UNKNOWN 대신 가장 보수적인 패턴

    def _map_technical_data(self, raw_data: Dict) -> Dict:
        """
        실제 기술적 분석 데이터를 Kelly Calculator가 이해할 수 있는 형태로 매핑

        Args:
            raw_data: 실제 technical_analysis 테이블의 데이터

        Returns:
            Dict: Kelly Calculator용 매핑된 데이터
        """
        mapped = {}

        try:
            # analysis_details 정보 파싱 (실제 DB 컬럼명에 맞게 수정)
            layers_data = raw_data.get('analysis_details') or raw_data.get('layers_data')
            if isinstance(layers_data, str):
                import json
                layers_data = json.loads(layers_data)

            if not layers_data:
                logger.debug("⚠️ analysis_details가 없음 - 기존 컬럼 기반 매핑 사용")
                layers_data = {}

                # 대안: 기존 technical_analysis 테이블의 직접 컬럼 사용
                return self._map_from_direct_columns(raw_data)

            # 패턴 정보 추출
            patterns_found = []
            if 'micro' in layers_data and 'modules' in layers_data['micro']:
                pattern_module = layers_data['micro']['modules'].get('PatternRecognition', {})
                pattern_details = pattern_module.get('details', {})
                patterns_found = pattern_details.get('patterns_found', [])

            # 이동평균 정보 추출
            ma_info = {}
            if 'structural' in layers_data and 'modules' in layers_data['structural']:
                ma_module = layers_data['structural']['modules'].get('MovingAverage', {})
                ma_details = ma_module.get('details', {})
                ma_info = ma_details

            # 볼륨 정보 추출
            volume_info = {}
            if 'macro' in layers_data and 'modules' in layers_data['macro']:
                volume_module = layers_data['macro']['modules'].get('VolumeProfile', {})
                volume_details = volume_module.get('details', {})
                volume_info = volume_details

            # Stage 1→2 전환 매핑
            mapped['stage_2_entry'] = (
                ma_info.get('price_vs_ma20', False) and
                ma_info.get('ma20_slope', 0) > 0.5 and
                raw_data.get('stage_status', '') != 'AVOID'
            )

            mapped['volume_breakout'] = (
                volume_info.get('spike_ratio', 0) > 1.5 or
                volume_info.get('volume_trend', 0) > 1.2
            )

            mapped['ma_trend_strength'] = abs(ma_info.get('ma20_slope', 0)) / 100.0

            # VCP 패턴 매핑
            mapped['volatility_contraction'] = (
                'ascending_triangle' in patterns_found or
                'bull_flag' in patterns_found or
                'consolidation' in patterns_found
            )

            mapped['volume_dry_up'] = volume_info.get('volume_trend', 1.0) < 0.8

            # Cup & Handle 패턴 매핑
            mapped['cup_formation'] = (
                'cup_handle' in patterns_found or
                'rounding_bottom' in patterns_found or
                'u_shape' in patterns_found
            )

            mapped['handle_formation'] = 'handle' in str(patterns_found)
            mapped['cup_depth_ok'] = True  # 일단 True로 설정

            # 60일 고점 돌파 매핑
            mapped['high_60d_breakout'] = (
                'breakout' in patterns_found or
                'resistance_break' in patterns_found or
                raw_data.get('price_position', 0) > 0.8
            )

            # Stage 2 지속 매핑
            stage_status = raw_data.get('stage_status', '').upper()
            mapped['stage_2_active'] = stage_status in ['BUY', 'STRONG_BUY', 'HOLD']
            mapped['price_above_ma20'] = ma_info.get('price_vs_ma20', False)

            # MA200 돌파 매핑
            mapped['ma200_breakout'] = (
                ma_info.get('price_vs_ma200', False) or
                (ma_info.get('current_price', 0) > ma_info.get('ma200', 0) if ma_info.get('ma200') else False)
            )

            logger.debug(f"🔧 기술적 분석 데이터 매핑 완료: {len(mapped)}개 필드 생성")
            return mapped

        except Exception as e:
            logger.warning(f"⚠️ 기술적 분석 데이터 매핑 실패: {e}, 원본 데이터 사용")
            return raw_data

    def _map_from_direct_columns(self, raw_data: Dict) -> Dict:
        """
        analysis_details가 없을 때 technical_analysis 테이블의 직접 컬럼들을 사용한 매핑

        Args:
            raw_data: technical_analysis 테이블의 raw 데이터

        Returns:
            Dict: Kelly Calculator용 매핑된 데이터
        """
        mapped = {}

        try:
            # Stage 분석 기반 매핑 - 문자열과 정수 모두 처리
            current_stage_raw = raw_data.get('current_stage', 0)

            # Stage 값 정규화 (문자열과 정수 모두 처리)
            if isinstance(current_stage_raw, str):
                # "Stage 2", "stage 2", "Stage2" 등 모든 형태 처리
                import re
                stage_match = re.search(r'[Ss]tage\s*(\d+)', str(current_stage_raw))
                current_stage = int(stage_match.group(1)) if stage_match else 0
            else:
                current_stage = int(current_stage_raw) if current_stage_raw else 0

            stage_confidence = float(raw_data.get('stage_confidence', 0))
            recommendation = str(raw_data.get('recommendation', '')).upper()

            # Stage 1→2 전환 매핑 (조건 완화)
            mapped['stage_2_entry'] = (
                current_stage == 2 and
                stage_confidence > 0.6 and  # 0.7 → 0.6으로 완화
                recommendation in ['BUY', 'STRONG_BUY', 'HOLD']  # HOLD도 포함
            )

            # 볼륨 돌파 매핑
            volume_surge = raw_data.get('volume_surge', 0)
            mapped['volume_breakout'] = volume_surge > 1.5

            # 트렌드 강도 매핑
            ma200_slope = raw_data.get('ma200_slope', 0) or 0
            mapped['ma_trend_strength'] = abs(ma200_slope) / 100.0

            # VCP 패턴 매핑 (품질 점수 기반)
            quality_score = raw_data.get('quality_score', 0) or 0
            total_gates_passed = raw_data.get('total_gates_passed', 0) or 0

            mapped['volatility_contraction'] = (
                quality_score > 15 and
                total_gates_passed >= 3
            )

            mapped['volume_dry_up'] = volume_surge < 0.8

            # Cup & Handle 패턴 매핑 (구조적 점수 기반)
            breakout_strength = raw_data.get('breakout_strength', 0) or 0
            mapped['cup_formation'] = breakout_strength > 0.6
            mapped['handle_formation'] = breakout_strength > 0.4 and quality_score > 12
            mapped['cup_depth_ok'] = True

            # 60일 고점 돌파 매핑
            gate1_stage2 = raw_data.get('gate1_stage2', 0) or 0
            gate2_volume = raw_data.get('gate2_volume', 0) or 0
            mapped['high_60d_breakout'] = gate1_stage2 > 0 and gate2_volume > 0

            # Stage 2 지속 매핑
            mapped['stage_2_active'] = (
                current_stage == 2 and
                recommendation in ['BUY', 'STRONG_BUY', 'HOLD']
            )

            # MA20 위 여부
            price_vs_ma200 = raw_data.get('price_vs_ma200', 0) or 0
            close_price = raw_data.get('close_price', 0) or 0
            ma20 = raw_data.get('ma20', 0) or 0

            if ma20 > 0 and close_price > 0:
                mapped['price_above_ma20'] = close_price > ma20
            else:
                mapped['price_above_ma20'] = price_vs_ma200 > 1.0

            # MA200 돌파 매핑
            mapped['ma200_breakout'] = (
                price_vs_ma200 > 1.0 and
                ma200_slope > 0
            )

            logger.debug(f"🔧 직접 컬럼 기반 데이터 매핑 완료: {len(mapped)}개 필드 생성")
            return mapped

        except Exception as e:
            logger.warning(f"⚠️ 직접 컬럼 매핑 실패: {e}, 빈 매핑 반환")
            return {}

    def _is_stage_1_to_2_transition(self, result: Dict) -> bool:
        """스탠 와인스타인 Stage 1→2 전환 감지"""
        try:
            # Stage 2 진입 + 강한 기술적 지표 조합
            stage_2_entry = result.get('stage_2_entry', False)
            volume_breakout = result.get('volume_breakout', False)
            ma_trend_strong = result.get('ma_trend_strength', 0) > 0.7

            return stage_2_entry and volume_breakout and ma_trend_strong

        except Exception:
            return False

    def _is_vcp_pattern(self, result: Dict) -> bool:
        """VCP 패턴 감지"""
        try:
            # 변동성 수축 + 돌파 패턴
            volatility_contraction = result.get('volatility_contraction', False)
            volume_dry_up = result.get('volume_dry_up', False)
            breakout_volume = result.get('volume_breakout', False)

            return volatility_contraction and volume_dry_up and breakout_volume

        except Exception:
            return False

    def _is_cup_handle_pattern(self, result: Dict) -> bool:
        """Cup & Handle 패턴 감지"""
        try:
            # U자 형태 + 핸들 형성
            cup_formation = result.get('cup_formation', False)
            handle_formation = result.get('handle_formation', False)
            proper_depth = result.get('cup_depth_ok', False)

            return cup_formation and handle_formation and proper_depth

        except Exception:
            return False

    def _is_60d_high_breakout(self, result: Dict) -> bool:
        """60일 고점 돌파 감지"""
        try:
            high_breakout = result.get('high_60d_breakout', False)
            volume_support = result.get('volume_breakout', False)

            return high_breakout and volume_support

        except Exception:
            return False

    def _is_stage_2_continuation(self, result: Dict) -> bool:
        """Stage 2 지속 감지 (개선된 로직)"""
        try:
            # Stage 2 활성 상태 + MA20 위 + 적절한 트렌드 강도
            stage_2_active = result.get('stage_2_active', False)
            price_above_ma20 = result.get('price_above_ma20', False)
            ma_trend_strength = result.get('ma_trend_strength', 0)

            # 🔧 더 유연한 조건: Stage 2 상태이거나 강한 트렌드 + MA20 위
            return (stage_2_active and price_above_ma20) or (ma_trend_strength > 0.5 and price_above_ma20)

        except Exception:
            return False

    def _is_ma200_breakout(self, result: Dict) -> bool:
        """단순 MA200 돌파 감지"""
        try:
            ma200_breakout = result.get('ma200_breakout', False)
            return ma200_breakout

        except Exception:
            return False

    def get_quality_multiplier(self, quality_score: float) -> Tuple[float, str]:
        """품질 점수에 따른 조정 배수 계산"""
        for adjustment in self.quality_adjustments:
            min_score, max_score = adjustment.score_range
            if min_score <= quality_score < max_score:
                return adjustment.multiplier, adjustment.description

        # 기본값 (점수가 범위를 벗어날 경우)
        return 1.0, "Default (범위 외)"

    def calculate_technical_position(self,
                                   pattern_type: PatternType,
                                   quality_score: float) -> Tuple[float, float, float]:
        """Stage 1: Technical Filter 단계 포지션 계산"""

        # 1. 패턴별 기본 포지션 확인
        if pattern_type not in self.pattern_probabilities:
            logger.warning(f"⚠️ 알 수 없는 패턴: {pattern_type}")
            base_position = 1.0  # 최소 포지션
        else:
            base_position = self.pattern_probabilities[pattern_type].base_position

        # 2. 품질 점수 조정
        quality_multiplier, quality_desc = self.get_quality_multiplier(quality_score)

        # 3. 리스크 레벨 조정
        risk_adjustment = self._get_risk_adjustment()

        # 4. 최종 기술적 포지션 계산
        technical_position = base_position * quality_multiplier * risk_adjustment

        # 5. 최대 포지션 제한
        technical_position = min(technical_position, self.max_single_position)

        logger.debug(f"📊 기술적 포지션: {base_position}% × {quality_multiplier:.2f} × {risk_adjustment:.2f} = {technical_position:.2f}%")

        return base_position, quality_multiplier, technical_position

    def _get_risk_adjustment(self) -> float:
        """리스크 레벨에 따른 조정"""
        if self.risk_level == RiskLevel.CONSERVATIVE:
            return 0.7
        elif self.risk_level == RiskLevel.MODERATE:
            return 1.0
        elif self.risk_level == RiskLevel.AGGRESSIVE:
            return 1.3
        return 1.0

    def apply_gpt_adjustment(self,
                           technical_position: float,
                           gpt_confidence: Optional[float] = None,
                           gpt_recommendation: Optional[str] = None) -> Tuple[float, float]:
        """Stage 2: GPT 분석 후 최종 조정"""

        if gpt_confidence is None or gpt_recommendation is None:
            # GPT 분석 없음 - 기술적 포지션 그대로 사용
            return technical_position, 1.0

        # GPT 추천에 따른 기본 조정
        if gpt_recommendation == "STRONG_BUY":
            base_adjustment = 1.4
        elif gpt_recommendation == "BUY":
            base_adjustment = 1.2
        elif gpt_recommendation == "HOLD":
            base_adjustment = 1.0
        elif gpt_recommendation == "AVOID":
            base_adjustment = 0.3  # 크게 축소
        else:
            base_adjustment = 1.0

        # GPT 신뢰도 반영 (0.5 ~ 1.5 범위로 조정)
        confidence_adjustment = 0.5 + (gpt_confidence * 1.0)

        # 최종 GPT 조정 배수
        gpt_adjustment = base_adjustment * confidence_adjustment

        # 50%~150% 범위 제한 (초기 사이징의 절반~1.5배)
        gpt_adjustment = max(0.5, min(1.5, gpt_adjustment))

        # 최종 포지션 계산
        final_position = technical_position * gpt_adjustment

        # 최대 포지션 제한
        final_position = min(final_position, self.max_single_position)

        logger.debug(f"🤖 GPT 조정: {technical_position:.2f}% × {gpt_adjustment:.2f} = {final_position:.2f}%")

        return final_position, gpt_adjustment

    def calculate_position_size(self,
                              technical_result: Dict,
                              gpt_result: Optional[Dict] = None) -> KellyResult:
        """종합 포지션 사이징 계산"""

        ticker = technical_result.get('ticker', 'UNKNOWN')
        quality_score = technical_result.get('quality_score', 10.0)

        try:
            # 1. 패턴 타입 감지
            pattern_type = self.detect_pattern_type(technical_result)

            # 2. Stage 1: Technical Filter 단계
            base_position, quality_multiplier, technical_position = self.calculate_technical_position(
                pattern_type, quality_score
            )

            # 3. Stage 2: GPT 조정 단계 (선택적)
            gpt_confidence = None
            gpt_recommendation = None
            gpt_adjustment = 1.0
            final_position = technical_position

            if gpt_result:
                gpt_confidence = gpt_result.get('confidence', None)
                gpt_recommendation = gpt_result.get('recommendation', None)

                final_position, gpt_adjustment = self.apply_gpt_adjustment(
                    technical_position, gpt_confidence, gpt_recommendation
                )

            # 4. 결과 생성
            result = KellyResult(
                ticker=ticker,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                detected_pattern=pattern_type,
                quality_score=quality_score,
                base_position_pct=base_position,
                quality_multiplier=quality_multiplier,
                technical_position_pct=technical_position,
                gpt_confidence=gpt_confidence,
                gpt_recommendation=gpt_recommendation,
                gpt_adjustment=gpt_adjustment,
                final_position_pct=final_position,
                risk_level=self.risk_level,
                max_portfolio_allocation=self.max_total_allocation,
                reasoning=self._generate_reasoning(pattern_type, quality_score, gpt_result)
            )

            # 5. DB 저장
            self._save_kelly_result(result)

            logger.info(f"🎲 {ticker}: Kelly 계산 완료 - {pattern_type.value} → {final_position:.2f}%")
            return result

        except Exception as e:
            logger.error(f"❌ {ticker} Kelly 계산 실패: {e}")

            # 기본값 반환
            return KellyResult(
                ticker=ticker,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                detected_pattern=PatternType.UNKNOWN,
                quality_score=quality_score,
                base_position_pct=1.0,
                quality_multiplier=1.0,
                technical_position_pct=1.0,
                final_position_pct=1.0,
                reasoning="계산 실패 - 최소 포지션 적용"
            )

    def _generate_reasoning(self,
                          pattern_type: PatternType,
                          quality_score: float,
                          gpt_result: Optional[Dict]) -> str:
        """포지션 결정 근거 생성"""

        reasoning_parts = []

        # 패턴 설명
        pattern_desc = {
            PatternType.STAGE_1_TO_2: "Stage 1→2 전환 (최강 신호)",
            PatternType.VCP_BREAKOUT: "VCP 돌파 패턴",
            PatternType.CUP_HANDLE: "Cup & Handle 패턴",
            PatternType.HIGH_60D_BREAKOUT: "60일 고점 돌파",
            PatternType.STAGE_2_CONTINUATION: "Stage 2 지속",
            PatternType.MA200_BREAKOUT: "MA200 돌파",
            PatternType.UNKNOWN: "패턴 불명확"
        }

        reasoning_parts.append(f"패턴: {pattern_desc.get(pattern_type, '알 수 없음')}")
        reasoning_parts.append(f"품질점수: {quality_score:.1f}점")

        if gpt_result:
            gpt_rec = gpt_result.get('recommendation', 'HOLD')
            gpt_conf = gpt_result.get('confidence', 0.0)
            reasoning_parts.append(f"GPT: {gpt_rec} ({gpt_conf:.2f})")

        return " | ".join(reasoning_parts)

    def _save_kelly_result(self, result: KellyResult):
        """Kelly 계산 결과 저장 (GPT fields 포함)

        KellyResult를 kelly_analysis 테이블에 저장합니다.
        GPT 분석 결과 (gpt_confidence, gpt_recommendation, gpt_adjustment, final_position_pct)도 함께 저장됩니다.

        Args:
            result: KellyResult dataclass instance

        Database Schema:
            - ticker, analysis_date, detected_pattern, quality_score
            - base_position_pct, quality_multiplier, technical_position_pct
            - gpt_confidence, gpt_recommendation, gpt_adjustment, final_position_pct
            - risk_level, max_portfolio_allocation, reasoning
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO kelly_analysis (
                    ticker, analysis_date, detected_pattern, quality_score,
                    base_position_pct, quality_multiplier, technical_position_pct,
                    gpt_confidence, gpt_recommendation, gpt_adjustment, final_position_pct,
                    risk_level, max_portfolio_allocation, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.ticker,
                result.analysis_date,
                result.detected_pattern.value if isinstance(result.detected_pattern, PatternType) else result.detected_pattern,
                result.quality_score,
                result.base_position_pct,
                result.quality_multiplier,
                result.technical_position_pct,
                result.gpt_confidence,       # None if GPT disabled, float if enabled
                result.gpt_recommendation,   # None if GPT disabled, str if enabled
                result.gpt_adjustment,       # 1.0 if GPT disabled, 0.5-1.5 if enabled
                result.final_position_pct,   # Same as technical_position_pct if GPT disabled
                result.risk_level.value if isinstance(result.risk_level, RiskLevel) else result.risk_level,
                result.max_portfolio_allocation,
                result.reasoning
            ))

            conn.commit()
            conn.close()

            # Log save details
            if result.gpt_confidence is not None:
                logger.debug(f"💾 {result.ticker}: Kelly 결과 DB 저장 완료 "
                           f"(Technical: {result.technical_position_pct:.2f}% "
                           f"× GPT: {result.gpt_adjustment:.2f} "
                           f"→ Final: {result.final_position_pct:.2f}%)")
            else:
                logger.debug(f"💾 {result.ticker}: Kelly 결과 DB 저장 완료 "
                           f"(Final: {result.final_position_pct:.2f}%, GPT disabled)")

        except Exception as e:
            logger.error(f"❌ {result.ticker} Kelly 결과 저장 실패: {e}")
            logger.error(f"   Result data: {result}")

    def adjust_position_for_lot_size(self,
                                    ticker: str,
                                    region: str,
                                    final_position_pct: float,
                                    portfolio_value: float,
                                    current_price: float) -> Dict[str, Any]:
        """Adjust position percentage to respect lot_size constraints

        Kelly Calculator에서 계산한 포지션 비율을 lot_size 제약에 맞게 조정합니다.

        Args:
            ticker: 종목 코드
            region: 지역 코드 (KR, US, CN, HK, JP, VN)
            final_position_pct: Kelly에서 계산한 최종 포지션 비율 (%)
            portfolio_value: 현재 포트폴리오 가치 (KRW)
            current_price: 현재 주가 (KRW)

        Returns:
            Dict with:
                - adjusted_position_pct: lot_size 조정된 포지션 비율 (%)
                - raw_quantity: 원래 계산된 수량
                - adjusted_quantity: lot_size 반영된 수량
                - lot_size: 종목의 lot_size
                - warning: 경고 메시지 (있을 경우)

        Example:
            >>> result = kelly_calc.adjust_position_for_lot_size(
            ...     ticker="0700",
            ...     region="HK",
            ...     final_position_pct=5.0,
            ...     portfolio_value=10000000,
            ...     current_price=350
            ... )
            >>> print(result['adjusted_position_pct'])  # 4.9% (rounded down)
            >>> print(result['adjusted_quantity'])      # 1400 (14 lots × 100)
        """
        try:
            # 1. Get lot_size from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT lot_size
                FROM tickers
                WHERE ticker = ? AND region = ?
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result or not result[0]:
                logger.warning(f"⚠️ [{ticker}] lot_size not found in DB, defaulting to 1")
                lot_size = 1
            else:
                lot_size = int(result[0])

            # 2. Calculate raw quantity from Kelly position %
            position_value = portfolio_value * (final_position_pct / 100.0)
            raw_quantity = int(position_value / current_price)

            # 3. Round to lot_size multiple (round down)
            adjusted_quantity = (raw_quantity // lot_size) * lot_size

            # 4. Calculate adjusted position %
            adjusted_position_value = adjusted_quantity * current_price
            adjusted_position_pct = (adjusted_position_value / portfolio_value) * 100.0 if portfolio_value > 0 else 0.0

            # 5. Generate warnings
            warning = None
            if adjusted_quantity == 0 and raw_quantity > 0:
                warning = f"Position too small for lot_size {lot_size} (raw: {raw_quantity}, need: ≥{lot_size})"
                logger.warning(f"⚠️ [{ticker}] {warning}")
            elif adjusted_quantity != raw_quantity:
                reduction_pct = ((raw_quantity - adjusted_quantity) / raw_quantity) * 100 if raw_quantity > 0 else 0
                logger.info(f"📊 [{ticker}] Quantity adjusted for lot_size {lot_size}: "
                          f"{raw_quantity} → {adjusted_quantity} (-{reduction_pct:.1f}%)")

            return {
                'adjusted_position_pct': adjusted_position_pct,
                'raw_quantity': raw_quantity,
                'adjusted_quantity': adjusted_quantity,
                'lot_size': lot_size,
                'warning': warning
            }

        except Exception as e:
            logger.error(f"❌ [{ticker}] lot_size adjustment failed: {e}")
            # Return original values as fallback
            return {
                'adjusted_position_pct': final_position_pct,
                'raw_quantity': 0,
                'adjusted_quantity': 0,
                'lot_size': 1,
                'warning': f"Adjustment error: {str(e)}"
            }

    def get_portfolio_allocation_status(self) -> Dict[str, float]:
        """현재 포트폴리오 할당 상태 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            # 오늘 계산된 포지션들의 합계
            cursor.execute("""
                SELECT SUM(final_position_pct) as total_allocation,
                       COUNT(*) as position_count
                FROM kelly_analysis
                WHERE analysis_date = ?
            """, (today,))

            row = cursor.fetchone()
            total_allocation = row[0] or 0.0
            position_count = row[1] or 0

            conn.close()

            remaining_allocation = self.max_total_allocation - total_allocation

            return {
                'total_allocation': total_allocation,
                'remaining_allocation': max(0, remaining_allocation),
                'position_count': position_count,
                'utilization_rate': (total_allocation / self.max_total_allocation) * 100
            }

        except Exception as e:
            logger.error(f"❌ 포트폴리오 할당 상태 조회 실패: {e}")
            return {
                'total_allocation': 0.0,
                'remaining_allocation': self.max_total_allocation,
                'position_count': 0,
                'utilization_rate': 0.0
            }

    def calculate_batch_positions(self, candidates: List[Dict]) -> List[Dict]:
        """다수 후보에 대한 배치 포지션 계산"""
        logger.info(f"🎲 Kelly 배치 계산 시작: {len(candidates)}개 후보")

        enhanced_candidates = []

        for candidate in candidates:
            try:
                # GPT 결과 추출 (있을 경우)
                gpt_result = None
                if 'gpt_analysis' in candidate and candidate['gpt_analysis']:
                    gpt_analysis = candidate['gpt_analysis']
                    gpt_result = {
                        'confidence': gpt_analysis.confidence,
                        'recommendation': gpt_analysis.recommendation.value
                    }

                # Kelly 계산 실행
                kelly_result = self.calculate_position_size(candidate, gpt_result)

                # 결과 추가
                candidate['kelly_analysis'] = kelly_result
                enhanced_candidates.append(candidate)

            except Exception as e:
                logger.error(f"❌ {candidate.get('ticker', 'UNKNOWN')} Kelly 계산 실패: {e}")
                # 실패해도 기본값으로 포함
                candidate['kelly_analysis'] = None
                enhanced_candidates.append(candidate)

        # 포트폴리오 할당 상태 확인
        allocation_status = self.get_portfolio_allocation_status()

        logger.info(f"✅ Kelly 배치 계산 완료")
        logger.info(f"📊 포트폴리오 할당: {allocation_status['total_allocation']:.2f}% / {self.max_total_allocation}%")
        logger.info(f"🎯 남은 할당: {allocation_status['remaining_allocation']:.2f}%")

        return enhanced_candidates

def main():
    """테스트 실행"""
    print("🧪 Kelly Calculator 테스트 시작")

    # Kelly 계산기 초기화
    calculator = KellyCalculator(risk_level=RiskLevel.MODERATE)
    print("✅ KellyCalculator 초기화 완료")

    # 테스트 기술적 분석 결과
    test_technical_results = [
        {
            'ticker': 'KRW-BTC',
            'quality_score': 18.5,
            'stage_2_entry': True,
            'volume_breakout': True,
            'ma_trend_strength': 0.8,
            'volatility_contraction': True,
        },
        {
            'ticker': 'KRW-ETH',
            'quality_score': 16.2,
            'high_60d_breakout': True,
            'volume_breakout': True,
            'current_stage': 2,
        },
        {
            'ticker': 'KRW-ADA',
            'quality_score': 12.8,
            'ma200_breakout': True,
        }
    ]

    # 테스트 GPT 결과
    test_gpt_results = [
        {'confidence': 0.85, 'recommendation': 'STRONG_BUY'},
        {'confidence': 0.65, 'recommendation': 'BUY'},
        None  # GPT 분석 없음
    ]

    print(f"\n📊 테스트 후보: {len(test_technical_results)}개")

    # 개별 계산 테스트
    for i, technical_result in enumerate(test_technical_results):
        ticker = technical_result['ticker']
        gpt_result = test_gpt_results[i] if i < len(test_gpt_results) else None

        print(f"\n🎯 {ticker} Kelly 계산:")

        # Kelly 계산
        kelly_result = calculator.calculate_position_size(technical_result, gpt_result)

        print(f"  감지 패턴: {kelly_result.detected_pattern.value}")
        print(f"  품질 점수: {kelly_result.quality_score:.1f}")
        print(f"  기술적 포지션: {kelly_result.technical_position_pct:.2f}%")
        if kelly_result.gpt_confidence:
            print(f"  GPT 조정: {kelly_result.gpt_adjustment:.2f}x")
        print(f"  최종 포지션: {kelly_result.final_position_pct:.2f}%")
        print(f"  근거: {kelly_result.reasoning}")

    # 포트폴리오 할당 상태 확인
    allocation_status = calculator.get_portfolio_allocation_status()
    print(f"\n📈 포트폴리오 상태:")
    print(f"  총 할당: {allocation_status['total_allocation']:.2f}%")
    print(f"  남은 할당: {allocation_status['remaining_allocation']:.2f}%")
    print(f"  포지션 수: {allocation_status['position_count']}개")
    print(f"  활용률: {allocation_status['utilization_rate']:.1f}%")

    print("\n🎯 Kelly Calculator 구현 완료!")
    print("📋 주요 기능:")
    print("  ✅ 역사적 패턴 승률 기반 Kelly 계산")
    print("  ✅ 2단계 포지션 사이징 (Technical → GPT)")
    print("  ✅ 품질 점수 조정 시스템")
    print("  ✅ 리스크 레벨 맞춤 조정")
    print("  ✅ 포트폴리오 할당 관리")
    print("  ✅ SQLite 통합 저장")

if __name__ == "__main__":
    main()