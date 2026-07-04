# coding: utf-8
"""分段切点吸附（segmenter）单元测试。

覆盖：
- pick_cut 纯函数：可信断点选取、多断点取最近、无断点兜底
- CutFinder RMS 降级路径：真实找到合成音频中的静音缝隙
- _submit_segments 弹性策略：file 无断点时等待延长、到上限强制下刀、
  mic 就地下刀不等待、offset 按实际切点累计
- silero-VAD 路径：模型存在时的通路冒烟（缺模型/缺 onnxruntime 自动 skip）
"""

import asyncio
import time

import numpy as np
import pytest

from core.constants import AudioFormat
from core.server.connection import segmenter
from core.server.connection.segmenter import (
    FRAME_SEC, CutFinder, pick_cut,
)
from core.server.connection.ws_recv import AudioCache, _submit_segments
from core.protocol import AudioMessage
from config_server import ServerConfig as Config, ModelPaths

SR = AudioFormat.SAMPLE_RATE


# ---------------------------------------------------------------- pick_cut

def _scores(spec):
    """按 (值, 秒数) 列表生成帧分数序列。"""
    parts = [np.full(int(round(sec / FRAME_SEC)), val, dtype=np.float32)
             for val, sec in spec]
    return np.concatenate(parts)


def test_pick_cut_finds_quiet_run():
    # [0,5s] 语音(0.9)、[5,6s] 静音(0.05)、[6,10s] 语音
    scores = _scores([(0.9, 5), (0.05, 1), (0.9, 4)])
    cut, confident = pick_cut(scores, 0.0, 3.0, 9.0, nominal=6.0,
                              threshold=0.35, min_quiet=0.25)
    assert confident
    assert 5.0 < cut < 6.0          # 静音段中点附近


def test_pick_cut_prefers_run_nearest_nominal():
    # 两段静音：4~4.5s 和 7~7.5s，名义切点 6.8s → 应选后者
    scores = _scores([(0.9, 4), (0.05, 0.5), (0.9, 2.5), (0.05, 0.5), (0.9, 2)])
    cut, confident = pick_cut(scores, 0.0, 3.0, 9.0, nominal=6.8,
                              threshold=0.35, min_quiet=0.25)
    assert confident
    assert 6.9 < cut < 7.6


def test_pick_cut_ignores_too_short_quiet():
    # 静音只有 1 帧（32ms < min_quiet），不算可信断点
    scores = _scores([(0.9, 5), (0.05, FRAME_SEC), (0.9, 5)])
    cut, confident = pick_cut(scores, 0.0, 3.0, 9.0, nominal=6.0,
                              threshold=0.35, min_quiet=0.25)
    assert not confident
    assert 3.0 <= cut <= 9.0        # 兜底仍落在窗口内


def test_pick_cut_fallback_argmin():
    # 无静音，但 7s 处分数相对最低 → 兜底选它
    scores = _scores([(0.9, 7), (0.5, 0.5), (0.9, 2.5)])
    cut, confident = pick_cut(scores, 0.0, 3.0, 9.0, nominal=6.0,
                              threshold=0.35, min_quiet=0.25)
    assert not confident
    assert 6.8 < cut < 7.8


def test_pick_cut_frame_aligned():
    scores = _scores([(0.9, 5), (0.05, 1), (0.9, 4)])
    cut, _ = pick_cut(scores, 0.0, 3.0, 9.0, nominal=6.0,
                      threshold=0.35, min_quiet=0.25)
    n_samples = cut * SR
    assert abs(n_samples - round(n_samples)) < 1e-6   # 整采样点，切片字节对齐


# ---------------------------------------------------------- CutFinder (RMS)

def _rms_finder():
    finder = CutFinder()
    finder._vad_failed = True      # 强制走 RMS 降级路径
    return finder


def _noise_with_gap(total_sec, gap_start, gap_end, amp=0.3):
    rng = np.random.default_rng(42)
    audio = (rng.standard_normal(int(total_sec * SR)) * amp).astype('<f4')
    audio[int(gap_start * SR):int(gap_end * SR)] = 0.0
    return audio


def test_rms_finder_locates_gap():
    audio = _noise_with_gap(12, 6.5, 7.2)
    cut, confident = _rms_finder().find(audio.tobytes(), 4.0, 10.0, nominal=6.0)
    assert confident
    assert 6.5 < cut < 7.2


def test_rms_finder_no_gap_falls_back():
    audio = _noise_with_gap(12, 0, 0)      # 全程无静音
    cut, confident = _rms_finder().find(audio.tobytes(), 4.0, 10.0, nominal=6.0)
    assert not confident
    assert 4.0 <= cut <= 10.0


