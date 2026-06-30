# coding: utf-8

from core.proxy.backend import BackendState


def test_backend_active_tasks_increment_and_decrement():
    backend = BackendState(id="backend-0", url="ws://localhost:6016")

    backend.acquire_task()
    backend.acquire_task()
    assert backend.active_tasks == 2

    backend.release_task()
    backend.release_task()
    backend.release_task()
    assert backend.active_tasks == 0


def test_backend_connect_failures_mark_unhealthy_after_threshold():
    backend = BackendState(
        id="backend-0",
        url="ws://localhost:6016",
        max_connect_failures=3,
    )

    backend.record_connect_failure()
    backend.record_connect_failure()
    assert backend.healthy is True
    assert backend.consecutive_failures == 2

    backend.record_connect_failure()
    assert backend.healthy is False
    assert backend.consecutive_failures == 3


def test_backend_success_resets_failures_and_health():
    backend = BackendState(
        id="backend-0",
        url="ws://localhost:6016",
        max_connect_failures=2,
    )
    backend.record_connect_failure()
    backend.record_connect_failure()
    assert backend.healthy is False

    backend.record_connect_success()

    assert backend.healthy is True
    assert backend.consecutive_failures == 0
