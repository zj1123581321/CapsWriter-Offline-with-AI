# ASR 负载均衡代理

当有多台机器都在运行 CapsWriter Server 时，可以启动 ASR WebSocket 代理，把下游客户端连接到代理端口，由代理按任务把音频分发到不同后端。

## 适用场景

- 批量文件转录，需要同时利用多台 Mac / PC 的 ASR 算力。
- 下游客户端已经按 `AudioMessage` / `RecognitionMessage` 协议接入，只想通过改连接地址扩容。
- 后端 Server 地址固定，暂不需要运行中动态增删机器。

## 启动步骤

1. 在每台后端机器启动普通 CapsWriter Server，例如监听 `6016`：

```bash
python start_server.py
```

2. 在代理所在机器编辑根目录 `config_proxy.py`：

```python
class ProxyConfig:
    listen_addr = "0.0.0.0"
    listen_port = 6020

    backends = [
        "ws://mac-studio.local:6016",
        "ws://mac-mini.local:6016",
        "ws://pc.local:6016",
    ]

    max_connect_failures = 3
    log_level = "DEBUG"
```

3. 启动代理：

```bash
python start_proxy.py
```

4. 下游客户端把连接地址从单台 Server 改成代理地址：

```python
URI = "ws://<proxy-host>:6020"
```

代理协议完全兼容现有服务端。客户端仍然发送 `AudioMessage`，接收 `RecognitionMessage`，不需要额外握手或代理专用字段。

## 路由规则

- 每个新的 `task_id` 会创建一条独立的后端 WebSocket 连接。
- 同一个 `task_id` 后续所有音频帧都会走同一个后端连接。
- 不同 `task_id` 会按后端 `active_tasks` 计数选择当前最空闲的后端。
- 多个后端负载相同时，按 `config_proxy.py` 中的配置顺序选择。
- 收到后端返回的最终 `RecognitionMessage`（`is_final=true`）后，代理关闭该任务的后端连接并释放负载计数。

之所以每个任务独立连接，是因为 Server 端音频缓存绑定在每条 WebSocket 连接上，不按 `task_id` 隔离。代理不会复用后端连接。

## 故障处理

- 代理不使用 ping/pong 健康检查，避免后端推理阻塞事件循环时误判。
- 新任务连接后端失败会累加 `consecutive_failures`。
- 连续失败达到 `max_connect_failures` 后，该后端标记为 unhealthy，后续新任务不会再分配给它。
- 所有后端都 unhealthy 时，代理会关闭客户端连接并返回 WebSocket code `1013`。
- 任务进行中后端断开时，代理关闭客户端连接；v1 不缓存音频，需要下游重新发起该任务。

## 日志

代理复用项目的日志系统，日志文件为：

```text
logs/proxy_latest.log
```

日志会记录新任务路由到哪个后端、后端连接失败次数、任务释放后的活跃任务数等信息。

## 验证

单元与轻量集成测试：

```bash
python -m pytest tests/test_proxy_*.py -q
```

真实端到端验证时，先启动至少一台后端 Server 和代理，再让验证脚本连接代理：

```bash
python scripts/_verify_dictation.py --server ws://localhost:6020
```

