# coding: utf-8
"""Backend state tracking for the ASR proxy."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BackendState:
    """Mutable health and load counters for one backend ASR server."""

    id: str
    url: str
    active_tasks: int = 0
    healthy: bool = True
    consecutive_failures: int = 0
    last_result_time: float = 0.0
    max_connect_failures: int = 3

    def acquire_task(self) -> None:
        self.active_tasks += 1

    def release_task(self) -> None:
        self.active_tasks = max(0, self.active_tasks - 1)

    def record_connect_success(self) -> None:
        self.consecutive_failures = 0
        self.healthy = True

    def record_connect_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_connect_failures:
            self.healthy = False

    def record_result(self) -> None:
        self.last_result_time = time.time()

