# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for SQLite backend."""

import tempfile
from pathlib import Path

import pytest


class TestSQLiteConfig:
    """Tests for SQLiteConfig."""

    def test_default_config(self):
        """Test default configuration."""
        from locus.memory.backends.sqlite import SQLiteConfig

        config = SQLiteConfig()
        assert config.path == "locus_checkpoints.db"
        assert config.table_name == "checkpoints"

    def test_custom_config(self):
        """Test custom configuration."""
        from locus.memory.backends.sqlite import SQLiteConfig

        config = SQLiteConfig(path="/custom/path.db", table_name="my_table")
        assert config.path == "/custom/path.db"
        assert config.table_name == "my_table"


class TestSQLiteBackend:
    """Tests for SQLiteBackend."""

    def test_create_backend_default(self):
        """Test creating backend with defaults."""
        from locus.memory.backends.sqlite import SQLiteBackend

        backend = SQLiteBackend()
        assert backend.config.path == "locus_checkpoints.db"

    def test_create_backend_custom_path(self):
        """Test creating backend with custom path."""
        from locus.memory.backends.sqlite import SQLiteBackend

        backend = SQLiteBackend(path="/custom/db.sqlite")
        assert backend.config.path == "/custom/db.sqlite"

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test saving and loading data."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            test_data = {"key": "value", "number": 42}
            await backend.save("thread1", test_data)

            loaded = await backend.load("thread1")
            assert loaded == test_data

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading nonexistent thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            result = await backend.load("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Test deleting existing thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("thread1", {"data": "test"})
            result = await backend.delete("thread1")

            assert result is True
            assert await backend.load("thread1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test deleting nonexistent thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            # Ensure table exists
            await backend.save("other", {"data": "test"})

            result = await backend.delete("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test exists returns True for existing thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("thread1", {"data": "test"})
            result = await backend.exists("thread1")

            assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test exists returns False for nonexistent thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            # Ensure table exists
            await backend.save("other", {"data": "test"})

            result = await backend.exists("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_list_threads(self):
        """Test listing threads."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("thread1", {"data": "1"})
            await backend.save("thread2", {"data": "2"})
            await backend.save("thread3", {"data": "3"})

            threads = await backend.list_threads()

            assert len(threads) == 3
            assert "thread1" in threads
            assert "thread2" in threads
            assert "thread3" in threads

    @pytest.mark.asyncio
    async def test_list_threads_with_pattern(self):
        """Test listing threads with pattern."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("user_1", {"data": "1"})
            await backend.save("user_2", {"data": "2"})
            await backend.save("other", {"data": "3"})

            threads = await backend.list_threads(pattern="user_%")

            assert len(threads) == 2
            assert "user_1" in threads
            assert "user_2" in threads

    @pytest.mark.asyncio
    async def test_list_threads_with_limit(self):
        """Test listing threads with limit."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            for i in range(10):
                await backend.save(f"thread{i}", {"data": str(i)})

            threads = await backend.list_threads(limit=5)

            assert len(threads) == 5

    @pytest.mark.asyncio
    async def test_get_metadata(self):
        """Test getting thread metadata."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("thread1", {"data": "test"})

            metadata = await backend.get_metadata("thread1")

            assert metadata is not None
            assert "created_at" in metadata
            assert "updated_at" in metadata

    @pytest.mark.asyncio
    async def test_get_metadata_nonexistent(self):
        """Test getting metadata for nonexistent thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            # Ensure table exists
            await backend.save("other", {"data": "test"})

            metadata = await backend.get_metadata("nonexistent")
            assert metadata is None

    @pytest.mark.asyncio
    async def test_update_existing_thread(self):
        """Test updating existing thread."""
        from locus.memory.backends.sqlite import SQLiteBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            backend = SQLiteBackend(path=db_path)

            await backend.save("thread1", {"version": 1})
            await backend.save("thread1", {"version": 2})

            loaded = await backend.load("thread1")
            assert loaded == {"version": 2}
