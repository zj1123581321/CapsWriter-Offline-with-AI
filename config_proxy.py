# coding: utf-8
"""
ASR WebSocket 负载均衡代理配置。

部署时通过环境变量覆盖，无需改源码：
  CW_PROXY_BACKENDS    逗号分隔的后端列表，如 "ws://192.168.1.10:6017,ws://192.168.1.20:6017"
  CW_PROXY_PORT        代理监听端口，默认 6020
  CW_PROXY_ADDR        代理监听地址，默认 0.0.0.0
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _env_str(key, default):
    return os.environ.get(key, default)

def _env_backends(key, default):
    raw = os.environ.get(key)
    if raw:
        return [s.strip() for s in raw.split(',') if s.strip()]
    return default


class ProxyConfig:
    """CapsWriter ASR proxy runtime config."""

    listen_addr = _env_str('CW_PROXY_ADDR', '0.0.0.0')
    listen_port = int(_env_str('CW_PROXY_PORT', '6020'))

    backends = _env_backends('CW_PROXY_BACKENDS', [
        "ws://127.0.0.1:6016",
        "ws://127.0.0.1:6017",
    ])

    max_connect_failures = 3
    log_level = "DEBUG"
