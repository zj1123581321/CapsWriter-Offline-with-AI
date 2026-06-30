# coding: utf-8

import json

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


def test_router_tie_breaks_by_config_order():
    backends = [
        BackendState(id="backend-0", url="ws://a"),
        BackendState(id="backend-1", url="ws://b"),
    ]
    router = TaskRouter(backends)

    selected = router.select_backend()

    assert selected.id == "backend-0"


def test_router_rejects_when_all_backends_unhealthy():
    backends = [
        BackendState(id="backend-0", url="ws://a", healthy=False),
        BackendState(id="backend-1", url="ws://b", healthy=False),
    ]
    router = TaskRouter(backends)

    with pytest.raises(NoHealthyBackendError):
        router.select_backend()


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
