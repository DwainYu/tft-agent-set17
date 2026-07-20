from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str
    password: str = Field(..., min_length=6)
    sms_code: str | None = None


class LoginRequest(BaseModel):
    phone: str
    password: str | None = None
    sms_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    phone: str
    created_at: str | None = None
