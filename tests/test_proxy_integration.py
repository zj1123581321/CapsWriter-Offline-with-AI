# coding: utf-8

import asyncio
import json

import pytest

websockets = pytest.importorskip("websockets")

from core.proxy.backend import BackendState
from core.proxy.proxy_server import ProxyServer


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


def make_recognition(task_id: str, is_final: bool = True) -> str:
    return json.dumps(
        {
            "task_id": task_id,
            "is_final": is_final,
            "duration": 1.0,
            "time_start": 1.0,
            "time_submit": 2.0,
            "time_complete": 3.0,
            "text": f"done:{task_id}",
        }
    )


@pytest.mark.asyncio
async def test_proxy_routes_different_tasks_to_least_loaded_backends():
    backend_hits = {"a": [], "b": []}
    release_backend_a = asyncio.Event()

    async def backend_a_handler(ws):
        raw = await ws.recv()
        data = json.loads(raw)
        backend_hits["a"].append(data["task_id"])
        await release_backend_a.wait()
        await ws.send(make_recognition(data["task_id"]))

    async def backend_b_handler(ws):
        raw = await ws.recv()
        data = json.loads(raw)
        backend_hits["b"].append(data["task_id"])
        await ws.send(make_recognition(data["task_id"]))

    async with websockets.serve(backend_a_handler, "127.0.0.1", 0, max_size=None) as server_a:
        async with websockets.serve(backend_b_handler, "127.0.0.1", 0, max_size=None) as server_b:
            port_a = server_a.sockets[0].getsockname()[1]
            port_b = server_b.sockets[0].getsockname()[1]
            proxy = ProxyServer(
                "127.0.0.1",
                0,
                [
                    BackendState(id="backend-0", url=f"ws://127.0.0.1:{port_a}"),
                    BackendState(id="backend-1", url=f"ws://127.0.0.1:{port_b}"),
                ],
            )
            async with proxy.serve() as proxy_ws_server:
                proxy_port = proxy_ws_server.sockets[0].getsockname()[1]
                async with websockets.connect(f"ws://127.0.0.1:{proxy_port}", max_size=None) as client:
                    await client.send(make_audio("task-a"))
                    await asyncio.sleep(0.05)
                    await client.send(make_audio("task-b"))
                    result_b = json.loads(await client.recv())
                    release_backend_a.set()
                    result_a = json.loads(await client.recv())

    assert backend_hits == {"a": ["task-a"], "b": ["task-b"]}
    assert {result_a["task_id"], result_b["task_id"]} == {"task-a", "task-b"}
