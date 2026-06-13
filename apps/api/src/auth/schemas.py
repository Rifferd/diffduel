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


class RegisterResponse(BaseModel):
    """Единый ответ register для обоих режимов.

    OFF: verification_required=false + токены (авто-логин).
    ON: verification_required=true (код отправлен, токенов нет).
    """

    verification_required: bool
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyLinkRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class VerifyLinkResponse(BaseModel):
    """verify-link: на том же устройстве — авто-логин; на другом — только подтверждение.

    Код в БД лежит только хэшем, в открытом виде его взять неоткуда. На другом
    устройстве пользователь берёт код из своего же письма и вводит на устройстве
    регистрации — поэтому здесь код не возвращается.
    """

    logged_in: bool
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


class ResendCodeRequest(BaseModel):
    email: EmailStr
