from __future__ import annotations

from fastapi import BackgroundTasks

from app.workers.execution import process_test_run


class InProcessTestRunDispatcher:
    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def dispatch_test_run(self, test_run_id: int) -> None:
        self._background_tasks.add_task(process_test_run, test_run_id)


def get_test_run_dispatcher(background_tasks: BackgroundTasks) -> InProcessTestRunDispatcher:
    return InProcessTestRunDispatcher(background_tasks)
