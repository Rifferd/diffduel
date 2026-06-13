# Спека: AI-разбор ошибок дуэли (Релиз 2, часть C)

> Pro-функция. LLM-вызов в фоновом воркере (ТЗ §3.6, §7). Флаг + ключ.

## Контракт API (apps/api)

- Таблица `ai_reviews(duel_id uuid, user_id uuid, status enum('pending','done','failed'), content text null, error text null, created_at, updated_at, pk(duel_id, user_id))` — миграция **0006**.
- `POST /ai/review/{duel_id}` (auth + **require_pro** → 402): пользователь должен быть участником дуэли (иначе 403/404), дуэль finished. Идемпотентно: если запись уже pending/done — вернуть её. Иначе создать `pending`, спродюсировать Kafka-событие `ai.review.requested` (конверт {v,type,occurred_at,payload:{duel_id, user_id}}), вернуть `{status:"pending"}`.
- `GET /ai/review/{duel_id}` (auth, участник): `{status, content?, error?}`.
- Internal: `POST /internal/ai-reviews/{duel_id}/{user_id}` {status, content?, error?} — воркер пишет результат (X-Internal-Token). Идемпотентно.
- Эндпоинт собирает данные для разбора и кладёт в событие ИЛИ воркер запрашивает их через internal `GET /internal/duels/{id}/review-data?user_id=` → вопросы дуэли (body+эталон+объяснение), ответы игрока (selected, correct, time_ms). Реши: проще — воркер тянет через internal GET (эталоны не должны утекать публично, internal — ок).

## Воркер (apps/workers)

- Новый консьюмер топика `ai.review.requested` (aiokafka, group_id=ai-review, идемпотентность по (duel_id,user_id) — если запись уже done, пропуск).
- Вызов Claude через **официальный Anthropic Python SDK** (`anthropic`): модель из env `AI_REVIEW_MODEL` (дефолт `claude-opus-4-8`), `thinking={"type":"adaptive"}`, **стриминг** (`client.messages.stream(...)` → `get_final_message()`), `max_tokens` ~4000. Системный промпт: «ты — тренер по программированию, разбери ошибки игрока в дуэли по-русски, кратко и по делу, с конкретными советами по каждой проваленной задаче». Вход: темы, задачи (вопрос+варианты+верный ответ+объяснение), что выбрал игрок, время. **Обработать `stop_reason=="refusal"`** (записать failed с понятным текстом). Ошибки/таймаут SDK → status=failed.
- Флаг: если `ANTHROPIC_API_KEY` пуст → воркер пишет failed `{error:"AI-разбор временно недоступен"}` (или не обрабатывает и оставляет pending — реши; лучше failed с понятным текстом, чтобы UI не висел). Конфиг: ANTHROPIC_API_KEY, AI_REVIEW_MODEL.
- Записывает результат через internal API Core (как image-gen).

## Качество и DoD
ruff + ruff format --check + mypy strict + pytest (api и workers). alembic 0006 проходит. Тесты: эндпоинт 402 без Pro, 200 с Pro (pending), идемпотентность, internal-запись; воркер — рендер промпта из фикстуры, обработка refusal, отсутствие ключа → failed (Anthropic SDK замокать, реальных вызовов в тестах НЕ делать). Anthropic-вызовы за флагом, в CI без ключа зелено.
