"""HTTP-клиент к Core API ``/internal/*``.

По смыслу повторяет realtime internal-client: auth через ``X-Internal-Token``,
таймаут, ретраи на сетевые ошибки и 5xx. Идемпотентные операции, повтор безопасен.

Эндпоинты (контракт API-агента, leaderboards-admin.md §C):
- ``GET  /internal/duels/{id}/card``  → данные для рендера + текущий share_card_key;
- ``POST /internal/duels/{id}/share-card`` {key} → записать ключ карточки.

API-агент пишет эндпоинты параллельно — в тестах клиент мокается.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from src.workers.config import Settings
from src.workers.logging import get_logger

logger = get_logger("internal_client")


class InternalClientError(RuntimeError):
    """Неустранимая ошибка обращения к Core API internal."""


@dataclass(frozen=True, slots=True)
class DuelCard:
    """Данные дуэли для рендера карточки (отдаёт Core API)."""

    duel_id: str
    # Имена игроков по их id (для подписи победителя/проигравшего).
    usernames: dict[str, str]
    # Уже сгенерированный ключ карточки (идемпотентность) — None, если ещё нет.
    share_card_key: str | None


class InternalClient:
    """Тонкая async-обёртка над httpx с ретраями (как realtime internal-client)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.core_api_url.rstrip("/")
        self._token = settings.internal_api_token
        self._timeout = settings.internal_timeout_s
        self._max_retries = settings.internal_max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> InternalClient:
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise InternalClientError("InternalClient используется вне async-контекста")
        return self._client

    def _headers(self) -> dict[str, str]:
        return {"content-type": "application/json", "x-internal-token": self._token}

    async def _request(self, method: str, path: str, *, json: object = None) -> httpx.Response:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.request(method, url, headers=self._headers(), json=json)
                if response.status_code >= 500:
                    raise _RetryableStatus(response.status_code)
                if response.status_code >= 400:
                    raise InternalClientError(
                        f"Core API {path} -> {response.status_code}: {response.text}"
                    )
                return response
            except (httpx.TransportError, _RetryableStatus) as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    break
                backoff = 0.1 * (attempt + 1)
                logger.warning(
                    "internal_request_retry",
                    path=path,
                    attempt=attempt + 1,
                    error=str(exc),
                    backoff_s=backoff,
                )
                await asyncio.sleep(backoff)
        raise InternalClientError(f"Core API {path} недоступен: {last_exc}")

    async def get_duel_card(self, duel_id: str) -> DuelCard:
        """Данные дуэли для рендера + текущий share_card_key (для идемпотентности)."""
        response = await self._request("GET", f"/internal/duels/{duel_id}/card")
        body = response.json()
        usernames_raw = body.get("usernames", {})
        usernames = {
            str(k): str(v) for k, v in usernames_raw.items() if isinstance(usernames_raw, dict)
        }
        key = body.get("share_card_key")
        return DuelCard(
            duel_id=duel_id,
            usernames=usernames,
            share_card_key=str(key) if key else None,
        )

    async def set_share_card(self, duel_id: str, key: str) -> None:
        """Записывает ключ карточки в дуэль (идемпотентно на стороне API)."""
        await self._request("POST", f"/internal/duels/{duel_id}/share-card", json={"key": key})


class _RetryableStatus(Exception):
    """Внутренний маркер 5xx-ответа, который имеет смысл повторить."""

    def __init__(self, status: int) -> None:
        super().__init__(f"Core API responded {status}")
        self.status = status
