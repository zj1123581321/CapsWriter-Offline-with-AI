# coding: utf-8
"""
FunASR-ONNX 兼容性补丁

此模块通过 monkey patch 的方式修复 funasr-onnx 0.4.1 与项目的兼容性问题，
无需修改虚拟环境中的第三方包文件。
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_funasr_onnx_patches():
    """
    应用 funasr-onnx 的兼容性补丁

    修复的问题：
    1. SenseVoiceSmall 导入 torch 的问题
    2. CT_Transformer 配置格式兼容性问题

    注意：此方法会在首次运行时自动修补虚拟环境中的文件
    """
    try:
        # 修复 SenseVoiceSmall 导入问题
        _patch_sensevoice_import()

        # 修复 punc_bin.py 配置读取问题
        _patch_punc_bin()

        # 修复 CT_Transformer 配置读取问题（Monkey Patch 方式）
        _patch_ct_transformer_config()

        logger.info("FunASR-ONNX 补丁应用成功")
        return True
    except Exception as e:
        logger.error(f"应用 FunASR-ONNX 补丁失败: {e}")
        return False


def _patch_sensevoice_import():
    """
    修复 funasr_onnx 导入 SenseVoiceSmall 时需要 torch 的问题

    不修改源文件，而是通过自动修补虚拟环境中的文件（运行时一次性修改）
    """
    try:
        import sys
        import importlib.util

        # 找到 funasr_onnx 的 __init__.py 路径
        spec = importlib.util.find_spec('funasr_onnx')
        if spec is None or spec.origin is None:
            logger.warning("找不到 funasr_onnx 模块")
            return

        init_file = spec.origin

        # 读取原始内容
        with open(init_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # 检查是否需要修补
        if 'SenseVoiceSmall = None' in original_content:
            # 已经修补过了
            return

        # 检查是否有无条件的 SenseVoiceSmall 导入
        if 'from .sensevoice_bin import SenseVoiceSmall' in original_content:
            # 创建修补后的内容
            patched_content = original_content.replace(
                'from .sensevoice_bin import SenseVoiceSmall',
                '''# SenseVoiceSmall 需要 torch，设为可选导入
try:
    from .sensevoice_bin import SenseVoiceSmall
except ImportError:
    SenseVoiceSmall = None'''
            )

            # 写回文件（运行时一次性修改）
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(patched_content)

            logger.info("已自动修补 funasr_onnx/__init__.py（首次运行时自动应用）")

            # 如果已经导入过，需要重新加载
            if 'funasr_onnx' in sys.modules:
                del sys.modules['funasr_onnx']

    except Exception as e:
        logger.warning(f"自动修补 SenseVoiceSmall 导入失败: {e}")
        logger.warning("将使用备用方案...")


def _patch_punc_bin():
    """
    修补 punc_bin.py 文件，兼容不同的配置格式
    """
    try:
        import importlib.util

        # 找到 funasr_onnx 的 punc_bin.py 路径
        spec = importlib.util.find_spec('funasr_onnx.punc_bin')
        if spec is None or spec.origin is None:
            logger.warning("找不到 funasr_onnx.punc_bin 模块")
            return

        punc_bin_file = spec.origin

        # 读取原始内容
        with open(punc_bin_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # 检查是否需要修补
        if '兼容不同的配置格式' in original_content:
            # 已经修补过了
            return

        # 检查是否有硬编码的 config["model_conf"]["punc_list"]
        if 'self.punc_list = config["model_conf"]["punc_list"]' in original_content:
            # 创建修补后的内容
            patched_content = original_content.replace(
                'self.punc_list = config["model_conf"]["punc_list"]',
                '''# 兼容不同的配置格式
        if "model_conf" in config and "punc_list" in config["model_conf"]:
            self.punc_list = config["model_conf"]["punc_list"]
        elif "punc_list" in config:
            self.punc_list = config["punc_list"]
        else:
            raise KeyError("Cannot find punc_list in config")'''
            )

            # 写回文件
            with open(punc_bin_file, 'w', encoding='utf-8') as f:
                f.write(patched_content)

            logger.info("已自动修补 funasr_onnx/punc_bin.py（首次运行时自动应用）")

    except Exception as e:
        logger.warning(f"自动修补 punc_bin.py 失败: {e}")


def _patch_ct_transformer_config():
    """
    修复 CT_Transformer 的配置读取问题，兼容不同的 YAML 格式
    """
    try:
        from funasr_onnx.punc_bin import CT_Transformer

        # 保存原始的 __init__ 方法
        original_init = CT_Transformer.__init__

        def patched_init(self, *args, **kwargs):
            # 调用原始 __init__，但捕获 KeyError
            try:
                original_init(self, *args, **kwargs)
            except KeyError as e:
                if 'punc_list' in str(e):
                    # 重新读取配置，使用兼容的方式获取 punc_list
                    model_dir = args[0] if args else kwargs.get('model_dir')
                    if model_dir:
                        from funasr_onnx.utils.utils import read_yaml
                        config_file = os.path.join(model_dir, "config.yaml")
                        config = read_yaml(config_file)

                        # 兼容不同的配置格式
                        if "model_conf" in config and "punc_list" in config["model_conf"]:
                            self.punc_list = config["model_conf"]["punc_list"]
                        elif "punc_list" in config:
                            self.punc_list = config["punc_list"]
                        else:
                            raise KeyError("Cannot find punc_list in config")

                        # 初始化 period
                        self.period = 0
                        for i in range(len(self.punc_list)):
                            if self.punc_list[i] == ",":
                                self.punc_list[i] = "，"
                            elif self.punc_list[i] == "?":
                                self.punc_list[i] = "？"
                            elif self.punc_list[i] == "。":
                                self.period = i

                        logger.info("已应用 CT_Transformer 配置兼容性补丁")
                else:
                    raise

        # 替换 __init__ 方法
        CT_Transformer.__init__ = patched_init

    except ImportError:
        logger.warning("无法导入 CT_Transformer，跳过补丁")
    except Exception as e:
        logger.warning(f"修复 CT_Transformer 配置读取失败: {e}")


def ensure_model_files():
    """
    确保模型文件完整性，自动生成缺失的文件
    """
    from ...config import ModelPaths

    punc_model_dir = Path(ModelPaths.punc_model_dir)

    if not punc_model_dir.exists():
        logger.warning(f"标点模型目录不存在: {punc_model_dir}")
        return False

    # 1. 确保 config.yaml 存在
    config_yaml = punc_model_dir / "config.yaml"
    punc_yaml = punc_model_dir / "punc.yaml"

    if not config_yaml.exists() and punc_yaml.exists():
        logger.info("正在创建 config.yaml 链接...")
        try:
            # Windows 上使用复制，Linux/Mac 使用符号链接
            import shutil
            import platform

            if platform.system() == 'Windows':
                shutil.copy2(punc_yaml, config_yaml)
            else:
                config_yaml.symlink_to(punc_yaml)

            logger.info("config.yaml 创建成功")
        except Exception as e:
            logger.error(f"创建 config.yaml 失败: {e}")
            return False

    # 2. 确保 tokens.json 存在
    tokens_json = punc_model_dir / "tokens.json"

    if not tokens_json.exists():
        logger.info("正在生成 tokens.json...")
        try:
            import yaml

            with open(config_yaml, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            token_list = config.get('token_list', [])

            with open(tokens_json, 'w', encoding='utf-8') as f:
                json.dump(token_list, f, ensure_ascii=False, indent=2)

            logger.info(f"tokens.json 生成成功，包含 {len(token_list)} 个 tokens")
        except Exception as e:
            logger.error(f"生成 tokens.json 失败: {e}")
            return False

    return True
