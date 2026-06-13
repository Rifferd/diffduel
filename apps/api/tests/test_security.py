"""Unit-тесты криптопримитивов: argon2, JWT, sha256 refresh."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.core.security import (
    constant_time_equals,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_argon2_hash_and_verify() -> None:
    password = "super-secret-password"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_on_garbage_hash() -> None:
    assert verify_password("x", "not-a-hash") is False


def test_jwt_encode_decode_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]


def test_jwt_expired_raises() -> None:
    user_id = uuid.uuid4()
    past = datetime.now(tz=UTC) - timedelta(seconds=3600)
    token = create_access_token(user_id, now=past)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_rejects_non_access_type() -> None:
    # Подделываем токен с type != access.
    from src.core.config import get_settings

    settings = get_settings()
    now = int(time.time())
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": now, "exp": now + 60, "type": "refresh"},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(forged)


def test_jwt_rejects_bad_signature() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_sha256_refresh_hash_deterministic() -> None:
    token = generate_refresh_token()
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != hash_refresh_token(generate_refresh_token())
    assert len(hash_refresh_token(token)) == 64  # hex sha256


def test_refresh_token_entropy() -> None:
    tokens = {generate_refresh_token() for _ in range(1000)}
    assert len(tokens) == 1000  # без коллизий


def test_constant_time_equals() -> None:
    assert constant_time_equals("abc", "abc") is True
    assert constant_time_equals("abc", "abd") is False
    assert constant_time_equals("abc", "abcd") is False


class TestProdConfigGuard:
    """Прод с dev-секретами не должен подняться (fail fast)."""

    _GOOD_SECRET = "a" * 64
    _GOOD_INTERNAL = "b" * 32

    def test_prod_rejects_dev_jwt_secret(self) -> None:
        import pytest
        from pydantic import ValidationError

        from src.core.config import _DEV_JWT_SECRET, Settings

        with pytest.raises(ValidationError, match="JWT_SECRET"):
            Settings(
                app_env="prod",
                jwt_secret=_DEV_JWT_SECRET,
                internal_api_token=self._GOOD_INTERNAL,
                cors_origins=["https://diffduel.com"],
            )

    def test_prod_rejects_http_cors_and_short_internal_token(self) -> None:
        import pytest
        from pydantic import ValidationError

        from src.core.config import Settings

        with pytest.raises(ValidationError, match="CORS_ORIGINS"):
            Settings(
                app_env="prod",
                jwt_secret=self._GOOD_SECRET,
                internal_api_token=self._GOOD_INTERNAL,
                cors_origins=["http://diffduel.com"],
            )
        with pytest.raises(ValidationError, match="INTERNAL_API_TOKEN"):
            Settings(
                app_env="prod",
                jwt_secret=self._GOOD_SECRET,
                internal_api_token="short",
                cors_origins=["https://diffduel.com"],
            )

    def test_prod_accepts_strong_secrets(self) -> None:
        from src.core.config import Settings

        settings = Settings(
            app_env="prod",
            jwt_secret=self._GOOD_SECRET,
            internal_api_token=self._GOOD_INTERNAL,
            cors_origins=["https://diffduel.com"],
            s3_secret_key="prod-grade-s3-secret-key",  # noqa: S106
        )
        assert settings.cookie_secure is True

    def test_prod_rejects_dev_s3_secret(self) -> None:
        import pytest
        from pydantic import ValidationError

        from src.core.config import _DEV_S3_SECRET, Settings

        with pytest.raises(ValidationError, match="S3_SECRET_KEY"):
            Settings(
                app_env="prod",
                jwt_secret=self._GOOD_SECRET,
                internal_api_token=self._GOOD_INTERNAL,
                cors_origins=["https://diffduel.com"],
                s3_secret_key=_DEV_S3_SECRET,
            )

    def test_dev_allows_defaults(self) -> None:
        from src.core.config import Settings

        assert Settings(app_env="dev").cookie_secure is False


def test_cors_origins_parses_csv_from_env() -> None:
    """CORS_ORIGINS как CSV-строка из env не должен падать (баг pydantic NoDecode)."""
    from src.core.config import Settings

    s = Settings(cors_origins="https://a.com,https://b.com, https://c.com")  # type: ignore[arg-type]
    assert s.cors_origins == ["https://a.com", "https://b.com", "https://c.com"]
