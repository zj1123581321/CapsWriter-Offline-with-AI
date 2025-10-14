"""
测试 SenseVoice 模型初始化方法
"""
import sherpa_onnx
from pathlib import Path

# 测试路径
model_path = Path('models') / 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17' / 'model.int8.onnx'
tokens_path = Path('models') / 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17' / 'tokens.txt'

print("正在测试 SenseVoice 初始化方法...")
print(f"模型路径: {model_path}")
print(f"Tokens路径: {tokens_path}")

# 方法1: 使用 from_nemo_ctc (因为 SenseVoice 是 CTC 模型)
try:
    print("\n测试方法1: OfflineRecognizer.from_nemo_ctc()")
    recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
        model=str(model_path),
        tokens=str(tokens_path),
        num_threads=6,
        sample_rate=16000,
        feature_dim=80,
        decoding_method='greedy_search',
        debug=False,
        provider='cpu'
    )
    print("✓ 方法1 成功!")
except Exception as e:
    print(f"✗ 方法1 失败: {e}")

# 方法2: 使用配置对象手动构建
try:
    print("\n测试方法2: 使用 OfflineRecognizerConfig 手动构建")

    # 创建模型配置
    nemo_config = sherpa_onnx.offline_recognizer.OfflineNemoEncDecCtcModelConfig(
        model=str(model_path)
    )

    # 创建整体模型配置
    model_config = sherpa_onnx.offline_recognizer.OfflineModelConfig(
        nemo_ctc=nemo_config,
        tokens=str(tokens_path),
        num_threads=6,
        provider='cpu',
        debug=False
    )

    # 创建特征提取器配置
    feat_config = sherpa_onnx.offline_recognizer.OfflineFeatureExtractorConfig(
        sampling_rate=16000,
        feature_dim=80
    )

    # 创建识别器配置
    config = sherpa_onnx.offline_recognizer.OfflineRecognizerConfig(
        feat_config=feat_config,
        model_config=model_config,
        decoding_method='greedy_search'
    )

    # 创建识别器
    recognizer = sherpa_onnx.OfflineRecognizer(config)
    print("✓ 方法2 成功!")
except Exception as e:
    print(f"✗ 方法2 失败: {e}")

print("\n测试完成!")
