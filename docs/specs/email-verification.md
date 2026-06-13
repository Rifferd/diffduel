# Спека: подтверждение email при регистрации

> Новое требование (вне исходного ТЗ). Гейтит регистрацию кодом из письма.
> Источник правды контракта между apps/api и apps/web.

## Поведение и фиче-флаг

Настройка `EMAIL_VERIFICATION_ENABLED` (env, bool). Позволяет выкатить код, не ломая
живую регистрацию до настройки SMTP.

- **OFF** (временно, пока нет SMTP): `POST /auth/register` создаёт пользователя сразу
  `email_verified=true`, выдаёт токены (авто-логин). Письма не шлются. Это и есть фикс
  текущего бага «регистрация не проходит».
- **ON** (после настройки SMTP): регистрация создаёт `email_verified=false`, шлёт 6-значный
  код на email, токены НЕ выдаёт. Логин запрещён до подтверждения.

## Контракт register (единый для обоих режимов)

`POST /auth/register` {email, username, password} →
- 201 `{"verification_required": false, "access_token": str, "token_type": "bearer", "expires_in": int}` + refresh-cookie — режим OFF (авто-логин).
- 201 `{"verification_required": true}` — режим ON (код отправлен).

SPA ветвится по `verification_required`: false → setSession + /app; true → страница ввода кода.

## Новые эндпоинты (режим ON)

```
POST /auth/verify-email {email, code}
  → 200 {access_token, token_type, expires_in} + refresh-cookie   (авто-логин после верификации)
  → 400 code=invalid_code | code_expired | too_many_attempts
  rate limit: 10/мин/IP
POST /auth/resend-code {email}
  → 204 всегда (не раскрывать существование/статус email)
  rate limit: 3/15мин/IP + не чаще 1/60с на email
```

`POST /auth/login`: если `email_verified=false` → 403 `{code: "email_not_verified"}`
(SPA ведёт на страницу кода с предложением переслать). В режиме OFF все verified, не срабатывает.

## Код подтверждения

6 цифр (000000–999999), криптослучайный (`secrets.randbelow`). В БД — только sha256-хэш.
TTL 15 минут. Максимум 5 попыток ввода, потом код инвалидируется (нужен resend).
Хранение: таблица `email_verifications(user_id pk → users, code_hash, expires_at, attempts int default 0, sent_at)`.
Миграция 0004 + колонка `users.email_verified boolean not null default false`
(существующим строкам бэкофилл `true`, чтобы не залочить уже заведённых).

## Отправка письма (`src/core/email.py`)

Бэкенды по `EMAIL_BACKEND`:
- `console` (dev/test): логирует код через structlog (письмо не уходит) — позволяет тестировать флоу без SMTP.
- `smtp` (prod): aiosmtplib, STARTTLS, креды из env.

Env: `EMAIL_BACKEND=console|smtp`, `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM=DiffDuel <verification@diffduel.com>`, `SMTP_STARTTLS=true`.
Письмо: тема «DiffDuel — код подтверждения», тело с кодом (текст + простой HTML, бренд diffduel.com).
Отправка из эндпоинта register/resend — best-effort с таймаутом 10с; провал SMTP логируется,
но в режиме ON регистрация без отправленного кода бессмысленна → при ошибке SMTP вернуть 503
(код в БД уже есть, пользователь может нажать resend).

## Безопасность

- verify/resend/register — rate limited (как выше), Lua sliding window (уже есть).
- Ответы resend не различают существование email. verify не различает «нет кода»/«нет юзера» (общий invalid_code).
- Код только хэш в БД; сравнение по хэшу. attempts инкрементируется атомарно.
- В режиме ON логин забаненного/неподтверждённого не выдаёт токены.

## Тесты (console-бэкенд, без реального SMTP)

API: register(OFF)→токены; register(ON)→verification_required + код в БД + «письмо» залогировано;
verify верный→verified+токены; неверный→attempts++ и 400; >5 попыток→инвалидирован; expired→400;
login до verify→403; resend генерит новый код и старый перестаёт работать; rate limits.
SPA: register(ON)→редирект на verify; verify успех→/app; login 403 email_not_verified→verify-страница.
