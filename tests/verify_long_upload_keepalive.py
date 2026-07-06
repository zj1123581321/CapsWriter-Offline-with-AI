# coding: utf-8
"""
Long-connection keepalive verification script (manual, requires a running server).

Reproduces the failure mode reported by VideoTranscriptAPI: a client that keeps
uploading audio chunks for longer than 40 seconds while the server (with default
websockets keepalive: ping_interval=20, ping_timeout=20) kills the connection
with "1011 keepalive ping timeout".

The script connects to the CapsWriter server and uploads synthetic audio.
Two pacing modes:
  flood (default): send --audio-seconds of audio in 60s chunks back-to-back
      with no pauses, saturating the pipe like the real failing client did.
      Outbound pong frames queue behind the bulk data, so with default server
      keepalive the connection dies around t=40s.
  real: send chunks paced at real-time speed for --hold wall-clock seconds
      (gentler; may not reproduce the bug on fast networks).

PASS: connection stays alive for the whole upload and a final result arrives.
FAIL: connection is closed by the server (typically code 1011) mid-upload.

Usage:
    python tests/verify_long_upload_keepalive.py [--server ws://localhost:6016] [--mode flood] [--audio-seconds 600]

Dependencies: numpy, websockets. Console output is ASCII-only by design.
"""

import argparse
import asyncio
import base64
import json
import sys
import time
import uuid

import numpy as np
import websockets


SAMPLE_RATE = 16000


def make_chunk(seconds: float) -> str:
    """Generate a base64-encoded float32 audio chunk of low-volume noise."""
    samples = int(SAMPLE_RATE * seconds)
    audio = (np.random.randn(samples) * 0.01).astype(np.float32)
    return base64.b64encode(audio.tobytes()).decode()


async def run(server: str, mode: str, hold: float, audio_seconds: float, chunk_seconds: float) -> int:
    task_id = str(uuid.uuid4())
    time_start = time.time()
    print(f"[info] connecting to {server}")
    print(f"[info] task_id={task_id} mode={mode} hold={hold}s audio_seconds={audio_seconds}s chunk={chunk_seconds}s")

    try:
        ws = await websockets.connect(
            server, subprotocols=["binary"], max_size=None, ping_interval=None
        )
    except Exception as e:
        print(f"[fail] cannot connect: {e!r}")
        return 1

    sent_seconds = 0.0
    upload_start = time.monotonic()
    try:
        if mode == "flood":
            # Send the whole payload back-to-back with no pauses, exactly like
            # the failing client (one ~5MB message per minute of audio, pipe
            # saturated for the whole upload). Outbound pongs queue behind the
            # bulk frames, which is what used to trip the 20s server deadline.
            payload = make_chunk(chunk_seconds)
            while sent_seconds < audio_seconds:
                msg = {
                    "task_id": task_id,
                    "source": "file",
                    "data": payload,
                    "is_final": False,
                    "time_start": time_start,
                    "seg_duration": 60.0,
                    "seg_overlap": 4.0,
                }
                await ws.send(json.dumps(msg))
                sent_seconds += chunk_seconds
                elapsed = time.monotonic() - upload_start
                print(f"[send] elapsed={elapsed:6.1f}s audio_sent={sent_seconds:6.1f}s")
        else:
            # Real-time pacing: keep the connection busy for `hold` wall-clock
            # seconds with a gentler, slow-uploader profile.
            while time.monotonic() - upload_start < hold:
                msg = {
                    "task_id": task_id,
                    "source": "file",
                    "data": make_chunk(chunk_seconds),
                    "is_final": False,
                    "time_start": time_start,
                    "seg_duration": 60.0,
                    "seg_overlap": 4.0,
                }
                await ws.send(json.dumps(msg))
                sent_seconds += chunk_seconds
                elapsed = time.monotonic() - upload_start
                print(f"[send] elapsed={elapsed:6.1f}s audio_sent={sent_seconds:6.1f}s")
                await asyncio.sleep(chunk_seconds)

        # Final empty chunk closes the task on the server side.
        final_msg = {
            "task_id": task_id,
            "source": "file",
            "data": "",
            "is_final": True,
            "time_start": time_start,
            "seg_duration": 60.0,
            "seg_overlap": 4.0,
        }
        await ws.send(json.dumps(final_msg))
        print(f"[info] upload finished, {sent_seconds:.1f}s of audio sent, waiting for final result")

        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=300)
            result = json.loads(raw)
            if result.get("task_id") != task_id:
                continue
            if result.get("is_final"):
                text = (result.get("text") or "")[:80]
                print(f"[info] final result received, duration={result.get('duration')} text={text!r}")
                print("[pass] connection survived the long upload, no keepalive disconnect")
                return 0
        print("[fail] timed out waiting for final result")
        return 1

    except websockets.ConnectionClosed as e:
        elapsed = time.monotonic() - upload_start
        print(f"[fail] server closed connection after {elapsed:.1f}s: code={e.code} reason={e.reason!r}")
        if e.code == 1011:
            print("[fail] this is the keepalive ping timeout bug (1011)")
        return 1
    except Exception as e:
        print(f"[fail] unexpected error: {e!r}")
        return 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify server survives long saturated uploads without keepalive disconnect")
    parser.add_argument("--server", default="ws://localhost:6016", help="server websocket url")
    parser.add_argument("--mode", choices=["flood", "real"], default="flood", help="flood: back-to-back bulk send (repro mode); real: real-time paced")
    parser.add_argument("--audio-seconds", type=float, default=600.0, help="flood mode: total seconds of audio to upload")
    parser.add_argument("--hold", type=float, default=75.0, help="real mode: wall-clock seconds to keep uploading")
    parser.add_argument("--chunk", type=float, default=60.0, help="seconds of audio per chunk (real client sends 60)")
    args = parser.parse_args()
    return asyncio.run(run(args.server, args.mode, args.hold, args.audio_seconds, args.chunk))


if __name__ == "__main__":
    sys.exit(main())
