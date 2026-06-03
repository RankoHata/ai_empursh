"""
FastAPI application serving the AI Companion backend.

Start with:  python main.py
Stop with:   Ctrl+C
"""

import asyncio
import base64
import json
import logging
import os
from contextlib import asynccontextmanager

os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
# Bypass system proxy for DeepSeek API (direct connection)
os.environ["no_proxy"] = "api.deepseek.com"
os.environ["NO_PROXY"] = "api.deepseek.com"
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from agent.chat import ChatSession
from db import notes as notes_db
from voice import stt
from voice import tts as voice_tts
from agent import skills as skills_lib

# Load skills on startup
SKILLS = skills_lib.load_skills()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


cfg = load_config()
MODEL_CFG = cfg["model"]
SERVER_CFG = cfg["server"]
CHAT_CFG = cfg["chat"]

# ---------------------------------------------------------------------------
# OpenAI client (lazy init in lifespan)
# ---------------------------------------------------------------------------
openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """Build or return the cached AsyncOpenAI client, respecting proxy env vars."""
    global openai_client
    if openai_client is None:
        # Proxy: respect HTTP_PROXY / HTTPS_PROXY env vars automatically by the
        # httpx layer. Set them before running if needed:
        #   set HTTP_PROXY=http://127.0.0.1:7890
        #   set HTTPS_PROXY=http://127.0.0.1:7890
        openai_client = AsyncOpenAI(
            base_url=MODEL_CFG["base_url"],
            api_key=MODEL_CFG["api_key"],
        )
    return openai_client


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify config, pre-warm OpenAI client. Shutdown: clean up."""
    logger.info("Starting AI Companion backend...")
    logger.info("Model: %s @ %s", MODEL_CFG["model_name"], MODEL_CFG["base_url"])
    logger.info("Server: %s:%s", SERVER_CFG["host"], SERVER_CFG["port"])

    # Pre-init the client so the first request is fast
    get_openai_client()
    logger.info("OpenAI client ready")

    yield  # app runs here

    logger.info("Shutting down backend")
    if openai_client is not None:
        await openai_client.close()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Companion Backend", lifespan=lifespan)


from fastapi.responses import FileResponse

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def health_check():
    return {"status": "running", "model": MODEL_CFG["model_name"]}


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serve generated audio files to the frontend."""
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}, 404
    return FileResponse(file_path, media_type="audio/mpeg")


def _timestamp() -> str:
    """Return a short timestamp string for filenames."""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


