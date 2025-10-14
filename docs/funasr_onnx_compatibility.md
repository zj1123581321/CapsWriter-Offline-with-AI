# FunASR-ONNX 兼容性说明

## 问题背景

本项目使用的 `funasr-onnx==0.4.1` 版本与项目中的模型文件存在一些兼容性问题。为了保持虚拟环境的纯净，我们采用了 **运行时补丁（Monkey Patch）** 的方式来解决这些问题。

## 兼容性问题列表

### 1. SenseVoiceSmall 导入 torch 问题

**问题描述：**
- `funasr-onnx` 的 `__init__.py` 无条件导入 `SenseVoiceSmall` 模块
- `SenseVoiceSmall` 模块需要 `torch`，但本项目只使用 ONNX 推理，不需要 torch

**解决方案：**
- 在运行时捕获 `ImportError`，将 `SenseVoiceSmall` 设置为可选导入

### 2. CT_Transformer 配置格式不兼容

**问题描述：**
- `funasr-onnx` 期望配置格式为：`config["model_conf"]["punc_list"]`
- 但本项目的标点模型 YAML 文件中，`punc_list` 在顶层

**解决方案：**
- 使用 Monkey Patch 修改 `CT_Transformer.__init__` 方法
- 兼容两种配置格式

### 3. 缺少 config.yaml 文件

**问题描述：**
- 标点模型目录中配置文件名为 `punc.yaml`
- 但 `funasr-onnx` 硬编码要求 `config.yaml`

**解决方案：**
- 启动时自动创建符号链接或复制文件

### 4. 缺少 tokens.json 文件

**问题描述：**
- `funasr-onnx` 要求 `tokens.json` 文件
- 但模型的 token_list 在 YAML 文件中

**解决方案：**
- 启动时自动从 YAML 提取并生成 JSON 文件

## 补丁实现

补丁代码位于：`src/capswriter/server/utils/funasr_onnx_patch.py`

### 主要函数

#### `apply_funasr_onnx_patches()`
应用所有运行时补丁，包括：
- 修复 SenseVoiceSmall 导入问题
- 修复 CT_Transformer 配置读取问题

#### `ensure_model_files()`
确保模型文件完整性，自动生成缺失的文件：
- 创建 `config.yaml`（如果不存在）
- 生成 `tokens.json`（如果不存在）

## 使用方法

补丁会在服务端启动时自动应用，用户无需手动操作。

启动服务端：
```bash
python scripts/start_server.py
```

或使用虚拟环境：
```bash
./venv/Scripts/python.exe scripts/start_server.py
```

## 技术优势

### ✅ 优点

1. **不修改第三方包**：保持虚拟环境纯净
2. **可维护性高**：所有补丁代码集中在项目中
3. **易于调试**：补丁逻辑清晰，便于排查问题
4. **版本控制友好**：补丁代码纳入版本控制
5. **可移植性强**：重新创建虚拟环境后无需手动修复

### ⚠️ 注意事项

1. 补丁使用 Monkey Patch 技术，可能在 funasr-onnx 升级后失效
2. 如果遇到补丁相关的错误，请检查 funasr-onnx 版本
3. 建议锁定 `funasr-onnx==0.4.1` 版本

## 依赖要求

```txt
funasr-onnx==0.4.1
sherpa-onnx==1.12.14
kaldi-native-fbank>=1.22.3
PyYAML>=5.1.2
```

## 故障排查

### 如果补丁应用失败

1. 检查日志输出中的错误信息
2. 确认 funasr-onnx 版本是否正确
3. 检查模型文件是否完整

### 如果模型加载失败

1. 确认标点模型目录存在：`models/punc_ct-transformer_cn-en/`
2. 检查 `punc.yaml` 文件是否存在
3. 确认 PyYAML 已安装

## 未来改进

如果 funasr-onnx 后续版本修复了这些问题，可以考虑：
1. 升级 funasr-onnx 版本
2. 移除补丁代码
3. 更新文档
