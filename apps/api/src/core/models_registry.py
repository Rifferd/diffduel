"""Импортирует все ORM-модели, чтобы они зарегистрировались в Base.metadata.

Используется Alembic (autogenerate/target_metadata) и тестовыми фикстурами.
"""

from __future__ import annotations

from src.auth import models as auth_models
from src.billing import models as billing_models
from src.core.db import Base
from src.duels import models as duels_models
from src.topics import models as topics_models
from src.tournaments import models as tournaments_models
from src.users import models as users_models

__all__ = [
    "Base",
    "auth_models",
    "billing_models",
    "duels_models",
    "topics_models",
    "tournaments_models",
    "users_models",
]
