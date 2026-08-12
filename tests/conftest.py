import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.user import User


TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@db_test:5432/payments_test"
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(autouse=True)
async def prepare_database(
    test_engine,
    test_session_factory,
):
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        async with session.begin():
            session.add(
                User(
                    id=42,
                    email="roman@example.com",
                )
            )

    yield


@pytest_asyncio.fixture
async def client(test_session_factory):
    async def override_get_db_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    async with test_session_factory() as session:
        yield session