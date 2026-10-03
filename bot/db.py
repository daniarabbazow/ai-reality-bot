import logging
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "bot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  session_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  level INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  user_answer TEXT NOT NULL,
  is_correct INTEGER NOT NULL,
  response_time_sec REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS photo_cache (
  item_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
    logger.info("База данных готова: %s", DB_PATH)


async def log_answer(
    *,
    user_id: int,
    session_id: str,
    category_id: str,
    level: int,
    item_id: str,
    user_answer: str,
    is_correct: bool,
    response_time_sec: Optional[float],
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO answers
                (user_id, session_id, category_id, level, item_id,
                 user_answer, is_correct, response_time_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id,
                category_id,
                level,
                item_id,
                user_answer,
                int(is_correct),
                response_time_sec,
            ),
        )
        await db.commit()


async def get_cached_file_id(item_id: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM photo_cache WHERE item_id = ?", (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_user_stats(user_id: int) -> dict[str, tuple[int, int]]:
    """Returns {category_id: (total_answers, correct_answers)} for the user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT category_id, COUNT(*), SUM(is_correct)
            FROM answers
            WHERE user_id = ?
            GROUP BY category_id
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: (row[1], row[2] or 0) for row in rows}


async def cache_file_id(item_id: str, file_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO photo_cache (item_id, file_id) VALUES (?, ?)",
            (item_id, file_id),
        )
        await db.commit()
