# 快速开始

本指南将帮助您在 5-10 分钟内快速上手 CapsWriter Offline。

## 前提条件

- 已完成[安装指南](installation.md)中的环境配置
- 已下载并配置好语音识别模型

## 第一步：启动服务端

在项目根目录下运行：

```bash
python scripts/start_server.py
```

成功启动后，您应该看到类似以下输出：

```
CapsWriter Offline Server
项目地址：https://github.com/HaujetZhao/CapsWriter-Offline
当前基文件夹：/path/to/CapsWriter-Offline
绑定的服务地址：127.0.0.1:6016
```

## 第二步：启动客户端

在另一个终端窗口中运行：

```bash
python scripts/start_client.py
```

客户端启动后会显示使用提示和快捷键说明。

## 第三步：开始语音识别

### 麦克风模式

1. 按住 `Caps Lock` 键（默认快捷键）
2. 对着麦克风说话
3. 松开按键，识别结果会自动输入到当前活动窗口

### 文件转录模式

```bash
python scripts/start_client.py /path/to/audio/file.wav
```

## 热词配置

您可以通过编辑以下文件来自定义热词替换：

- `data/hot-zh.txt`：中文热词
- `data/hot-en.txt`：英文热词  
- `data/hot-rule.txt`：替换规则

文件格式示例：

```
# data/hot-zh.txt
人工智能->AI
机器学习->ML

# data/hot-en.txt
artificial intelligence->AI
machine learning->ML
```

## 常见问题

### Q: 按键没有响应怎么办？

A: 
1. 检查快捷键配置是否正确
2. 在 macOS 上需要给终端应用授予辅助功能权限
3. 确保客户端已成功连接到服务端

### Q: 识别准确率不高怎么办？

A: 
1. 确保麦克风音质良好
2. 在安静环境中进行录音
3. 通过热词文件添加专业术语

### Q: 如何修改快捷键？

A: 编辑 `src/capswriter/config.py` 中的 `ClientConfig.shortcut` 参数。

## 下一步

- 了解[系统架构](architecture.md)
- 查看完整的配置选项
- 学习如何自定义热词和替换规则