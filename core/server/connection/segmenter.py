# coding: utf-8
"""
分段切点吸附模块

固定时长盲切会把刀口剁在连续语音中间，第二段开头是"半个词"，外挂强制
对齐器（ForceAligner）会把段头的字吸附到段边界，再经单调化插值摊开，
产生数秒级的虚假时间跨度（详见 temp/字幕时间戳错位诊断.md）。

本模块在名义切点附近寻找"最不像人声"的位置下刀：
- 首选 silero-VAD（ONNX，~2.3MB）的逐帧人声概率，背景音乐骗不了它；
- 模型文件缺失或 onnxruntime 不可用时，降级为 RMS 能量检测并告警；
- 两者都基于 32ms 帧网格，返回的切点已对齐到帧边界。

本模块运行在服务端网络主进程中，`CutFinder.find()` 是同步阻塞调用
（VAD 推理 CPU 开销约为音频时长的 2%~5%），调用方必须放入线程池执行，
不可阻塞 event loop。
"""

from __future__ import annotations

import threading
from typing import List, Optional, Tuple

import numpy as np

from config_server import ServerConfig as Config, ModelPaths
from core.constants import AudioFormat
from .. import logger


# 帧长：512 采样点 @16kHz = 32ms，与 silero-VAD 的原生分帧一致
FRAME_SAMPLES = 512
FRAME_SEC = FRAME_SAMPLES / AudioFormat.SAMPLE_RATE
# VAD 是有状态模型，从切点搜索窗前额外多喂 1 秒音频预热内部状态
WARMUP_SEC = 1.0


class SileroVAD:
    """silero-VAD ONNX 推理封装（兼容 v5 / v4 两代输入布局）。

    每次 probs() 调用使用独立的初始状态，无跨调用可变状态，
    多线程并发调用是安全的（onnxruntime session.run 本身线程安全）。
    """

    def __init__(self, model_path: str):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = ort.InferenceSession(
            model_path, sess_options=opts, providers=['CPUExecutionProvider']
        )
        input_names = {i.name for i in self.session.get_inputs()}
        if 'state' in input_names:
            self._layout = 'v5'      # input[1, 64+512] + state(2,1,128) + sr
        elif 'h' in input_names and 'c' in input_names:
            self._layout = 'v4'      # input[1, 512] + h/c(2,1,64) + sr
        else:
            raise RuntimeError(f'无法识别的 silero-VAD 模型输入布局: {input_names}')

    def probs(self, samples: np.ndarray) -> np.ndarray:
        """对 float32 单声道 16k 音频逐帧计算人声概率，帧长 32ms。"""
        n_frames = len(samples) // FRAME_SAMPLES
        result = np.zeros(n_frames, dtype=np.float32)
        sr = np.array(AudioFormat.SAMPLE_RATE, dtype=np.int64)

        if self._layout == 'v5':
            state = np.zeros((2, 1, 128), dtype=np.float32)
            context = np.zeros((1, 64), dtype=np.float32)
            for i in range(n_frames):
                chunk = samples[i * FRAME_SAMPLES:(i + 1) * FRAME_SAMPLES][None, :]
                x = np.concatenate([context, chunk], axis=1)
                out, state = self.session.run(None, {'input': x, 'state': state, 'sr': sr})
                context = x[:, -64:]
                result[i] = out[0, 0]
        else:  # v4
            h = np.zeros((2, 1, 64), dtype=np.float32)
            c = np.zeros((2, 1, 64), dtype=np.float32)
            for i in range(n_frames):
                chunk = samples[i * FRAME_SAMPLES:(i + 1) * FRAME_SAMPLES][None, :]
                out, h, c = self.session.run(None, {'input': chunk, 'sr': sr, 'h': h, 'c': c})
                result[i] = out[0, 0]
        return result


def pick_cut(
    scores: np.ndarray,
    region_start: float,
    lo: float,
    hi: float,
    nominal: float,
    threshold: float,
    min_quiet: float,
) -> Tuple[float, bool]:
    """在逐帧分数序列中挑选切点（纯函数，便于单测）。

    scores[i] 覆盖时间 [region_start + i*FRAME_SEC, region_start + (i+1)*FRAME_SEC)，
    分数越低越"安静"。在 [lo, hi] 范围内：
    - 找到持续 ≥ min_quiet 的低分（< threshold）连续区间 → 按"越长越安静越好、
      离 nominal 越远轻度扣分"打分选最佳区间，取其中点，返回 (切点, True)。
      不能单纯取距 nominal 最近的区间：句中 0.3~0.5s 的词间小缝隙可能比几秒外
      的真句间静音更近，但后者才是稳妥刀口；
    - 找不到 → 返回平滑后分数最低帧的中心，(切点, False)。
    """
    n = len(scores)
    if n == 0:
        return nominal, False
    times = region_start + np.arange(n) * FRAME_SEC          # 各帧起始时刻
    in_window = (times + FRAME_SEC > lo) & (times < hi)
    if not in_window.any():
        return nominal, False

    # 1. 在整个分析区域找低分连续段，再裁剪到 [lo, hi] 判断有效长度
    quiet = scores < threshold
    runs: List[Tuple[float, float, float]] = []   # [(start_sec, end_sec, mean_score)]
    i = 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            start = max(times[i], lo)
            end = min(times[j - 1] + FRAME_SEC, hi)
            if end - start >= min_quiet:
                runs.append((start, end, float(scores[i:j].mean())))
            i = j
        else:
            i += 1

    if runs:
        def run_score(r):
            start, end, mean = r
            center = (start + end) / 2
            # 时长收益封顶 0.8s；偏离 nominal 每 1s 扣 0.1；越安静越好
            return min(end - start, 0.8) - abs(center - nominal) / 10.0 - mean

        start, end, _ = max(runs, key=run_score)
        return _snap_to_frame((start + end) / 2), True

    # 2. 兜底：窗口内平滑分数最低点（仍严格优于盲切）
    kernel = min(5, n)
    smoothed = np.convolve(scores, np.ones(kernel) / kernel, mode='same')
    masked = np.where(in_window, smoothed, np.inf)
    idx = int(np.argmin(masked))
    cut = min(max(times[idx] + FRAME_SEC / 2, lo), hi)
    return _snap_to_frame(cut), False


