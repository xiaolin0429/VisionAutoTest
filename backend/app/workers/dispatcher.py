from __future__ import annotations

from typing import Protocol

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.workers.execution import process_test_run


class TestRunDispatcher(Protocol):
    def dispatch_test_run(self, test_run_id: int) -> None: ...


class InProcessTestRunDispatcher:
    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def dispatch_test_run(self, test_run_id: int) -> None:
        self._background_tasks.add_task(process_test_run, test_run_id)


class DeferredTestRunDispatcher:
    def dispatch_test_run(self, test_run_id: int) -> None:
        _ = test_run_id


def get_test_run_dispatcher(background_tasks: BackgroundTasks) -> TestRunDispatcher:
    settings = get_settings()
    if settings.execution_dispatch_backend == "deferred":
        return DeferredTestRunDispatcher()
    return InProcessTestRunDispatcher(background_tasks)
