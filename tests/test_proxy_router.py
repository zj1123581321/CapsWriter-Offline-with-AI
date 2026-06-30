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


def test_backend_score_includes_idle_latency_signal_after_warmup():
    backend = BackendState(id="backend-0", url="ws://a", weight=1.0)
    backend.avg_latency = 3.0
    backend.latency_samples = 4
    router = TaskRouter([backend])

    assert router.backend_score(backend) == pytest.approx(3.0)


def test_router_deprioritizes_idle_remote_backend_with_high_latency_and_low_weight():
    lan = BackendState(id="lan", url="ws://lan", weight=1.0)
    remote = BackendState(id="remote", url="ws://remote", weight=0.3)
    lan.avg_latency = 1.0
    remote.avg_latency = 6.0
    lan.latency_samples = remote.latency_samples = 4
    router = TaskRouter([remote, lan])

    selected = router.select_backend()

    assert selected.id == "lan"


def test_router_expires_stale_latency_to_allow_backend_recovery(monkeypatch):
    now = {"value": 1000.0}
    monkeypatch.setattr("core.proxy.router.monotonic", lambda: now["value"])
    monkeypatch.setattr("core.proxy.backend.monotonic", lambda: 1001.0)
    recovered = BackendState(id="recovered", url="ws://recovered", weight=1.0)
    current = BackendState(id="current", url="ws://current", weight=1.0)
    recovered.avg_latency = 300.0
    current.avg_latency = 1.0
    recovered.latency_samples = current.latency_samples = 4
    recovered.last_latency_time = 600.0
    current.last_latency_time = 990.0
    router = TaskRouter([recovered, current], latency_ttl_seconds=300)

    selected = router.select_backend()

    assert selected.id == "recovered"

    recovered.record_processing_latency(1.0, latency_ttl_seconds=300)
    now["value"] = 1002.0

    assert router.select_backend().id == "recovered"


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
async def test_in_cooldown_fallback_failure_does_not_extend_cooldown(monkeypatch):
    monkeypatch.setattr("core.proxy.router.time.time", lambda: 120.0)
    backend = BackendState(
        id="backend-0",
        url="ws://a",
        healthy=False,
        max_connect_failures=1,
        last_failure_time=100.0,
    )

    async def failing_connect(_url):
        raise OSError("still down")

    router = TaskRouter([backend], connect_func=failing_connect, cooldown_seconds=60)

    with pytest.raises(OSError):
        await router.route_client_message(make_audio("task-a"), object())

    assert backend.healthy is False
    assert backend.last_failure_time == 100.0


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
            "start_time": 10.0,
        },
    )()

    await router._backend_to_client("task-a", backend_ws, client_ws)

    assert backend.avg_latency == pytest.approx(1.0)
    assert backend.latency_samples == 1
    assert len(client_ws.sent) == 1


@pytest.mark.asyncio
async def test_backend_to_client_skips_invalid_latency_but_still_forwards_message():
    backend = BackendState(id="backend-0", url="ws://a")
    router = TaskRouter([backend])

    class FakeBackendWebSocket:
        def __init__(self):
            self.messages = [
                json.dumps(
                    {
                        "task_id": "task-a",
                        "is_final": True,
                        "duration": 1.0,
                        "time_start": 1.0,
                        "time_submit": None,
                        "time_complete": 3.0,
                        "text": "ok",
                    }
                )
            ]

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
            "start_time": 10.0,
        },
    )()

    await router._backend_to_client("task-a", backend_ws, client_ws)

    assert backend.latency_samples == 0
    assert len(client_ws.sent) == 1


@pytest.mark.asyncio
async def test_backend_to_client_logs_end_to_end_latency_only_for_matching_final(monkeypatch):
    backend = BackendState(id="backend-0", url="ws://a")
    router = TaskRouter([backend])
    backend_times = iter([101.0, 102.0, 103.0])
    infos = []
    monkeypatch.setattr("core.proxy.backend.monotonic", lambda: next(backend_times))
    monkeypatch.setattr("core.proxy.router.monotonic", lambda: 103.5)
    monkeypatch.setattr(
        "core.proxy.router.logger.info",
        lambda message, *args, **kwargs: infos.append(message % args),
    )

    class FakeBackendWebSocket:
        def __init__(self):
            self.messages = [
                make_recognition("other-task", True),
                make_recognition("task-a", False),
                make_recognition("task-a", True),
            ]

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
            "start_time": 100.0,
        },
    )()

    await router._backend_to_client("task-a", backend_ws, client_ws)

    completion_logs = [message for message in infos if "任务完成:" in message]
    assert len(completion_logs) == 1
    assert "task_id=task-a" in completion_logs[0]
    assert "inference_latency=1.000" in completion_logs[0]
    assert "end_to_end=3.500" in completion_logs[0]
