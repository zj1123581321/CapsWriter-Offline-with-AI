# coding: utf-8
"""Backend state tracking for the ASR proxy."""

from __future__ import annotations

import time
from dataclasses import dataclass

from core.logger import get_logger


logger = get_logger("proxy")


@dataclass
class BackendState:
    """Mutable health and load counters for one backend ASR server."""

    id: str
    url: str
    weight: float = 1.0
    active_tasks: int = 0
    healthy: bool = True
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    last_result_time: float = 0.0
    avg_latency: float = 0.0
    latency_samples: int = 0
    max_connect_failures: int = 3

    def acquire_task(self) -> None:
        self.active_tasks += 1

    def release_task(self) -> None:
        self.active_tasks = max(0, self.active_tasks - 1)

    def record_connect_success(self) -> None:
        self.consecutive_failures = 0
        self.healthy = True

    def record_connect_failure(self, refresh_cooldown: bool = True) -> None:
        self.consecutive_failures += 1
        if refresh_cooldown:
            self.last_failure_time = time.time()
        if self.consecutive_failures >= self.max_connect_failures:
            self.healthy = False

    def record_result(self) -> None:
        self.last_result_time = time.time()

    def record_processing_latency(self, latency: float) -> bool:
        if latency < 0 or latency > 60:
            logger.warning(
                "异常 processing_latency 已排除: backend=%s latency=%.3f",
                self.id,
                latency,
            )
            return False

        if self.latency_samples == 0:
            self.avg_latency = latency
        else:
            self.avg_latency = (self.avg_latency * 0.8) + (latency * 0.2)
        self.latency_samples += 1
        return True
