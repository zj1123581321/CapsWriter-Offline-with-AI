# TODOS

延期工作清单。每项含背景与起点,便于将来接手。

## MLX Qwen3-ASR 引擎(qwen_asr_mlx)

### [ ] MLX 原生段级时间戳减载 Aligner
- **What:** 调研 `mlx-qwen3-asr` 的段级时间戳能否满足字幕精度;若可,让 `qwen_asr_mlx` 声明 `TIMESTAMPS` 能力,省掉外挂 `ManagedAlignerProxy`。
- **Why:** 初版文件转录靠外挂 Aligner 补字级时间戳,多一次模型加载/对齐开销;MLX `Session.transcribe(return_timestamps=True, return_chunks=True)` 本身能返回 `result.segments`(段级 `text`/`start`)。
- **现状/起点:** 初版决策为 `[ASR, PUNC]` + 外挂 Aligner(与 `qwen_asr_gguf` 一致),因为段级 ≠ 字级、直接暴露会破坏 `text_accu`(字级 token 去重)。改造前需先确认 MLX 段级时间戳能否细化到字级或可接受降级。
- **Depends on:** qwen_asr_mlx 引擎已上线并稳定。

### [ ] MLX 听写续写 context 支持
- **What:** 查 `mlx-qwen3-asr` 的 `Session.transcribe` 是否支持 prompt/context 注入;若支持,把 `task.context` 映射进去,与 `qwen_asr_gguf` 的听写续写行为对齐。
- **Why:** GGUF 版在 `decode_stream` 里用 `context` 构造 prompt(`core/server/engines/qwen_asr_gguf/asr_engine.py:67-73`)做分段续写;MLX 初版丢弃了 `context`,相对 GGUF 是行为回归。
- **现状/起点:** 初版决策不支持 context(与 paraformer/sensevoice 同级,客户端音素 RAG 热词兜底)。真机验 `transcribe()` 签名时顺便查 prompt/context 参数。
- **Depends on:** 上游 `mlx-qwen3-asr` API 支持 prompt 注入。
