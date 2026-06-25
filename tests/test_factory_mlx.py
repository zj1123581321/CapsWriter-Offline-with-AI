# coding: utf-8
"""
工厂注册与 Args→Config 展开测试。

验证 'qwen_asr_mlx' 已注册、loader 返回正确三元组，
以及 config_server 的 Args 公开属性能原样展开成 ConfigClass kwargs
（plan §3.4 强调字段名必须严格对应，否则工厂构造即报错）。
"""
import pytest

from core.server.engines.factory import EngineFactory


def test_mlx_registered():
    assert "qwen_asr_mlx" in EngineFactory._ASR_LOADERS


def test_mlx_loader_triple():
    loader = EngineFactory._ASR_LOADERS["qwen_asr_mlx"]
    EngineClass, ConfigClass, ArgsObj = loader()
    assert EngineClass.__name__ == "QwenASRMLXEngine"
    assert ConfigClass.__name__ == "MLXEngineConfig"
    assert ArgsObj.__name__ == "QwenASRMLXArgs"


def test_args_fields_match_config():
    """Args 的公开类属性集合必须是 MLXEngineConfig 字段的子集，否则工厂报错。"""
    from config_server import QwenASRMLXArgs
    from core.server.engines.qwen_asr_mlx.asr_engine import MLXEngineConfig
    import dataclasses

    args_keys = {k for k in vars(QwenASRMLXArgs) if not k.startswith("_")}
    config_fields = {f.name for f in dataclasses.fields(MLXEngineConfig)}
    missing = args_keys - config_fields
    assert not missing, f"Args 多出 MLXEngineConfig 没有的字段: {missing}"


def test_create_engine_via_factory(fake_mlx):
    """完整走工厂：create_asr_engine('qwen_asr_mlx') 返回引擎且 config 注入正确。"""
    engine = EngineFactory.create_asr_engine("qwen_asr_mlx")
    assert engine.__class__.__name__ == "QwenASRMLXEngine"
    # config 由 QwenASRMLXArgs 展开而来，model 应为默认 repo id
    assert engine.config.model == "Qwen/Qwen3-ASR-0.6B"
