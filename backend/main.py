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
from db.init_db import init_db as init_db_conn
from db.workspace_sync import (
    async_sync_all_workspaces,
    async_sync_workspace,
    start_background_sync,
)
from voice import stt
from voice import tts as voice_tts
from agent import skills as skills_lib
from agent.personality import get_manager, ensure_seeded
from tools import create_default_registry
from mcp import MCPManager
from routers.notes import handle_secret_message, handle_public_notes
from routers.personalities import handle_personalities
from utils.markdown import strip_markdown

# Initialize databases and seed data on startup
init_db_conn("public")
init_db_conn("secret")
SKILLS = skills_lib.load_skills()
ensure_seeded()

# Personality manager — unified entry point for all personality operations
personality_manager = get_manager(config)

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

    # Initialize MCP Manager
    mcp_manager = MCPManager.from_config()
    await mcp_manager.connect_all()
    app.state.mcp_manager = mcp_manager
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
    # Disconnect MCP servers
    if app.state.mcp_manager:
        await app.state.mcp_manager.disconnect_all()


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


async def _send_thinking(websocket: WebSocket, content: str):
    """Send a thinking status message to the frontend."""
    await _ws_send_safe(websocket, "thinking", {"content": content})


async def _send_done(websocket: WebSocket):
    """Signal the frontend that the current turn is fully complete."""
    await _ws_send_safe(websocket, "done", {})


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    client = get_openai_client()

    # Per-connection tool callbacks (capture websocket in closure)
    async def on_tool_call(name: str, args: dict, call_id: str = ""):
        logger.debug("WS → tool_call_start: %s id=%s args=%s",
                     name, call_id, json.dumps(args, ensure_ascii=False)[:120])
        await _ws_send_safe(websocket, "tool_call_start", {
            "id": call_id,
            "name": name,
            "args": args,
        })

    async def on_tool_result(name: str, result: dict, call_id: str = ""):
        duration_ms = result.pop("_duration_ms", 0) if isinstance(result, dict) else 0
        success = result.get("success", True) if isinstance(result, dict) else True
        if success:
            logger.debug("WS → tool_call_result: %s id=%s duration=%dms",
                         name, call_id, duration_ms)
            await _ws_send_safe(websocket, "tool_call_result", {
                "id": call_id,
                "name": name,
                "result": result,
                "duration_ms": duration_ms,
            })
        else:
            logger.debug("WS → tool_call_error: %s id=%s error=%s",
                         name, call_id, result.get("message", ""))
            await _ws_send_safe(websocket, "tool_call_error", {
                "id": call_id,
                "name": name,
                "error": result.get("message", str(result)) if isinstance(result, dict) else str(result),
            })

    # Build unified tool dispatcher (ToolProvider interface)
    from tools.dispatcher import ToolDispatcher
    from mcp.provider import MCPToolProvider
    tool_dispatcher = ToolDispatcher()
    tool_dispatcher.register(tool_registry)
    if app.state.mcp_manager:
        tool_dispatcher.register(MCPToolProvider(app.state.mcp_manager))

    session = ChatSession(
        client=client,
        model_name=config.model["model_name"],
        max_rounds=config.chat["max_history_rounds"],
        tool_dispatcher=tool_dispatcher,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
        on_thinking=lambda c: _send_thinking(websocket, c),
    )
    tts_task: asyncio.Task | None = None
    tts_enabled = True
    compact_enabled = False
    current_conv_id: Optional[str] = None
    turn_index = 0
    current_personality = personality_manager.get_default()  # active personality (DB record)

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
                await handle_secret_message(websocket, msg_type, payload)
                continue

            # --- Routers: notes ---
            if await handle_public_notes(websocket, msg_type, payload):
                continue

            # --- Routers: personalities ---
            updated_personality = await handle_personalities(
                websocket, msg_type, payload, personality_manager, current_personality
            )
            if updated_personality is not None:
                current_personality = updated_personality
            if msg_type.startswith(("get_personalities", "set_personality", "create_personality",
                                     "update_personality", "delete_personality", "reseed_personalities")):
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

                # Build tool list: built-in (possibly skill-filtered) + MCP (always available)
                mcp_manager = app.state.mcp_manager
                mcp_tools = mcp_manager.get_all_tools() if mcp_manager else []
                active_tool_schemas = tool_registry.get_schemas() + mcp_tools

                for command, skill in SKILLS.items():
                    if user_text.startswith(command):
                        active_skill = skill
                        logger.info("Skill activated: %s (command=%s)", skill["name"], command)
                        logger.debug("Skill allowed_tools: %s", skill.get("allowed_tools", []))
                        augmented_text = _build_skill_prompt(skill, user_text)
                        active_tool_schemas = tool_registry.get_for_skill(skill) + mcp_tools
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
                # Build system prompt via pipeline (消除硬编码)
                from prompt import PromptPipeline, PromptContext
                pipeline = PromptPipeline.default(personality_manager, current_personality)
                prompt_ctx = PromptContext(
                    user_name=config.user.get("name", "") or "用户",
                    compact_enabled=compact_enabled,
                )
                personality_prompt = pipeline.build(prompt_ctx)
                if personality_prompt:
                    session.set_system_prompt(personality_prompt)

                session.add_user_message(augmented_text)
                session.clear_stop()

                collected_chunks: list[str] = []
                import re as _re
                _tag_re = _re.compile(r'\[?!emotion:\s*\w+\s*!\]?')
                _stream_buf: str = ""
                try:
                    async for event_type, data in session.stream_with_tool_loop(active_tool_schemas):
                        if event_type == "content":
                            collected_chunks.append(data)
                            _stream_buf += data
                            # Buffer: keep last 30 chars to catch emotion tag at end
                            if len(_stream_buf) > 30:
                                safe = _stream_buf[:-30]
                                _stream_buf = _stream_buf[-30:]
                                await websocket.send_json({
                                    "type": "message_chunk",
                                    "payload": {"content": safe},
                                })
                        # tool_call events are already pushed via on_tool_call/on_tool_result callbacks
                    # Flush remaining buffer (strip tag if present)
                    if _stream_buf:
                        clean_tail = _tag_re.sub('', _stream_buf)
                        if clean_tail:
                            await websocket.send_json({
                                "type": "message_chunk",
                                "payload": {"content": clean_tail},
                            })
                except Exception as exc:
                    logger.error("Stream error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Model error: {exc}"},
                    })
                else:
                    full = "".join(collected_chunks)
                    # Extract emotion tag from response
                    clean_content, emotion = personality_manager.extract_emotion(full)
                    partial = session.stopped()
                    trace = session.get_trace()
                    logger.info(
                        "Chat complete: content_chars=%d partial=%s trace_steps=%d emotion=%s",
                        len(clean_content), partial, len(trace), emotion,
                    )
                    await websocket.send_json({
                        "type": "message_complete",
                        "payload": {
                            "full_content": clean_content,
                            "partial": partial,
                            "trace": trace,
                            "emotion": emotion,
                        },
                    })

                    # Send done AFTER all chunks + message_complete
                    _send_done(websocket)

                    # Auto TTS (use clean content without emotion tag)
                    if clean_content.strip() and tts_enabled:
                        if tts_task and not tts_task.done():
                            tts_task.cancel()
                        tts_task = asyncio.create_task(_synthesize_and_send(websocket, clean_content))

                    # Auto-save conversation turn (use clean content)
                    if not partial:
                        if current_conv_id is None:
                            conv = conv_db.create_conversation(title=user_text)
                            current_conv_id = conv["id"]
                            turn_index = 0
                            logger.info("Auto-created conversation %s", current_conv_id)
                        elif not conv_db.get_conversation(current_conv_id):
                            logger.warning("Conversation %s no longer exists, auto-creating new one", current_conv_id)
                            conv = conv_db.create_conversation(title=user_text)
                            current_conv_id = conv["id"]
                            turn_index = 0

                        trace = session.get_trace()
                        conv_db.add_turn(
                            conv_id=current_conv_id,
                            turn_index=turn_index,
                            user_message=user_text,
                            assistant_content=clean_content,
                            trace=trace,
                        )
                        turn_index += 1
                        logger.debug(
                            "Saved turn %d in conv %s (%d trace steps)",
                            turn_index - 1, current_conv_id, len(trace),
                        )

                    # Skill markdown preview (use clean content)
                    if active_skill:
                        await websocket.send_json({
                            "type": "markdown_preview",
                            "payload": {
                                "content": clean_content,
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

            elif msg_type == "compact_mode":
                compact_enabled = payload.get("enabled", False)
                logger.info("Compact mode: %s", compact_enabled)

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
                    "user": config.user,
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
