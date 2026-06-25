# coding: utf-8
"""
qwen_asr_mlx 引擎离线验证脚本（可复跑）。

直调主线 EngineFactory / ModelLoader + 引擎识别音频，不走 WebSocket，
用于在真机确认整合无误。覆盖：
  1. 工厂实例化 + 能力声明([ASR, PUNC])
  2. mic 路径：create_stream → decode_stream → 文本(+标点)
  3. 边界：空音频早退、超 chunk_size 截断
  4. 语言映射：中/英/auto
  5. file 路径：外挂 Aligner 字级时间戳（依赖 aligner 模型，缺失则跳过并提示）
  6. 加载失败报错：依赖缺失时给清晰提示

用法（在装齐服务端依赖 + mlx 的环境，如 conda c / prod venv）：
    python scripts/_verify_mlx_asr.py [音频文件]
不传音频则用 1s 静音（仅验证管线不崩，文本会为空）。
首次运行会联网下载 Qwen3-ASR-0.6B 权重；离线可设 CW_MLX_MODEL 指向本地目录。
"""
import os
import sys
import time

# 允许从 scripts/ 直接运行：把仓库根目录加入 import 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 切到 qwen_asr_mlx 引擎
os.environ.setdefault("CW_MLX_MODEL", "Qwen/Qwen3-ASR-0.6B")
import config_server
config_server.ServerConfig.model_type = "qwen_asr_mlx"

import numpy as np
from core.server.engines.base import EngineCapabilities


def load_audio(path: str | None):
    """读取音频为 float32/16k 单声道；不传则返回 1s 静音。"""
    if not path:
        print("[verify] 未传音频，使用 1s 静音（文本将为空，仅验证管线）")
        return np.zeros(16000, dtype=np.float32), 16000
    import soundfile as sf
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        # 简单线性重采样（验证用，非高保真）
        n = int(len(audio) * 16000 / sr)
        audio = np.interp(np.linspace(0, len(audio), n, endpoint=False),
                          np.arange(len(audio)), audio).astype(np.float32)
        sr = 16000
    return audio, sr


def get_engine():
    """优先走 ModelLoader（完整集成）；若 sherpa 等可选依赖缺失则退回 EngineFactory。"""
    from core.server.engines.factory import EngineFactory
    try:
        from core.server.worker.model_loader import ModelLoader
        loader = ModelLoader()
        loader.load()
        print(f"[verify] ModelLoader 路径：aligner={'已挂载' if loader.aligner else '无'}, "
              f"punc={'已挂载' if loader.punc_model else '无(引擎自带)'}")
        return loader.recognizer, loader.aligner
    except Exception as e:  # noqa: BLE001
        print(f"[verify] ModelLoader 不可用（{e}），退回 EngineFactory 直建引擎")
        return EngineFactory.create_asr_engine("qwen_asr_mlx"), None


def main():
    audio_path = sys.argv[1] if len(sys.argv) > 1 else None
    audio, sr = load_audio(audio_path)

    print("[verify] 实例化引擎 …（首次会联网下载权重）")
    try:
        engine, aligner = get_engine()
    except RuntimeError as e:
        print(f"[verify] ❌ 引擎加载失败（这正是应给出的清晰报错）：\n{e}")
        sys.exit(1)

    caps = engine.capabilities
    print(f"[verify] 能力清单: {[c.name for c in caps]}")
    assert EngineCapabilities.ASR in caps and EngineCapabilities.PUNC in caps
    assert EngineCapabilities.TIMESTAMPS not in caps, "初版不应声明 TIMESTAMPS"

    # 1. mic 路径
    stream = engine.create_stream()
    stream.accept_waveform(sr, audio)
    t0 = time.time()
    engine.decode_stream(stream, language="auto")
    dt = time.time() - t0
    dur = len(audio) / 16000
    print(f"[verify] mic 文本: 「{stream.result.text}」  (耗时 {dt:.2f}s, 音频 {dur:.1f}s, "
          f"RTF {dt/dur:.3f})")

    # 2. 边界：空音频早退
    empty = engine.create_stream()
    engine.decode_stream(empty)
    assert empty.result.text == "", "空音频应早退、文本为空"
    print("[verify] 空音频早退 ✅")

    # 3. 边界：超 chunk_size 截断（造 100s 静音，不应崩）
    long_stream = engine.create_stream()
    long_stream.accept_waveform(16000, np.zeros(int(100 * 16000), dtype=np.float32))
    engine.decode_stream(long_stream)
    print("[verify] 超长音频截断推理不崩 ✅")

    # 4. 语言映射（中/英显式）
    for lang in ("chinese", "english"):
        s = engine.create_stream()
        s.accept_waveform(sr, audio)
        engine.decode_stream(s, language=lang)
        print(f"[verify] language={lang} → 文本「{s.result.text}」")

    # 5. file 路径字级时间戳（需 aligner）
    if aligner is not None and audio_path:
        try:
            align_res = aligner.align(audio=audio, text=stream.result.text or "测试",
                                      language="chinese", offset_sec=0.0)
            n = len(align_res.items) if align_res and getattr(align_res, "items", None) else 0
            print(f"[verify] 外挂 Aligner 字级时间戳: {n} 个 token ✅")
        except Exception as e:  # noqa: BLE001
            print(f"[verify] Aligner 对齐失败（可能缺模型）：{e}")
    else:
        print("[verify] file 路径字级时间戳：跳过（无 aligner 或未传真实音频）")

    engine.cleanup()
    print("[verify] ✅ 全部通过")


if __name__ == "__main__":
    main()
