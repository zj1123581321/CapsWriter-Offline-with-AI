## 数据流 (Data Flow)
```
[Microphone] -> sounddevice callback -> asyncio.Queue
   |
   v  (ShortcutManager 检测按键)
[AudioStreamManager] 开始录音 -> WebSocketManager 发送 AudioMessage (base64 chunks)
   |
   v  (WebSocket, 子协议 "binary")
[Server: SocketManager] -> ws_recv -> AudioCache 切片 -> Task -> multiprocessing.Queue
   |
   v
[Worker 子进程: RecognizerWorker]
   |-- TaskPipeline: 音频预处理 -> ASR 解码 -> 文本合并 -> 格式化
   |-- 输出两路结果: text (简单合并) + text_accu (时间戳去重)
   |
   v
[Server: ws_send] -> RecognitionMessage -> WebSocket -> Client
   |
   v
[Client: ResultProcessor]
   |-- 音素热词纠正 (FastRAG + AccuRAG)
   |-- 正则规则替换 (hot-rule.txt)
   |-- LLM 角色检测 -> 上下文组装 -> API 调用 -> 流式输出
   |-- TextOutput 上屏 (type/paste) 或 Toast 显示
   |-- DiaryWriter 日记归档
   |-- UDP 广播识别结果
```

