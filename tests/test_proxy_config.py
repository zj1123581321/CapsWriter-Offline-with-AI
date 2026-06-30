# coding: utf-8

import pytest

from core.proxy.proxy_server import build_proxy_from_config


class Config:
    listen_addr = "127.0.0.1"
    listen_port = 0
    max_connect_failures = 3
    cooldown_seconds = 30
    backends = [
        "ws://plain",
        ("ws://tuple", 2.0),
        {"url": "ws://dict", "weight": 3.0},
    ]


def test_build_proxy_from_config_parses_backend_weights():
    proxy = build_proxy_from_config(Config)

    assert [(backend.url, backend.weight) for backend in proxy.backends] == [
        ("ws://plain", 1.0),
        ("ws://tuple", 2.0),
        ("ws://dict", 3.0),
    ]
    assert proxy.cooldown_seconds == 30


def test_build_proxy_from_config_rejects_non_positive_weight():
    class BadConfig(Config):
        backends = [("ws://bad", 0)]

    with pytest.raises(ValueError, match="weight"):
        build_proxy_from_config(BadConfig)


@pytest.mark.parametrize("weight", [float("nan"), float("inf")])
def test_build_proxy_from_config_rejects_non_finite_weight(weight):
    class BadConfig(Config):
        backends = [("ws://bad", weight)]

    with pytest.raises(ValueError, match="weight"):
        build_proxy_from_config(BadConfig)
