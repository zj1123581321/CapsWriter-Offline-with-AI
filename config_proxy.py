# coding: utf-8
"""
ASR WebSocket 负载均衡代理配置。
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class ProxyConfig:
    """CapsWriter ASR proxy runtime config."""

    listen_addr = "0.0.0.0"
    listen_port = 6020

    backends = [
        "ws://192.168.31.222:6017",
        "ws://100.103.92.95:6017",
    ]

    max_connect_failures = 3
    log_level = "DEBUG"
