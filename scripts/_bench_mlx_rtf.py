# coding: utf-8
"""
qwen_asr_mlx 端到端 RTF 基准：真实音频走 MLX ASR + 外挂 ForceAligner 全链路。

RTF = 处理耗时 / 音频时长。按段处理(默认 30s/段)以贴近文件转录的分段方式，
并避开对齐器单段超 n_ctx 的降级路径。先做一次预热(排除 Metal/llama 首次 JIT)，
再正式计时，分别报告 ASR / Aligner / 合计。

用法：
    python scripts/_bench_mlx_rtf.py <音频文件> [段长秒,默认30]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CW_MLX_MODEL", "Qwen/Qwen3-ASR-0.6B")
import config_server
config_server.ServerConfig.model_type = "qwen_asr_mlx"

import numpy as np
import soundfile as sf
from core.server.worker.model_loader import ModelLoader


def load_audio(path):
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        n = int(len(audio) * 16000 / sr)
        audio = np.interp(np.linspace(0, len(audio), n, endpoint=False),
                          np.arange(len(audio)), audio).astype(np.float32)
    return audio


def main():
    path = sys.argv[1]
    seg_sec = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    audio = load_audio(os.path.expanduser(path))
    dur = len(audio) / 16000
    seg_len = int(seg_sec * 16000)

    print(f"[bench] 音频: {os.path.basename(path)}  时长 {dur:.1f}s  段长 {seg_sec:.0f}s")
    print("[bench] 加载模型(MLX + 外挂 Aligner)…")
    loader = ModelLoader()
    loader.load()
    engine, aligner = loader.recognizer, loader.aligner
    print(f"[bench] aligner={'已挂载' if aligner else '无'}")

    # 预热：排除首次 Metal/llama JIT
    warm = audio[: 2 * 16000]
    s = engine.create_stream(); s.accept_waveform(16000, warm)
    engine.decode_stream(s, language="chinese")
    if aligner:
        aligner.align(audio=warm, text=s.result.text or "预热", language="chinese", offset_sec=0.0)
    print("[bench] 预热完成，开始正式计时…\n")

    asr_t = 0.0
    align_t = 0.0
    n_tokens = 0
    texts = []
    for i in range(0, len(audio), seg_len):
        chunk = audio[i:i + seg_len]
        if len(chunk) < 1600:
            continue
        st = engine.create_stream(); st.accept_waveform(16000, chunk)
        t0 = time.time(); engine.decode_stream(st, language="chinese"); asr_t += time.time() - t0
        text = st.result.text or ""
        texts.append(text)
        if aligner and text.strip():
            t1 = time.time()
            res = aligner.align(audio=chunk, text=text, language="chinese", offset_sec=0.0)
            align_t += time.time() - t1
            if res and getattr(res, "items", None):
                n_tokens += len(res.items)

    total = asr_t + align_t
    print("识别文本:")
    print("  " + " ".join(texts)[:300])
    print()
    print(f"{'阶段':<14}{'耗时(s)':>10}{'RTF':>10}")
    print(f"{'ASR (MLX)':<14}{asr_t:>10.3f}{asr_t/dur:>10.4f}")
    print(f"{'Aligner':<14}{align_t:>10.3f}{align_t/dur:>10.4f}")
    print(f"{'合计':<14}{total:>10.3f}{total/dur:>10.4f}")
    print(f"\n字级时间戳 token 数: {n_tokens}   (音频 {dur:.1f}s)")
    if aligner and hasattr(aligner, "cleanup"):
        aligner.cleanup()
    engine.cleanup()


if __name__ == "__main__":
    main()
