"""Pydantic-схемы домена auth."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.users.schemas import validate_username


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        return validate_username(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access-токен отдаётся в JSON; refresh — в httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  # это тип токена OAuth2, не секрет
    expires_in: int
