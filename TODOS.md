# TODOS

延期工作清单。每项含背景与起点,便于将来接手。

## MLX Qwen3-ASR 引擎(qwen_asr_mlx)

### [ ] MLX 原生段级时间戳减载 Aligner
- **What:** 调研 `mlx-qwen3-asr` 的段级时间戳能否满足字幕精度;若可,让 `qwen_asr_mlx` 声明 `TIMESTAMPS` 能力,省掉外挂 `ManagedAlignerProxy`。
- **Why:** 初版文件转录靠外挂 Aligner 补字级时间戳,多一次模型加载/对齐开销;MLX `Session.transcribe(return_timestamps=True, return_chunks=True)` 本身能返回 `result.segments`(段级 `text`/`start`)。
- **现状/起点:** 初版决策为 `[ASR, PUNC]` + 外挂 Aligner(与 `qwen_asr_gguf` 一致),因为段级 ≠ 字级、直接暴露会破坏 `text_accu`(字级 token 去重)。改造前需先确认 MLX 段级时间戳能否细化到字级或可接受降级。
- **Depends on:** qwen_asr_mlx 引擎已上线并稳定。

### [ ] MLX 听写续写 context 支持(上游已确认支持)
- **What:** 在 `decode_stream` 里把 `task.context` 通过 `transcribe(audio, context=context, ...)` 传入,与 `qwen_asr_gguf` 的听写续写行为对齐。
- **Why:** GGUF 版在 `decode_stream` 里用 `context` 构造 prompt(`core/server/engines/qwen_asr_gguf/asr_engine.py:67-73`)做分段续写;MLX 初版丢弃了 `context`,相对 GGUF 是行为回归。
- **现状/起点:** **已真机核实 `mlx-qwen3-asr==0.3.5` 的 `Session.transcribe` 签名含 `context: str = ''` 参数,接线只需一行**(`if context: t_kwargs["context"] = context`)。初版按评审决策仍不接(与 paraformer/sensevoice 同级,客户端音素 RAG 热词兜底),留作 v2 增量。需补一条 context 透传的单测。
- **Depends on:** 无(上游已支持);仅需评审放行扩大初版范围。

## ASR 负载均衡代理 (core/proxy/)

### [ ] 设备算力权重路由
- **What:** 路由策略从纯 `active_tasks` 计数升级为加权选择,让算力强的设备接更多任务。
- **Why:** v1 按任务计数做 least-loaded,一个 2 小时文件和一个 5 秒文件都算 1。M1 Max 64GB 和 M2 Pro 16GB 算力差异大,均匀分配不是最优。Codex review 指出此问题。
- **现状/起点:** `BackendState.active_tasks` 是唯一路由依据。可加 `weight: float` 字段到 `config_proxy.py`,路由时按 `active_tasks / weight` 选最小值。
- **Depends on:** 代理已上线并稳定运行。

### [ ] 后端中途故障音频重发
- **What:** 代理缓存当前任务的音频数据,后端断开时自动重发到其他后端,而非让客户端重新发起。
- **Why:** v1 不缓存音频,后端中途挂掉时文件转录需用户重新拖入文件。对 1 万文件批量场景,手动重试不可接受。
- **现状/起点:** `_client_to_backend` 直接转发不缓存。需在 `TaskSession` 中维护 `sent_messages: list` 缓存已发消息,故障时重放到新后端。内存开销约 5MB/分钟音频,需评估。
- **Depends on:** 代理已上线并稳定运行。

### [ ] 动态后端添加/移除
- **What:** 支持运行时通过 API 或信号添加/移除后端,无需重启代理。
- **Why:** v1 需要改 `config_proxy.py` 后重启。设备上下线频繁时不方便。
- **现状/起点:** `ProxyServer.backends` 是启动时固定的列表。可加 UDP 控制接口(类似客户端的 `udp_control`)或 HTTP API。
- **Depends on:** 代理已上线并稳定运行。
