"""HTTP-роутер auth: register / login / refresh / logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.cookies import (
    REFRESH_COOKIE_NAME,
    VERIFY_SID_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
    set_verify_sid_cookie,
)
from src.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    TokenResponse,
    VerifyEmailRequest,
    VerifyLinkRequest,
    VerifyLinkResponse,
)
from src.auth.service import AuthService, IssuedTokens
from src.core.db import get_db
from src.core.errors import AuthError
from src.core.rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(response: Response, tokens: IssuedTokens) -> TokenResponse:
    set_refresh_cookie(response, tokens.refresh_token, expires_at=tokens.refresh_expires_at)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth_register", limit=5, window_s=60, key="ip"))],
)
async def register(
    data: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    result = await AuthService(session).register(data)
    if result.tokens is None:
        # Режим ON: токенов нет, ставим sid-cookie, фронт ведёт на ввод кода.
        if result.verify_sid is not None:
            set_verify_sid_cookie(response, result.verify_sid)
        return RegisterResponse(verification_required=True)
    # Режим OFF: авто-логин (refresh-cookie + access в теле).
    set_refresh_cookie(
        response, result.tokens.refresh_token, expires_at=result.tokens.refresh_expires_at
    )
    return RegisterResponse(
        verification_required=False,
        access_token=result.tokens.access_token,
        token_type="bearer",  # noqa: S106  # тип токена OAuth2, не секрет
        expires_in=result.tokens.access_expires_in,
    )


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
    "/verify-email",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_verify_email", limit=10, window_s=60, key="ip"))],
)
async def verify_email(
    data: VerifyEmailRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tokens = await AuthService(session).verify_email(data.email, data.code)
    return _token_response(response, tokens)


@router.post(
    "/verify-link",
    response_model=VerifyLinkResponse,
    dependencies=[Depends(rate_limit("auth_verify_link", limit=20, window_s=60, key="ip"))],
)
async def verify_link(
    data: VerifyLinkRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> VerifyLinkResponse:
    sid = request.cookies.get(VERIFY_SID_COOKIE_NAME)
    _logged_in, tokens = await AuthService(session).verify_link(data.token, sid=sid)
    if tokens is None:
        # Другое устройство: email подтверждён, но логина здесь нет.
        return VerifyLinkResponse(logged_in=False)
    set_refresh_cookie(response, tokens.refresh_token, expires_at=tokens.refresh_expires_at)
    return VerifyLinkResponse(
        logged_in=True,
        access_token=tokens.access_token,
        token_type="bearer",  # noqa: S106  # тип токена OAuth2, не секрет
        expires_in=tokens.access_expires_in,
    )


@router.post(
    "/resend-code",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("auth_resend_code", limit=3, window_s=900, key="ip"))],
)
async def resend_code(
    data: ResendCodeRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await AuthService(session).resend_code(data.email)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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
