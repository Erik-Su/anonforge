from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models.user  # noqa: F401 — 注册 SQLModel metadata
from app.core.database import get_session
from app.main import create_app
from app.models.user import User
from app.utils.string_tools import hash_password
from app.utils.time_tools import utc_now


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(engine: AsyncEngine) -> AsyncGenerator[httpx.AsyncClient, None]:
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with maker() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = override_get_session

    transport = httpx.ASGITransport(app=application)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def saved_user(db_session: AsyncSession) -> User:
    user = User(
        username="testuser",
        password_hash=hash_password("password123"),
        email="testuser@example.com",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
