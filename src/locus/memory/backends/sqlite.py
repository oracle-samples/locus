# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""SQLite checkpoint backend - 100% Pydantic."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


_SAFE_SQL_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


class SQLiteConfig(BaseModel):
    """Configuration for SQLite backend."""

    path: str = "locus_checkpoints.db"
    table_name: str = "checkpoints"

    def model_post_init(self, __context: Any) -> None:
        """Validate table name to prevent SQL injection."""
        if not _SAFE_SQL_IDENTIFIER.match(self.table_name):
            msg = (
                f"Invalid table_name: {self.table_name!r}. "
                "Must start with a letter or underscore and contain only "
                "alphanumeric characters and underscores (max 63 chars)."
            )
            raise ValueError(msg)


class SQLiteBackend(BaseModel):
    """
    SQLite checkpoint backend.

    Persistent local storage using async SQLite.

    Example:
        >>> backend = SQLiteBackend(path="./checkpoints.db")
        >>> await backend.save("thread_1", state.model_dump())
        >>> data = await backend.load("thread_1")
    """

    config: SQLiteConfig = Field(default_factory=SQLiteConfig)
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, path: str = "locus_checkpoints.db", **kwargs: Any) -> None:
        config = SQLiteConfig(path=path, **kwargs)
        super().__init__(config=config)

    async def _ensure_table(self) -> None:
        """Create table if not exists."""
        if self._initialized:
            return

        try:
            import aiosqlite
        except ImportError as e:
            raise ImportError(
                "SQLiteBackend requires the 'aiosqlite' package. "
                "Install with: pip install aiosqlite"
            ) from e

        path = Path(self.config.path)
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(str(path)) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.config.table_name} (
                    thread_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.commit()

        self._initialized = True

    async def save(self, thread_id: str, data: dict[str, Any]) -> None:
        """Save checkpoint to SQLite."""
        import aiosqlite

        await self._ensure_table()

        now = datetime.now(UTC).isoformat()
        json_data = json.dumps(data)

        async with aiosqlite.connect(self.config.path) as db:
            await db.execute(
                f"""
                INSERT INTO {self.config.table_name} (thread_id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (thread_id, json_data, now, now),
            )
            await db.commit()

    async def load(self, thread_id: str) -> dict[str, Any] | None:
        """Load checkpoint from SQLite."""
        import aiosqlite

        await self._ensure_table()

        async with (
            aiosqlite.connect(self.config.path) as db,
            db.execute(
                f"SELECT data FROM {self.config.table_name} WHERE thread_id = ?",
                (thread_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()

        if row is None:
            return None

        data: dict[str, Any] = json.loads(row[0])
        return data

    async def delete(self, thread_id: str) -> bool:
        """Delete checkpoint from SQLite."""
        import aiosqlite

        await self._ensure_table()

        async with aiosqlite.connect(self.config.path) as db:
            cursor = await db.execute(
                f"DELETE FROM {self.config.table_name} WHERE thread_id = ?",
                (thread_id,),
            )
            await db.commit()
            deleted: bool = cursor.rowcount > 0
            return deleted

    async def exists(self, thread_id: str) -> bool:
        """Check if checkpoint exists."""
        import aiosqlite

        await self._ensure_table()

        async with (
            aiosqlite.connect(self.config.path) as db,
            db.execute(
                f"SELECT 1 FROM {self.config.table_name} WHERE thread_id = ?",
                (thread_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()

        return row is not None

    async def list_threads(
        self,
        limit: int = 100,
        offset: int = 0,
        pattern: str = "%",
    ) -> list[str]:
        """List all thread IDs matching pattern."""
        import aiosqlite

        await self._ensure_table()

        async with (
            aiosqlite.connect(self.config.path) as db,
            db.execute(
                f"""SELECT thread_id FROM {self.config.table_name}
                WHERE thread_id LIKE ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?""",
                (pattern, limit, offset),
            ) as cursor,
        ):
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def get_metadata(self, thread_id: str) -> dict[str, Any] | None:
        """Get checkpoint metadata (created_at, updated_at)."""
        import aiosqlite

        await self._ensure_table()

        async with (
            aiosqlite.connect(self.config.path) as db,
            db.execute(
                f"SELECT created_at, updated_at FROM {self.config.table_name} WHERE thread_id = ?",
                (thread_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()

        if row is None:
            return None

        return {"created_at": row[0], "updated_at": row[1]}
