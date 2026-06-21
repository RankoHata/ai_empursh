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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from config import config
from agent.chat import ChatSession
from db import conversations as conv_db
from db import notes as notes_db
from db import secret_notes as secret_notes_db
from db.init_db import init_db as init_db_conn
from db.workspace_sync import (
    async_sync_all_workspaces,
    async_sync_workspace,
    start_background_sync,
)
from voice import stt
from voice import tts as voice_tts
from agent import skills as skills_lib
from agent.personality import (
    ensure_seeded, list_personalities, get_personality,
    create_personality, update_personality, delete_personality,
    get_default_personality,
)
from tools import create_default_registry
from utils.markdown import strip_markdown

# Initialize databases and seed data on startup
init_db_conn("public")
init_db_conn("secret")
SKILLS = skills_lib.load_skills()
ensure_seeded()

# Tool registry — created once at module load, shared across connections
tool_registry = create_default_registry()

# TTS engine configured at module load after config is read

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Our modules — DEBUG for troubleshooting
logging.getLogger("agent.chat").setLevel(logging.DEBUG)
logging.getLogger("backend").setLevel(logging.DEBUG)
logging.getLogger("tools").setLevel(logging.DEBUG)
logging.getLogger("voice.tts").setLevel(logging.DEBUG)
logging.getLogger("voice.tts_xtts").setLevel(logging.DEBUG)
# Quiet down noisy third-party loggers
logging.getLogger("numba").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# Configure TTS engine from config (edge-tts or XTTS-v2)
voice_tts.configure_engine()

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
            base_url=config.model["base_url"],
            api_key=config.model["api_key"],
        )
    return openai_client


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify config, pre-warm OpenAI client. Shutdown: clean up."""
    logger.info("Starting AI Companion backend...")
    logger.info("Model: %s @ %s", config.model["model_name"], config.model["base_url"])
    logger.info("Server: %s:%s", config.server["host"], config.server["port"])

    # Pre-init the client so the first request is fast
    get_openai_client()
    logger.info("OpenAI client ready")

    # Initial workspace sync + start background sync task
    sync_task: Optional[asyncio.Task] = None
    if config.workspaces:
        logger.info("Syncing %d workspace(s)...", len(config.workspaces))
        result = await async_sync_all_workspaces(config.workspaces)
        logger.info(
            "Initial sync done: +%d ~%d -%d, errors=%d",
            result["added"], result["updated"], result["deleted"],
            len(result.get("errors", [])),
        )
        sync_task = asyncio.create_task(
            start_background_sync(config.workspaces)
        )

    yield  # app runs here

    # Shutdown
    logger.info("Shutting down backend")
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    if openai_client is not None:
        await openai_client.close()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Companion Backend", lifespan=lifespan)


from fastapi.responses import FileResponse, StreamingResponse

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# In-memory map of stream_id → text for streaming TTS
# Populated by _synthesize_and_send(), consumed by /audio/stream/{stream_id}
_tts_streams: dict[str, str] = {}


@app.get("/")
async def health_check():
    return {"status": "running", "model": config.model["model_name"]}


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serve generated audio files to the frontend."""
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}, 404
    return FileResponse(file_path, media_type="audio/mpeg")


@app.get("/audio/stream/{stream_id}")
async def stream_audio(stream_id: str, request: Request):
    """Stream TTS audio chunks as they are synthesized.

    The client connects once, receives MP3 byte chunks as they arrive
    from edge-tts, and the browser's <audio> tag decodes and plays them
    incrementally.  When the client disconnects (pause / new message),
    `request.is_disconnected` becomes True and we stop streaming.
    """
    text = _tts_streams.pop(stream_id, None)
    if text is None:
        return {"error": "Stream not found or already consumed"}, 404

    async def generate():
        try:
            async for chunk in voice_tts.stream_synthesize(text):
                if await request.is_disconnected():
                    logger.info("TTS client disconnected for stream %s", stream_id)
                    break
                yield chunk
        except Exception as exc:
            logger.error("TTS stream error for %s: %s", stream_id, exc, exc_info=True)

    return StreamingResponse(
        generate(),
        media_type="audio/mpeg",
        headers={"X-Content-Type-Options": "nosniff"},
    )


