"""
Pytest configuration: isolate the database and provide a TestClient fixture.

The real ``server.core.database`` engine is replaced with one pointing at a
temp file so tests never touch ``./data/novels.db``. Tables are cleared
before each test for full isolation.
"""

import asyncio
import os
import shutil
import tempfile

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine


# --- Create an isolated test DB before importing the app -------------------

_tmpdir = tempfile.mkdtemp(prefix="novel_test_")
TEST_DB_PATH = os.path.join(_tmpdir, "test.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# Patch settings.database_url (used by the app for display only at this point)
from server.core import config as _config  # noqa: E402
_config.settings.database_url = TEST_DB_URL

# Replace the module-level engine + session maker BEFORE the app imports them.
import server.core.database as _db_mod  # noqa: E402

test_engine = create_async_engine(TEST_DB_URL, echo=False)
_db_mod.engine = test_engine
_db_mod.async_session_maker = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

# Now safe to import the app (it will pick up the patched engine via the
# module globals referenced inside get_db / init_db).
from server.core.database import Base, get_db, init_db  # noqa: E402
from server.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# Ensure tables exist for the whole session. Using asyncio.run here because
# pytest has not started an event loop yet.
asyncio.run(init_db())


@pytest.fixture()
def client():
    """Yield a FastAPI TestClient. Tables are truncated between tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_tables():
    """Delete all rows before each test for isolation."""
    async def _truncate():
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
    asyncio.run(_truncate())


@pytest.fixture(scope="session", autouse=True)
def _cleanup(request):
    """Remove the temp DB dir after the test session ends."""
    request.addfinalizer(lambda: shutil.rmtree(_tmpdir, ignore_errors=True))
