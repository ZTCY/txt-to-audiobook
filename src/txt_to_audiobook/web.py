"""Web UI for txt-to-audiobook using FastAPI + WebSocket.

Replaces the tkinter GUI. Pipeline runs in a background thread so the
async event loop stays responsive. Real-time progress and logs are
pushed via WebSocket.
"""

import asyncio
import json
import queue
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import io
import uvicorn

from .config import OUTPUT_DIR, TXT_INPUT_DIR, VOICE_DISPLAY_NAMES, RECOMMENDED_VOICES
from .models import ConversionConfig
from .parser import split_chapters, clean_text
from .pipeline import AudiobookPipeline
from .tts.edge import EdgeTTSProvider

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Cache for voice preview audio (voice_id -> bytes)
_preview_cache: dict[str, bytes] = {}

app = FastAPI(title="txt-to-audiobook", docs_url=None, redoc_url=None)

# Serve static assets (stickers, background)
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = TEMPLATE_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------

@app.get("/api/voices")
async def list_voices():
    """Return available voices for the dropdown."""
    return [
        {"label": label, "value": value}
        for label, value in VOICE_DISPLAY_NAMES.items()
    ]


@app.get("/api/files")
async def list_input_files():
    """List TXT files in txt_input/."""
    p = Path(TXT_INPUT_DIR)
    if not p.exists():
        return []
    return sorted(
        [{"name": f.name, "path": str(f)} for f in p.glob("*.txt")],
        key=lambda x: x["name"],
    )


@app.post("/api/upload")
async def upload_file(file: UploadFile):
    """Upload a TXT file into txt_input/."""
    p = Path(TXT_INPUT_DIR)
    p.mkdir(parents=True, exist_ok=True)
    dest = p / file.filename
    content = await file.read()
    dest.write_bytes(content)
    return {"name": file.filename, "path": str(dest)}


@app.post("/api/preview")
async def preview_chapters(file_path: str):
    """Return chapter count and preview for a file."""
    try:
        txt_path = Path(file_path)
        if not txt_path.exists():
            return {"error": "File not found"}
        try:
            text = txt_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = txt_path.read_text(encoding="gbk")
        text = clean_text(text)
        chapters = split_chapters(text)
        return {
            "total": len(chapters),
            "preview": [
                {"index": i + 1, "title": ch.title}
                for i, ch in enumerate(chapters[:20])
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/voice-preview")
async def voice_preview(voice: str = Query(...)):
    """Generate a short preview audio clip for the given voice.
    Cached per-voice after first generation."""
    from .config import VOICE_CN_NAMES

    # Return cached preview if available
    if voice in _preview_cache:
        buf = io.BytesIO(_preview_cache[voice])
        return StreamingResponse(buf, media_type="audio/mpeg")

    # Use the same edge_tts that EdgeTTSProvider patched to 96kbps
    from .tts.edge import edge_tts as patched_edge_tts
    cn_name = VOICE_CN_NAMES.get(voice, voice)
    preview_text = f"你好啊，我是{cn_name}。"
    communicate = patched_edge_tts.Communicate(preview_text, voice)
    raw_buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            raw_buf.write(chunk["data"])
    raw_buf.seek(0)
    # Enhance with ffmpeg if available
    import tempfile, os, subprocess
    raw_path = None
    enhanced_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as raw_f:
            raw_f.write(raw_buf.read())
            raw_path = raw_f.name
        enhanced_path = raw_path.replace(".mp3", "_enhanced.mp3")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", raw_path,
             "-ar", "48000", "-b:a", "320k",
             "-af", "loudnorm=I=-16:LRA=11:TP=-1.5,volume=0.8",
             "-codec:a", "libmp3lame", "-q:a", "0",
             enhanced_path],
            capture_output=True, timeout=30,
        )
        if os.path.exists(enhanced_path) and os.path.getsize(enhanced_path) > 0:
            audio_data = open(enhanced_path, "rb").read()
            _preview_cache[voice] = audio_data
            return StreamingResponse(io.BytesIO(audio_data), media_type="audio/mpeg")
    except Exception:
        pass
    finally:
        if raw_path and os.path.exists(raw_path):
            os.unlink(raw_path)
        if enhanced_path and os.path.exists(enhanced_path):
            os.unlink(enhanced_path)
    # Fallback: return raw audio
    raw_data = raw_buf.read()
    _preview_cache[voice] = raw_data
    return StreamingResponse(io.BytesIO(raw_data), media_type="audio/mpeg")


