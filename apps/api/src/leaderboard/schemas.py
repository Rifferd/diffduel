"""Pydantic-схемы лидербордов (публичные — без чувствительных полей)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    """Одна строка лидерборда."""

    rank: int
    user_id: uuid.UUID
    username: str
    avatar_url: str | None
    elo: int


class MyLeaderboardPosition(BaseModel):
    """GET /leaderboard/me — моя позиция и соседи ±2 (rank=null если меня нет)."""

    rank: int | None
    entries: list[LeaderboardEntry]
