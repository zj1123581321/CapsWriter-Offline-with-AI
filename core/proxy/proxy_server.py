# coding: utf-8
"""WebSocket server entrypoint for the ASR load-balancing proxy."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Iterable, Optional

from core.logger import setup_logger

from .backend import BackendState
from .router import NoHealthyBackendError, TaskRouter


class ProxyServer:
    """Accepts client WebSockets and proxies task streams to ASR backends."""

    def __init__(
        self,
        listen_addr: str,
        listen_port: int,
        backends: Iterable[BackendState],
        cooldown_seconds: int = 60,
        log_level: str = "DEBUG",
    ):
        self.listen_addr = listen_addr
        self.listen_port = listen_port
        self.backends = list(backends)
        self.cooldown_seconds = cooldown_seconds
        self.logger = setup_logger("proxy", level=log_level, log_filename="proxy")
        self._server = None

    def serve(self):
        import websockets

        return websockets.serve(
            self.handle_client,
            self.listen_addr,
            self.listen_port,
            max_size=None,
            ping_interval=None,
        )

    async def start(self) -> None:
        self.logger.info(
            "正在拉起 ASR 代理服务 (监听: %s:%s, 后端数: %s)",
            self.listen_addr,
            self.listen_port,
            len(self.backends),
        )
        async with self.serve() as server:
            self._server = server
            await asyncio.Future()

    async def handle_client(self, client_ws) -> None:
        remote = getattr(client_ws, "remote_address", None)
        self.logger.info("代理客户端已连接: %s", remote)
        router = TaskRouter(self.backends, cooldown_seconds=self.cooldown_seconds)

        try:
            async for raw_message in client_ws:
                try:
                    await router.route_client_message(raw_message, client_ws)
                except NoHealthyBackendError:
                    self.logger.error("没有健康后端可用，关闭客户端连接: %s", remote)
                    await client_ws.close(code=1013, reason="No healthy ASR backend")
                    break
                except Exception:
                    self.logger.error("代理消息处理失败，关闭客户端连接: %s", remote, exc_info=True)
                    await client_ws.close(code=1011, reason="ASR proxy routing failed")
                    break
        finally:
            await router.close_all()
            self.logger.info("代理客户端已断开: %s", remote)


def build_proxy_from_config(config: Optional[object] = None) -> ProxyServer:
    if config is None:
        from config_proxy import ProxyConfig as config

    backends = [
        BackendState(
            id=f"backend-{index}",
            url=url,
            weight=weight,
            max_connect_failures=config.max_connect_failures,
        )
        for index, (url, weight) in enumerate(_parse_backend_config(config.backends))
    ]
    return ProxyServer(
        config.listen_addr,
        config.listen_port,
        backends,
        cooldown_seconds=getattr(config, "cooldown_seconds", 60),
        log_level=getattr(config, "log_level", "DEBUG"),
    )


def _parse_backend_config(backends_config):
    parsed = []
    for index, item in enumerate(backends_config):
        if isinstance(item, str):
            url = item
            weight = 1.0
        elif isinstance(item, dict):
            url = item["url"]
            weight = float(item.get("weight", 1.0))
        else:
            url, weight = item
            weight = float(weight)

        if weight <= 0:
            raise ValueError(f"backend weight must be > 0: index={index} url={url!r} weight={weight}")
        parsed.append((url, weight))
    return parsed


def run_proxy() -> None:
    proxy = build_proxy_from_config()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(proxy.start())
