# coding: utf-8
"""
听写路径端到端冒烟：发整段音频到运行中的 server，验证识别连通 + 文本 + RTF。

默认 `--source mic`(听写路径，纯 ASR，不触发时间戳/aligner)，验证最常用的麦克风
听写链路。配对脚本 `_verify_file_transcribe.py` 走 `--source file`(文件转录，触发
字级时间戳/aligner + 落 srt)。两者覆盖 server 的两条识别路径。

音频来源二选一：
  --wav <文件>     真实 wav(16bit/32bit PCM，自动转 float32 16k mono)，验证真实识别
  --duration <秒>  无 wav 时合成类语音音频，只验证连通/协议/RTF(识别不出有意义文本)

用法：
    python scripts/_verify_dictation.py --wav <wav> [--server ws://localhost:6016]
    python scripts/_verify_dictation.py --server ws://localhost:6017 --wav <wav>   # 验 MLX 实例
    python scripts/_verify_dictation.py --duration 5                               # 合成音频冒烟

退出码：0=收到 final 结果(连通成功)；1=连接失败/超时。
依赖：numpy websockets(wav 读取用标准库 wave，无需 soundfile)。
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
import wave
from base64 import b64encode

import numpy as np

try:
    import websockets
except ImportError:
    print('请先安装 websockets: pip install websockets')
    sys.exit(1)


def generate_speech_like_audio(duration_sec: float = 3.0, sample_rate: int = 16000) -> np.ndarray:
    """生成模拟语音的 float32 音频(16kHz mono)：基频+泛音+噪声，仅供连通/RTF 测试。"""
    n = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, n, dtype=np.float32)
    audio = (0.3 * np.sin(2 * np.pi * 200 * t)
             + 0.2 * np.sin(2 * np.pi * 400 * t)
             + 0.1 * np.sin(2 * np.pi * 800 * t)
             + 0.05 * np.random.randn(n).astype(np.float32)).astype(np.float32)
    return audio / np.max(np.abs(audio)) * 0.5


def load_wav_as_float32(path: str, target_sr: int = 16000) -> np.ndarray:
    """加载 WAV 转 float32 16k mono(标准库 wave，避免 soundfile 依赖)。"""
    with wave.open(path, 'rb') as wf:
        channels, sampwidth, framerate = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    print(f'WAV: channels={channels}, bits={sampwidth*8}, rate={framerate}')
    if sampwidth == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f'不支持的采样位深: {sampwidth*8} bit')
    if channels > 1:
        audio = audio.reshape(-1, channels)[:, 0]
    if framerate != target_sr:
        new_len = int(len(audio) / framerate * target_sr)
        audio = np.interp(np.linspace(0, len(audio) - 1, new_len),
                          np.arange(len(audio)), audio).astype(np.float32)
    return audio


async def recognize(server_url: str, audio: np.ndarray, source: str) -> bool:
    """发整段音频，接收识别结果，打印文本 + RTF。返回是否收到 final。"""
    task_id = str(uuid.uuid4())
    print(f'连接 {server_url} ... (source={source})')
    t0 = time.time()
    try:
        async with websockets.connect(server_url, subprotocols=['binary']) as ws:
            t_conn = time.time()
            audio_bytes = audio.astype('<f4').tobytes()
            msg = {
                'task_id': task_id, 'source': source,
                'data': b64encode(audio_bytes).decode('ascii'), 'is_final': True,
                'time_start': time.time(), 'seg_duration': 15.0, 'seg_overlap': 2.0,
                'context': '', 'language': 'auto',
            }
            t_send = time.time()
            await ws.send(json.dumps(msg))
            print(f'已发送 {len(audio)/16000:.2f}s 音频, {len(audio_bytes)} bytes')

            t_final, got_final = None, False
            try:
                while True:
                    resp = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    if not isinstance(resp, str):
                        continue
                    data = json.loads(resp)
                    print(f"\n--- 识别结果 (延迟 {time.time()-t_send:.3f}s) ---")
                    print(f"  text     : {data.get('text', '')}")
                    print(f"  text_accu: {data.get('text_accu', '')}")
                    print(f"  is_final : {data.get('is_final', False)}  duration: {data.get('duration', 0):.2f}s")
                    if data.get('is_final', False):
                        t_final, got_final = time.time(), True
                        break
            except asyncio.TimeoutError:
                print('✗ 等待响应超时 (30s)')
                return False

            audio_dur = len(audio) / 16000
            print('\n=== 性能统计 ===')
            print(f'  音频时长 : {audio_dur:.2f}s ; 连接 {t_conn-t0:.3f}s ; 首响 {t_final-t_send:.3f}s')
            print(f'  RTF      : {(t_final-t_send)/audio_dur:.3f} (< 1.0 = 实时)')
            return got_final
    except (ConnectionRefusedError, OSError) as e:
        print(f'✗ 连接失败: {type(e).__name__}: {e}')
        return False
    except Exception as e:
        print(f'✗ 错误: {type(e).__name__}: {e}')
        return False


def main() -> int:
    p = argparse.ArgumentParser(description='听写路径端到端冒烟客户端')
    p.add_argument('--server', default='ws://localhost:6016', help='服务端地址(默认 6016)')
    p.add_argument('--wav', default=None, help='WAV 文件路径(不传则用合成音频)')
    p.add_argument('--duration', type=float, default=3.0, help='合成音频时长(秒)')
    p.add_argument('--source', choices=['mic', 'file'], default='mic',
                   help="任务类型：mic=听写(默认,纯ASR)/file=文件转录(触发时间戳/aligner)")
    args = p.parse_args()

    if args.wav:
        audio = load_wav_as_float32(args.wav)
    else:
        audio = generate_speech_like_audio(args.duration)
        print(f'使用合成音频: {args.duration}s（仅验连通/RTF，识别不出有意义文本）')

    ok = asyncio.run(recognize(args.server, audio, args.source))
    print('\n✓ 听写路径连通验证通过' if ok else '\n✗ 未收到 final 结果')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
