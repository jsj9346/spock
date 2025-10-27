#!/usr/bin/env python3
"""
strategy_models.py - Pydantic Models for Strategy CRUD API

Purpose:
- Define request/response models for Strategy endpoints
- Validate factor weights and constraints
- Provide type safety and auto-documentation

Design:
- FactorWeightConfig: JSONB structure for factor_weights (validates sum=1.0)
- StrategyConstraints: JSONB structure for portfolio constraints
- StrategyBase: Base fields shared across operations
- StrategyCreate: POST request model (validates factor weights)
- StrategyUpdate: PUT/PATCH request model (all fields optional)
- StrategyResponse: GET response model (includes id, timestamps)
- StrategyListResponse: Paginated list response with metadata
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class FactorCategory(str, Enum):
    """Factor category classification (matches modules/factors/factor_base.py)"""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    LOW_VOL = "low_volatility"
    SIZE = "size"


class FactorWeightConfig(BaseModel):
    """
    Factor weight configuration (stored in strategies.factor_weights JSONB)

    All weights must be 0.0-1.0 and sum to 1.0 (±0.01 tolerance)
    """
    momentum: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Momentum factor weight (trend following)"
    )
    value: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Value factor weight (fundamental valuation)"
    )
    quality: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality factor weight (business quality)"
    )
    low_volatility: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Low volatility factor weight (risk reduction)"
    )
    size: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Size factor weight (market cap)"
    )

    @model_validator(mode='after')
    def validate_weight_sum(self):
        """Validate that factor weights sum to 1.0 (±0.01 tolerance)"""
        total = self.momentum + self.value + self.quality + self.low_volatility + self.size

        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Factor weights must sum to 1.0 (got {total:.4f}). "
                f"Current weights: momentum={self.momentum:.2f}, "
                f"value={self.value:.2f}, "
                f"quality={self.quality:.2f}, "
                f"low_volatility={self.low_volatility:.2f}, "
                f"size={self.size:.2f}"
            )

        return self

    class Config:
        schema_extra = {
            "example": {
                "momentum": 0.4,
                "value": 0.3,
                "quality": 0.2,
                "low_volatility": 0.1,
                "size": 0.0
            }
        }


class StrategyConstraints(BaseModel):
    """
    Portfolio constraints configuration (stored in strategies.constraints JSONB)

    Defines limits for position sizing, sector exposure, and risk management
    """
    max_position_size: Optional[float] = Field(
        default=0.15,
        ge=0.01,
        le=1.0,
        description="Maximum weight per position (default: 15%)"
    )
    min_position_size: Optional[float] = Field(
        default=0.01,
        ge=0.001,
        le=0.5,
        description="Minimum weight per position (default: 1%)"
    )
    max_sector_weight: Optional[float] = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Maximum weight per sector (default: 40%)"
    )
    max_turnover: Optional[float] = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Maximum portfolio turnover per rebalance (default: 20%)"
    )
    min_liquidity: Optional[float] = Field(
        default=1000000.0,
        ge=0.0,
        description="Minimum daily trading volume in USD (default: $1M)"
    )
    cash_reserve: Optional[float] = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Minimum cash reserve ratio (default: 10%)"
    )
    long_only: Optional[bool] = Field(
        default=True,
        description="Long-only constraint (default: True)"
    )

    class Config:
        schema_extra = {
            "example": {
                "max_position_size": 0.15,
                "min_position_size": 0.01,
                "max_sector_weight": 0.40,
                "max_turnover": 0.20,
                "min_liquidity": 1000000.0,
                "cash_reserve": 0.10,
                "long_only": True
            }
        }


class StrategyBase(BaseModel):
    """Base model with fields shared across all Strategy operations"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique strategy name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Strategy description and rationale"
    )
    factor_weights: FactorWeightConfig = Field(
        ...,
        description="Factor weight configuration (must sum to 1.0)"
    )
    constraints: Optional[StrategyConstraints] = Field(
        default=StrategyConstraints(),
        description="Portfolio constraints (optional, uses defaults if not provided)"
    )


class StrategyCreate(StrategyBase):
    """Model for creating new strategy (POST /strategies)"""

    class Config:
        schema_extra = {
            "example": {
                "name": "Momentum-Value Strategy",
                "description": "Combines 12-month momentum (40%) with value factors (30%), quality (20%), and low-vol (10%)",
                "factor_weights": {
                    "momentum": 0.4,
                    "value": 0.3,
                    "quality": 0.2,
                    "low_volatility": 0.1,
                    "size": 0.0
                },
                "constraints": {
                    "max_position_size": 0.15,
                    "max_sector_weight": 0.40,
                    "max_turnover": 0.20,
                    "long_only": True
                }
            }
        }


class StrategyUpdate(BaseModel):
    """Model for updating existing strategy (PUT/PATCH /strategies/{id})"""
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Strategy name (optional)"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Strategy description (optional)"
    )
    factor_weights: Optional[FactorWeightConfig] = Field(
        default=None,
        description="Factor weight configuration (optional, must sum to 1.0 if provided)"
    )
    constraints: Optional[StrategyConstraints] = Field(
        default=None,
        description="Portfolio constraints (optional)"
    )

    class Config:
        schema_extra = {
            "example": {
                "description": "Updated: Added quality factor for better downside protection",
                "factor_weights": {
                    "momentum": 0.35,
                    "value": 0.25,
                    "quality": 0.25,
                    "low_volatility": 0.15,
                    "size": 0.0
                }
            }
        }


class StrategyResponse(StrategyBase):
    """Model for strategy response (GET /strategies, GET /strategies/{id})"""
    id: int = Field(..., description="Strategy ID (auto-generated)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Momentum-Value Strategy",
                "description": "Combines 12-month momentum (40%) with value factors (30%)",
                "factor_weights": {
                    "momentum": 0.4,
                    "value": 0.3,
                    "quality": 0.2,
                    "low_volatility": 0.1,
                    "size": 0.0
                },
                "constraints": {
                    "max_position_size": 0.15,
                    "max_sector_weight": 0.40,
                    "max_turnover": 0.20,
                    "long_only": True
                },
                "created_at": "2024-10-22T10:30:00Z",
                "updated_at": "2024-10-22T10:30:00Z"
            }
        }


class StrategyListResponse(BaseModel):
    """Model for paginated strategy list (GET /strategies)"""
    total: int = Field(..., description="Total number of strategies")
    skip: int = Field(..., description="Number of strategies skipped (offset)")
    limit: int = Field(..., description="Maximum strategies per page")
    strategies: List[StrategyResponse] = Field(..., description="List of strategies")

    class Config:
        schema_extra = {
            "example": {
                "total": 5,
                "skip": 0,
                "limit": 50,
                "strategies": [
                    {
                        "id": 1,
                        "name": "Momentum-Value Strategy",
                        "description": "Combines momentum and value factors",
                        "factor_weights": {
                            "momentum": 0.4,
                            "value": 0.3,
                            "quality": 0.2,
                            "low_volatility": 0.1,
                            "size": 0.0
                        },
                        "constraints": {
                            "max_position_size": 0.15,
                            "max_sector_weight": 0.40
                        },
                        "created_at": "2024-10-22T10:30:00Z",
                        "updated_at": "2024-10-22T10:30:00Z"
                    }
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Model for error responses"""
    detail: str = Field(..., description="Error message")

    class Config:
        schema_extra = {
            "example": {
                "detail": "Strategy not found"
            }
        }
