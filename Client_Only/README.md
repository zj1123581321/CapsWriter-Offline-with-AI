# CapsWriter文件转录模块

这是一个从CapsWriter-Offline项目中提取出来的独立文件转录模块，专门用于将音视频文件转录为文本和字幕。

## 功能特点

- 支持多种音视频格式（mp4, avi, wav等）
- 生成SRT字幕文件、纯文本和JSON详细信息
- 提供同步和异步API，方便集成到其他项目
- 支持配置服务器地址和转录参数
- 简单易用的命令行接口

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 命令行使用

```bash
python transcriber.py 视频文件路径 [--server 服务器地址] [--port 端口号] [--verbose] [--no-srt]
```

例如：

```bash
python transcriber.py D:/Videos/test.mp4 --server 127.0.0.1 --port 6007 --verbose
```

### 2. 作为Python模块导入

#### 基本用法

```python
from Client_Only import transcribe, Config

# 配置服务器
Config.server_addr = "127.0.0.1"
Config.server_port = 6007

# 执行转录
success, files = transcribe("D:/Videos/test.mp4")

if success:
    print(f"转录成功！生成了以下文件:")
    for file in files:
        print(f"  - {file}")
else:
    print("转录失败")
```

#### 通过参数配置

```python
from Client_Only import transcribe

# 通过参数配置
success, files = transcribe(
    "D:/Videos/test.mp4",
    server_addr="127.0.0.1",
    server_port=6007,
    generate_json=False,  # 不生成JSON文件
    generate_merge_txt=False  # 不生成合并文本
)
```

#### 使用异步API

```python
import asyncio
from Client_Only import transcribe_async

async def main():
    success, files = await transcribe_async(
        "D:/Videos/test.mp4",
        server_addr="127.0.0.1",
        server_port=6007
    )
    print(f"转录{'成功' if success else '失败'}")

# 运行异步函数
asyncio.run(main())
```

## 配置项

可以通过`Config`类设置以下配置项：

- `server_addr`: 服务器地址 (默认: "127.0.0.1")
- `server_port`: 服务器端口 (默认: 6007)
- `file_seg_duration`: 转录文件时分段长度 (默认: 25秒)
- `file_seg_overlap`: 转录文件时分段重叠 (默认: 2秒)
- `generate_txt`: 是否生成纯文本文件 (默认: True)
- `generate_merge_txt`: 是否生成合并文本 (默认: True)
- `generate_srt`: 是否生成SRT字幕文件 (默认: True)
- `generate_json`: 是否生成JSON详细信息 (默认: True)
- `verbose`: 是否显示详细日志 (默认: True)

## 注意事项

- 使用前需要确保CapsWriter-Offline服务器已经启动
- 需要安装ffmpeg并添加到系统PATH
- 转录结果将保存在与输入文件相同的目录下

## 示例

请参考`example.py`文件中的示例代码，包括：

1. 基本用法示例
2. 使用参数覆盖配置
3. 异步API使用示例
4. 批量转录示例 