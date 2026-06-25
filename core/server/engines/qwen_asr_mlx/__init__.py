# coding: utf-8
"""
qwen_asr_mlx: Apple MLX 版 Qwen3-ASR 引擎（仅 Apple Silicon）。

与 qwen_asr_gguf 是同一模型（Qwen3-ASR）的不同推理后端：
  - qwen_asr_gguf: ONNX encoder + llama.cpp(GGUF) decoder，跨平台
  - qwen_asr_mlx : Apple MLX / Metal，原生 GPU，仅 arm64 macOS

适配层极薄：把推理委托给第三方包 mlx-qwen3-asr 的 Session API，
能力声明 [ASR, PUNC]，字级时间戳交外挂 Aligner（与 GGUF 版一致）。
"""
from .. import logger  # noqa: F401
