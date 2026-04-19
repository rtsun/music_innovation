import asyncio
from typing import Any, Awaitable, Callable
from uuid import uuid4


TaskProgressUpdater = Callable[[str], None]
TaskHandler = Callable[[dict, TaskProgressUpdater], Awaitable[dict]]


class TaskQueueService:
    def __init__(self, worker_count: int = 2):
        self.worker_count = worker_count
        self.queue: asyncio.Queue[tuple[str, str, dict]] = asyncio.Queue()
        self.tasks: dict[str, dict[str, Any]] = {}
        self.handlers: dict[str, TaskHandler] = {}
        self.workers: list[asyncio.Task] = []

    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        self.handlers[task_type] = handler

    def submit(self, task_type: str, payload: dict) -> str:
        task_id = str(uuid4())
        self.tasks[task_id] = {
            "status": "queued",
            "type": task_type,
            "message": "排队中...",
        }
        self.queue.put_nowait((task_id, task_type, payload))
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.tasks[task_id]

    async def _worker(self) -> None:
        while True:
            task_id, task_type, payload = await self.queue.get()
            self.tasks[task_id]["status"] = "running"

            def _update_progress(msg: str) -> None:
                self.tasks[task_id]["message"] = msg

            try:
                handler = self.handlers.get(task_type)
                if not handler:
                    raise ValueError(f"No handler for task type: {task_type}")
                result = await handler(payload, _update_progress)
                self.tasks[task_id]["status"] = "succeeded"
                self.tasks[task_id]["result"] = result
            except Exception as exc:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = str(exc)
            finally:
                self.queue.task_done()

    async def start(self) -> None:
        for _ in range(self.worker_count):
            self.workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)