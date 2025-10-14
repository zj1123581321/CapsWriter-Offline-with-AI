"""
测试 FireRed ASR 模型初始化和基本功能
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def test_firered():
    print("=" * 70)
    print("测试 FireRed ASR 模型初始化")
    print("=" * 70)

    # 导入配置
    from capswriter.config import FireRedArgs, ServerConfig

    print(f"\n[INFO] 当前模型类型: {ServerConfig.model_type}")
    print(f"[INFO] Encoder路径: {FireRedArgs.encoder}")
    print(f"[INFO] Decoder路径: {FireRedArgs.decoder}")
    print(f"[INFO] Tokens路径: {FireRedArgs.tokens}")

    # 检查文件是否存在
    encoder_path = Path(FireRedArgs.encoder)
    decoder_path = Path(FireRedArgs.decoder)
    tokens_path = Path(FireRedArgs.tokens)

    if not encoder_path.exists():
        print(f"\n[ERROR] Encoder文件不存在: {encoder_path}")
        return False

    if not decoder_path.exists():
        print(f"[ERROR] Decoder文件不存在: {decoder_path}")
        return False

    if not tokens_path.exists():
        print(f"[ERROR] Tokens文件不存在: {tokens_path}")
        return False

    print(f"\n[OK] Encoder文件存在 ({encoder_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"[OK] Decoder文件存在 ({decoder_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"[OK] Tokens文件存在")

    # 导入 sherpa_onnx
    try:
        import sherpa_onnx
        print(f"\n[OK] sherpa_onnx 版本: {sherpa_onnx.__version__}")
    except ImportError as e:
        print(f"\n[ERROR] 无法导入 sherpa_onnx: {e}")
        return False

    # 初始化模型
    print("\n[INFO] 正在初始化 FireRed ASR 模型...")
    print("[INFO] FireRed 是大型模型，加载时间较长，请耐心等待...")
    t_start = time.time()

    try:
        recognizer = sherpa_onnx.OfflineRecognizer.from_fire_red_asr(
            encoder=str(FireRedArgs.encoder),
            decoder=str(FireRedArgs.decoder),
            tokens=str(FireRedArgs.tokens),
            num_threads=FireRedArgs.num_threads,
            decoding_method=FireRedArgs.decoding_method,
            debug=FireRedArgs.debug,
            provider=FireRedArgs.provider
        )

        t_end = time.time()
        print(f"\n[SUCCESS] FireRed ASR 模型初始化成功!")
        print(f"[INFO] 初始化耗时: {t_end - t_start:.2f} 秒")

        print(f"\n[INFO] 模型特性:")
        print(f"  - 支持语言: 中文、英文")
        print(f"  - 支持方言: 四川话、河南话、天津话等")
        print(f"  - 标点符号: 需要外部 CT-Transformer 模型")

        return True

    except Exception as e:
        print(f"\n[ERROR] 模型初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_firered()
    print("\n" + "=" * 70)
    if success:
        print("[SUCCESS] 测试通过!")
    else:
        print("[FAILED] 测试失败!")
    print("=" * 70)
    sys.exit(0 if success else 1)
