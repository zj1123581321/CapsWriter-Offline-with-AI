# FunASR-ONNX 兼容性说明

## 问题背景

本项目使用的 `funasr-onnx==0.4.1` 版本与项目中的模型文件存在一些兼容性问题。我们采用了 **自动修补 + Monkey Patch** 的混合策略来解决这些问题，在首次运行时自动应用，无需用户手动干预。

## 兼容性问题列表

### 1. SenseVoiceSmall 导入 torch 问题

**问题描述：**
- `funasr-onnx` 的 `__init__.py` 无条件导入 `SenseVoiceSmall` 模块
- `SenseVoiceSmall` 模块需要 `torch`，但本项目只使用 ONNX 推理，不需要 torch
- 导致导入 `funasr_onnx` 时直接失败

**解决方案：**
- 首次运行时自动修补虚拟环境中的 `funasr_onnx/__init__.py`
- 将无条件导入改为 try-except 包装，使 `SenseVoiceSmall` 成为可选导入

### 2. CT_Transformer 配置格式不兼容

**问题描述：**
- `funasr-onnx` 的 `punc_bin.py` 硬编码期望配置格式：`config["model_conf"]["punc_list"]`
- 但本项目的标点模型 YAML 文件中，`punc_list` 在顶层

**解决方案：**
- 首次运行时自动修补 `funasr_onnx/punc_bin.py`
- 添加兼容代码，支持两种配置格式
- 同时提供 Monkey Patch 作为备用方案

### 3. 缺少 config.yaml 文件

**问题描述：**
- 标点模型目录中配置文件名为 `punc.yaml`
- 但 `funasr-onnx` 硬编码要求 `config.yaml`

**解决方案：**
- 启动时自动检测，如果 `config.yaml` 不存在，从 `punc.yaml` 创建副本

### 4. 缺少 tokens.json 文件

**问题描述：**
- `funasr-onnx` 要求 `tokens.json` 文件
- 但模型的 token_list 在 YAML 文件中

**解决方案：**
- 启动时自动从 YAML 提取 token_list 并生成 `tokens.json`

## 补丁实现

补丁代码位于：`src/capswriter/server/utils/funasr_onnx_patch.py`

### 补丁策略

采用 **双层保护机制**：

1. **文件自动修补**（首次运行时一次性修改）
   - 修补 `funasr_onnx/__init__.py`
   - 修补 `funasr_onnx/punc_bin.py`

2. **Monkey Patch**（运行时动态修改）
   - 作为备用方案
   - 在文件修补失败时生效

### 主要函数

#### `apply_funasr_onnx_patches()`
应用所有兼容性补丁，包括：
- 修复 SenseVoiceSmall 导入问题（文件修补）
- 修复 punc_bin 配置读取问题（文件修补）
- 修复 CT_Transformer 配置读取问题（Monkey Patch 备用）

#### `ensure_model_files()`
确保模型文件完整性，自动生成缺失的文件：
- 创建 `config.yaml`（如果不存在）
- 生成 `tokens.json`（如果不存在）

#### `_patch_sensevoice_import()`
自动修补 `funasr_onnx/__init__.py`：
```python
# 修补前
from .sensevoice_bin import SenseVoiceSmall

# 修补后
try:
    from .sensevoice_bin import SenseVoiceSmall
except ImportError:
    SenseVoiceSmall = None
```

#### `_patch_punc_bin()`
自动修补 `funasr_onnx/punc_bin.py`：
```python
# 修补前
self.punc_list = config["model_conf"]["punc_list"]

# 修补后
if "model_conf" in config and "punc_list" in config["model_conf"]:
    self.punc_list = config["model_conf"]["punc_list"]
elif "punc_list" in config:
    self.punc_list = config["punc_list"]
else:
    raise KeyError("Cannot find punc_list in config")
```

## 使用方法

补丁会在服务端启动时自动应用，**完全无需用户手动操作**。

启动服务端：
```bash
python scripts/start_server.py
```

或使用虚拟环境：
```bash
./venv/Scripts/python.exe scripts/start_server.py
```

### 首次运行

首次运行时，你会看到：
```
应用兼容性补丁...
兼容性补丁应用完成

模块加载中…
```

补丁会自动：
1. 修补 `funasr_onnx/__init__.py`
2. 修补 `funasr_onnx/punc_bin.py`
3. 生成缺失的模型配置文件

### 后续运行

由于补丁具有幂等性，后续运行会快速检测到文件已修补，直接跳过。

## 技术优势

### ✅ 优点

