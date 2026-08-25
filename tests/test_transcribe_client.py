# coding: utf-8
"""transcribe_client.py 单测：协议兼容、自包含、退出码、srt、假 server 端到端。"""
from __future__ import annotations

import ast
import asyncio
import base64
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import websockets

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "transcribe_client.py"


def _load_module(path: Path = SCRIPT_PATH, name: str = "transcribe_client"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tc():
    return _load_module()


@pytest.fixture(scope="module")
def core_protocol():
    sys.path.insert(0, str(REPO_ROOT))
    from core.protocol import AudioMessage, RecognitionMessage
    return AudioMessage, RecognitionMessage


# --- 约束 1：协议双向兼容 ---


def test_protocol_audio_message_compatible(tc, core_protocol):
    AudioMessage, _ = core_protocol
    kwargs = dict(
        task_id=str(uuid.uuid1()),
        source="file",
        data=base64.b64encode(b"\x00\x00\x80?").decode(),
        is_final=False,
        time_start=time.time(),
        seg_duration=60.0,
        seg_overlap=4.0,
        context="",
        language="auto",
    )
    ours = tc.AudioMessage(**kwargs)
    theirs = AudioMessage(**kwargs)
    assert json.loads(ours.to_json()) == json.loads(theirs.to_json())


def test_protocol_recognition_message_compatible(tc, core_protocol):
    _, RecognitionMessage = core_protocol
    payload = {
        "task_id": "t1",
        "is_final": True,
        "duration": 3.5,
        "time_start": 1.0,
        "time_submit": 2.0,
        "time_complete": 3.0,
        "text": "你好世界。",
        "text_accu": "你好世界。",
        "tokens": ["你", "好", "世", "界", "。"],
        "timestamps": [0.0, 0.2, 0.5, 0.8, 1.0],
    }
    ours = tc.RecognitionMessage.from_dict(payload)
    theirs = RecognitionMessage.from_dict(payload)
    assert ours.to_dict() == theirs.to_dict()
    roundtrip = tc.RecognitionMessage.from_dict(json.loads(theirs.to_json()))
    assert roundtrip.to_dict() == theirs.to_dict()


# --- 约束 2：自包含 ---


def test_no_core_imports():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("core"), f"禁止 import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("core"), f"禁止 from {mod}"


def test_import_from_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "transcribe_client.py"
        shutil.copy(SCRIPT_PATH, dst)
        mod = _load_module(dst, name="tc_isolated")
        assert hasattr(mod, "main")


# --- 约束 5：srt 格式 ---


def test_write_srt_format(tc):
    msg = tc.RecognitionMessage(
        task_id="t",
        is_final=True,
        duration=5.0,
        time_start=0,
        time_submit=1,
        time_complete=2,
        text="你好，世界！测试完毕。",
        text_accu="你好，世界！测试完毕。",
        tokens=["你", "好", "，", "世", "界", "！", "测", "试", "完", "毕", "。"],
        timestamps=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    out = Path(tempfile.mkdtemp()) / "out.srt"
    try:
        tc.write_srt(msg, out)
        text = out.read_text(encoding="utf-8")
        lines = text.strip().split("\n")
        assert lines[0] == "1"
        assert "-->" in lines[1]
        assert lines[1].count(",") == 2  # HH:MM:SS,mmm
        assert "你好" in lines[2]
        assert [ln for ln in lines if ln][3] == "2"
    finally:
        out.unlink(missing_ok=True)
        out.parent.rmdir()


def test_fmt_timestamp(tc):
    assert tc._fmt_timestamp(3661.5) == "01:01:01,500"
    assert tc._fmt_timestamp(1.9999) == "00:00:02,000"
    assert tc._fmt_timestamp(59.9995) == "00:01:00,000"
    assert tc._fmt_timestamp(0.1234) == "00:00:00,123"


# --- 约束 3：退出码 ---


def test_exit_code_file_not_found(tc):
    assert tc.main(["/nonexistent/audio.wav"]) == 2


def test_exit_code_ffmpeg_missing(tc, monkeypatch, tmp_path):
    wav = tmp_path / "44k.wav"
    sr = 44100
    audio = np.zeros(sr, dtype=np.float32)
    sf.write(str(wav), audio, sr)
    monkeypatch.setattr(tc, "find_ffmpeg", lambda: None)
    assert tc.main([str(wav)]) == 2


def test_exit_code_task_failure_no_server(tc, tmp_path):
    wav = tmp_path / "16k.wav"
    sf.write(str(wav), np.zeros(16000, dtype=np.float32), 16000)
    code = tc.main([str(wav), "--server", "ws://127.0.0.1:1", "--timeout", "2"])
    assert code == 1


# --- 音频装载 ---


def test_load_16k_mono_wav_direct(tc, tmp_path):
    wav = tmp_path / "ok.wav"
    data = np.linspace(-0.1, 0.1, 16000, dtype=np.float32)
    sf.write(str(wav), data, 16000)
    audio, sr = tc.load_audio(wav)
    assert sr == 16000
    assert audio.dtype == np.float32
    assert len(audio) == 16000


def test_load_non_16k_uses_ffmpeg(tc, tmp_path, monkeypatch):
    wav = tmp_path / "44k.wav"
    sf.write(str(wav), np.zeros(44100, dtype=np.float32), 44100)
    fake = np.ones(16000, dtype=np.float32) * 0.5
    monkeypatch.setattr(tc, "_ffmpeg_to_float32", lambda p: (fake, 16000))
    audio, sr = tc.load_audio(wav)
    assert sr == 16000
    assert len(audio) == 16000


def test_load_mp3_uses_ffmpeg(tc, tmp_path, monkeypatch):
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"fake")
    fake = np.zeros(8000, dtype=np.float32)
    monkeypatch.setattr(tc, "_ffmpeg_to_float32", lambda p: (fake, 16000))
    audio, sr = tc.load_audio(mp3)
    assert sr == 16000
    assert len(audio) == 8000


def test_run_batch_loads_audio_once(tc, tmp_path, monkeypatch):
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"fake")
    calls: list[Path] = []

    def fake_ffmpeg(path):
        calls.append(path)
        return np.zeros(1600, dtype=np.float32), 16000

    monkeypatch.setattr(tc, "_ffmpeg_to_float32", fake_ffmpeg)

    async def fake_transcribe(path, **kwargs):
        assert kwargs.get("audio") is not None
        assert kwargs.get("sr") == 16000
        return None

    monkeypatch.setattr(tc, "transcribe_file", fake_transcribe)

    asyncio.run(
        tc._run_batch(
            [mp3],
            server="ws://127.0.0.1:1",
            seg_duration=60,
            seg_overlap=4,
            language="auto",
            out_dir=None,
            fmt="srt",
            timeout=1,
        )
    )
    assert len(calls) == 1


