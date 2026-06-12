"""Тесты presigned-флоу аватаров. Happy-path требует MinIO (маркер s3)."""

from __future__ import annotations

import socket

import httpx
import pytest
from httpx import AsyncClient

from src.core.config import get_settings


def _minio_available() -> bool:
    settings = get_settings()
    host_port = settings.s3_endpoint.removeprefix("http://").removeprefix("https://")
    host, _, port = host_port.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=1):
            return True
    except OSError:
        return False


async def _auth_headers(client: AsyncClient, *, suffix: str) -> dict[str, str]:
    reg = {
        "email": f"{suffix}@example.com",
        "username": f"user_{suffix}",
        "password": "verylongpassword1",
    }
    assert (await client.post("/auth/register", json=reg)).status_code == 201
    login = await client.post(
        "/auth/login", json={"email": reg["email"], "password": reg["password"]}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_presign_validates_input(client: AsyncClient) -> None:
    headers = await _auth_headers(client, suffix="presignval")

    bad_type = await client.post(
        "/me/avatar/presign",
        json={"content_type": "application/x-sh", "size_bytes": 1000},
        headers=headers,
    )
    assert bad_type.status_code == 422

    too_big = await client.post(
        "/me/avatar/presign",
        json={"content_type": "image/png", "size_bytes": 3 * 1024 * 1024},
        headers=headers,
    )
    assert too_big.status_code == 422


@pytest.mark.asyncio
async def test_presign_key_is_scoped_to_user(client: AsyncClient) -> None:
    headers = await _auth_headers(client, suffix="presignkey")
    me = await client.get("/me", headers=headers)
    user_id = me.json()["id"]

    resp = await client.post(
        "/me/avatar/presign",
        json={"content_type": "image/png", "size_bytes": 1000},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"].startswith(f"{user_id}/")
    assert body["expires_in"] == 300
    assert body["upload_url"].startswith("http")


@pytest.mark.asyncio
async def test_confirm_rejects_foreign_key(client: AsyncClient) -> None:
    headers = await _auth_headers(client, suffix="foreign")
    resp = await client.post(
        "/me/avatar/confirm",
        json={"key": "11111111-1111-1111-1111-111111111111/evil.png"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "avatar_key_forbidden"


@pytest.mark.s3
@pytest.mark.asyncio
async def test_avatar_happy_path_with_minio(client: AsyncClient) -> None:
    if not _minio_available():
        pytest.skip("MinIO недоступен — happy-path пропущен (CI без S3)")

    headers = await _auth_headers(client, suffix="happyavatar")

    # confirm до загрузки — объект ещё не существует.
    presign = await client.post(
        "/me/avatar/presign",
        json={"content_type": "image/png", "size_bytes": 68},
        headers=headers,
    )
    key = presign.json()["key"]
    upload_url = presign.json()["upload_url"]
    early = await client.post("/me/avatar/confirm", json={"key": key}, headers=headers)
    assert early.status_code == 422
    assert early.json()["error"]["code"] == "avatar_not_uploaded"

    # Загрузка напрямую в MinIO по presigned PUT (мимо API).
    png_1px = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fcffff3f0300050001ff5ccc59e50000000049454e44ae426082"
    )
    async with httpx.AsyncClient() as raw:
        put = await raw.put(upload_url, content=png_1px, headers={"Content-Type": "image/png"})
        assert put.status_code == 200, put.text

    confirm = await client.post("/me/avatar/confirm", json={"key": key}, headers=headers)
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["avatar_url"] is not None and key in body["avatar_url"]
