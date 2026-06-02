import json
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.storage.db import connect


ALLOWED_SETTING_KEYS = {
    "llm_base_url",
    "llm_model",
    "enable_thinking",
    "default_max_tokens",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_setting_overrides(settings: Settings) -> dict[str, Any]:
    with connect(settings) as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key IN ({})".format(
                ",".join("?" for _ in ALLOWED_SETTING_KEYS)
            ),
            tuple(ALLOWED_SETTING_KEYS),
        ).fetchall()

    overrides: dict[str, Any] = {}
    for row in rows:
        try:
            overrides[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            continue
    return overrides


def save_setting_overrides(settings: Settings, updates: dict[str, Any]) -> None:
    timestamp = _now()
    allowed_updates = {
        key: value for key, value in updates.items() if key in ALLOWED_SETTING_KEYS
    }
    if not allowed_updates:
        return

    with connect(settings) as conn:
        conn.executemany(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            [
                (key, json.dumps(value, ensure_ascii=False), timestamp)
                for key, value in allowed_updates.items()
            ],
        )
        conn.commit()
