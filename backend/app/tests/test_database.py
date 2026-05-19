from __future__ import annotations

import importlib
import inspect

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.tests.base import EnvTestBase

class TestDatabaseEngine(EnvTestBase):
    def test_database_engine_uses_sqlite_async_driver_in_unit_tests(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self.set_env(
            monkeypatch,
            {
                "DB_ENGINE": "sqlite",
                "DB_DRIVER": "aiosqlite",
                "DB_SQLITE_PATH": ":memory:",
            },
        )

        from app.core import config
        from app.core import database

        importlib.reload(config)
        database = importlib.reload(database)
        setattr(database, "_engine", None)
        setattr(database, "_session_maker", None)

        assert isinstance(database.get_engine(), AsyncEngine)
        assert database.get_engine().url.drivername == "sqlite+aiosqlite"
        assert database.get_session_maker().class_ is AsyncSession
        assert inspect.isasyncgenfunction(database.get_session)
