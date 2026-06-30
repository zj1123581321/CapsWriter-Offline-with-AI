# coding: utf-8
"""Task-aware routing and backend WebSocket lifecycle management."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Iterable, Optional

from core.logger import get_logger
from core.protocol import AudioMessage, RecognitionMessage

from .backend import BackendState

logger = get_logger("proxy")


class NoHealthyBackendError(RuntimeError):
    """Raised when no backend can accept a new task."""


def parse_audio_message(raw_message: str) -> AudioMessage:
    """Parse client AudioMessage JSON and validate the CapsWriter protocol."""
    data = json.loads(raw_message)
    return AudioMessage.from_dict(data)


def is_final_recognition_message(raw_message: str) -> bool:
    """Return True when a backend RecognitionMessage is the final result."""
    data = json.loads(raw_message)
    return bool(data.get("is_final", False))


def recognition_task_id(raw_message: str) -> Optional[str]:
    data = json.loads(raw_message)
    task_id = data.get("task_id")
    return str(task_id) if task_id is not None else None


ConnectFunc = Callable[[str], Awaitable[object]]


@dataclass
class TaskSession:
    task_id: str
    backend: BackendState
    backend_ws: object
    outbound_queue: asyncio.Queue
    client_to_backend_task: asyncio.Task
    backend_to_client_task: asyncio.Task


class TaskRouter:
    """Routes each task_id to one short-lived backend WebSocket connection."""

    def __init__(
        self,
        backends: Iterable[BackendState],
        connect_func: Optional[ConnectFunc] = None,
        cooldown_seconds: int = 60,
    ):
        self.backends = list(backends)
        self.task_sessions: Dict[str, TaskSession] = {}
        self._connect_func = connect_func
        self.cooldown_seconds = cooldown_seconds

    def select_backend(self) -> BackendState:
        if not self.backends:
            raise NoHealthyBackendError("No ASR backend is configured")

        now = time.time()
        for backend in self.backends:
            if (
                not backend.healthy
                and backend.last_failure_time > 0
                and now - backend.last_failure_time >= self.cooldown_seconds
            ):
                backend.consecutive_failures = 0
                backend.healthy = True
                logger.info(
                    "后端 cooldown 已结束，恢复健康: backend=%s url=%s cooldown_seconds=%s",
                    backend.id,
                    backend.url,
                    self.cooldown_seconds,
                )

        healthy_backends = [backend for backend in self.backends if backend.healthy]
        if not healthy_backends:
            selected = min(self.backends, key=lambda backend: backend.active_tasks)
            logger.warning(
                "全部后端 unhealthy，降级路由到 cooldown 中负载最低后端: backend=%s active_tasks=%s score=%.6f",
                selected.id,
                selected.active_tasks,
                self.backend_score(selected),
            )
            return selected

        selected = min(healthy_backends, key=self.backend_score)
        logger.info(
            "后端选择: backend=%s active_tasks=%s weight=%.3f avg_latency=%.3f latency_samples=%s score=%.6f",
            selected.id,
            selected.active_tasks,
            selected.weight,
            selected.avg_latency,
            selected.latency_samples,
            self.backend_score(selected),
        )
        logger.debug(
            "后端延迟状态: %s",
            ", ".join(
                f"{backend.id}:avg_latency={backend.avg_latency:.3f},samples={backend.latency_samples}"
                for backend in self.backends
            ),
        )
        return selected

    def backend_score(self, backend: BackendState) -> float:
        latency = backend.avg_latency if backend.latency_samples >= 3 and backend.avg_latency > 0 else 1.0
        return backend.active_tasks * latency / backend.weight

    def get_backend_for_task(self, task_id: str) -> Optional[BackendState]:
        session = self.task_sessions.get(task_id)
        return session.backend if session else None

    async def route_client_message(self, raw_message: str, client_ws) -> None:
        msg = parse_audio_message(raw_message)
        session = self.task_sessions.get(msg.task_id)
        if session is None:
            session = await self._open_task_session(msg.task_id, client_ws)
        await session.outbound_queue.put(raw_message)

    async def close_all(self) -> None:
        task_ids = list(self.task_sessions)
        await asyncio.gather(
            *(self.close_session(task_id) for task_id in task_ids),
            return_exceptions=True,
        )

    async def close_session(self, task_id: str) -> None:
        session = self.task_sessions.pop(task_id, None)
        if session is None:
            return

        session.backend.release_task()
        await session.outbound_queue.put(None)

        current = asyncio.current_task()
        for task in (session.client_to_backend_task, session.backend_to_client_task):
            if task is not current and not task.done():
                task.cancel()

        try:
            await session.backend_ws.close()
        except Exception:
            logger.debug("后端连接关闭时出现异常，任务ID: %s", task_id, exc_info=True)

        logger.info(
            "任务连接已释放: task_id=%s backend=%s active_tasks=%s",
            task_id,
            session.backend.id,
            session.backend.active_tasks,
        )

    async def _open_task_session(self, task_id: str, client_ws) -> TaskSession:
        backend = self.select_backend()
        backend.acquire_task()
        try:
            backend_ws = await self._connect_backend(backend.url)
        except asyncio.CancelledError:
            backend.release_task()
            raise
        except Exception:
            backend.release_task()
            backend.record_connect_failure()
            logger.warning(
                "后端连接失败: backend=%s url=%s failures=%s healthy=%s",
                backend.id,
                backend.url,
                backend.consecutive_failures,
                backend.healthy,
                exc_info=True,
            )
            raise

        backend.record_connect_success()
        outbound_queue = asyncio.Queue()
        session = TaskSession(
            task_id=task_id,
            backend=backend,
            backend_ws=backend_ws,
            outbound_queue=outbound_queue,
            client_to_backend_task=asyncio.create_task(
                self._client_to_backend(task_id, backend_ws, outbound_queue)
            ),
            backend_to_client_task=asyncio.create_task(
                self._backend_to_client(task_id, backend_ws, client_ws)
            ),
        )
        self.task_sessions[task_id] = session
        logger.info(
            "新任务路由: task_id=%s backend=%s url=%s active_tasks=%s score=%.6f",
            task_id,
            backend.id,
            backend.url,
            backend.active_tasks,
            self.backend_score(backend),
        )
        return session

    async def _connect_backend(self, url: str):
        if self._connect_func is not None:
            return await self._connect_func(url)

        import websockets

        kwargs = {
            "uri": url,
            "max_size": None,
            "ping_interval": None,
        }
        version_parts = tuple(int(part) for part in websockets.__version__.split(".")[:2])
        if version_parts >= (14, 0):
            kwargs["proxy"] = None
        return await websockets.connect(**kwargs)

    async def _client_to_backend(self, task_id: str, backend_ws, outbound_queue: asyncio.Queue) -> None:
        try:
            while True:
                raw_message = await outbound_queue.get()
                if raw_message is None:
                    return
                await backend_ws.send(raw_message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("客户端到后端转发失败: task_id=%s", task_id, exc_info=True)
            await self.close_session(task_id)
            raise

    async def _backend_to_client(self, task_id: str, backend_ws, client_ws) -> None:
        try:
            async for raw_message in backend_ws:
                session = self.task_sessions.get(task_id)
                if session is None:
                    return
                session.backend.record_result()
                self._record_backend_latency(session.backend, raw_message)
                await client_ws.send(raw_message)
                if recognition_task_id(raw_message) == task_id and is_final_recognition_message(raw_message):
                    await self.close_session(task_id)
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("后端到客户端转发失败: task_id=%s", task_id, exc_info=True)
            await self.close_session(task_id)
            try:
                await client_ws.close()
            except Exception:
                logger.debug("客户端连接关闭失败: task_id=%s", task_id, exc_info=True)
            raise

    def _record_backend_latency(self, backend: BackendState, raw_message: str) -> None:
        try:
            message = RecognitionMessage.from_dict(json.loads(raw_message))
        except Exception:
            logger.debug("无法解析后端 RecognitionMessage，跳过延迟统计: backend=%s", backend.id, exc_info=True)
            return

        backend.record_processing_latency(message.time_complete - message.time_submit)
