# TTS 流式播报 — 设计文档

**日期**: 2026-06-05
**状态**: 已实现

## 背景

当前 TTS 播报采用 edge-tts 生成完整 MP3 文件，前端下载后播放：
```
AI回复完 → synthesize() → 写完整MP3到磁盘 → WS通知前端url → <audio>下载文件 → 播放
```

问题：
- 必须等整个 MP3 生成完毕才能开始播放，首音延迟高
- MP3 文件落盘产生磁盘 I/O 和临时文件残留
- 前端停止播放时后端不知道，继续浪费资源合成

## 方案

利用 edge-tts 的 `Communicate.stream()` 异步生成器，边合成边推送音频块：

```
AI回复完 → WS通知前端stream URL → <audio>连接流式端点 → 边生成边推送MP3块 → 边收边播
```

### 架构

```
┌──────────────────────────────────────────────────────────────────┐
│  main.py                                                         │
│                                                                   │
│  _synthesize_and_send(ws, text)          GET /audio/stream/{id}  │
│  ┌─────────────────────────┐           ┌──────────────────────┐  │
│  │ store text → _tts_dict   │           │ text = _tts_dict.pop() │  │
│  │ send play_audio ws msg  │           │ while chunk ← tts:    │  │
│  │ (fast, returns quickly) │           │   yield chunk          │  │
│  └─────────────────────────┘           │   if disconnected:break │  │
│                                         └──────────────────────┘  │
│                                                    │              │
│  voice/tts.py                                      │              │
│  ┌──────────────────────────────┐                  │              │
│  │ stream_synthesize(text):     │ ←───────────────┘              │
│  │   for chunk in edge_tts:     │                                 │
│  │     if audio: yield data     │                                 │
│  └──────────────────────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 数据流

1. AI 回复完成 → `_synthesize_and_send()` 生成 `stream_id`，存储 text，发送 `play_audio` 消息
2. 前端收到 → `new Audio(url)` → 浏览器发起 `GET /audio/stream/{stream_id}`
3. 后端 `StreamingResponse` → 调用 `voice_tts.stream_synthesize()` → 逐块 yield MP3
4. 浏览器 `<audio>` 标签原生支持流式 MP3，边收边解码播放
5. 用户停止/新消息 → 前端 `stopAudio()` 清空 `audio.src` → 浏览器 abort HTTP 请求
6. 后端 `request.is_disconnected` 为 True → 停止迭代，资源释放

### 停止能力对比

| 场景 | 旧方案 | 新方案 |
|------|--------|--------|
| 前端停止 | `audio.pause()` | `audio.pause()` → HTTP abort |
| 后端感知 | ❌ 不知道 | ✅ 检测断开，立即取消 |
| 资源浪费 | 整段 MP3 白做 | 仅当前 chunk 浪费 |

## 改动文件

### `backend/voice/tts.py`
- 新增 `stream_synthesize(text)` 异步生成器，逐块 yield MP3 bytes
- 保留原有 `synthesize()` 和 `synthesize_sync()` 不变

### `backend/main.py`
- 新增 `_tts_streams: dict[str, str]` 内存字典，存储 stream_id → text
- 新增 `GET /audio/stream/{stream_id}` 流式端点（`StreamingResponse`）
- 修改 `_synthesize_and_send()`：不再调用 `synthesize()`，改为存储 text 并发送流式 URL
- 保留 `GET /audio/{filename}` 端点（兼容旧逻辑）

### `electron-app/`（零改动）
- `<audio>` 标签原生支持流式 MP3
- `play_audio` 消息格式不变（仅 URL 路径变化）
- `stopAudio()` 行为不变

## 关键实现细节

### stream_synthesize
```python
async def stream_synthesize(text: str):
    communicate = edge_tts.Communicate(text=text, voice=VOICE)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
```

### 流式端点
```python
@app.get("/audio/stream/{stream_id}")
async def stream_audio(stream_id: str, request: Request):
    text = _tts_streams.pop(stream_id, None)
    if text is None:
        return {"error": "Stream not found or already consumed"}, 404
    async def generate():
        async for chunk in voice_tts.stream_synthesize(text):
            if await request.is_disconnected():
                break
            yield chunk
    return StreamingResponse(generate(), media_type="audio/mpeg")
```

### _synthesize_and_send
```python
async def _synthesize_and_send(websocket, text):
    stream_id = os.urandom(6).hex()
    _tts_streams[stream_id] = text
    await _ws_send_safe(websocket, "play_audio", {
        "url": f"http://127.0.0.1:8765/audio/stream/{stream_id}"
    })
```

## 风险与边界

- `_tts_streams` dict：仅在服务端内存中，重启丢失但无影响。极端情况下若前端永不请求 URL，条目会残留（大小可忽略）
- 流式 MP3 兼容性：所有现代浏览器 `<audio>` 标签均支持
- `request.is_disconnected`：Starlette/FastAPI 原生支持，无需额外依赖
- edge-tts 网络波动：`StreamingResponse` 自然结束，前端 `<audio>` 停止播放，用户体验降级但不会报错
