import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from api.config import get_settings

_REQUIRED_TABLES = [
    "champions",
    "items",
    "traits",
    "augments",
    "champion_traits",
    "aliases",
    "item_stats",
    "users",
    "conversations",
    "messages",
]

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT,
    last_login_at TEXT
);
"""

_CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    title TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    role TEXT,
    content TEXT,
    metadata_json TEXT,
    created_at TEXT
);
"""


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with WAL mode, row factory, and FK enforcement.

    Commits on clean exit, rolls back on exception, and always closes.
    """
    settings = get_settings()
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Ensure all required tables exist; create users/conversations/messages if missing."""
    with get_db() as conn:
        existing = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }

        missing = [t for t in _REQUIRED_TABLES if t not in existing]
        if missing:
            for table in ("users", "conversations", "messages"):
                if table in missing:
                    if table == "users":
                        conn.execute(_CREATE_USERS)
                    elif table == "conversations":
                        conn.execute(_CREATE_CONVERSATIONS)
                    elif table == "messages":
                        conn.execute(_CREATE_MESSAGES)

            still_missing = [
                t for t in missing if t not in ("users", "conversations", "messages")
            ]
            if still_missing:
                raise RuntimeError(
                    f"Required tables missing and cannot be auto-created: {still_missing}"
                )
