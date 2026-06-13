"""Импортирует все ORM-модели, чтобы они зарегистрировались в Base.metadata.

Используется Alembic (autogenerate/target_metadata) и тестовыми фикстурами.
"""

from __future__ import annotations

from src.admin import models as admin_models
from src.ai_review import models as ai_review_models
from src.auth import models as auth_models
from src.billing import models as billing_models
from src.core.db import Base
from src.daily import models as daily_models
from src.duels import models as duels_models
from src.topics import models as topics_models
from src.tournaments import models as tournaments_models
from src.users import models as users_models

__all__ = [
    "Base",
    "admin_models",
    "ai_review_models",
    "auth_models",
    "billing_models",
    "daily_models",
    "duels_models",
    "topics_models",
    "tournaments_models",
    "users_models",
]
