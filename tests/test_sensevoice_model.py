"""
测试 SenseVoice 模型初始化和基本功能
"""
import sys
import io
from pathlib import Path

# 设置 Windows 下的标准输出编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

import sherpa_onnx
from capswriter.config import SenseVoiceArgs, ServerConfig

def test_sensevoice_init():
    """测试 SenseVoice 模型初始化"""
    print("=" * 60)
    print("测试 SenseVoice 模型初始化")
    print("=" * 60)

    # 检查 sherpa-onnx 版本
    print(f"\n✓ sherpa-onnx 版本: {sherpa_onnx.__version__}")

    # 显示配置信息
    print(f"\n配置信息:")
    print(f"  - 当前选择模型: {ServerConfig.model_type}")
    print(f"  - 模型路径: {SenseVoiceArgs.model}")
    print(f"  - Tokens路径: {SenseVoiceArgs.tokens}")
    print(f"  - 线程数: {SenseVoiceArgs.num_threads}")
    print(f"  - 语言模式: {SenseVoiceArgs.language}")

    # 检查模型文件是否存在
    model_path = Path(SenseVoiceArgs.model)
    tokens_path = Path(SenseVoiceArgs.tokens)

    if not model_path.exists():
        print(f"\n✗ 错误: 模型文件不存在: {model_path}")
        return False
    else:
        print(f"\n✓ 模型文件存在: {model_path}")

    if not tokens_path.exists():
        print(f"✗ 错误: Tokens文件不存在: {tokens_path}")
        return False
    else:
        print(f"✓ Tokens文件存在: {tokens_path}")

    # 尝试初始化模型
    print(f"\n正在初始化 SenseVoice 模型...")
    try:
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            **{key: value for key, value in SenseVoiceArgs.__dict__.items() if not key.startswith('_')}
        )
        print("✓ SenseVoice 模型初始化成功!")
        return True
    except Exception as e:
        print(f"✗ 模型初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_sensevoice_init()
    print("\n" + "=" * 60)
    if success:
        print("✓ 测试通过!")
    else:
        print("✗ 测试失败!")
    print("=" * 60)
    sys.exit(0 if success else 1)