def _snap_to_frame(sec: float) -> float:
    """切点对齐到帧边界，保证换算字节数时是整采样点。"""
    return round(sec / FRAME_SEC) * FRAME_SEC


class CutFinder:
    """切点搜索门面：VAD 优先，RMS 能量兜底。线程安全，进程内单例使用。"""

    def __init__(self):
        self._vad: Optional[SileroVAD] = None
        self._vad_failed = False
        self._lock = threading.Lock()

    def _get_vad(self) -> Optional[SileroVAD]:
        if self._vad is not None or self._vad_failed:
            return self._vad
        with self._lock:
            if self._vad is not None or self._vad_failed:
                return self._vad
            model_path = ModelPaths.silero_vad_model
            try:
                if not model_path.exists():
                    raise FileNotFoundError(f'VAD 模型不存在: {model_path}')
                self._vad = SileroVAD(model_path.as_posix())
                logger.info(f'[Segmenter] silero-VAD 已加载: {model_path}')
            except Exception as e:
                self._vad_failed = True
                logger.warning(
                    f'[Segmenter] silero-VAD 不可用（{e}），'
                    f'切点吸附降级为 RMS 能量检测。'
                )
        return self._vad

    def find(self, chunks: bytes, lo: float, hi: float, nominal: float) -> Tuple[float, bool]:
        """在音频缓冲的 [lo, hi] 秒范围内找切点。

        Args:
            chunks: float32 小端单声道 16k PCM 字节串（缓冲区全量）
            lo/hi:  搜索窗口（相对缓冲区起点，秒）
            nominal: 名义切点（秒），多个候选断点时取最近者

        Returns:
            (切点秒数[帧对齐], 是否找到可信静音断点)
        """
        samples = np.frombuffer(chunks, dtype='<f4')
        total_sec = len(samples) / AudioFormat.SAMPLE_RATE
        hi = min(hi, total_sec)
        if hi <= lo:
            return min(nominal, total_sec), False

        # 只分析 [lo - 预热, hi] 区域，避免对整个缓冲做无谓推理
        vad = self._get_vad()
        warmup = WARMUP_SEC if vad else 0.0
        region_start = max(0.0, lo - warmup)
        start_idx = int(region_start * AudioFormat.SAMPLE_RATE)
        end_idx = min(len(samples), int(hi * AudioFormat.SAMPLE_RATE))
        region = samples[start_idx:end_idx]
        region_start = start_idx / AudioFormat.SAMPLE_RATE   # 按实际截取修正

        if vad is not None:
            scores = vad.probs(region)
            threshold = Config.seg_vad_threshold
        else:
            scores, threshold = self._rms_scores(region)

        return pick_cut(
            scores, region_start, lo, hi, nominal,
            threshold=threshold, min_quiet=Config.seg_min_quiet,
        )

    @staticmethod
    def _rms_scores(region: np.ndarray) -> Tuple[np.ndarray, float]:
        """RMS 能量兜底：帧 RMS 作为分数，阈值取相对语音电平的比例。

        对干净人声等价于静音检测；持续背景音乐下可能找不到可信断点
        （返回的阈值判定不出低分段），此时 pick_cut 会走兜底最低点。
        """
        n_frames = len(region) // FRAME_SAMPLES
        if n_frames == 0:
            return np.zeros(0, dtype=np.float32), 1.0
        frames = region[:n_frames * FRAME_SAMPLES].reshape(n_frames, FRAME_SAMPLES)
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1)).astype(np.float32)
        speech_level = float(np.percentile(rms, 95))
        threshold = max(speech_level * 0.12, 1e-4)
        return rms, threshold


# 进程内单例（网络主进程使用；模型懒加载，首次调用时初始化）
_finder: Optional[CutFinder] = None
_finder_lock = threading.Lock()


def get_cut_finder() -> CutFinder:
    global _finder
    if _finder is None:
        with _finder_lock:
            if _finder is None:
                _finder = CutFinder()
    return _finder
