"""Pydantic-схемы домена topics."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class TopicPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
