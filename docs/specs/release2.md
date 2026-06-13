# Спека: Релиз 2 «Деньги»

> Платёж — ЗАГЛУШКА: реального провайдера нет, Pro/вход выдаются вручную через
> админку за интерфейсом `PaymentProvider` (потом включается реальный провайдер).
> Таблицы subscriptions/payments/tournaments уже существуют (миграция 0001).

## A. Pro-подписка (apps/api)

- `PaymentProvider` — абстракция (Protocol) в `src/billing/providers/`: метод `create_checkout(user, product) -> CheckoutResult`. Реализация `ManualProvider` (заглушка): возвращает «оплата недоступна, обратитесь к админу» / создаёт pending-платёж. Структура готова под ЮKassa/Stripe — но их НЕ реализуем.
- Pro-статус через таблицу `subscriptions` (plan='pro', status='active', current_period_end). Хелпер `is_pro(user)` = активная подписка с current_period_end > now. Включить `is_pro: bool` в GET /me (UserMe) и в публичный профиль (бейдж).
- Админка: `POST /admin/users/{id}/grant-pro {days:int}` (только admin) — создаёт/продлевает активную подписку на N дней, пишет payment purpose='subscription' provider='manual'. `POST /admin/users/{id}/revoke-pro`. Идемпотентно/безопасно.
- Пейволл: эндпоинты Pro-функций возвращают 402 `{code:"pro_required"}` без активной подписки. Pro-функции: AI-разбор (релиз 2b), расширенная статистика профиля (`GET /me/stats?period=` — отдать только Pro полную; не-Pro урезанную или 402 — реши, задокументируй), кастомные темы share-карточек (вне MVP).
- Миграция: только если нужны новые колонки (вероятно нет). Если subscriptions достаточно — без миграции.

## B. Дневной челлендж (apps/api)

- Таблица `daily_challenges(challenge_date date pk, task_id uuid fk→tasks, created_at)` — миграция **0005**.
- Выбор задачи дня: команда/леним — `GET /daily` (auth): возвращает задачу дня (без эталона, как training); если на сегодня нет записи — лениво выбрать случайную published-задачу и зафиксировать (атомарно, ON CONFLICT). 
- `POST /daily/answer {answer}` (auth, rate limit): проверка как в соло; **один зачётный ответ в день на юзера** (повторные — показываем результат, но в лидерборд не идут). Запись в answers (duel_id=null) + членство в дневном лидерборде.
- Дневной лидерборд: Redis ZSET `lb:daily:{YYYY-MM-DD}` score = (correct? быстрее время лучше): храни score как (верно: большой бонус − время_мс; неверно: 0). `GET /daily/leaderboard` — топ-N с никами (без N+1, как обычный лидерборд). `GET /daily/me` — моя позиция.
- Челлендж — НЕ Pro-гейтед (retention-петля для всех).

## DoD
Слои/стиль как в существующем apps/api. ruff + ruff format --check + mypy strict + pytest — ВСЁ зелёное (прогнать самому, включая format!). alembic upgrade head проходит (миграция 0005). Тесты: grant-pro/revoke-pro + is_pro в /me, пейволл 402 для не-Pro, дневной челлендж (ленивый выбор, один зачётный ответ, лидерборд дня, позиция). RBAC grant-pro только admin.