1. **自动化程度高**：首次运行时自动应用，用户无感知
2. **幂等性强**：多次运行不会重复修补或报错
3. **可维护性高**：所有补丁代码集中在项目中
4. **易于调试**：补丁逻辑清晰，修补后的代码有明确注释
5. **版本控制友好**：补丁代码纳入版本控制
6. **可恢复性**：重新安装 funasr-onnx 即可恢复原始状态

### ⚠️ 注意事项

1. **首次运行会修改虚拟环境文件**：为了解决导入问题，必须在导入前修补文件
2. **重装 funasr-onnx 后需重新运行**：重新安装会恢复原始文件，需要再次运行服务端来重新应用补丁
3. **版本锁定**：建议锁定 `funasr-onnx==0.4.1` 版本，避免升级后补丁失效

## 依赖要求

```txt
funasr-onnx==0.4.1
sherpa-onnx==1.12.14
kaldi-native-fbank>=1.22.3
PyYAML>=5.1.2
```

## 工作流程

### 启动流程

1. **应用补丁**（`server_init_recognizer.py:51-55`）
   ```python
   apply_funasr_onnx_patches()  # 自动修补第三方包
   ensure_model_files()          # 生成缺失的配置文件
   ```

2. **导入模块**（`server_init_recognizer.py:58-76`）
   ```python
   import sherpa_onnx
   import funasr_onnx  # 此时已修补，可以正常导入
   from funasr_onnx import CT_Transformer
   ```

3. **加载模型**
   - SenseVoice / Paraformer / FireRed 模型
   - 标点模型（如果需要）

### 补丁应用逻辑

```
启动服务端
    ↓
检测 funasr_onnx/__init__.py
    ↓
需要修补? ──Yes──→ 修补文件 ──→ 清除模块缓存
    ↓ No
检测 funasr_onnx/punc_bin.py
    ↓
需要修补? ──Yes──→ 修补文件
    ↓ No
应用 Monkey Patch（备用）
    ↓
生成缺失的模型配置文件
    ↓
继续正常启动
```

## 故障排查

### 如果提示 "缺少 funasr_onnx 模块"

**可能原因：**
- funasr-onnx 未安装
- 虚拟环境未激活

**解决方法：**
```bash
# 在虚拟环境中安装
./venv/Scripts/pip.exe install funasr-onnx==0.4.1
```

### 如果提示 "导入错误详情: No module named 'torch'"

**可能原因：**
- 补丁未生效（首次运行被中断）
- funasr-onnx 被重新安装

**解决方法：**
```bash
# 重新运行服务端，补丁会自动重新应用
python scripts/start_server.py
```

### 如果标点模型加载失败

**可能原因：**
- 标点模型文件不完整
- config.yaml 或 tokens.json 生成失败

**解决方法：**
1. 确认标点模型目录存在：`models/punc_ct-transformer_cn-en/`
2. 检查 `punc.yaml` 文件是否存在
3. 确认 PyYAML 已安装：`pip install PyYAML`
4. 手动删除 `config.yaml` 和 `tokens.json`，重新运行服务端

### 如果想恢复原始 funasr-onnx

```bash
# 重新安装即可恢复
./venv/Scripts/pip.exe uninstall -y funasr-onnx
./venv/Scripts/pip.exe install funasr-onnx==0.4.1
```

## 测试结果

### Paraformer 模式
```
✓ 兼容性补丁应用完成
✓ Paraformer 模型载入完成
✓ 模型加载耗时 3.89s
✓ 开始服务
```

### SenseVoice 模式
```
✓ 兼容性补丁应用完成
✓ SenseVoice 模型载入完成 (已自带标点符号)
✓ 模型加载耗时 4.22s
✓ 开始服务
```

## 未来改进

### 如果 funasr-onnx 后续版本修复了这些问题

可以考虑：
1. 升级 funasr-onnx 版本
2. 在补丁代码中添加版本检测
3. 对新版本跳过补丁应用
4. 更新文档

### 可能的优化方向

1. **减少文件修改**：探索更优雅的导入拦截机制（如 import hooks）
2. **版本兼容**：支持多个 funasr-onnx 版本
3. **错误恢复**：自动检测修补失败并回滚

---

## 快速参考

| 问题 | 解决方案 | 方式 |
|------|---------|------|
| SenseVoiceSmall 需要 torch | 修补 `__init__.py`，使其可选导入 | 文件修补 |
| punc_list 配置格式不兼容 | 修补 `punc_bin.py`，兼容两种格式 | 文件修补 |
| 缺少 config.yaml | 从 punc.yaml 自动生成 | 文件生成 |
| 缺少 tokens.json | 从 YAML 提取并生成 | 文件生成 |

**关键点：**
- ✅ 首次运行时自动应用
- ✅ 幂等性，多次运行不出错
- ✅ 无需用户手动操作
- ⚠️ 会修改虚拟环境文件（不可避免）
