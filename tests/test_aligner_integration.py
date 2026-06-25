# coding: utf-8
"""
外挂 ForceAligner 集成测试(macOS GGUF 后端)。

qwen_asr_mlx / qwen_asr 都声明 [ASR, PUNC] 无 TIMESTAMPS，文件转录的字级时间戳
由外挂 QwenForceAligner 补齐。本测试验证该外挂在本机真实可跑、能为给定文本
产出 token 级时间戳。

依赖运行时资产(不入库，需各机自行下载)：
  - llama.cpp 后端 dylib: core/server/engines/llama/bin/libllama.dylib 等(b7798 macos-arm64)
  - 对齐模型: models/Qwen3-ForcedAligner/Qwen3-ForcedAligner-0.6B/*(int4 onnx + q5_k gguf)
  - onnxruntime(对齐器编码器)
资产缺失时自动 skip(其它机器/CI 不受影响)；本机装好后即转为真实断言。
"""
import os
import sys
import pytest
import numpy as np

from config_server import ModelPaths
from core.server.engines.base import BaseAlignEngine

_LLAMA_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "server", "engines", "llama", "bin",
)


def _llama_lib_name() -> str:
    if sys.platform == "win32":
        return "llama.dll"
    if sys.platform == "darwin":
        return "libllama.dylib"
    return "libllama.so"


def _aligner_assets_ready() -> bool:
    """llama 后端 + 对齐模型文件是否齐备。"""
    return (
        os.path.exists(os.path.join(_LLAMA_BIN, _llama_lib_name()))
        and ModelPaths.force_aligner_gguf_llm_decode.exists()
        and ModelPaths.force_aligner_gguf_encoder_frontend.exists()
        and ModelPaths.force_aligner_gguf_encoder_backend.exists()
    )


pytestmark = pytest.mark.skipif(
    not _aligner_assets_ready(),
    reason="ForceAligner 后端/模型未安装(macOS 需下载 b7798 dylib + Qwen3-ForcedAligner 模型 + onnxruntime)",
)


def test_aligner_loads_not_fallback():
    """工厂应造出真正的 QwenForceAligner，而非加载失败时的空 BaseAlignEngine 兜底。"""
    from core.server.engines.factory import EngineFactory
    aligner = EngineFactory.create_align_engine()
    assert type(aligner).__name__ == "QwenForceAligner", \
        "aligner 退回空实现，说明 llama 后端/模型/onnxruntime 加载失败"
    aligner.cleanup()


def test_aligner_produces_token_timestamps():
    """强制对齐应为给定文本的每个 token 产出带时间戳的结果项。"""
    from core.server.engines.factory import EngineFactory
    aligner = EngineFactory.create_align_engine()
    assert type(aligner).__name__ == "QwenForceAligner"

    audio = np.zeros(int(2 * 16000), dtype=np.float32)  # 2s 音频，强制对齐固定文本
    res = aligner.align(audio=audio, text="测试对齐", language="chinese", offset_sec=0.0)

    assert res is not None and getattr(res, "items", None), "对齐未返回 items"
    assert len(res.items) >= 1
    for it in res.items:
        assert hasattr(it, "text") and hasattr(it, "start_time")
    # 时间戳应非负且不下降(单调)
    starts = [it.start_time for it in res.items]
    assert all(s >= 0 for s in starts)
    assert starts == sorted(starts), "时间戳应单调不降"
    aligner.cleanup()