def _build_skill_prompt(skill: dict, user_text: str) -> str:
    """Build the augmented prompt for a skill (system prompt + user text only).

    Note data is no longer injected here — the model will call tools to retrieve it.
    """
    return f"{skill['system_prompt']}\n\n## 用户指令\n{user_text}"


def _timestamp() -> str:
    """Return a short timestamp string for filenames."""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


async def _synthesize_and_send(websocket: WebSocket, text: str):
    """Background task: register a streaming TTS session and send URL to frontend.

    The actual synthesis happens inside GET /audio/stream/{stream_id},
    where edge-tts streams MP3 chunks directly to the browser's <audio> tag.
    """
    stream_id = os.urandom(6).hex()
    try:
        await _ws_send_safe(websocket, "avatar_state", {"action": "speaking"})
        _tts_streams[stream_id] = strip_markdown(text)
        await _ws_send_safe(websocket, "play_audio", {
            "url": f"http://127.0.0.1:8765/audio/stream/{stream_id}"
        })
    except asyncio.CancelledError:
        _tts_streams.pop(stream_id, None)
        raise
    except Exception as exc:
        _tts_streams.pop(stream_id, None)
        logger.error("TTS error: %s", exc)


async def _ws_send_safe(websocket: WebSocket, msg_type: str, payload: dict):
    """Send a WebSocket message, ignoring errors if connection is closed."""
    try:
        await websocket.send_json({"type": msg_type, "payload": payload})
    except Exception:
        pass  # WebSocket already closed, ignore


# ---------------------------------------------------------------------------
# Secret message handler (hard-routed, never touches LLM)
# ---------------------------------------------------------------------------

