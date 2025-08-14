# CapsWriter Offline 文档

## 项目简介

CapsWriter Offline 是一个支持离线运行的语音转写工具，提供了完整的客户端和服务端功能。

## 核心特性

- **离线运行**：无需联网即可进行语音识别
- **客户端服务端分离**：支持分布式部署
- **多平台支持**：兼容 Windows、macOS 和 Linux
- **热词替换**：支持自定义热词和替换规则
- **多种输出格式**：支持文本、SRT字幕等格式

## 快速导航

- [安装指南](installation.md)
- [快速开始](quickstart.md)
- [系统架构](architecture.md)

## 项目结构

```
CapsWriter-Offline/
├── src/                    # 源代码
│   ├── capswriter/         # 主包
│   │   ├── client/         # 客户端模块
│   │   ├── server/         # 服务端模块
│   │   └── utils/          # 通用工具
│   └── capswriter_client_only/  # 独立客户端
├── docs/                   # 文档
├── tests/                  # 测试
├── scripts/                # 启动脚本
└── assets/                 # 资源文件
```

## 联系我们

项目地址：[GitHub](https://github.com/HaujetZhao/CapsWriter-Offline)