# ---------------------------------------------------------------------------
# WebSocket – real-time conversion
# ---------------------------------------------------------------------------

async def _do_convert(
    data: dict,
    msg_queue: queue.Queue,
    pipeline_ref: dict,
) -> None:
    """Run the full pipeline in this thread's event loop.

    Callbacks push JSON-serializable dicts into ``msg_queue`` (thread-safe).
    ``pipeline_ref["pipeline"]`` is set so the WebSocket handler can call
    pause/stop/skip.
    """
    voice = data.get("voice", "zh-CN-YunxiNeural")
    rate = data.get("rate", "+0%")
    start_ch = data.get("start_chapter")
    end_ch = data.get("end_chapter")
    files = data.get("files", [])

    config = ConversionConfig(
        voice=voice,
        rate=rate,
        output_dir=Path(OUTPUT_DIR),
        start_chapter=start_ch if start_ch else None,
        end_chapter=end_ch if end_ch else None,
    )

    pipeline = AudiobookPipeline(config=config, tts_provider=EdgeTTSProvider())
    pipeline_ref["pipeline"] = pipeline

    # Wire callbacks → queue
    pipeline.on_log = lambda msg: msg_queue.put({
        "type": "log", "message": msg, "level": "INFO",
    })

    def _on_chapter_start(idx: int, total: int, title: str):
        msg_queue.put({
            "type": "progress",
            "chapter": idx,
            "total": total,
            "title": title,
            "percent": round((idx - 1) / total * 100, 1) if total else 0,
        })

    pipeline.on_chapter_start = _on_chapter_start

    pipeline.on_chapter_done = lambda result: msg_queue.put({
        "type": "chapter_done",
        "title": result.chapter.title,
        "success": result.success,
        "duration_s": round(result.duration_s, 2),
        "chunks": result.chunks_count,
    })

    try:
        for fpath in files:
            msg_queue.put({"type": "status", "status": "converting"})
            await pipeline.convert(Path(fpath))
        msg_queue.put({
            "type": "status",
            "status": "complete",
            "output_dir": OUTPUT_DIR,
        })
    except Exception as exc:
        msg_queue.put({
            "type": "status",
            "status": "error",
            "error": str(exc),
        })
    finally:
        pipeline_ref["pipeline"] = None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    loop = asyncio.get_running_loop()
    msg_queue: queue.Queue = queue.Queue()
    pipeline_ref: dict = {"pipeline": None}  # mutable ref for control

    async def _send_worker():
        while True:
            # Pull from the thread-safe queue without blocking the event loop
            msg = await loop.run_in_executor(None, msg_queue.get)
            if msg is None:                     # sentinel
                break
            try:
                await ws.send_json(msg)
            except Exception:
                break

    send_task = asyncio.create_task(_send_worker())

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action", "")

            if action == "start":
                # Kick off the pipeline in a background thread
                def _run():
                    asyncio.run(_do_convert(data, msg_queue, pipeline_ref))
                    msg_queue.put(None)  # signal completion

                t = threading.Thread(target=_run, daemon=True)
                t.start()

            elif action == "pause":
                p = pipeline_ref["pipeline"]
                if p:
                    p.pause()
                    msg_queue.put({"type": "status", "status": "paused"})

            elif action == "resume":
                p = pipeline_ref["pipeline"]
                if p:
                    p.resume()
                    msg_queue.put({"type": "status", "status": "converting"})

            elif action == "stop":
                p = pipeline_ref["pipeline"]
                if p:
                    p.stop()
                    msg_queue.put({"type": "status", "status": "stopped"})

            elif action == "skip":
                p = pipeline_ref["pipeline"]
                if p:
                    p.skip_current()

    except WebSocketDisconnect:
        pass
    finally:
        p = pipeline_ref["pipeline"]
        if p:
            p.stop()
        msg_queue.put(None)
        send_task.cancel()
        try:
            await asyncio.wait_for(send_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Start the web server."""
    import os
    port = int(os.environ.get("PORT", "8081"))

    print(f"\n  Audiobook Web UI")
    print(f"  ==========================================\n")
    print(f"  Starting web server at http://127.0.0.1:{port}")
    print(f"  Press Ctrl+C to stop\n")

    # Open browser after a short delay (let uvicorn bind first)
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    uvicorn.run(
        "txt_to_audiobook.web:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