# --- 假 server 端到端 ---


@pytest.fixture
def canned_message():
    tokens = ["你", "好", "，", "世", "界", "。"]
    ts = [0.0, 0.3, 0.5, 0.7, 0.9, 1.1]
    return {
        "task_id": "placeholder",
        "is_final": True,
        "duration": 2.0,
        "time_start": time.time(),
        "time_submit": time.time(),
        "time_complete": time.time(),
        "text": "你好，世界。",
        "text_accu": "你好，世界。",
        "tokens": tokens,
        "timestamps": ts,
    }


async def _fake_server(websocket, canned: dict):
    async for raw in websocket:
        msg = json.loads(raw)
        assert msg["source"] == "file"
        if not msg["is_final"]:
            raw_bytes = base64.b64decode(msg["data"])
            samples = len(raw_bytes) // 4
            assert samples * 4 == len(raw_bytes)
            canned = dict(canned)
            canned["task_id"] = msg["task_id"]
            await websocket.send(json.dumps(canned, ensure_ascii=False))
        else:
            canned_final = dict(canned)
            canned_final["task_id"] = msg["task_id"]
            canned_final["is_final"] = True
            await websocket.send(json.dumps(canned_final, ensure_ascii=False))
            break


@pytest.mark.asyncio
async def test_transcribe_e2e_fake_server(tc, tmp_path, canned_message):
    wav = tmp_path / "test.wav"
    sf.write(str(wav), np.zeros(32000, dtype=np.float32), 16000)

    port = 8765
    server = None

    async def handler(ws):
        await _fake_server(ws, canned_message)

    for p in range(8765, 8785):
        try:
            server = await websockets.serve(handler, "127.0.0.1", p, subprotocols=["binary"])
            port = p
            break
        except OSError:
            continue
    assert server is not None

    try:
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        msg = await tc.transcribe_file(
            wav,
            server=f"ws://127.0.0.1:{port}",
            seg_duration=60,
            seg_overlap=4,
            language="auto",
            timeout=10,
        )
        assert msg is not None
        assert msg.is_final
        srt_path = out_dir / "test.srt"
        tc.write_srt(msg, srt_path)
        assert srt_path.exists()
        content = srt_path.read_text(encoding="utf-8")
        assert "你好" in content
        assert "00:00:00," in content
    finally:
        server.close()
        await server.wait_closed()


