## 架构细节与流程 (Architecture & Workflows)

### 1. 识别全链路 (Recognition Flow)
- **采集**: Client 监听快捷键（默认 CapsLock 和 X2）。按下就开始收集录音chunk，超过 **0.3s (Threshold)** 不松则触发识别，**实时流式**通过 WebSocket 发送。
- **切片 (Slicing)**: Client 配置 `mic_seg_duration` (60s) 和 `mic_seg_overlap` (4s)。Server 按时间切片但**切点吸附静音**（[`core/server/connection/segmenter.py`](core/server/connection/segmenter.py)）：名义切点 ±5s 窗口内用 silero-VAD（缺模型时降级 RMS 能量）找人声概率最低的断点下刀，避免硬切在连续语音中间导致对齐器时间戳畸变。file 任务无可信断点时弹性延长至 `seg_max_cut`（72s，须 ≤ 引擎 chunk_size 80s）；mic 任务就地取最优点、不额外等待。不做语义级 VAD 切分以保留完整上下文。
- **Server 处理**:
    - **双重结果**: 同时计算 `text` (简单文本拼接, Robust) 和 `text_accu` (基于 Token 时间戳去重, Precision)。
    - **拼接算法**: `text_accu`使用 **Token 时间戳去重** ([`core/server/merger/`](core/server/merger/))，`text` 使用 **模糊文本匹配**。
- **Client 后处理**:
    - **触发**: 用户**松开按键** -> Server 返回 IsFinal 结果。
    - **热词 (RAG)**: 基于 **音素 (Phoneme)** 的两阶段模糊检索，匹配 `hot.txt`（统一中英文热词）。
    - **规则替换**: `hot-rule.txt` 正则替换。
    - **LLM 润色**: 根据角色配置进行智能润色或回答。
    - **上屏**: 模拟键盘输入或 Toast 显示。

### 2. 客户端模式 (Client Modes)
- **听写 (Dictation)**: 默认模式。按住快捷键 -> 发送音频 -> 松开上屏。
- **转录 (Transcription)**: 拖入文件 -> `ffmpeg` 提取音频 -> 发送 Server -> 接收带时间戳结果 -> 生成 `.srt` / `.txt` / `.json`。

### 3. LLM Agent & 智能修正
- **实时监控 (Hot Reload)**: Client 启动 `watchdog` 文件监视器，实时响应 `hot*.txt` 和 `LLM/*.py` 的修改（3秒防抖）。
- **角色系统**: 模块化的 LLM 角色配置，支持多角色切换。
- **角色触发**: 检测识别结果前缀（如"翻译"、"助理"），匹配 [`LLM/`](LLM/) 下定义的角色。
- **Context 组装**（根据角色配置决定是否启用）:
    1.  **潜在热词**: RAG 检索 `hot.txt`（`enable_hotwords`）。
    2.  **选中文字**: 模拟 Ctrl+C 获取的鼠标选中文本（`enable_read_selection`）。
    3.  **对话历史**: 保留上下文历史记录（`enable_history`）。
    4.  **用户指令**: 当前语音输入内容。
- **输出模式**:
    - **typing**: 直接模拟键盘打字输出。
    - **toast**: 在 Toast 弹窗中显示，支持 Markdown 渲染。
- **UI**: 结果流式显示在 **Toast** (Tkinter 无边框置顶窗)，支持 Markdown 渲染。

### 4. 热词系统 (Hotword System)
- **服务器热词**: `hot-server.txt` 用于服务端热词增强。
- **统一文件**: `hot.txt` 统一管理中英文热词（基于音素匹配）。
- **两阶段检索**:
    1.  **FastRAG**: 倒排索引 + Numba JIT 快速粗筛（减少 90% 计算量）。
    2.  **AccuRAG**: 模糊音权重精确匹配（前后鼻音、平翘舌等）。
- **双阈值机制**:
    - `hot_thresh` (0.85): 高阈值用于实际替换。
    - `hot_similar` (0.6): 低阈值用于 LLM 上下文参考。
- **规则替换**: `hot-rule.txt` 支持正则表达式规则替换 (`pattern = replacement`)。

### 5. 历史归档 (Diary)
- **按日期归档**: `年份/月份/日期.md`。
- **音频**: 原始录音存入 `年份/月份/assets/`，Markdown 中自动生成 HTML 音频控件链接。

### 6. UDP 广播与控制
- **UDP 广播**: 识别结果可通过 UDP 广播到局域网（`udp_broadcast=True`）。
- **UDP 控制**: 支持通过 UDP 命令远程控制录音启停（`udp_control=True`）。

### 7. ASR 负载均衡代理 (Proxy)
- **独立组件**: 不改 Server/Client 代码，代理层在 Server 前面做中转
- **Per-task 路由**: 每个 task_id 独立建后端 WS 连接（Server 的 `AudioCache` 是 per-websocket 的，不能复用连接）
- **Least-connections 路由策略**: 评分公式 `(active_tasks + 1) / weight`，平局时选最久未被选中的后端（`BackendState._last_selected` per-instance 逻辑时钟，不受 unhealthy 后端 cooldown 循环干扰）。支持设备算力权重（`config_proxy.py` 中配置）。processing_latency EWMA（alpha=0.2，异常截断时自动重置）仅用于诊断日志和 `/status` 端点，不参与路由决策
- **网络感知诊断**: 记录任务端到端延迟（连接建立→收到结果）和推理延迟双指标日志，用于诊断网络 vs 推理瓶颈；EWMA 样本过期（默认 300s）自动重置
- **健康检查**: 不用 ping/pong（推理时会阻塞 event loop），用连接失败计数（连续 3 次标记 unhealthy）；后台探活任务定期对 unhealthy 后端做轻量 connect+close（指数退避 60s→120s→300s 封顶），探活成功才恢复 healthy；连接失败时自动重试下一个 healthy 后端，不丢失任务
- **WS 参数**: `max_size=None`, `ping_interval=None`（与 Server 一致）
- **使用方式**: 启动 `start_proxy.py`，客户端改 addr:port 指向代理即可
- **设计文档**: [`docs/designs/proxy-concurrent-routing.md`](docs/designs/proxy-concurrent-routing.md)，[`docs/消费方并发改造指南.md`](docs/消费方并发改造指南.md)

