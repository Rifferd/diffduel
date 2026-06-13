"""CLI создания/повышения администратора.

Продакшен-бутстрап: первый администратор заводится этой командой, дальше роли
выдаются через админку. Пароль читается из env ADMIN_PASSWORD или интерактивно
(getpass), в аргументы CLI не передаётся — чтобы не утёк в историю shell/ps.

Запуск:
    ADMIN_PASSWORD=... uv run python -m src.create_admin --email a@b.com --username admin
    uv run python -m src.create_admin --email a@b.com --username admin  # спросит пароль
    uv run python -m src.create_admin --email a@b.com --role moderator
"""

from __future__ import annotations

import argparse
import asyncio
import os
from getpass import getpass

from src.core.db import dispose_engine, get_sessionmaker
from src.core.enums import UserRole
from src.core.security import hash_password
from src.users.repository import UserRepository
from src.users.schemas import validate_username


async def _run(email: str, username: str | None, role: UserRole, password: str) -> None:
    try:
        await _do_run(email, username, role, password)
    finally:
        await dispose_engine()


async def _do_run(email: str, username: str | None, role: UserRole, password: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            # Пользователь есть — только повышаем роль (пароль не трогаем).
            existing.role = role
            await session.commit()
            print(f"Роль пользователя {email} повышена до {role.value}.")
            return

        if username is None:
            raise SystemExit("Для нового пользователя обязателен --username")
        normalized = validate_username(username)
        if await repo.exists_username(normalized):
            raise SystemExit(f"Username {normalized} уже занят")

        user = await repo.create(
            email=email,
            username=normalized,
            password_hash=hash_password(password),
        )
        user.role = role
        await session.commit()
        print(f"Создан {role.value}: {email} / {normalized} (id={user.id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать/повысить администратора DiffDuel")
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", default=None, help="обязателен для нового пользователя")
    parser.add_argument(
        "--role",
        choices=[r.value for r in UserRole if r is not UserRole.user],
        default=UserRole.admin.value,
    )
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD") or getpass("Пароль администратора: ")
    if len(password) < 10:
        raise SystemExit("Пароль должен быть не короче 10 символов")

    asyncio.run(_run(args.email, args.username, UserRole(args.role), password))


if __name__ == "__main__":
    main()
