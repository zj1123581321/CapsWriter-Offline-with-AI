# coding: utf-8

import json
import asyncio

import pytest

from core.proxy.backend import BackendState
from core.proxy.router import (
    NoHealthyBackendError,
    TaskRouter,
    is_final_recognition_message,
    parse_audio_message,
)


def make_audio(task_id: str, is_final: bool = False) -> str:
    return json.dumps(
        {
            "task_id": task_id,
            "source": "file",
            "data": "",
            "is_final": is_final,
            "time_start": 1.0,
        }
    )


def make_recognition(task_id: str, is_final: bool = False) -> str:
    return json.dumps(
        {
            "task_id": task_id,
            "is_final": is_final,
            "duration": 1.0,
            "time_start": 1.0,
            "time_submit": 2.0,
            "time_complete": 3.0,
            "text": "ok",
        }
    )


def test_parse_audio_message_extracts_task_id():
    msg = parse_audio_message(make_audio("task-a"))

    assert msg.task_id == "task-a"
    assert msg.source == "file"
    assert msg.is_final is False


def test_is_final_recognition_message_detects_final_result():
    assert is_final_recognition_message(make_recognition("task-a", True)) is True
    assert is_final_recognition_message(make_recognition("task-a", False)) is False


def test_router_selects_least_loaded_backend():
    backends = [
        BackendState(id="backend-0", url="ws://a"),
        BackendState(id="backend-1", url="ws://b"),
        BackendState(id="backend-2", url="ws://c"),
    ]
    backends[0].active_tasks = 2
    backends[1].active_tasks = 1
    backends[2].active_tasks = 3
    router = TaskRouter(backends)

    selected = router.select_backend()

    assert selected.id == "backend-1"


def test_router_selects_lowest_weighted_load_backend():
    backends = [
        BackendState(id="backend-0", url="ws://a", weight=1.0),
        BackendState(id="backend-1", url="ws://b", weight=4.0),
    ]
    backends[0].active_tasks = 1
    backends[1].active_tasks = 2
    router = TaskRouter(backends)

    selected = router.select_backend()

    assert selected.id == "backend-1"


def test_router_uses_latency_after_warmup():
    fast = BackendState(id="backend-fast", url="ws://a", weight=1.0)
    slow = BackendState(id="backend-slow", url="ws://b", weight=1.0)
    fast.active_tasks = slow.active_tasks = 1
    fast.avg_latency = 1.0
    slow.avg_latency = 4.0
    fast.latency_samples = slow.latency_samples = 4
    router = TaskRouter([slow, fast])

    selected = router.select_backend()

    assert selected.id == "backend-fast"


def test_router_ignores_latency_during_warmup():
    cold_fast = BackendState(id="backend-cold", url="ws://a", weight=1.0)
    warm_slow = BackendState(id="backend-warm", url="ws://b", weight=1.0)
    cold_fast.active_tasks = warm_slow.active_tasks = 1
    cold_fast.avg_latency = 0.5
    warm_slow.avg_latency = 4.0
    cold_fast.latency_samples = 2
    warm_slow.latency_samples = 4
    router = TaskRouter([cold_fast, warm_slow])

    selected = router.select_backend()

    assert selected.id == "backend-cold"


def test_router_tie_breaks_by_config_order():
    backends = [
        BackendState(id="backend-0", url="ws://a"),
        BackendState(id="backend-1", url="ws://b"),
    ]
    router = TaskRouter(backends)

    selected = router.select_backend()

    assert selected.id == "backend-0"


def test_router_recovers_unhealthy_backend_after_cooldown(monkeypatch):
    backend = BackendState(id="backend-0", url="ws://a", healthy=False)
    backend.consecutive_failures = 3
    backend.last_failure_time = 10.0
    monkeypatch.setattr("core.proxy.router.time.time", lambda: 75.0)
    router = TaskRouter([backend], cooldown_seconds=60)

    selected = router.select_backend()

    assert selected is backend
    assert backend.healthy is True
    assert backend.consecutive_failures == 0


