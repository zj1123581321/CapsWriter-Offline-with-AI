# coding: utf-8
"""
check_model 对 qwen_asr_mlx 的处理测试（P0 修复）。

原 check_model 的 if/elif 链对未知 model_type 走 else 分支 sys.exit(1)，
会在子进程 spawn 前拒掉 qwen_asr_mlx。修复后应：
- repo id 形态（如 'Qwen/Qwen3-ASR-0.6B'，非本地路径）→ 旁路放行，不 sys.exit
- 本地目录存在 → 放行
- 全程不应调用 input()（那是失败退出路径）
"""
import builtins
import pytest

import config_server
from core.server.worker.check_model import check_model


@pytest.fixture
def no_input(monkeypatch):
    """任何 input() 调用都视为走到了失败退出路径，测试失败。"""
    def _boom(*a, **k):
        raise AssertionError("check_model 走到了 input() 退出路径，不应发生")
    monkeypatch.setattr(builtins, "input", _boom)


def _set_mlx(monkeypatch, model_value):
    monkeypatch.setattr(config_server.ServerConfig, "model_type", "qwen_asr_mlx")
    monkeypatch.setattr(config_server.QwenASRMLXArgs, "model", model_value, raising=False)


def test_repo_id_bypasses_file_check(monkeypatch, no_input):
    """HF repo id（非本地路径）应旁路放行，不 sys.exit。"""
    _set_mlx(monkeypatch, "Qwen/Qwen3-ASR-0.6B")
    # 不应抛 SystemExit
    check_model()


def test_local_existing_dir_ok(monkeypatch, no_input, tmp_path):
    """配置为已存在的本地目录时应放行。"""
    _set_mlx(monkeypatch, str(tmp_path))
    check_model()


def test_other_types_still_validated(monkeypatch):
    """回归保护：未知的真·非法类型仍应 sys.exit（不破坏原有校验）。"""
    monkeypatch.setattr(config_server.ServerConfig, "model_type", "definitely_not_a_real_engine")
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "")
    with pytest.raises(SystemExit):
        check_model()
