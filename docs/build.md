## 打包与部署 (Build)
- [`build.spec`](build.spec): Server + Client 打包。
- [`build-client.spec`](build-client.spec): 仅 Client (Win7兼容)。
- **策略**: 所有 Python 依赖放入 `internal/`。根目录仅保留配置文件、源码入口 ([`start_*.py`](start_server.py))、核心源码 ([`core/`](core/))、模型文件夹 ([`models/`](models/)) 和说明文档。
- **PyInstaller 6.0+**: 使用现代化打包配置，支持 CUDA provider 可选收集。

