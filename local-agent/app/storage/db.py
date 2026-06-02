import sqlite3
from pathlib import Path

from app.config import Settings


def resolve_data_dir(settings: Settings) -> Path:
    data_dir = Path(settings.data_dir)
    if data_dir.is_absolute():
        return data_dir
    return Path.cwd() / data_dir


def database_path(settings: Settings) -> Path:
    return resolve_data_dir(settings) / "app.db"


def init_database(settings: Settings) -> None:
    path = database_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                priority TEXT NOT NULL DEFAULT 'medium',
                progress INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_status_updated_at
            ON tasks(status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def connect(settings: Settings) -> sqlite3.Connection:
    init_database(settings)
    conn = sqlite3.connect(database_path(settings))
    conn.row_factory = sqlite3.Row
    return conn
