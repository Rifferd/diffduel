"""Идемпотентный сид топиков и задач из seeds/*.json.

Запуск: ``uv run python -m src.seeds`` (по DATABASE_URL из окружения).

Upsert по фиксированному uuid (INSERT ... ON CONFLICT DO UPDATE):
повторный прогон обновляет редактируемые поля, не плодя дубликатов.
Задачи сидятся сразу status=published, author_id NULL.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dispose_engine, get_sessionmaker
from src.core.logging import configure_logging, get_logger

logger = get_logger("seeds")

_SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
_TOPIC_SLUGS = ("sql", "javascript", "python")


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


async def _upsert_topics(
    session: AsyncSession, topics: list[dict[str, Any]]
) -> dict[str, uuid.UUID]:
    """Upsert тем по slug. Возвращает map slug -> id."""
    slug_to_id: dict[str, uuid.UUID] = {}
    for topic in topics:
        row = await session.execute(
            text(
                """
                INSERT INTO topics (id, slug, title, is_active)
                VALUES (gen_random_uuid(), :slug, :title, true)
                ON CONFLICT (slug) DO UPDATE
                    SET title = EXCLUDED.title, is_active = true
                RETURNING id
                """
            ),
            {"slug": topic["slug"], "title": topic["title"]},
        )
        slug_to_id[topic["slug"]] = row.scalar_one()
    return slug_to_id


async def _upsert_tasks(
    session: AsyncSession,
    tasks: list[dict[str, Any]],
    topic_id: uuid.UUID,
) -> None:
    """Upsert задач по фиксированному id. Сразу published, author_id NULL."""
    for task in tasks:
        await session.execute(
            text(
                """
                INSERT INTO tasks
                    (id, topic_id, difficulty, type, body, answer, explanation,
                     status, author_id, version)
                VALUES
                    (:id, :topic_id, :difficulty, 'quiz', :body, :answer, :explanation,
                     'published', NULL, 1)
                ON CONFLICT (id) DO UPDATE SET
                    topic_id = EXCLUDED.topic_id,
                    difficulty = EXCLUDED.difficulty,
                    type = EXCLUDED.type,
                    body = EXCLUDED.body,
                    answer = EXCLUDED.answer,
                    explanation = EXCLUDED.explanation,
                    status = 'published'
                """
            ),
            {
                "id": task["id"],
                "topic_id": topic_id,
                "difficulty": task["difficulty"],
                "body": json.dumps(task["body"], ensure_ascii=False),
                "answer": json.dumps(task["answer"], ensure_ascii=False),
                "explanation": task["explanation"],
            },
        )


async def seed() -> int:
    """Прогоняет сид. Возвращает число засеянных задач."""
    topics = _load_json(_SEEDS_DIR / "topics.json")
    sessionmaker = get_sessionmaker()
    total = 0
    async with sessionmaker() as session:
        slug_to_id = await _upsert_topics(session, topics)
        for slug in _TOPIC_SLUGS:
            tasks = _load_json(_SEEDS_DIR / f"tasks_{slug}.json")
            await _upsert_tasks(session, tasks, slug_to_id[slug])
            total += len(tasks)
        await session.commit()
    logger.info("seeds_applied", topics=len(topics), tasks=total)
    return total


async def _main() -> None:
    configure_logging()
    count = await seed()
    logger.info("seeds_done", tasks=count)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())