async def _synthesize_and_send(websocket: WebSocket, text: str):
    """Background task: synthesize speech and send URL to frontend."""
    try:
        await websocket.send_json({
            "type": "avatar_state",
            "payload": {"action": "speaking"},
        })
        mp3_path = await voice_tts.synthesize(text)
        filename = Path(mp3_path).name
        await websocket.send_json({
            "type": "play_audio",
            "payload": {"url": f"http://127.0.0.1:8765/audio/{filename}"},
        })
    except Exception as exc:
        logger.error("TTS error: %s", exc)
    finally:
        await websocket.send_json({
            "type": "avatar_state",
            "payload": {"action": "idle"},
        })


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    client = get_openai_client()
    session = ChatSession(
        client=client,
        model_name=MODEL_CFG["model_name"],
        max_rounds=CHAT_CFG["max_history_rounds"],
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": "Invalid JSON"},
                })
                continue

            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "chat":
                user_text = payload.get("message", "").strip()
                if not user_text:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Empty message"},
                    })
                    continue

                # Skill routing: detect /command and inject system_prompt + context
                active_skill = None
                augmented_text = user_text
                for command, skill in SKILLS.items():
                    if user_text.startswith(command):
                        active_skill = skill
                        logger.info("Skill activated: %s", skill["name"])
                        # Build augmented prompt with notes if skill uses notes tools
                        context_parts = [skill["system_prompt"]]
                        if any(t in skill["allowed_tools"] for t in ("search_notes", "get_notes")):
                            all_notes = notes_db.get_all_notes()
                            if all_notes:
                                context_parts.append("\n\n## 当前所有笔记\n")
                                for n in all_notes:
                                    tags_str = ", ".join(n["tags"]) if n["tags"] else "无"
                                    context_parts.append(
                                        f"- [{n['id']}] {n['created_at']} #{tags_str}\n  {n['content']}"
                                    )
                                context_parts.append("\n请根据以上笔记整理生成文档。")
                        context_parts.append(f"\n## 用户指令\n{user_text}")
                        augmented_text = "\n".join(context_parts)
                        break

                session.add_user_message(augmented_text)
                session.clear_stop()

                collected_chunks: list[str] = []
                try:
                    async for token in session.stream_chat():
                        collected_chunks.append(token)
                        await websocket.send_json({
                            "type": "message_chunk",
                            "payload": {"content": token},
                        })
                except Exception as exc:
                    logger.error("Stream error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Model error: {exc}"},
                    })
                else:
                    full = "".join(collected_chunks)
                    partial = session.stopped()
                    await websocket.send_json({
                        "type": "message_complete",
                        "payload": {"full_content": full, "partial": partial},
                    })

                    # Auto TTS: synthesize reply as speech (fire-and-forget)
                    if full.strip():
                        asyncio.create_task(_synthesize_and_send(websocket, full))

                    # If a skill was used, send markdown preview
                    if active_skill:
                        await websocket.send_json({
                            "type": "markdown_preview",
                            "payload": {
                                "content": full,
                                "suggested_filename": f"{active_skill['name']}_{_timestamp()}.md",
                            },
                        })

            elif msg_type == "stop":
                session.request_stop()
                logger.info("Stop requested by client")

            # --- Voice handlers ---
            elif msg_type == "voice_input":
                audio_b64 = payload.get("audio_data", "")
                if not audio_b64:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Missing audio_data"},
                    })
                    continue

                try:
                    # Decode base64 to WAV
                    audio_bytes = base64.b64decode(audio_b64)
                    temp_dir = Path(__file__).parent / "temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    wav_path = temp_dir / f"recording_{os.urandom(6).hex()}.wav"
                    wav_path.write_bytes(audio_bytes)
                    logger.info("Received voice input: %d bytes", len(audio_bytes))

                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "thinking"},
                    })

                    # Transcribe
                    text = await asyncio.to_thread(stt.transcribe, str(wav_path))
                    logger.info("Voice transcribed: %s", text[:100])

                    await websocket.send_json({
                        "type": "voice_result",
                        "payload": {"text": text},
                    })
                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "idle"},
                    })

                    # Clean up temp file
                    wav_path.unlink(missing_ok=True)

                except Exception as exc:
                    logger.error("Voice processing error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Voice error: {exc}"},
                    })
                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "idle"},
                    })

            elif msg_type == "voice_mode":
                always_on = payload.get("always_on", False)
                logger.info("Voice mode: always_on=%s", always_on)
                await websocket.send_json({
                    "type": "voice_status",
                    "payload": {"always_on": always_on, "recording": False},
                })

            elif msg_type == "save_file":
                content = payload.get("content", "")
                filename = payload.get("filename", f"export_{_timestamp()}.md")
                output_dir = Path(os.path.expanduser("~/Desktop"))
                output_dir.mkdir(parents=True, exist_ok=True)
                file_path = output_dir / filename
                file_path.write_text(content, encoding="utf-8")
                logger.info("File saved: %s", file_path)
                await websocket.send_json({
                    "type": "file_saved",
                    "payload": {"file_path": str(file_path)},
                })

            # --- Notes handlers ---
            elif msg_type == "add_note":
                try:
                    note = notes_db.add_note(
                        content=payload.get("content", ""),
                        tags=payload.get("tags", []),
                    )
                    await websocket.send_json({
                        "type": "note_saved",
                        "payload": {"note": note},
                    })
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Failed to save note: {exc}"},
                    })

            elif msg_type == "get_notes":
                all_notes = notes_db.get_all_notes()
                await websocket.send_json({
                    "type": "notes_list",
                    "payload": {"notes": all_notes},
                })

            elif msg_type == "search_notes":
                results = notes_db.search_notes(
                    query=payload.get("query", ""),
                    tags=payload.get("tags", []),
                )
                await websocket.send_json({
                    "type": "search_results",
                    "payload": {"results": results},
                })

            elif msg_type == "delete_note":
                note_id = payload.get("note_id")
                if note_id is not None:
                    ok = notes_db.delete_note(int(note_id))
                    await websocket.send_json({
                        "type": "note_deleted",
                        "payload": {"note_id": note_id, "deleted": ok},
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Missing note_id"},
                    })

            elif msg_type == "export_notes":
                note_ids = payload.get("note_ids", [])
                if note_ids:
                    output_path = notes_db.export_notes(note_ids)
                    await websocket.send_json({
                        "type": "notes_exported",
                        "payload": {"file_path": output_path},
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "No note_ids provided"},
                    })

            else:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": f"Unknown message type: {msg_type}"},
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("Unexpected error in WebSocket handler: %s", exc)
    finally:
        logger.info("Cleaning up session")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=SERVER_CFG["host"],
        port=SERVER_CFG["port"],
        log_level="info",
    )
