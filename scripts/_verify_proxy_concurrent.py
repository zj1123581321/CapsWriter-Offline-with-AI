#!/usr/bin/env python3
# coding: utf-8
"""Self-contained concurrent routing verification for the ASR proxy.

The script starts mock WebSocket ASR backends and an in-process ProxyServer.
It verifies:
1. concurrent tasks are routed to different backends;
2. final results are returned to the correct client connection;
3. all messages for the same task_id stay on the same backend;
4. a failed backend is marked unhealthy and later tasks use a healthy backend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import sys
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import websockets
except ImportError:
    print("Please install websockets first: pip install websockets")
    sys.exit(1)

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


def make_recognition(task_id: str, backend_id: str) -> str:
    return json.dumps(
        {
            "task_id": task_id,
            "is_final": True,
            "duration": 1.0,
            "time_start": 1.0,
            "time_submit": 2.0,
            "time_complete": 3.0,
            "text": f"{backend_id}:{task_id}",
        }
    )


async def connect_ws(url: str):
    kwargs = {"uri": url, "max_size": None, "ping_interval": None}
    version = tuple(int(part) for part in websockets.__version__.split(".")[:2])
    if version >= (14, 0):
        kwargs["proxy"] = None
    return await websockets.connect(**kwargs)


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def backend_handler(backend_id: str, hits: Dict[str, List[str]]):
    async def handle(ws):
        async for raw_message in ws:
            data = json.loads(raw_message)
            task_id = data["task_id"]
            hits[backend_id].append(task_id)
            if data.get("is_final", False):
                await ws.send(make_recognition(task_id, backend_id))
                return

    return handle


async def verify_concurrent_routing() -> None:
    hits = {"backend-a": [], "backend-b": []}
    async with websockets.serve(backend_handler("backend-a", hits), "127.0.0.1", 0, max_size=None) as server_a:
        async with websockets.serve(backend_handler("backend-b", hits), "127.0.0.1", 0, max_size=None) as server_b:
            port_a = server_a.sockets[0].getsockname()[1]
            port_b = server_b.sockets[0].getsockname()[1]
            proxy = ProxyServer(
                "127.0.0.1",
                0,
                [
                    BackendState(id="backend-a", url=f"ws://127.0.0.1:{port_a}"),
                    BackendState(id="backend-b", url=f"ws://127.0.0.1:{port_b}"),
                ],
            )
            async with proxy.serve() as proxy_server:
                proxy_port = proxy_server.sockets[0].getsockname()[1]
                async with await connect_ws(f"ws://127.0.0.1:{proxy_port}") as client:
                    await client.send(make_audio("task-a", is_final=False))
                    await client.send(make_audio("task-b", is_final=True))
                    await client.send(make_audio("task-a", is_final=True))
                    responses = [
                        json.loads(await asyncio.wait_for(client.recv(), timeout=5.0)),
                        json.loads(await asyncio.wait_for(client.recv(), timeout=5.0)),
                    ]

    task_ids = {response["task_id"] for response in responses}
    assert task_ids == {"task-a", "task-b"}, responses
    assert hits["backend-a"] == ["task-a", "task-a"], hits
    assert hits["backend-b"] == ["task-b"], hits


async def verify_failed_backend_fallback() -> None:
    hits = {"healthy": []}
    dead = BackendState(
        id="dead",
        url=f"ws://127.0.0.1:{unused_port()}",
        max_connect_failures=1,
    )
    async with websockets.serve(backend_handler("healthy", hits), "127.0.0.1", 0, max_size=None) as healthy_server:
        healthy_port = healthy_server.sockets[0].getsockname()[1]
        healthy = BackendState(id="healthy", url=f"ws://127.0.0.1:{healthy_port}")
        proxy = ProxyServer("127.0.0.1", 0, [dead, healthy])
        async with proxy.serve() as proxy_server:
            proxy_port = proxy_server.sockets[0].getsockname()[1]
            proxy_logger = logging.getLogger("proxy")
            was_disabled = proxy_logger.disabled
            proxy_logger.disabled = True
            try:
                async with await connect_ws(f"ws://127.0.0.1:{proxy_port}") as client:
                    await client.send(make_audio("dead-task", is_final=True))
                    await asyncio.wait_for(client.recv(), timeout=5.0)
            except Exception:
                pass
            finally:
                proxy_logger.disabled = was_disabled

            assert dead.healthy is False
            async with await connect_ws(f"ws://127.0.0.1:{proxy_port}") as client:
                await client.send(make_audio("live-task", is_final=True))
                response = json.loads(await asyncio.wait_for(client.recv(), timeout=5.0))

    assert response["task_id"] == "live-task", response
    assert hits["healthy"] == ["live-task"], hits


async def main_async() -> None:
    await verify_concurrent_routing()
    print("OK concurrent routing: task distribution, replies, and affinity")
    await verify_failed_backend_fallback()
    print("OK backend failure fallback")


def main() -> int:
    try:
        asyncio.run(main_async())
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
