# coding: utf-8
"""
单文件独立转录客户端 —— 拷走即用。

将本脚本复制到任意有 Python 的设备，配合 CapsWriter-Offline ASR 服务端，
即可转录本地音频并生成 srt / txt / json 字幕文件。

依赖（pip 安装）：
  pip install soundfile numpy websockets

可选系统依赖：
  ffmpeg —— 输入非 16kHz 单声道 wav 或其它格式（mp3/m4a/flac 等）时需安装。

用法示例：
  # 转录单个文件（默认连 ws://localhost:6016，旁路生成 .srt）
  python3 transcribe_client.py recording.wav

  # 批量转录目录下所有音频
  python3 transcribe_client.py ./podcasts/ --format all --out-dir ./subs/

  # 指定远端服务端（Tailscale / 局域网）
  python3 transcribe_client.py interview.mp3 --server ws://192.168.1.10:6016
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Literal, Optional

import numpy as np
import soundfile as sf
import websockets

# ---------------------------------------------------------------------------
# 内联协议（与 core/protocol.py 字段名、默认值、序列化行为对齐）
# ---------------------------------------------------------------------------

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.opus'}
DEFAULT_SERVER = 'ws://localhost:6016'
SRT_SOFT_LIMIT = 18


@dataclass
class AudioMessage:
    task_id: str
    source: Literal['mic', 'file']
    data: str
    is_final: bool
    time_start: float
    seg_duration: float = 15.0
    seg_overlap: float = 2.0
    context: str = ''
    language: str = 'auto'

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> AudioMessage:
        return cls(
            task_id=data['task_id'],
            source=data['source'],
            data=data['data'],
            is_final=data['is_final'],
            time_start=data['time_start'],
            seg_duration=data.get('seg_duration', 15.0),
            seg_overlap=data.get('seg_overlap', 2.0),
            context=data.get('context', ''),
            language=data.get('language', 'auto'),
        )


@dataclass
class RecognitionMessage:
    task_id: str
    is_final: bool
    duration: float
    time_start: float
    time_submit: float
    time_complete: float
    text: str
    text_accu: str = ''
    tokens: List[str] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RecognitionMessage:
        return cls(
            task_id=data['task_id'],
            is_final=data['is_final'],
            duration=data['duration'],
            time_start=data['time_start'],
            time_submit=data['time_submit'],
            time_complete=data['time_complete'],
            text=data['text'],
            text_accu=data.get('text_accu', ''),
            tokens=data.get('tokens', []),
            timestamps=data.get('timestamps', []),
        )


# ---------------------------------------------------------------------------
# 音频装载
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str | None:
    return shutil.which('ffmpeg')


def _ffmpeg_to_float32(path: Path) -> tuple[np.ndarray, int]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('需要 ffmpeg 转码，但系统未找到 ffmpeg 可执行文件')
    cmd = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(path),
        '-f', 'f32le', '-acodec', 'pcm_f32le', '-ac', '1', '-ar', '16000',
        '-',
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f'ffmpeg 转码失败: {err or proc.returncode}')
    raw = proc.stdout
    if len(raw) % 4 != 0:
        raise RuntimeError('ffmpeg 输出字节数不是 float32 对齐')
    audio = np.frombuffer(raw, dtype='<f4').copy()
    return audio, 16000


def _is_16k_mono_wav(path: Path) -> bool:
    if path.suffix.lower() != '.wav':
        return False
    try:
        info = sf.info(str(path))
    except Exception:
        return False
    return info.samplerate == 16000 and info.channels == 1


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """装载音频为 16kHz 单声道 float32。"""
    if _is_16k_mono_wav(path):
        audio = sf.read(str(path), dtype='float32')[0]
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio.astype(np.float32), 16000
    return _ffmpeg_to_float32(path)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _fmt_timestamp(t: float) -> str:
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def write_srt(message: RecognitionMessage, out: Path) -> None:
    ts, tokens = message.timestamps, message.tokens
    if not tokens:
        out.write_text('', encoding='utf-8')
        return
    lines: list[str] = []
    idx, buf, start = 1, '', None
    for i, (w, t) in enumerate(zip(tokens, ts)):
        if start is None:
            start = t
        buf += w
        end_seg = (
            w in '。！？!?'
            or (len(buf.strip()) >= SRT_SOFT_LIMIT and w in '，、,;；')
        )
        if end_seg or i == len(tokens) - 1:
            end = ts[i + 1] if i + 1 < len(ts) else t + 0.5
            if buf.strip():
                lines.append(f'{idx}\n{_fmt_timestamp(start)} --> {_fmt_timestamp(end)}\n{buf.strip()}\n')
                idx += 1
            buf, start = '', None
    out.write_text('\n'.join(lines), encoding='utf-8')


def write_txt(message: RecognitionMessage, out: Path) -> None:
    out.write_text(message.text, encoding='utf-8')


def write_json(message: RecognitionMessage, out: Path) -> None:
    out.write_text(message.to_json(), encoding='utf-8')


def save_outputs(
    audio_path: Path,
    message: RecognitionMessage,
    out_dir: Path | None,
    fmt: str,
) -> None:
    base_dir = out_dir if out_dir else audio_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem
    fmts = {'srt', 'txt', 'json'} if fmt == 'all' else {fmt}
    if 'srt' in fmts:
        write_srt(message, base_dir / f'{stem}.srt')
    if 'txt' in fmts:
        write_txt(message, base_dir / f'{stem}.txt')
    if 'json' in fmts:
        write_json(message, base_dir / f'{stem}.json')


# ---------------------------------------------------------------------------
# 输入收集
# ---------------------------------------------------------------------------

def collect_input_paths(items: list[str]) -> list[Path]:
    found: list[Path] = []
    for item in items:
        p = Path(item)
        if not p.exists():
            raise FileNotFoundError(str(p))
        if p.is_dir():
            for f in sorted(p.rglob('*')):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                    found.append(f)
        elif p.suffix.lower() in AUDIO_EXTENSIONS:
            found.append(p)
    return found


# ---------------------------------------------------------------------------
# 转录
# ---------------------------------------------------------------------------

async def transcribe_file(
    audio_path: Path,
    *,
    server: str = DEFAULT_SERVER,
    seg_duration: float = 60.0,
    seg_overlap: float = 4.0,
    language: str = 'auto',
    timeout: float = 900.0,
) -> RecognitionMessage | None:
    audio, sr = load_audio(audio_path)
    raw = audio.astype('<f4').tobytes()
    dur = len(audio) / sr
    task_id = str(uuid.uuid1())
    common = dict(
        task_id=task_id,
        source='file',
        time_start=time.time(),
        seg_duration=seg_duration,
        seg_overlap=seg_overlap,
        context='',
        language=language,
    )
    deadline = time.monotonic() + timeout
    try:
        async with websockets.connect(server, subprotocols=['binary'], max_size=None) as ws:
            await ws.send(AudioMessage(data=base64.b64encode(raw).decode(), is_final=False, **common).to_json())
            await ws.send(AudioMessage(data='', is_final=True, **common).to_json())
            async for resp in ws:
                if time.monotonic() > deadline:
                    print(f'✗ 超时 ({timeout}s): {audio_path.name}')
                    return None
                rm = RecognitionMessage.from_dict(json.loads(resp))
                print(f'  [{audio_path.name}] 进度 {rm.duration:.1f}s / {dur:.1f}s', end='\r')
                if rm.is_final:
                    print()
                    return rm
    except (OSError, websockets.exceptions.WebSocketException) as e:
        print(f'✗ 连接失败 {audio_path.name}: {e}')
        return None
    print(f'\n✗ 连接结束但未收到最终结果: {audio_path.name}')
    return None


async def _run_batch(
    paths: list[Path],
    *,
    server: str,
    seg_duration: float,
    seg_overlap: float,
    language: str,
    out_dir: Path | None,
    fmt: str,
    timeout: float,
) -> tuple[list[Path], list[tuple[Path, str]], list[tuple[Path, str]]]:
    ok: list[Path] = []
    failed: list[tuple[Path, str]] = []
    env_errors: list[tuple[Path, str]] = []
    for i, path in enumerate(paths, 1):
        print(f'\n[{i}/{len(paths)}] 转录: {path}')
        try:
            load_audio(path)
        except RuntimeError as e:
            reason = str(e)
            print(f'✗ 装载失败: {reason}')
            env_errors.append((path, reason))
            continue
        except Exception as e:
            reason = f'装载失败: {e}'
            print(f'✗ {reason}')
            env_errors.append((path, reason))
            continue
        msg = await transcribe_file(
            path,
            server=server,
            seg_duration=seg_duration,
            seg_overlap=seg_overlap,
            language=language,
            timeout=timeout,
        )
        if msg is None:
            failed.append((path, '转录失败或无最终结果'))
            continue
        save_outputs(path, msg, out_dir, fmt)
        print(f'✓ 完成: {path.name} → {msg.text[:60]}...' if len(msg.text) > 60 else f'✓ 完成: {path.name} → {msg.text}')
        ok.append(path)
    return ok, failed, env_errors


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='单文件独立转录客户端 —— 连接 CapsWriter ASR 服务端转录本地音频',
    )
    p.add_argument('inputs', nargs='+', help='音频文件或目录（目录递归枚举音频）')
    p.add_argument('--server', default=DEFAULT_SERVER, help=f'WebSocket 服务端地址（默认 {DEFAULT_SERVER}）')
    p.add_argument('--language', default='auto', help='识别语言（auto/chinese/english/...）')
    p.add_argument('--seg-duration', type=float, default=60.0, help='分段长度（秒，默认 60）')
    p.add_argument('--seg-overlap', type=float, default=4.0, help='分段重叠（秒，默认 4）')
    p.add_argument('--format', choices=['srt', 'txt', 'json', 'all'], default='srt',
                   help='输出格式（默认 srt）')
    p.add_argument('--out-dir', default=None, help='输出目录（默认与音频同目录）')
    p.add_argument('--timeout', type=float, default=900.0, help='单文件转录超时（秒，默认 900）')
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        paths = collect_input_paths(args.inputs)
    except FileNotFoundError as e:
        print(f'✗ 路径不存在: {e}')
        return 2
    if not paths:
        print('✗ 未找到可转录的音频文件')
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else None
    print(f'共 {len(paths)} 个文件，服务端 {args.server}')
    ok, failed, env_errors = asyncio.run(_run_batch(
        paths,
        server=args.server,
        seg_duration=args.seg_duration,
        seg_overlap=args.seg_overlap,
        language=args.language,
        out_dir=out_dir,
        fmt=args.format,
        timeout=args.timeout,
    ))
    print('\n========== 汇总 ==========')
    print(f'成功: {len(ok)}')
    for p in ok:
        print(f'  ✓ {p}')
    if env_errors:
        print(f'环境/装载错误: {len(env_errors)}')
        for p, reason in env_errors:
            print(f'  ✗ {p} ({reason})')
    print(f'失败: {len(failed)}')
    for p, reason in failed:
        print(f'  ✗ {p} ({reason})')
    if env_errors:
        return 2
    if failed:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
