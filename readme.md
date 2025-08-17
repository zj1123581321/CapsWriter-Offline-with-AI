# CapsWriter-Offline

![CapsWriter Logo](assets/image-20240108115946521.png)

**一个完全离线的 PC 端语音输入和字幕转录工具，现已支持 AI 校对润色功能**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

## ✨ 主要功能

- **🎤 实时语音输入**：按下 `Caps Lock` 键开始录音，松开后立即识别并输入结果
- **📁 文件转录**：拖拽音视频文件即可生成 SRT 字幕和文本转录
- **🔒 完全离线**：无需联网，保护隐私，支持无限时长录音
- **🤖 AI 校对润色**：可选的 AI 驱动文本校对和润色功能
- **📝 智能日志系统**：自动记录转录历史，便于问题定位和分析

## 🚀 核心特性

### 语音识别
- ✅ **完全离线运行** - 无需联网，保护数据隐私
- ✅ **低延迟高准确率** - 基于阿里巴巴 Paraformer 模型
- ✅ **中英混输支持** - 智能识别中英文混合语音
- ✅ **实时语音输入** - 支持长按和单击两种录音模式

### 文本处理
- ✅ **AI 校对润色** - 可选的基于 OpenAI API 的文本校对
- ✅ **热词自定义** - 支持动态热词替换和专业术语
- ✅ **自动格式化** - 智能数字转换和中英文间距调整
- ✅ **标点符号处理** - 基于 CT-Transformer 的智能标点添加

### 输出功能
- ✅ **多种输出模式** - 支持直接输入、剪贴板和文件输出
- ✅ **日记功能** - 基于关键词的自动分类记录
- ✅ **转录日志** - 结构化记录原始转录和 AI 校对结果
- ✅ **SRT 字幕生成** - 音视频文件转录支持

### 系统兼容
- ✅ **跨平台支持** - Windows、macOS、Linux 全平台兼容
- ✅ **客户端-服务端分离** - 支持分布式部署和多客户端
- ✅ **灵活配置** - 丰富的配置选项和自定义功能

## 📖 视频教程

