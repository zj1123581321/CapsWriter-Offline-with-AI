# CapsWriter-Offline 开发指南
risk-tier: internal

## 核心设计 (Core Design)
**"快、准、稳、离线"**
- **离线 (Offline)**: 全本地模型 (ASR, 标点, LLM)，保护隐私。
- **C/S 架构**:
    - **Server**: 主进程处理 WebSocket，**独立子进程** (`multiprocessing.Process`) 运行 AI 模型，确保推理（CPU密集）不阻塞网络心跳。
    - **Client**: 轻量启动，负责全局快捷键监听、录音采集、UI 展示。
- **源代码开放**: 入口 [`start_server.py`](start_server.py) / [`start_client.py`](start_client.py) 为冻结入口；核心源码在 [`core/`](core/) 目录，发行版保留为源码供用户修改。
- **配置化**: [`config_client.py`](config_client.py) / [`config_server.py`](config_server.py) 及 `hot*.txt`、[`LLM/*.py`](LLM/) 位于根目录。
- **版本**: v2.5-alpha（2026-04-28）

## 架构细节与流程 (Architecture & Workflows)
详见 [`docs/architecture-workflows.md`](docs/architecture-workflows.md)。

## 关键路径 (Key Paths)
详见 [`docs/key-paths.md`](docs/key-paths.md)。

## 打包与部署 (Build)
详见 [`docs/build.md`](docs/build.md)。

## 测试 (Testing)
详见 [`docs/testing.md`](docs/testing.md)。

## 模型支持 (Models)
详见 [`docs/models.md`](docs/models.md)。

## LLM 提供商支持 (LLM Providers)
详见 [`docs/llm-providers.md`](docs/llm-providers.md)。

## 数据流 (Data Flow)
详见 [`docs/data-flow.md`](docs/data-flow.md)。

## 用户偏好 (User Preferences)
- **语言**: 中文 (Chinese)，总结、Plan、WalkThrough、注释都要用中文。
- **环境**: 运行环境是 `conda activate c`，或用 `D:/anaconda3/envs/c/python.exe` 或 `conda run -n c` 执行。所有的临时 Python 代码要先写到临时脚本文件，再运行，而不要直接用命令行跑代码。临时脚本用完不要删。