def test_main_success_fake_server(tc, tmp_path, canned_message):
    wav = tmp_path / "clip.wav"
    sf.write(str(wav), np.zeros(16000, dtype=np.float32), 16000)
    out_dir = tmp_path / "results"
    out_dir.mkdir()

    ready = threading.Event()
    port_box: dict = {}
    thread = threading.Thread(
        target=_run_fake_server,
        args=(canned_message, ready, port_box),
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=5)
    code = tc.main(
        [
            str(wav),
            "--server",
            f"ws://127.0.0.1:{port_box['port']}",
            "--out-dir",
            str(out_dir),
            "--format",
            "all",
            "--timeout",
            "10",
        ]
    )
    assert code == 0
    assert (out_dir / "clip.srt").exists()
    assert (out_dir / "clip.txt").exists()
    assert (out_dir / "clip.json").exists()


def _run_fake_server(canned: dict, ready: threading.Event, port_box: dict) -> None:
    async def serve():
        async def handler(ws):
            await _fake_server(ws, canned)

        async with websockets.serve(handler, "127.0.0.1", 0, subprotocols=["binary"]) as server:
            port_box["port"] = server.sockets[0].getsockname()[1]
            ready.set()
            await asyncio.Future()

    asyncio.run(serve())


def _run_mixed_fake_server(
    canned: dict,
    ready: threading.Event,
    port_box: dict,
    state: dict,
) -> None:
    async def serve():
        async def handler(ws):
            state["calls"] = state.get("calls", 0) + 1
            if state["calls"] == 1:
                async for _raw in ws:
                    await ws.send("{invalid json")
                    return
            await _fake_server(ws, canned)

        async with websockets.serve(handler, "127.0.0.1", 0, subprotocols=["binary"]) as server:
            port_box["port"] = server.sockets[0].getsockname()[1]
            ready.set()
            await asyncio.Future()

    asyncio.run(serve())


def test_batch_bad_json_does_not_abort(tc, tmp_path, canned_message):
    bad = tmp_path / "bad.wav"
    good = tmp_path / "good.wav"
    sf.write(str(bad), np.zeros(16000, dtype=np.float32), 16000)
    sf.write(str(good), np.zeros(16000, dtype=np.float32), 16000)
    out_dir = tmp_path / "results"
    out_dir.mkdir()

    ready = threading.Event()
    port_box: dict = {}
    state: dict = {}
    thread = threading.Thread(
        target=_run_mixed_fake_server,
        args=(canned_message, ready, port_box, state),
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=5)

    code = tc.main(
        [
            str(bad),
            str(good),
            "--server",
            f"ws://127.0.0.1:{port_box['port']}",
            "--out-dir",
            str(out_dir),
            "--format",
            "srt",
            "--timeout",
            "10",
        ]
    )
    assert code == 1
    assert not (out_dir / "bad.srt").exists()
    assert (out_dir / "good.srt").exists()


def test_collect_paths(tc, tmp_path):
    d = tmp_path / "media"
    d.mkdir()
    (d / "a.wav").write_bytes(b"x")
    (d / "b.txt").write_bytes(b"x")
    (d / "sub").mkdir()
    (d / "sub" / "c.mp3").write_bytes(b"x")
    paths = tc.collect_input_paths([str(d)])
    names = {p.name for p in paths}
    assert names == {"a.wav", "c.mp3"}


def test_help_runs():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "transcribe_client" in result.stdout or "转录" in result.stdout
