"""
Authentication Pydantic Models

Request/response models for authentication endpoints.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request model."""

    username: str = Field(..., min_length=1, max_length=50, description="Username")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginResponse(BaseModel):
    """Login response model."""

    session_token: str = Field(..., description="Session token for authentication")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    user: 'UserInfo' = Field(..., description="User information")


class LogoutResponse(BaseModel):
    """Logout response model."""

    message: str = Field(default="Logged out successfully")


class UserInfo(BaseModel):
    """User information model."""

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    role: str = Field(..., description="User role (admin, user, analyst)")
    is_active: bool = Field(..., description="Account active status")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")


# Update forward references
LoginResponse.model_rebuild()