async def _handle_secret_message(
    websocket: WebSocket,
    msg_type: str,
    payload: dict,
) -> None:
    """Route secret-prefix messages to secret_notes_db. NO LLM involvement."""
    try:
        if msg_type == "secret_add_note":
            note = secret_notes_db.add_secret_note(
                content=payload.get("content", ""),
                tags=payload.get("tags", []),
                title=payload.get("title", ""),
            )
            await _ws_send_safe(websocket, "secret_note_saved", {"note": note})

        elif msg_type == "secret_get_notes":
            notes = secret_notes_db.get_all_secret_notes()
            await _ws_send_safe(websocket, "secret_notes_list", {"notes": notes})

        elif msg_type == "secret_search_notes":
            results = secret_notes_db.search_secret_notes(
                query=payload.get("query", ""),
                tags=payload.get("tags", []),
            )
            await _ws_send_safe(websocket, "secret_search_results", {
                "results": results,
                "count": len(results),
            })

        elif msg_type == "secret_delete_note":
            note_id = payload.get("note_id")
            if note_id is not None:
                ok = secret_notes_db.delete_secret_note(int(note_id))
                await _ws_send_safe(websocket, "secret_note_deleted", {
                    "note_id": note_id,
                    "deleted": ok,
                })
            else:
                await _ws_send_safe(websocket, "error", {
                    "message": "Missing note_id",
                })

        else:
            await _ws_send_safe(websocket, "error", {
                "message": f"Unknown secret message type: {msg_type}",
            })
    except Exception as exc:
        logger.error("Secret handler error (%s): %s", msg_type, exc)
        await _ws_send_safe(websocket, "error", {
            "message": f"Secret operation failed: {exc}",
        })


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    client = get_openai_client()

    # Per-connection tool callbacks (capture websocket in closure)
    async def on_tool_call(name: str, args: dict):
        logger.debug("WS → tool_call_start: %s args=%s",
                     name, json.dumps(args, ensure_ascii=False)[:120])
        await _ws_send_safe(websocket, "tool_call_start", {
            "name": name,
            "args": args,
        })

    async def on_tool_result(name: str, result: dict):
        duration_ms = result.pop("_duration_ms", 0) if isinstance(result, dict) else 0
        success = result.get("success", True) if isinstance(result, dict) else True
        if success:
            logger.debug("WS → tool_call_result: %s duration=%dms",
                         name, duration_ms)
            await _ws_send_safe(websocket, "tool_call_result", {
                "name": name,
                "result": result,
                "duration_ms": duration_ms,
            })
        else:
            logger.debug("WS → tool_call_error: %s error=%s",
                         name, result.get("message", ""))
            await _ws_send_safe(websocket, "tool_call_error", {
                "name": name,
                "error": result.get("message", str(result)) if isinstance(result, dict) else str(result),
            })

    session = ChatSession(
        client=client,
        model_name=config.model["model_name"],
        max_rounds=config.chat["max_history_rounds"],
        tool_registry=tool_registry,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )
    tts_task: asyncio.Task | None = None
    tts_enabled = True
    current_conv_id: Optional[str] = None
    turn_index = 0
    current_personality = get_default_personality()  # active personality (DB record)

    # Per-connection: set WebSocket sender for secret tool callbacks
    tool_registry._ws_sender = websocket.send_json

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

            # --- Gateway hard routing: secret-prefix messages NEVER touch LLM ---
            if msg_type.startswith("secret_"):
                await _handle_secret_message(websocket, msg_type, payload)
                continue

            if msg_type == "chat":
                user_text = payload.get("message", "").strip()
                if not user_text:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Empty message"},
                    })
                    continue

                # Cancel any in-progress TTS
                if tts_task and not tts_task.done():
                    tts_task.cancel()
                    tts_task = None

                # --- Skill routing: match /command, load system prompt, filter tools ---
                active_skill = None
                augmented_text = user_text
                active_tool_schemas = tool_registry.get_schemas()  # default: all tools

                for command, skill in SKILLS.items():
                    if user_text.startswith(command):
                        active_skill = skill
                        logger.info("Skill activated: %s (command=%s)", skill["name"], command)
                        logger.debug("Skill allowed_tools: %s", skill.get("allowed_tools", []))
                        augmented_text = _build_skill_prompt(skill, user_text)
                        active_tool_schemas = tool_registry.get_for_skill(skill)
                        logger.debug(
                            "Skill tool schemas: %s",
                            [t["function"]["name"] for t in active_tool_schemas],
                        )
                        break

                logger.debug(
                    "Chat request: text=%s active_skill=%s tools=%s",
                    user_text[:80],
                    active_skill["name"] if active_skill else "none",
                    [t["function"]["name"] for t in active_tool_schemas],
                )

                # --- Send to model ---
                # Inject personality system prompt at start of each turn
                personality_prompt = current_personality.get("system_prompt", "")
                if personality_prompt:
                    session.set_system_prompt(personality_prompt)

                session.add_user_message(augmented_text)
                session.clear_stop()

                collected_chunks: list[str] = []
                try:
                    async for event_type, data in session.stream_with_tool_loop(active_tool_schemas):
                        if event_type == "content":
                            collected_chunks.append(data)
                            await websocket.send_json({
                                "type": "message_chunk",
                                "payload": {"content": data},
                            })
                        # tool_call events are already pushed via on_tool_call/on_tool_result callbacks
                except Exception as exc:
                    logger.error("Stream error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Model error: {exc}"},
                    })
                else:
                    full = "".join(collected_chunks)
                    partial = session.stopped()
                    trace = session.get_trace()
                    logger.debug(
                        "Chat complete: content_chars=%d partial=%s trace_steps=%d",
                        len(full), partial, len(trace),
                    )
                    await websocket.send_json({
                        "type": "message_complete",
                        "payload": {"full_content": full, "partial": partial, "trace": trace},
                    })

                    # Auto TTS
                    if full.strip() and tts_enabled:
                        if tts_task and not tts_task.done():
                            tts_task.cancel()
                        tts_task = asyncio.create_task(_synthesize_and_send(websocket, full))

                    # Auto-save conversation turn
                    if not partial:
                        if current_conv_id is None:
                            # Auto-create conversation on first message
                            conv = conv_db.create_conversation(title=user_text)
                            current_conv_id = conv["id"]
                            turn_index = 0
                            logger.info("Auto-created conversation %s", current_conv_id)
                        elif not conv_db.get_conversation(current_conv_id):
                            # Current conversation was deleted — create a new one
                            logger.warning("Conversation %s no longer exists, auto-creating new one", current_conv_id)
                            conv = conv_db.create_conversation(title=user_text)
                            current_conv_id = conv["id"]
                            turn_index = 0

                        trace = session.get_trace()
                        conv_db.add_turn(
                            conv_id=current_conv_id,
                            turn_index=turn_index,
                            user_message=user_text,
                            assistant_content=full,
                            trace=trace,
                        )
                        turn_index += 1
                        logger.debug(
                            "Saved turn %d in conv %s (%d trace steps)",
                            turn_index - 1, current_conv_id, len(trace),
                        )

                    # Skill markdown preview
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
                if tts_task and not tts_task.done():
                    tts_task.cancel()
                    tts_task = None
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

            elif msg_type == "tts_enabled":
                tts_enabled = payload.get("enabled", True)
                logger.info("TTS enabled: %s", tts_enabled)

            elif msg_type == "delete_turn":
                turn_index = payload.get("turn_index")
                conv_id = payload.get("conversation_id", current_conv_id or "")
                if conv_id and turn_index is not None:
                    deleted = conv_db.delete_turn(conv_id, int(turn_index))
                    await websocket.send_json({
                        "type": "turn_deleted",
                        "payload": {"conversation_id": conv_id, "turn_index": turn_index, "deleted": deleted},
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Missing conversation_id or turn_index"},
                    })

            elif msg_type == "get_config":
                safe_cfg = {
                    "model": {
                        "base_url": config.model["base_url"],
                        "api_key": "***" + config.model.get("api_key", "")[-4:] if len(config.model.get("api_key", "")) > 4 else "***",
                        "model_name": config.model["model_name"],
                        "max_tokens": config.model["max_tokens"],
                    },
                    "voice": {
                        "stt_model": "base",
                        "tts_engine": voice_tts.get_engine_name(),
                        "tts_voice": config.voice.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
                    },
                    "workspaces": config.workspaces,
                }
                await websocket.send_json({"type": "config", "payload": safe_cfg})

            elif msg_type == "update_config":
                updates = payload.get("updates", {})
                try:
                    config.save(updates)
                    await websocket.send_json({"type": "config_updated", "payload": {"success": True}})
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error", "payload": {"message": f"Config update failed: {exc}"},
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

            # --- Conversation handlers ---
            elif msg_type == "create_conversation":
                conv = conv_db.create_conversation(title=payload.get("title", "新对话"))
                await websocket.send_json({
                    "type": "conversation_created",
                    "payload": conv,
                })

            elif msg_type == "list_conversations":
                convs = conv_db.list_conversations()
                await websocket.send_json({
                    "type": "conversations_list",
                    "payload": {"conversations": convs},
                })

            elif msg_type == "delete_conversation":
                conv_id = payload.get("conversation_id", "")
                if conv_id:
                    deleted = conv_db.delete_conversation(conv_id)
                    # Clear current conversation if it was deleted
                    if conv_id == current_conv_id:
                        current_conv_id = None
                        turn_index = 0
                        logger.info("Current conversation %s was deleted, resetting session", conv_id)
                    await websocket.send_json({
                        "type": "conversation_deleted",
                        "payload": {"conversation_id": conv_id, "deleted": deleted},
                    })

            elif msg_type == "rename_conversation":
                conv_id = payload.get("conversation_id", "")
                title = payload.get("title", "").strip()
                if conv_id and title:
                    ok = conv_db.update_conversation_title(conv_id, title)
                    await websocket.send_json({
                        "type": "conversation_renamed",
                        "payload": {"conversation_id": conv_id, "title": title, "ok": ok},
                    })

            elif msg_type == "get_personalities":
                plist = list_personalities()
                await websocket.send_json({
                    "type": "personalities_list",
                    "payload": {"personalities": plist, "current": current_personality.get("id")},
                })

            elif msg_type == "set_personality":
                pid = int(payload.get("personality_id", 0))
                p = get_personality(pid)
                if p:
                    current_personality = p
                    logger.info("Personality set to: %s", p["name"])
                    await websocket.send_json({
                        "type": "personality_set",
                        "payload": {"id": pid, "name": p["name"]},
                    })

            elif msg_type == "create_personality":
                name = payload.get("name", "").strip()
                if name:
                    p = create_personality(
                        name=name,
                        description=payload.get("description", ""),
                        system_prompt=payload.get("system_prompt", ""),
                    )
                    await websocket.send_json({
                        "type": "personality_created",
                        "payload": p,
                    })

            elif msg_type == "update_personality":
                pid = int(payload.get("id", 0))
                if pid:
                    p = update_personality(
                        pid=pid,
                        name=payload.get("name", ""),
                        description=payload.get("description", ""),
                        system_prompt=payload.get("system_prompt", ""),
                    )
                    if p:
                        # If this was our current personality, update reference
                        if current_personality.get("id") == pid:
                            current_personality = p
                        await websocket.send_json({
                            "type": "personality_updated",
                            "payload": p,
                        })

            elif msg_type == "delete_personality":
                pid = int(payload.get("id", 0))
                if pid:
                    ok = delete_personality(pid)
                    await websocket.send_json({
                        "type": "personality_deleted",
                        "payload": {"id": pid, "ok": ok},
                    })

            elif msg_type == "get_turns":
                conv_id = payload.get("conversation_id", current_conv_id or "")
                if conv_id:
                    turns = conv_db.get_turns(conv_id)
                    await websocket.send_json({
                        "type": "turns_list",
                        "payload": {"turns": turns, "conversation_id": conv_id},
                    })

            elif msg_type == "load_conversation":
                conv_id = payload.get("conversation_id", "")
                if conv_id:
                    conv = conv_db.get_conversation(conv_id)
                    if conv:
                        messages = conv_db.build_history_from_turns(conv_id)
                        session.load_history(messages)
                        current_conv_id = conv_id
                        turn_index = conv_db.get_turn_count(conv_id)
                        logger.info(
                            "Loaded conversation %s: %d turns, %d messages",
                            conv_id, turn_index, len(messages),
                        )
                        await websocket.send_json({
                            "type": "conversation_loaded",
                            "payload": {
                                "conversation": conv,
                                "turn_count": turn_index,
                            },
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "payload": {"message": f"Conversation not found: {conv_id}"},
                        })

            # --- Workspace sync handlers ---
            elif msg_type == "sync_workspace":
                ws_index = payload.get("workspace_index", 0)
                if 0 <= ws_index < len(config.workspaces):
                    result = await async_sync_workspace(config.workspaces[ws_index])
                    await websocket.send_json({
                        "type": "workspace_synced",
                        "payload": {
                            "workspace_index": ws_index,
                            "added": result["added"],
                            "updated": result["updated"],
                            "deleted": result["deleted"],
                            "errors": result.get("errors", []),
                        },
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Invalid workspace index: {ws_index}"},
                    })

            elif msg_type == "sync_all_workspaces":
                result = await async_sync_all_workspaces(config.workspaces)
                await websocket.send_json({
                    "type": "workspaces_synced",
                    "payload": {
                        "added": result["added"],
                        "updated": result["updated"],
                        "deleted": result["deleted"],
                        "errors": result.get("errors", []),
                    },
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
        if tts_task and not tts_task.done():
            tts_task.cancel()
        logger.info("Cleaning up session")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.server["host"],
        port=config.server["port"],
        log_level="info",
    )
