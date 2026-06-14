# Спека: Релиз 3 — привязка Telegram, виджет, PWA, UI турниров

## A. API: привязка Telegram-аккаунта + embeddable-виджет (apps/api, миграция 0008)

### Привязка Telegram
- Таблица `telegram_accounts(user_id pk fk→users, telegram_user_id bigint unique, linked_at)` — миграция 0008.
- `POST /me/telegram/link-code` (auth) — генерит одноразовый код (6-8 символов, TTL 10 мин, хранить в Redis `tg:link:{code}`→user_id), возвращает `{code, bot_url}` (bot_url = `https://t.me/<bot>?start=<code>` из env TELEGRAM_BOT_USERNAME).
- `POST /internal/telegram/redeem` {code, telegram_user_id} (X-Internal-Token) — бот вызывает: проверяет код в Redis, привязывает (upsert telegram_accounts), удаляет код. → `{user_id, username}` или 400.
- `GET /internal/telegram/user/{telegram_user_id}` (X-Internal-Token) — бот резолвит юзера: `{user_id, username, linked}` или 404. (для команды /rating).
- `DELETE /me/telegram` (auth) — отвязать.

### Embeddable-виджет рейтинга (для README на GitHub)
- `GET /widget/{username}.svg` (публичный, без auth) — отдаёт **SVG-бейдж** рейтинга: ник, глобальный Эло, винрейт. Content-Type image/svg+xml, Cache-Control public max-age 300. Бренд DiffDuel (цвета токенов). Несуществующий/забаненный → нейтральный SVG «not found» (200, не 404, чтобы README не ломался). НЕ требует JS — чистый SVG.
- Опц. `GET /widget/{username}` — маленькая HTML-страница-превью с кодом для вставки в README (markdown-сниппет). Не обязательно для MVP.

DoD api: ruff+format+mypy+pytest, alembic 0008. Тесты: link-code (Redis), redeem (валид/невалид/повтор), resolve, виджет SVG (валидный SVG, корректные данные, not-found нейтральный). Env: TELEGRAM_BOT_USERNAME.

## B. Web: UI турниров + PWA (apps/web), управление турнирами (apps/admin)

### Турниры (web, нарезка tournaments.html + tournament.html)
- `/tournaments` — список (upcoming/active/finished), вход.
- `/tournaments/:id` — детали, лидерборд, кнопка «Участвовать» (enter; 402 → сообщение «оплата недоступна, обратитесь к админу»), для активных участников — «Играть» → задачи/ответы (как тренировка), прогресс, итог.
- Эндпоинты: GET /tournaments, GET /tournaments/{id}, POST /tournaments/{id}/enter, GET /tournaments/{id}/tasks, POST /tournaments/{id}/answer. Регенерируй контракты (турниры добавились в API).

### Управление турнирами (admin)
- Страница «Турниры»: список + создание (title, тема, кол-во задач, starts_at/ends_at, entry_fee, prize_pool), смена статуса, grant-entry пользователю. Эндпоинты /admin/tournaments*.

### PWA (web)
- Манифест уже есть (public/manifest.webmanifest). Добавить **service worker** (vite-plugin-pwa или ручной): кэш статики (app shell) + офлайн-страница; **офлайн-тренировки** — кэшировать ответ `GET /tasks/training` и позволять решать закэшированные задачи офлайн (проверка ответов офлайн невозможна без эталона — для офлайна разреши просмотр и локальную пометку, синхронизация при сети опциональна; MVP: app shell офлайн + страница offline.html из дизайна). Push «тебя вызвали» — зарегистрировать SW для push (без сервера пушей в MVP — оставить хук/заготовку).
- offline.html из дизайн-кода как fallback.

DoD web/admin: lint+typecheck+test+build обоих. Тесты: турнирный composable/страница (мок), admin создание турнира (мутация). PWA: build генерит SW, manifest валиден.
