## 模型支持 (Models)

### ASR 引擎

| 引擎类型 | 类名 | 文件 | 能力 | 说明 |
|---------|------|------|------|------|
| `paraformer` | `ParaformerEngine` | [`engines/paraformer_onnx/`](core/server/engines/paraformer_onnx/) | ASR + TIMESTAMPS | 通过 `sherpa_onnx.OfflineRecognizer`，准确率高 |
| `sensevoice` | `SenseVoiceEngine` | [`engines/sensevoice_onnx/`](core/server/engines/sensevoice_onnx/) | ASR + PUNC + HOTWORDS + TIMESTAMPS | 自有 ONNX 推理，多语言（中英日韩粤） |
| `fun_asr_nano` | `FunASREngine` | [`engines/fun_asr_gguf/`](core/server/engines/fun_asr_gguf/) | ASR + PUNC + HOTWORDS + TIMESTAMPS | GGUF LLM 解码器 + ONNX 编码器/CTC，最准 |
| `qwen_asr` | `QwenASREngine` | [`engines/qwen_asr_gguf/`](core/server/engines/qwen_asr_gguf/) | ASR + PUNC | GGUF 版 Qwen3-ASR 模型 |
| `qwen_asr_mlx` | `QwenASRMLXEngine` | [`engines/qwen_asr_mlx/`](core/server/engines/qwen_asr_mlx/) | ASR + PUNC | Apple MLX/Metal 版 Qwen3-ASR，**仅 Apple Silicon**。推理委托第三方包 `mlx-qwen3-asr` 的 `Session`；薄适配层，延迟导入；模型默认 HF repo id（首次联网下载，`CW_MLX_MODEL` 可指本地目录）。初版不支持 context、不暴露原生时间戳（交外挂 Aligner） |

> **`qwen_asr_mlx` 说明**：与 `qwen_asr`(GGUF) 是同一模型 Qwen3-ASR 的不同后端，Mac 用 MLX 享 GPU 原生加速、Win/Linux 用 GGUF。依赖见 [`requirements-server-macos.txt`](requirements-server-macos.txt)（pin `mlx-qwen3-asr==0.3.5`，保留 `sherpa-onnx`）。验证脚本：[`scripts/_smoke_mlx_subprocess.py`](scripts/_smoke_mlx_subprocess.py)（spawn 子进程冒烟）、[`scripts/_verify_mlx_asr.py`](scripts/_verify_mlx_asr.py)（走 ModelLoader 全链路）。新增 ASR 引擎时除 `factory.py`/`config_server.py` 外，**务必同步改 [`core/server/worker/check_model.py`](core/server/worker/check_model.py)**——它在子进程启动前校验 `model_type`，漏改会 `sys.exit(1)`。

### 辅助模型
- **Punct-CT-Transformer**: 标点模型（`CTTransformerPuncEngine`），引擎无 PUNC 能力时自动加载。
- **QwenForceAligner**: 对齐器（`ManagedAlignerProxy` 延迟加载+闲置卸载），用于文件转录时间戳对齐。仅 `qwen_asr` / `qwen_asr_mlx`（无原生 TIMESTAMPS）会触发；解码器是 GGUF，走 [`engines/llama/`](core/server/engines/llama/) 后端。
  - **macOS 启用**（让 MLX/GGUF 也能做带字级时间戳的文件转录）：① 下载 b7798 macOS 二进制 dylib 放入 `engines/llama/bin/`（见该目录说明 + `xattr -dr com.apple.quarantine`）；② 下载 `Qwen3-ForcedAligner-0.6B.zip` 解压到 `models/Qwen3-ForcedAligner/`；③ 装 `onnxruntime`。**听写（mic）不需要 aligner**，此步仅文件转录字幕需要。
  - **aligner 默认跑 CPU，是文件转录的耗时大头**：Mac 上设环境变量 `CW_ALIGNER_LLM_USE_GPU=1` 让其 GGUF 解码器走 Metal（实测 60s 音频 aligner RTF 0.109→0.047，端到端 0.181→0.118）。RTF 基准脚本：[`scripts/_bench_mlx_rtf.py`](scripts/_bench_mlx_rtf.py)。
  - **内存占用（0.6B，实测 `footprint`/Activity Monitor 口径）**：听写（仅 MLX，MLX 权重 active 1.88GB）常驻 **~3.3GB**；文件转录（MLX + Metal aligner）稳态 ~3GB、按段处理瞬时峰值 **~7GB**。注意 `ps` 的 RSS 在 Metal 统一内存下严重低估，须用 `footprint`。测量脚本：[`scripts/_mem_mlx.py`](scripts/_mem_mlx.py)。

### 引擎能力检测
引擎通过 `EngineCapabilities` 标志位声明能力（`ASR` / `PUNC` / `TIMESTAMPS` / `STREAMING` / `HOTWORDS`）。`ModelLoader` 在加载时智能补丁：若引擎缺少 `PUNC` 则外挂标点模型，若缺少 `TIMESTAMPS` 则外挂对齐器。