[CapsWriter-Offline 电脑端离线语音输入工具](https://www.bilibili.com/video/BV1tt4y1d75s/)

## 🏗️ 系统架构

CapsWriter-Offline 采用客户端-服务端分离的架构设计：

```
┌─────────────────┐    WebSocket    ┌─────────────────┐
│     客户端       │ ◄──────────────► │     服务端       │
│                 │                 │                 │
│ • 音频采集       │                 │ • 语音识别       │
│ • 快捷键监听     │                 │ • 文本后处理     │
│ • AI校对润色     │                 │ • 模型管理       │
│ • 结果输出       │                 │ • WebSocket服务  │
└─────────────────┘                 └─────────────────┘
```

### 目录结构

```
CapsWriter-Offline/
├── src/                        # 源代码
│   ├── capswriter/             # 主包
│   │   ├── client/             # 客户端模块
│   │   │   ├── core.py         # 客户端核心逻辑
│   │   │   └── utils/          # 客户端工具函数
│   │   │       ├── ai_enhancer.py         # AI校对模块
│   │   │       ├── client_stream.py       # 音频流处理
│   │   │       ├── client_shortcut_handler.py  # 快捷键处理
│   │   │       └── ...
│   │   ├── server/             # 服务端模块
│   │   │   ├── core.py         # 服务端核心逻辑
│   │   │   └── utils/          # 服务端工具函数
│   │   │       ├── server_recognize.py    # 语音识别逻辑
│   │   │       ├── server_init_recognizer.py  # 识别器初始化
│   │   │       └── ...
│   │   ├── utils/              # 通用工具
│   │   │   ├── hot_sub_zh.py   # 中文热词替换
│   │   │   ├── hot_sub_en.py   # 英文热词替换
│   │   │   ├── transcription_logger.py  # 转录日志
│   │   │   └── ...
│   │   └── config.py           # 配置文件
├── scripts/                    # 启动脚本
│   ├── start_server.py         # 服务端启动脚本
│   ├── start_client.py         # 客户端启动脚本
│   └── transcribe_cmd.py       # 命令行转录脚本
├── docs/                       # 项目文档
│   ├── architecture.md         # 系统架构文档
│   └── ...
├── data/                       # 数据文件
│   ├── hot_zh.txt             # 中文热词文件
│   ├── hot_en.txt             # 英文热词文件
│   ├── hot_rule.txt           # 自定义规则文件
│   ├── keyword.txt            # 关键词文件
│   └── ai_ref_word.txt        # AI参考词文件
├── models/                     # 模型文件目录
├── logs/                       # 转录日志目录
├── tests/                      # 测试文件
├── assets/                     # 资源文件
├── requirements-server.txt     # 服务端依赖
├── requirements-client.txt     # 客户端依赖
└── .env.example               # 环境变量示例
```

## 🛠️ 安装和配置

### 快速开始

#### 1. 下载模型文件

服务端使用以下模型：
- **语音识别模型**：[sherpa-onnx-paraformer-zh](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-paraformer/paraformer-models.html)（约 230MB）
- **标点符号模型**：[CT-Transformer](https://www.modelscope.cn/models/damo/punc_ct-transformer_cn-en-common-vocab471067-large-onnx/summary)（约 1GB）

**下载地址：**
- 百度网盘: https://pan.baidu.com/s/1zNHstoWZDJVynCBz2yS9vg 提取码: eu4c
- GitHub Release: [Releases](https://github.com/HaujetZhao/CapsWriter-Offline/releases)

下载后解压到项目根目录的 `models` 文件夹中。

#### 2. 环境配置

**Python 版本要求**：Python 3.8 - 3.10（推荐 3.9）

**安装依赖**：

```bash
# 服务端依赖
pip install -r requirements-server.txt

# 客户端依赖  
pip install -r requirements-client.txt
```

**Linux 额外配置**：
```bash
sudo apt-get install xclip  # 剪贴板支持
```

**macOS 注意事项**：
- ARM 芯片的 MacBook 需要从源码编译 sherpa-onnx
- 可能需要 `brew install protobuf` 解决依赖问题
- 客户端需要 sudo 权限运行

#### 3. AI 校对功能配置（可选）

如需使用 AI 校对功能，请配置环境变量：

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置以下变量：
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # 或其他兼容的 API 地址
OPENAI_MODEL=gpt-4o-mini  # 或其他支持的模型
```

### 运行方式

#### 方式一：使用启动脚本（推荐）

```bash
# 启动服务端
python scripts/start_server.py

# 启动客户端（新终端窗口）
python scripts/start_client.py
```

#### 方式二：直接运行核心模块

```bash
# 启动服务端
python -m src.capswriter.server.core

# 启动客户端（新终端窗口）
python -m src.capswriter.client.core
```

#### Linux 一键启动

```bash
# 使用提供的启动脚本
./run.sh
```

#### macOS 注意事项

```bash
# 客户端需要 sudo 权限
sudo python scripts/start_client.py
```

### 配置说明

编辑 `src/capswriter/config.py` 文件可以自定义以下设置：

#### 服务端配置 (ServerConfig)
```python
addr = '0.0.0.0'          # 服务端监听地址
port = '6016'             # 服务端端口
format_num = True         # 是否将中文数字转为阿拉伯数字
format_punc = True        # 是否启用标点符号引擎
format_spell = True       # 是否调整中英文间距
```

#### 客户端配置 (ClientConfig)
```python
# 连接配置
addr = '127.0.0.1'        # 服务端地址
port = '6016'             # 服务端端口

# 快捷键配置
shortcut = 'caps lock'    # 录音快捷键
hold_mode = True          # True: 长按模式, False: 单击模式
suppress = False          # 是否阻塞按键事件
restore_key = True        # 是否恢复按键状态
threshold = 0.3           # 录音触发阈值（秒）

# 输出配置
paste = True              # 是否通过剪贴板粘贴输出
restore_clip = True       # 是否恢复剪贴板内容

# 音频配置
save_audio = False        # 是否保存录音文件
audio_name_len = 20       # 录音文件名包含的识别结果字数

# 功能开关
hot_zh = False            # 中文热词替换
hot_en = False            # 英文热词替换  
hot_rule = False          # 自定义规则替换
hot_kwd = False           # 关键词日记功能
ai_enhancement = True     # AI校对润色功能
enable_transcription_log = True  # 转录日志记录

# AI 配置
ai_context_segments = 5   # AI 上下文段数
```

## 📚 功能详解

### 🎯 热词替换

支持三种热词替换方式：

#### 中文热词 (`data/hot_zh.txt`)
基于拼音匹配，每行一个热词：
```
我家鸽鸽
特斯拉
```

#### 英文热词 (`data/hot_en.txt`)  
基于字母拼写匹配，每行一个热词：
```
ChatGPT
GitHub
```

#### 自定义规则 (`data/hot_rule.txt`)
自定义替换规则，格式为 `原文 = 替换文本`：
```
毫安时 = mAh
人工智能 = AI
```

热词文件修改后会自动重新加载，支持 `#` 开头的注释行。

### 📝 关键词日记

在 `data/keyword.txt` 中定义关键词，当识别结果以关键词开头时，会保存到对应的分类文件中：

```
健康
重要  
学习
工作
```

例如说"健康今天跑步30分钟"，会保存到 `2025/202501/20250117-健康.md` 文件中。

### 🤖 AI 校对润色

AI 校对功能特点：
- **上下文感知**：结合前序转录结果提供上下文
- **智能校对**：纠正语音识别错误，改善表达
- **可选功能**：可随时开启或关闭
- **错误处理**：AI 服务异常时自动降级到原始文本
- **性能统计**：显示 AI 处理耗时

### 📊 转录日志系统

自动记录所有转录结果，便于问题定位：

**日志结构**：`logs/年份/yyyymm/yyyymmdd.log`
```
logs/
├── 2025/
│   ├── 202501/
│   │   ├── 20250117.log
│   │   └── 20250118.log
└── 2024/
```

**日志格式**：JSON 格式，每行一条记录
```json
{
  "timestamp": 1705483200.0,
  "datetime": "2025-01-17 12:00:00", 
  "task_id": "abc123",
  "original_text": "你好世界",
  "ai_enhanced_text": "你好，世界！",
  "transcription_delay": 1.25,
  "ai_duration": 0.85,
  "has_ai_enhancement": true
}
```

### 🎬 文件转录

支持拖拽音视频文件进行批量转录：

**支持格式**：MP3、WAV、MP4、AVI、MOV、MKV 等

**输出文件**：
- `*.json` - 包含字级时间戳的详细数据
- `*.txt` - 分行转录结果
- `*.merge.txt` - 带标点的完整文本
- `*.srt` - 标准字幕文件

**字幕校正**：修改 txt 文件后重新拖拽，可更新 srt 字幕文件。

## ⚙️ 高级配置

### 环境变量

支持通过环境变量或 `.env` 文件配置：

```bash
# AI 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# 服务配置
CAPSWRITER_SERVER_ADDR=0.0.0.0
CAPSWRITER_SERVER_PORT=6016
```

### 分布式部署

客户端和服务端可分别部署：

1. **服务端**：部署在性能较好的机器上，负责语音识别
2. **客户端**：部署在工作机器上，负责音频采集和结果输出
3. **配置连接**：修改客户端配置中的服务端地址

### 系统集成

#### Windows
- 支持隐藏窗口启动（使用 VBS 脚本）
- 支持开机自启动
- 内置 FFmpeg 支持

#### Linux  
- 需要 xclip 支持剪贴板操作
- 客户端需要 root 权限监听全局按键
- 提供 run.sh 一键启动脚本

#### macOS
- 默认快捷键改为 `right shift`（CapsLock 监听问题）
- 客户端需要 sudo 权限
- 可能需要手动编译部分依赖

## 🔧 开发和调试

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_hot_sub.py
```

### 日志调试

- **命令行日志**：实时显示在终端
- **转录日志**：保存在 `logs/` 目录，用于问题定位
- **详细调试**：修改配置文件中的 debug 选项

### 性能优化

- **内存优化**：通过 `empty_working_set.py` 释放内存
- **并发处理**：支持多任务异步处理
- **模型量化**：使用 int8 量化模型减少内存占用

## 📦 打包部署

### 源码打包

```bash
# 使用 PyInstaller 打包
pyinstaller build.spec
```

### Docker 部署

参考社区版本：[Garonix/CapsWriter-Offline](https://github.com/Garonix/CapsWriter-Offline/tree/docker-support)

### GUI 版本

带系统托盘的 GUI 版本：[H1DDENADM1N/CapsWriter-Offline](https://github.com/H1DDENADM1N/CapsWriter-Offline/tree/GUI-(PySide6)-and-Portable-(PyStand))

## 🤝 社区和支持

### 相关项目

- **原项目**：[HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline)
- **GUI 版本**：[H1DDENADM1N/CapsWriter-Offline](https://github.com/H1DDENADM1N/CapsWriter-Offline)
- **Docker 版本**：[Garonix/CapsWriter-Offline](https://github.com/Garonix/CapsWriter-Offline)

### 技术栈

- **语音识别**：[sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/index.html) + Paraformer
- **标点符号**：CT-Transformer
- **AI 校对**：OpenAI API 兼容接口
- **界面框架**：Rich Console + 命令行
- **网络通信**：WebSocket
- **跨平台**：Python + 平台特定依赖

### 许可证

本项目基于 MIT 许可证开源。

### 致谢

感谢以下开源项目：
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) - 语音识别引擎
- [Paraformer](https://www.modelscope.cn/models/damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch) - 阿里巴巴语音识别模型
- [CT-Transformer](https://www.modelscope.cn/models/damo/punc_ct-transformer_cn-en-common-vocab471067-large-onnx) - 标点符号模型

## 💝 打赏支持

如果这个项目对你有帮助，欢迎打赏支持：

![sponsor](assets/sponsor.jpg)