def test_router_degrades_to_least_loaded_backend_when_all_in_cooldown(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "core.proxy.router.logger.warning",
        lambda message, *args, **kwargs: warnings.append(message % args),
    )
    backends = [
        BackendState(id="backend-0", url="ws://a", healthy=False),
        BackendState(id="backend-1", url="ws://b", healthy=False),
    ]
    backends[0].active_tasks = 2
    backends[1].active_tasks = 1
    router = TaskRouter(backends, cooldown_seconds=60)

    selected = router.select_backend()

    assert selected.id == "backend-1"
    assert any("全部后端 unhealthy" in message for message in warnings)


def test_router_rejects_when_no_backends_configured():
    router = TaskRouter([])

    with pytest.raises(NoHealthyBackendError):
        router.select_backend()


def test_router_logs_selected_score(monkeypatch):
    infos = []
    monkeypatch.setattr(
        "core.proxy.router.logger.info",
        lambda message, *args, **kwargs: infos.append(message % args),
    )
    backends = [
        BackendState(id="backend-0", url="ws://a", weight=2.0),
        BackendState(id="backend-1", url="ws://b", weight=1.0),
    ]
    router = TaskRouter(backends)

    router.select_backend()

    assert any("score=" in message for message in infos)


def test_router_keeps_task_affinity_for_existing_session():
    backends = [
        BackendState(id="backend-0", url="ws://a"),
        BackendState(id="backend-1", url="ws://b"),
    ]
    router = TaskRouter(backends)

    router.task_sessions["task-a"] = type(
        "FakeSession",
        (),
        {"backend": backends[1]},
    )()

    assert router.get_backend_for_task("task-a") is backends[1]


@pytest.mark.asyncio
async def test_router_reserves_backend_load_before_connect_completes():
    backends = [
        BackendState(id="backend-0", url="ws://a"),
        BackendState(id="backend-1", url="ws://b"),
    ]
    selected_urls = []
    connect_started = asyncio.Event()
    release_connect = asyncio.Event()

    class FakeBackendWebSocket:
        async def send(self, _raw_message):
            return None

        async def close(self):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(60)

    class FakeClientWebSocket:
        async def send(self, _raw_message):
            return None

        async def close(self, *args, **kwargs):
            return None

    async def delayed_connect(url):
        selected_urls.append(url)
        connect_started.set()
        await release_connect.wait()
        return FakeBackendWebSocket()

    router = TaskRouter(backends, connect_func=delayed_connect)

    first = asyncio.create_task(
        router.route_client_message(make_audio("task-a"), FakeClientWebSocket())
    )
    await connect_started.wait()
    second = asyncio.create_task(
        router.route_client_message(make_audio("task-b"), FakeClientWebSocket())
    )
    await asyncio.sleep(0)
    release_connect.set()
    await asyncio.gather(first, second)
    await router.close_all()

    assert selected_urls == ["ws://a", "ws://b"]


@pytest.mark.asyncio
async def test_backend_to_client_records_processing_latency_from_recognition():
    backend = BackendState(id="backend-0", url="ws://a")
    router = TaskRouter([backend])

    class FakeBackendWebSocket:
        def __init__(self):
            self.messages = [make_recognition("task-a", True)]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

        async def close(self):
            return None

    class FakeClientWebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, raw_message):
            self.sent.append(raw_message)

    backend_ws = FakeBackendWebSocket()
    client_ws = FakeClientWebSocket()
    placeholder_task = asyncio.current_task()
    router.task_sessions["task-a"] = type(
        "FakeSession",
        (),
        {
            "backend": backend,
            "backend_ws": backend_ws,
            "outbound_queue": asyncio.Queue(),
            "client_to_backend_task": placeholder_task,
            "backend_to_client_task": placeholder_task,
        },
    )()

    await router._backend_to_client("task-a", backend_ws, client_ws)

    assert backend.avg_latency == pytest.approx(1.0)
    assert backend.latency_samples == 1
    assert len(client_ws.sent) == 1
