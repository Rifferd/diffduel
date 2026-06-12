"""HTTP-роутер auth: register / login / refresh / logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from src.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from src.auth.service import AuthService, IssuedTokens
from src.core.db import get_db
from src.core.errors import AuthError
from src.core.rate_limit import rate_limit
from src.users.schemas import UserMe

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(response: Response, tokens: IssuedTokens) -> TokenResponse:
    set_refresh_cookie(response, tokens.refresh_token, expires_at=tokens.refresh_expires_at)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
    )


@router.post(
    "/register",
    response_model=UserMe,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth_register", limit=5, window_s=60, key="ip"))],
)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    user = await AuthService(session).register(data)
    return UserMe.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_login", limit=10, window_s=60, key="ip"))],
)
async def login(
    data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _user, tokens = await AuthService(session).login(data)
    return _token_response(response, tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_refresh", limit=30, window_s=60, key="ip"))],
)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise AuthError("Отсутствует refresh-токен", code="invalid_refresh_token")
    tokens = await AuthService(session).refresh(raw_token)
    return _token_response(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    await AuthService(session).logout(raw_token)
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
