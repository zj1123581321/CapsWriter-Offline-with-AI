# coding: utf-8
"""
qwen_asr_mlx 引擎单元测试共享夹具。

核心思路：MLX 推理仅 Apple Silicon 可用且依赖第三方包 mlx-qwen3-asr，
单元测试不依赖真机 —— 向 sys.modules 注入一个假的 mlx_qwen3_asr 模块，
其 Session.transcribe 记录调用参数、返回可控结果。适配层在方法内
`from mlx_qwen3_asr import Session` 延迟导入，因此注入即生效。
"""
import sys
import types
import numpy as np
import pytest


class FakeResult:
    """模拟 mlx_qwen3_asr Session.transcribe 的返回对象。"""
    def __init__(self, text="你好世界。", language="Chinese", segments=None):
        self.text = text
        self.language = language
        # 段级时间戳：list[{text,start}]，初版不使用，仅供将来 TODO 验证
        self.segments = segments if segments is not None else [
            {"text": "你好", "start": 0.0},
            {"text": "世界", "start": 0.5},
        ]


class FakeSession:
    """模拟 mlx_qwen3_asr 的 Session：记录构造与 transcribe 调用。"""
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.transcribe_calls = []  # list[dict(audio_len, kwargs, audio)]
        self.model_info = {"name": kwargs.get("model"), "fake": True}

    def transcribe(self, audio, **kwargs):
        self.transcribe_calls.append(
            {"audio_len": len(audio), "kwargs": dict(kwargs), "audio": audio}
        )
        return FakeResult()


@pytest.fixture
def fake_mlx(monkeypatch):
    """把假的 mlx_qwen3_asr 模块注入 sys.modules，返回 FakeSession 类。"""
    mod = types.ModuleType("mlx_qwen3_asr")
    mod.Session = FakeSession
    monkeypatch.setitem(sys.modules, "mlx_qwen3_asr", mod)
    return FakeSession


@pytest.fixture
def mlx_engine(fake_mlx):
    """构造一个使用假 Session 的 QwenASRMLXEngine 实例。"""
    from core.server.engines.qwen_asr_mlx.asr_engine import (
        QwenASRMLXEngine,
        MLXEngineConfig,
    )
    config = MLXEngineConfig(model="Qwen/Qwen3-ASR-0.6B", dtype=None,
                             chunk_size=80.0, verbose=False)
    return QwenASRMLXEngine(config)


def make_audio(seconds: float, sr: int = 16000) -> np.ndarray:
    """生成指定时长的 float32 静音音频。"""
    return np.zeros(int(seconds * sr), dtype=np.float32)
