"""语音管线扩展 — TTS/STT 作为可插拔的管线阶段。

每个 Extension 独立于聊天核心逻辑，通过 enable/disable 控制。
引擎替换不影响管线代码。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from fastapi import WebSocket

from utils.markdown import strip_markdown

logger = logging.getLogger(__name__)


class PipelineExtension(ABC):
    """语音管线阶段的抽象基类。

    每个扩展实现 input -> process -> output 三阶段，
    由管线按序调用。扩展之间不互相依赖。
    """

    def __init__(self, name: str):
        self.name = name
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        logger.info("Extension '%s' enabled", self.name)

    def disable(self) -> None:
        self._enabled = False
        logger.info("Extension '%s' disabled", self.name)

    async def cancel(self) -> None:
        """取消当前正在进行的处理（默认空实现）。"""
        pass


# ═══════════════════════════════════════════════════════════════════════
# TTS Extension
# ═══════════════════════════════════════════════════════════════════════

class TTSExtension(PipelineExtension):
    """TTS 输出管线：将 LLM 回复文本转为语音流，发送到前端。

    引擎在构造时注入，切换引擎只需替换 engine 对象。
    """

    def __init__(self, engine: Any):
        super().__init__("tts")
        self._engine = engine
        self._tasks: list[Any] = []  # track running synthesis tasks
        self._streams: dict[str, str] = {}

    async def synthesize_and_send(self, websocket: WebSocket, text: str) -> None:
        """TTS 合成并流式发送到前端。

        独立于聊天核心逻辑——管线在 LLM 完成回复后调用此方法。
        """
        if not self._enabled or not text.strip():
            return

        import asyncio
        import uuid

        stream_id = uuid.uuid4().hex[:12]
        clean_text = strip_markdown(text)
        self._streams[stream_id] = clean_text

        async def _run():
            try:
                await websocket.send_json({
                    "type": "play_audio",
                    "payload": {"stream_id": stream_id},
                })
                async for chunk in self._engine.stream_synthesize(clean_text):
                    await websocket.send_json({
                        "type": "play_audio",
                        "payload": {"audio": chunk, "stream_id": stream_id},
                    })
            except Exception as exc:
                logger.error("TTS error for stream %s: %s", stream_id, exc)
            finally:
                self._streams.pop(stream_id, None)

        task = asyncio.create_task(_run())
        self._tasks.append(task)
        # 清理已完成的任务
        self._tasks = [t for t in self._tasks if not t.done()]

    async def cancel(self) -> None:
        """取消所有进行中的 TTS 任务。"""
        import asyncio
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._streams.clear()


# ═══════════════════════════════════════════════════════════════════════
# STT Extension (placeholder — 前端实现为主)
# ═══════════════════════════════════════════════════════════════════════

class STTExtension(PipelineExtension):
    """STT 输入管线：接收语音，转为文本。

    当前为占位——STT 主要在前端 ChatPanel 实现。
    后端仅负责接收音频数据并转写。
    """

    def __init__(self, engine: Any):
        super().__init__("stt")
        self._engine = engine

    async def transcribe(self, audio_path: str) -> str:
        """转写音频文件为文本。"""
        import asyncio
        return await asyncio.to_thread(self._engine.transcribe, audio_path)
