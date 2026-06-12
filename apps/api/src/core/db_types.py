"""Общие колоночные хелперы и PG-типы (citext, uuid pk, timestamps)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import mapped_column

# uuid PK с server-side генерацией через gen_random_uuid().
uuid_pk = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
]

# citext — регистронезависимые строки (email, username).
citext = Annotated[str, mapped_column(CITEXT)]

# timestamptz с server-side now().
timestamptz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
timestamptz_now = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=text("now()")),
]
