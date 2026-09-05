import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    meta: dict = field(default_factory=dict)

    def cancel(self):
        self.cancel_event.set()
        self.status = TaskStatus.CANCELLED

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, fn: Callable, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        task = Task(id=task_id)

        with self._lock:
            self._tasks[task_id] = task

        thread = threading.Thread(
            target=self._run, args=(task, fn, args, kwargs), daemon=True
        )
        thread.start()
        return task_id

    def _run(self, task: Task, fn: Callable, args, kwargs):
        task.status = TaskStatus.RUNNING
        try:
            result = fn(task, *args, **kwargs)
            if not task.is_cancelled():
                task.result = result
                task.status = TaskStatus.COMPLETED
        except Exception as e:
            if not task.is_cancelled():
                task.error = str(e)
                task.status = TaskStatus.FAILED

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())


task_manager = TaskManager()
