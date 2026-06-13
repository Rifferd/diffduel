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

## Гибрид «ссылка + код» (режим ON)

В письме — И кликабельная кнопка-ссылка, И 6-значный код. Два пути подтверждения:

1. **Код** (основной, надёжный, кросс-девайс): пользователь вводит код на устройстве, где регистрировался.
2. **Ссылка**: `https://DOMAIN/verify?token=<link_token>` открывает красивую страницу:
   - если открыта в ТОМ ЖЕ браузере, где регистрировались (совпал cookie `dd_verify_sid`) →
     подтверждаем + авто-логин + «Почта подтверждена» + кнопка «Войти» (на /app, уже залогинен);
   - если открыта на ДРУГОМ устройстве → подтверждаем email, показываем код и текст
     «введите этот код на устройстве, где вы регистрировались» (без логина здесь).

При регистрации (режим ON) сервер ставит cookie `dd_verify_sid` (httpOnly, TTL 30 мин, path=/),
связанную с записью верификации — она и различает «то же устройство / другое».

```
POST /auth/register   (режим ON) — дополнительно ставит cookie dd_verify_sid, шлёт письмо
POST /auth/verify-email {email, code}
  → 200 {access_token, token_type, expires_in} + refresh-cookie   (код-путь, авто-логин)
  → 400 code=invalid_code | code_expired | too_many_attempts
  rate limit: 10/мин/IP
POST /auth/verify-link {token}              # вызывает SPA-страница /verify
  → 200 {logged_in: true, access_token, token_type, expires_in} + refresh-cookie   (то же устройство)
  → 200 {logged_in: false, code: "NNNNNN"}   (другое устройство — показать код)
  → 400 code=invalid_token | token_expired
  rate limit: 20/мин/IP
POST /auth/resend-code {email}
  → 204 всегда (не раскрывать существование/статус email); перегенерит код И link_token
  rate limit: 3/15мин/IP + не чаще 1/60с на email
```

`POST /auth/login`: если `email_verified=false` → 403 `{code: "email_not_verified"}`
(SPA ведёт на страницу кода с предложением переслать). В режиме OFF все verified, не срабатывает.

## Код и токен-ссылки

- Код: 6 цифр, криптослучайный (`secrets.randbelow`). TTL 15 мин. Макс 5 попыток → инвалидация (нужен resend).
- link_token: `secrets.token_urlsafe(32)`. Тот же TTL. В БД — только sha256-хэши кода и токена.
- `dd_verify_sid`: случайный id, в БД хранится его хэш; cookie сверяется по хэшу.
- Хранение: таблица `email_verifications(user_id pk → users, code_hash, link_token_hash, sid_hash,
  expires_at, attempts int default 0, sent_at)`. Миграция 0004 + колонка
  `users.email_verified boolean not null default false` (бэкофилл существующих → `true`).

## Отправка письма (`src/core/email.py`)

Бэкенды по `EMAIL_BACKEND`:
- `console` (dev/test): логирует код+ссылку через structlog — тестирование флоу без SMTP.
- `smtp` (prod): aiosmtplib.

Env: `EMAIL_BACKEND=console|smtp`, `SMTP_HOST=smtp.beget.com`, `SMTP_PORT=465`, `SMTP_SSL=true`
(Beget: 465 SSL; если 25 заблокирован — альтернатива 2525 STARTTLS, тогда SMTP_SSL=false SMTP_STARTTLS=true),
`SMTP_USER=verification@diffduel.com`, `SMTP_PASSWORD` (только в .env.prod, не в репо),
`SMTP_FROM=DiffDuel <verification@diffduel.com>`, `PUBLIC_WEB_URL=https://diffduel.com` (для ссылки в письме).

**Письмо обязательно:**
- Тема на русском, корректно MIME-кодирована (использовать `email.message.EmailMessage` —
  он сам кодирует заголовок в `=?UTF-8?B?...?=`; НЕ собирать заголовки строками вручную, иначе «звёздочки»).
- Красивый HTML (брендинг DiffDuel: VS-сплит/цвета токенов, моноширинный код крупно, кнопка «Подтвердить почту»
  со ссылкой) + текстовая альтернатива (multipart/alternative). Внизу — код текстом на случай, если кнопка не нажимается.
- From `DiffDuel <verification@diffduel.com>`.

Отправка из register/resend — таймаут 10с; провал SMTP → 503 (код в БД уже есть, доступен resend), залогировать.

## SPA-страницы

- `/verify` (читает `?token=` из письма): POST /auth/verify-link → если `logged_in` → красивая
  «Почта подтверждена» + кнопка «Перейти» (/app); иначе → «Подтверждено! Введите этот код на
  устройстве регистрации: NNNNNN».
- Страница ввода кода после register (режим ON): поле на 6 цифр → POST /auth/verify-email →
  /app. Кнопка «Выслать код повторно» (resend). На login-403 `email_not_verified` — сюда же.

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
