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
    """
    try:
        # 修复 SenseVoiceSmall 导入问题
        _patch_sensevoice_import()

        # 修复 CT_Transformer 配置读取问题
        _patch_ct_transformer_config()

        logger.info("FunASR-ONNX 补丁应用成功")
        return True
    except Exception as e:
        logger.error(f"应用 FunASR-ONNX 补丁失败: {e}")
        return False


def _patch_sensevoice_import():
    """
    修复 funasr_onnx 导入 SenseVoiceSmall 时需要 torch 的问题
    """
    try:
        import funasr_onnx

        # 检查是否已经有 SenseVoiceSmall 属性
        if not hasattr(funasr_onnx, 'SenseVoiceSmall'):
            # 尝试导入，失败则设为 None
            try:
                from funasr_onnx.sensevoice_bin import SenseVoiceSmall
                funasr_onnx.SenseVoiceSmall = SenseVoiceSmall
            except ImportError:
                funasr_onnx.SenseVoiceSmall = None
                logger.info("SenseVoiceSmall 需要 torch，已设为可选导入")
    except Exception as e:
        logger.warning(f"修复 SenseVoiceSmall 导入失败: {e}")


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
