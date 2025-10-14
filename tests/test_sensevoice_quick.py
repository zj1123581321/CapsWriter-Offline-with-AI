"""
快速测试 SenseVoice 模型初始化（不依赖完整服务端）
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def test_sensevoice():
    print("=" * 70)
    print("快速测试 SenseVoice 模型初始化")
    print("=" * 70)

    # 导入配置
    from capswriter.config import SenseVoiceArgs, ServerConfig

    print(f"\n[INFO] 当前模型类型: {ServerConfig.model_type}")
    print(f"[INFO] 模型路径: {SenseVoiceArgs.model}")
    print(f"[INFO] Tokens路径: {SenseVoiceArgs.tokens}")

    # 检查文件是否存在
    model_path = Path(SenseVoiceArgs.model)
    tokens_path = Path(SenseVoiceArgs.tokens)

    if not model_path.exists():
        print(f"\n[ERROR] 模型文件不存在: {model_path}")
        return False

    if not tokens_path.exists():
        print(f"[ERROR] Tokens文件不存在: {tokens_path}")
        return False

    print(f"\n[OK] 模型文件存在")
    print(f"[OK] Tokens文件存在")

    # 导入 sherpa_onnx
    try:
        import sherpa_onnx
        print(f"\n[OK] sherpa_onnx 版本: {sherpa_onnx.__version__}")
    except ImportError as e:
        print(f"\n[ERROR] 无法导入 sherpa_onnx: {e}")
        return False

    # 初始化模型
    print("\n[INFO] 正在初始化 SenseVoice 模型...")
    t_start = time.time()

    try:
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(SenseVoiceArgs.model),
            tokens=str(SenseVoiceArgs.tokens),
            num_threads=SenseVoiceArgs.num_threads,
            sample_rate=SenseVoiceArgs.sample_rate,
            feature_dim=SenseVoiceArgs.feature_dim,
            decoding_method=SenseVoiceArgs.decoding_method,
            debug=SenseVoiceArgs.debug,
            provider=SenseVoiceArgs.provider,
            language=SenseVoiceArgs.language,
            use_itn=SenseVoiceArgs.use_itn
        )

        t_end = time.time()
        print(f"\n[SUCCESS] SenseVoice 模型初始化成功!")
        print(f"[INFO] 初始化耗时: {t_end - t_start:.2f} 秒")
        return True

    except Exception as e:
        print(f"\n[ERROR] 模型初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_sensevoice()
    print("\n" + "=" * 70)
    if success:
        print("[SUCCESS] 测试通过!")
    else:
        print("[FAILED] 测试失败!")
    print("=" * 70)
    sys.exit(0 if success else 1)
