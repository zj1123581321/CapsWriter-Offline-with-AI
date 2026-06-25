# coding: utf-8
"""
qwen_asr_mlx 全链路内存占用测量。

分阶段记录进程 RSS(ps，含 mmap 进来的模型常驻页)与 MLX Metal 分配
(mx.get_active_memory / get_peak_memory)，覆盖：基线 → MLX 引擎加载 →
ASR 推理 → 首次 Aligner 对齐(触发对齐模型加载)。最后给进程峰值 RSS。

用法：python scripts/_mem_mlx.py <音频文件>
建议配合 CW_ALIGNER_LLM_USE_GPU=1 测 Metal 版 aligner 的占用。
"""
import os
import sys
import resource
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CW_MLX_MODEL", "Qwen/Qwen3-ASR-0.6B")
import config_server
config_server.ServerConfig.model_type = "qwen_asr_mlx"

import numpy as np
import soundfile as sf


def rss_mb():
    """当前进程 RSS(MB)，macOS ps 给 KB。"""
    out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())]).decode().strip()
    return int(out) / 1024


def peak_rss_mb():
    """进程历史峰值 RSS(MB)。macOS ru_maxrss 单位是字节。"""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def mlx_mb():
    import mlx.core as mx
    return mx.get_active_memory() / 1e6, mx.get_peak_memory() / 1e6


def line(stage, base=0.0):
    cur = rss_mb()
    a, p = mlx_mb()
    print(f"{stage:<26}RSS {cur:8.1f} MB (Δ{cur-base:+7.1f})   MLX active {a:7.1f} / peak {p:7.1f} MB")
    return cur


def main():
    path = os.path.expanduser(sys.argv[1])
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)

    base = line("0 基线(import 后)")
    from core.server.worker.model_loader import ModelLoader
    loader = ModelLoader()
    loader.load()
    engine, aligner = loader.recognizer, loader.aligner
    line("1 MLX 引擎加载后", base)

    chunk = audio[: 30 * 16000]
    st = engine.create_stream(); st.accept_waveform(16000, chunk)
    engine.decode_stream(st, language="chinese")
    line("2 ASR 推理后", base)

    if aligner and st.result.text.strip():
        aligner.align(audio=chunk, text=st.result.text, language="chinese", offset_sec=0.0)
        line("3 Aligner 对齐后(模型已载)", base)

    print("-" * 78)
    # macOS 权威物理内存：footprint 的 phys_footprint(含 Metal 统一内存，Activity Monitor 同源)
    try:
        fp = subprocess.check_output(["footprint", str(os.getpid())], stderr=subprocess.DEVNULL).decode()
        for ln in fp.splitlines():
            if "phys_footprint" in ln.lower():
                print("OS 物理占用:", ln.strip())
    except Exception as e:
        print(f"(footprint 不可用: {e})")
    a, p = mlx_mb()
    print(f"MLX Metal: active {a:.0f} MB / 加载峰值 {p:.0f} MB")
    print(f"进程峰值 RSS(ps口径,低估 Metal): {peak_rss_mb():.1f} MB")
    aon = os.environ.get("CW_ALIGNER_LLM_USE_GPU", "0")
    print(f"(aligner LLM 后端: {'Metal' if aon == '1' else 'CPU'})")
    if aligner and hasattr(aligner, "cleanup"):
        aligner.cleanup()
    engine.cleanup()


if __name__ == "__main__":
    main()
