from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.schemas import TaskCreate, TaskItem, TaskStatus, TaskUpdate
from app.storage.tasks import create_task, list_tasks, update_task


router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskItem])
def get_tasks(status: TaskStatus | None = Query(default=None)):
    return list_tasks(get_settings(), status=status)


@router.post("/tasks", response_model=TaskItem, status_code=201)
def post_task(payload: TaskCreate):
    return create_task(get_settings(), payload)


@router.patch("/tasks/{task_id}", response_model=TaskItem)
def patch_task(task_id: str, payload: TaskUpdate):
    task = update_task(get_settings(), task_id, payload)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task
