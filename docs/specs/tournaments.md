# Спека: турниры (Релиз 3, часть A)

> Платный вход — ЗАГЛУШКА (как Pro): реальной оплаты нет, вход выдаётся вручную
> через админку либо бесплатно в dev. Таблицы tournaments/tournament_entries есть (0001).

## Модель (миграция 0007)
Дополнить `tournaments`: `topic_id fk`, `ends_at timestamptz`, `task_ids uuid[]` (фиксированный набор задач турнира). Статусы enum: `upcoming|active|finished`. `tournament_entries` уже: tournament_id, user_id, score, place, unique(tournament_id,user_id) — дополнить `time_ms int`, `finished_at`.

## Публичные/auth эндпоинты
- `GET /tournaments?status=` — список (title, topic, starts_at, ends_at, entry_fee, prize_pool, status, entries_count).
- `GET /tournaments/{id}` — детали + лидерборд (entries с никами, score, place — без N+1).
- `POST /tournaments/{id}/enter` (auth) — вход. Платёж-заглушка: `ManualProvider` → 402 `{code:"entry_payment_unavailable"}` (вход выдаёт админ). Если уже участник — 200. Если entry_fee=0 — пускать бесплатно.
- `GET /tournaments/{id}/tasks` (auth, участник, status=active) — задачи турнира без эталонов (как training).
- `POST /tournaments/{id}/answer` (auth, участник, active) — `{task_id, answer, time_ms}`: проверка checker'ом, накопление score/time в entry; один зачётный ответ на задачу. По завершении всех задач/окна — фиксируется finished_at.

## Админка (RBAC admin)
- CRUD `/admin/tournaments`: create (title, topic, кол-во задач или явный список published-задач темы, starts_at, ends_at, entry_fee, prize_pool), update, изменение статуса.
- `POST /admin/tournaments/{id}/grant-entry {user_id}` — ручная выдача входа (заглушка оплаты).
- Пересчёт мест (place) — при завершении турнира или по запросу: `RANK() OVER (ORDER BY score DESC, time_ms ASC)`.

## DoD
Слои как в проекте. ruff + ruff format --check + mypy strict + pytest. alembic 0007 проходит. Тесты: список/детали, enter (402 заглушка / бесплатно / повтор), задачи без эталона, ответ и накопление score, RBAC admin CRUD + grant-entry, пересчёт мест. Эталоны не в публичных схемах. Лидерборд без N+1.
