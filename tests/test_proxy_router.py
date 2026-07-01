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


@pytest.fixture(autouse=True)
def _reset_rr_counter():
    BackendState._rr_counter = 0
    yield
    BackendState._rr_counter = 0


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


def test_round_robin_tiebreaker_cycles_through_tied_backends():
    """When all backends have the same score, round-robin cycles through them."""
    backends = [
        BackendState(id="a", url="ws://a"),
        BackendState(id="b", url="ws://b"),
        BackendState(id="c", url="ws://c"),
    ]
    router = TaskRouter(backends)

    ids = [router.select_backend().id for _ in range(6)]

    assert ids == ["a", "b", "c", "a", "b", "c"]


def test_ten_sequential_tasks_distribute_evenly_across_three_backends():
    """Acceptance: 3 idle backends, 10 sequential tasks, no starvation."""
    backends = [
        BackendState(id="mac-studio", url="ws://a"),
        BackendState(id="mac-mini", url="ws://b"),
        BackendState(id="amd-6800h", url="ws://c"),
    ]
    router = TaskRouter(backends)

    counts = {"mac-studio": 0, "mac-mini": 0, "amd-6800h": 0}
    for _ in range(10):
        selected = router.select_backend()
        counts[selected.id] += 1

    assert all(count >= 3 for count in counts.values()), f"Uneven distribution: {counts}"


def test_round_robin_counter_shared_across_taskrouter_instances():
    """TaskRouter is per-client; rr counter must be shared via BackendState ClassVar."""
    backends = [
        BackendState(id="a", url="ws://a"),
        BackendState(id="b", url="ws://b"),
        BackendState(id="c", url="ws://c"),
    ]
    router1 = TaskRouter(backends)
    router2 = TaskRouter(backends)

    assert router1.select_backend().id == "a"
    assert router2.select_backend().id == "b"
    assert router1.select_backend().id == "c"


def test_concurrent_tasks_unaffected_by_round_robin():
    """When active_tasks differ, least-connections wins over round-robin."""
    idle = BackendState(id="idle", url="ws://a")
    busy = BackendState(id="busy", url="ws://b")
    busy.active_tasks = 2
    router = TaskRouter([busy, idle])

    selected = router.select_backend()

    assert selected.id == "idle"


def test_load_dominates_latency_in_scoring():
    """A backend with fewer tasks must be preferred even if its latency is higher."""
    fast_busy = BackendState(id="fast-busy", url="ws://a", weight=1.0)
    slow_idle = BackendState(id="slow-idle", url="ws://b", weight=1.0)
    fast_busy.active_tasks = 1
    slow_idle.active_tasks = 0
    fast_busy.avg_latency = 1.0
    slow_idle.avg_latency = 100.0
    fast_busy.latency_samples = slow_idle.latency_samples = 4
    router = TaskRouter([fast_busy, slow_idle])

    selected = router.select_backend()

    assert selected.id == "slow-idle"


def test_three_concurrent_tasks_spread_to_three_backends():
    """Regression: 3 concurrent tasks must go to 3 different backends, not pile on one."""
    backends = [
        BackendState(id="mac-studio", url="ws://a", weight=1.0),
        BackendState(id="mac-mini", url="ws://b", weight=1.0),
        BackendState(id="amd-6800h", url="ws://c", weight=1.0),
    ]
    router = TaskRouter(backends)

    selected_ids = []
    for _ in range(3):
        selected = router.select_backend()
        selected_ids.append(selected.id)
        selected.acquire_task()

    assert len(set(selected_ids)) == 3


def test_backend_score_is_pure_least_connections():
    """Score = (active_tasks + 1) / weight, no latency component."""
    backend = BackendState(id="backend-0", url="ws://a", weight=2.0)
    backend.active_tasks = 3
    backend.avg_latency = 999.0
    backend.latency_samples = 100
    router = TaskRouter([backend])

    score = router.backend_score(backend)

    assert score == pytest.approx((3 + 1) / 2.0)


def test_router_weight_affects_selection_at_equal_load():
    """With same active_tasks, lower weight backend gets deprioritized."""
    lan = BackendState(id="lan", url="ws://lan", weight=1.0)
    remote = BackendState(id="remote", url="ws://remote", weight=0.3)
    router = TaskRouter([remote, lan])

    selected = router.select_backend()

    assert selected.id == "lan"


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
