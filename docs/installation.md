# 安装指南

## 系统要求

- Python 3.8+
- 操作系统：Windows 10+、macOS 10.14+、Ubuntu 18.04+

## 环境准备

### 1. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. 安装依赖

```bash
# 服务端依赖
pip install -r requirements-server.txt

# 客户端依赖  
pip install -r requirements-client.txt
```

## 模型文件

服务端需要下载语音识别模型文件，请按照以下步骤：

1. 下载模型文件（具体链接请参考原始项目文档）
2. 将模型文件放置在指定目录
3. 运行服务端时会自动检查模型文件

## 配置说明

### 服务端配置

编辑 `src/capswriter/config.py` 中的 `ServerConfig` 类：

```python
class ServerConfig:
    addr = '127.0.0.1'      # 服务地址
    port = '6016'           # 服务端口
    format_num = True       # 数字格式化
    format_punc = True      # 标点符号
    format_spell = True     # 空格调整
```

### 客户端配置

编辑 `src/capswriter/config.py` 中的 `ClientConfig` 类：

```python
class ClientConfig:
    addr = '127.0.0.1'      # 服务器地址
    port = '6016'           # 服务器端口
    shortcut = 'caps lock'  # 快捷键
    hold_mode = True        # 长按模式
    paste = True            # 粘贴模式
```

## 验证安装

运行以下命令验证安装是否成功：

```bash
# 启动服务端
python scripts/start_server.py

# 启动客户端
python scripts/start_client.py
```