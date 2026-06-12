"""Внутренний роутер /internal/* — НЕ публикуется в OpenAPI."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.internal_api.dependencies import require_internal_token

# include_in_schema=False на каждом маршруте — чтобы не попасть в публичный OpenAPI.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_token)],
)


@router.get("/ping", include_in_schema=False)
async def ping() -> dict[str, str]:
    return {"status": "ok"}