# ------------------------------------------------------- _submit_segments

class FakeQueue:
    def __init__(self):
        self.tasks = []

    def put(self, task):
        self.tasks.append(task)


def _msg(source, seg_duration=6.0, seg_overlap=1.0):
    return AudioMessage(
        data='', is_final=False, task_id='t1', source=source,
        time_start=time.time(), seg_duration=seg_duration,
        seg_overlap=seg_overlap, context='', language='zh',
    )


@pytest.fixture
def snap_config(monkeypatch):
    """缩小时长参数，用短音频快速验证弹性策略。"""
    monkeypatch.setattr(Config, 'seg_cut_snap', True)
    monkeypatch.setattr(Config, 'seg_search_before', 2.0)
    monkeypatch.setattr(Config, 'seg_search_after', 2.0)
    monkeypatch.setattr(Config, 'seg_max_cut', 10.0)
    monkeypatch.setattr(Config, 'seg_min_quiet', 0.25)
    monkeypatch.setattr(segmenter, '_finder', _rms_finder())


def _run(msg, audio_bytes, cache=None):
    cache = cache or AudioCache()
    cache.chunks += audio_bytes
    cache.byte_count += len(audio_bytes)
    queue = FakeQueue()
    asyncio.run(_submit_segments(msg, cache, queue, 'sock'))
    return cache, queue


def test_file_cuts_at_gap(snap_config):
    # 12s 音频，6.5~7.2s 静音 → 应在缝隙处下刀，offset 按实际切点累计
    audio = _noise_with_gap(12, 6.5, 7.2)
    cache, queue = _run(_msg('file'), audio.tobytes())
    assert len(queue.tasks) == 1
    task = queue.tasks[0]
    assert task.offset == 0.0
    seg_sec = len(task.data) / AudioFormat.BYTES_PER_SECOND
    assert 7.5 < seg_sec < 8.2                 # 切点(6.5~7.2) + overlap 1s
    assert 6.5 < cache.offset < 7.2            # 下一段起点 = 实际切点


def test_file_waits_when_no_gap(snap_config):
    # 9s 连续噪声，无断点：hi=8 < max_cut=10 → 暂不下刀，等更多音频
    audio = _noise_with_gap(9, 0, 0)
    cache, queue = _run(_msg('file'), audio.tobytes())
    assert len(queue.tasks) == 0
    assert cache.search_to > 0                 # 已记录搜索进度

    # 补到 12s（hi 达到 max_cut=10）→ 强制在最低分点下刀
    more = _noise_with_gap(3, 0, 0)
    cache, queue = _run(_msg('file'), more.tobytes(), cache)
    assert len(queue.tasks) == 1
    assert 4.0 <= cache.offset <= 10.0
    assert cache.search_to == 0.0              # 下刀后复位


def test_mic_never_waits(snap_config):
    # mic 同样 9s 无断点：就地取最优点下刀，不等待
    audio = _noise_with_gap(9, 0, 0)
    cache, queue = _run(_msg('mic'), audio.tobytes())
    assert len(queue.tasks) == 1
    assert 4.0 <= cache.offset <= 8.0


def test_snap_disabled_blind_cut(snap_config, monkeypatch):
    # 关闭吸附 → 恢复固定时长盲切（切点=名义 6s）
    monkeypatch.setattr(Config, 'seg_cut_snap', False)
    audio = _noise_with_gap(12, 6.5, 7.2)
    cache, queue = _run(_msg('file'), audio.tobytes())
    assert len(queue.tasks) == 1
    assert cache.offset == 6.0
    seg_sec = len(queue.tasks[0].data) / AudioFormat.BYTES_PER_SECOND
    assert abs(seg_sec - 7.0) < 0.01           # 6s + overlap 1s


# ------------------------------------------------------------- VAD 冒烟

def _vad_available():
    if not ModelPaths.silero_vad_model.exists():
        return False
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _vad_available(), reason='缺 silero-VAD 模型或 onnxruntime')
def test_vad_pipeline_smoke():
    finder = CutFinder()
    audio = _noise_with_gap(12, 6.5, 7.2)
    cut, confident = finder.find(audio.tobytes(), 4.0, 10.0, nominal=6.0)
    assert finder._vad is not None             # 确认走的是 VAD 路径
    assert 4.0 <= cut <= 10.0
    n_samples = cut * SR
    assert abs(n_samples - round(n_samples)) < 1e-6
