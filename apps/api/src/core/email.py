"""Отправка письма подтверждения email.

Два бэкенда (EMAIL_BACKEND):
- console (dev/test): логирует код+ссылку structlog'ом, письмо не уходит.
- smtp (prod): aiosmtplib, SSL или STARTTLS, таймаут 10с.

Заголовки письма НЕ собираются строками — используем email.message.EmailMessage,
он сам MIME-кодирует русскую тему (=?UTF-8?B?...?=). Тело — multipart/alternative
(text + брендированный HTML).
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from src.core.config import get_settings
from src.core.errors import ServiceUnavailableError
from src.core.logging import get_logger

logger = get_logger("email")

_SUBJECT = "DiffDuel — подтверждение почты"
_SMTP_TIMEOUT_S = 10.0

# Брендинг из packages/ui-tokens/tokens.css.
_ARENA = "#161B22"
_ARENA_2 = "#1F2630"
_PLUS = "#1F9D55"
_MINUS = "#E5484D"
_ARENA_INK = "#E6EDF3"
_ARENA_SOFT = "#8B98A9"


def _text_body(code: str, link_url: str) -> str:
    return (
        "Подтверждение почты DiffDuel\n\n"
        "Подтвердите адрес, чтобы завершить регистрацию.\n\n"
        f"Ваш код: {code}\n\n"
        "Или откройте ссылку (на том же устройстве произойдёт вход автоматически):\n"
        f"{link_url}\n\n"
        "Код действует 15 минут. Если вы не регистрировались — просто игнорируйте письмо.\n"
    )


def _html_body(code: str, link_url: str) -> str:
    return f"""\
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{_ARENA};font-family:Inter,system-ui,Segoe UI,Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_ARENA};padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:480px;background:{_ARENA_2};border-radius:16px;overflow:hidden;">
        <tr><td style="padding:28px 32px 8px;">
          <div style="font-size:22px;font-weight:800;color:{_ARENA_INK};letter-spacing:.5px;">
            Diff<span style="color:{_PLUS}">Duel</span>
          </div>
        </td></tr>
        <tr><td style="padding:0 32px;">
          <div style="height:3px;border-radius:99px;
               background:linear-gradient(90deg,{_PLUS} 0%,{_PLUS} 50%,{_MINUS} 50%,{_MINUS} 100%);"></div>
        </td></tr>
        <tr><td style="padding:24px 32px 8px;">
          <h1 style="margin:0 0 8px;font-size:20px;color:{_ARENA_INK};">Подтвердите почту</h1>
          <p style="margin:0;font-size:14px;line-height:1.5;color:{_ARENA_SOFT};">
            Введите код на устройстве регистрации или нажмите кнопку ниже.
          </p>
        </td></tr>
        <tr><td align="center" style="padding:24px 32px 8px;">
          <div style="font-family:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;
               font-size:40px;font-weight:700;letter-spacing:10px;color:{_PLUS};
               background:{_ARENA};border-radius:12px;padding:18px 8px;">{code}</div>
        </td></tr>
        <tr><td align="center" style="padding:16px 32px 8px;">
          <a href="{link_url}"
             style="display:inline-block;background:{_PLUS};color:#ffffff;text-decoration:none;
             font-weight:700;font-size:15px;padding:14px 28px;border-radius:99px;">
            Подтвердить почту
          </a>
        </td></tr>
        <tr><td style="padding:16px 32px 28px;">
          <p style="margin:0;font-size:12px;line-height:1.6;color:{_ARENA_SOFT};">
            Код действует 15 минут. Если кнопка не работает, скопируйте ссылку:<br>
            <span style="color:{_ARENA_INK};word-break:break-all;">{link_url}</span><br><br>
            Код текстом: <b style="color:{_ARENA_INK};">{code}</b><br><br>
            Если вы не регистрировались в DiffDuel — просто игнорируйте это письмо.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _build_message(to: str, code: str, link_url: str) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    # EmailMessage сам кодирует кириллицу в =?UTF-8?...?= по policy.default;
    # пробелы сохраняются при декодировании стандартным RFC2047-парсером
    # (почтовые клиенты показывают тему корректно).
    message["Subject"] = _SUBJECT
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(_text_body(code, link_url))
    message.add_alternative(_html_body(code, link_url), subtype="html")
    return message


async def send_verification_email(to: str, code: str, link_url: str) -> None:
    """Отправляет письмо подтверждения. SMTP-провал → ServiceUnavailableError (503)."""
    settings = get_settings()
    if settings.email_backend == "console":
        # Письмо не уходит — логируем код+ссылку для ручной проверки флоу.
        logger.info("verification_email_console", to=to, code=code, link_url=link_url)
        return

    message = _build_message(to, code, link_url)
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_ssl,
            start_tls=settings.smtp_starttls or None,
            timeout=_SMTP_TIMEOUT_S,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        # Код уже в БД — пользователь сможет запросить resend.
        logger.error("verification_email_smtp_failed", to=to, error=str(exc))
        raise ServiceUnavailableError(
            "Не удалось отправить письмо, попробуйте позже",
            code="email_send_failed",
        ) from exc
    logger.info("verification_email_sent", to=to)
