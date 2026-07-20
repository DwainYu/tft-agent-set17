"""Shared pytest fixtures for all test suites."""
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop shared across the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Temporary database
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(tmp_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection backed by a throwaway temp database.

    The schema mirrors api.database.init_db() so tests can run without the
    real data tables being populated.
    """
    db_file = tmp_path / "test_tft.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Create core tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS champions (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            cost INTEGER,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS traits (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS augments (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            tier TEXT,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS champion_traits (
            champion_id TEXT REFERENCES champions(id),
            trait_id TEXT REFERENCES traits(id)
        );
        CREATE TABLE IF NOT EXISTS aliases (
            alias TEXT PRIMARY KEY,
            champion_id TEXT REFERENCES champions(id)
        );
        CREATE TABLE IF NOT EXISTS item_stats (
            item_id TEXT REFERENCES items(id),
            stat_name TEXT,
            stat_value REAL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT,
            last_login_at TEXT
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER REFERENCES conversations(id),
            role TEXT,
            content TEXT,
            metadata_json TEXT,
            created_at TEXT
        );
    """)
    conn.commit()

    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def api_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx.AsyncClient wired to the FastAPI app.

    Copies the real tft.db to a temp location so integration tests have full
    schema and seed data. Overrides JWT_SECRET for testing.
    """
    import shutil

    # Copy the real DB to a temp location for isolation
    real_db = Path("data/tft.db")
    test_db = tmp_path / "test_api.db"
    if real_db.exists():
        shutil.copy2(str(real_db), str(test_db))
    monkeypatch.setenv("DB_PATH", str(test_db))
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-tests")
    monkeypatch.setenv("DEBUG", "true")

    # Clear lru_cache so settings are rebuilt with the test env vars
    from api.config import get_settings
    get_settings.cache_clear()

    from api.main import app  # noqa: WPS433 (import here after env override)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def auth_headers(api_client: AsyncClient) -> dict[str, str]:
    """Register a test user, log in, and return ``Authorization`` headers."""
    phone = "13900000001"
    password = "TestPass123!"

    # Register
    await api_client.post(
        "/auth/register",
        json={"phone": phone, "password": password},
    )

    # Login
    resp = await api_client.post(
        "/auth/login",
        json={"phone": phone, "password": password},
    )
    data = resp.json()
    token = data.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_question() -> list[str]:
    """Return a list of representative question strings for testing."""
    return [
        "盖伦最强出装推荐",
        "金克丝配什么装备好",
        "搜索暴风大剑",
        "阿狸和辛德拉的羁绊是什么",
        "当前版本强势阵容推荐",
    ]
