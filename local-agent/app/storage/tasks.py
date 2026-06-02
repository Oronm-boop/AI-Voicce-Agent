from datetime import datetime, timezone
from sqlite3 import Row
from uuid import uuid4

from app.config import Settings
from app.models.schemas import TaskCreate, TaskItem, TaskStatus, TaskUpdate
from app.storage.db import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_task(row: Row) -> TaskItem:
    return TaskItem(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        progress=row["progress"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_tasks(settings: Settings, status: TaskStatus | None = None) -> list[TaskItem]:
    with connect(settings) as conn:
        if status:
            rows = conn.execute(
                """
                SELECT id, title, description, status, priority, progress, created_at, updated_at
                FROM tasks
                WHERE status = ?
                ORDER BY updated_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, title, description, status, priority, progress, created_at, updated_at
                FROM tasks
                ORDER BY
                    CASE status
                        WHEN 'in_progress' THEN 0
                        WHEN 'todo' THEN 1
                        WHEN 'done' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC
                """
            ).fetchall()

    return [_to_task(row) for row in rows]


def create_task(settings: Settings, payload: TaskCreate) -> TaskItem:
    timestamp = _now()
    task_id = str(uuid4())

    with connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                id, title, description, status, priority, progress, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload.title,
                payload.description,
                payload.status,
                payload.priority,
                payload.progress,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, title, description, status, priority, progress, created_at, updated_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

    return _to_task(row)


def create_tasks(settings: Settings, payloads: list[TaskCreate]) -> list[TaskItem]:
    return [create_task(settings, payload) for payload in payloads]


def update_task(
    settings: Settings,
    task_id: str,
    payload: TaskUpdate,
) -> TaskItem | None:
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        return None

    changes["updated_at"] = _now()
    assignments = ", ".join(f"{field} = ?" for field in changes)
    values = list(changes.values())

    with connect(settings) as conn:
        cursor = conn.execute(
            f"""
            UPDATE tasks
            SET {assignments}
            WHERE id = ?
            """,
            (*values, task_id),
        )
        if cursor.rowcount == 0:
            return None

        conn.commit()
        row = conn.execute(
            """
            SELECT id, title, description, status, priority, progress, created_at, updated_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

    return _to_task(row)
