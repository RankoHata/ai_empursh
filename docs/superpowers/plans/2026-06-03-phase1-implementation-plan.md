# Phase 1: Project Skeleton & Basic Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Electron + React desktop app that communicates via WebSocket with a Python FastAPI backend to provide streaming chat through DeepSeek API.

**Architecture:** Electron main process creates a BrowserWindow loading a Vite-bundled React app. React app connects to a Python FastAPI WebSocket server (127.0.0.1:8765), sends chat messages, receives streaming tokens, and renders them in a chat UI. Python backend uses the OpenAI SDK pointed at DeepSeek's API for streaming completions.

**Tech Stack:** Electron 33+, Vite 6+, React 18+, FastAPI 0.110+, openai SDK 1.30+, Python 3.10, Node.js 22

**Proxy:** All package managers use `127.0.0.1:7890`. Python HTTP requests route through proxy via environment variables.

---

## File Structure (what we'll create)

```
f:/AI/ai_empursh/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, /ws endpoint
│   ├── agent/
│   │   ├── __init__.py      # Empty, makes agent a package
│   │   └── chat.py          # stream_chat() — DeepSeek streaming + stop support
│   ├── config.yaml           # Model settings, server host/port
│   └── requirements.txt      # fastapi, uvicorn, openai, pyyaml
│
├── electron-app/
│   ├── package.json          # Electron, React, Vite deps
│   ├── forge.config.js       # Electron Forge config
│   ├── vite.main.config.mjs  # Vite config for main process
│   ├── vite.preload.config.mjs # Vite config for preload
│   ├── vite.renderer.config.mjs # Vite config for renderer (React)
│   ├── index.html            # HTML entry point (renderer)
│   ├── src/
│   │   ├── main.js           # Electron main process: create window
│   │   ├── preload.js        # Context bridge for IPC
│   │   └── renderer/
│   │       ├── App.jsx       # Root component: state hub
│   │       ├── App.css       # All styles
│   │       ├── main.jsx      # React DOM entry point
│   │       ├── components/
│   │       │   ├── ChatPanel.jsx    # Message list + input area
│   │       │   ├── MessageBubble.jsx # Single message rendering
│   │       │   └── StatusBar.jsx    # Connection status indicator
│   │       └── hooks/
│   │           └── useWebSocket.js  # WS connect, reconnect, send, receive
│   └── assets/               # (empty for now)
```

---

### Task 1: Python Backend Skeleton

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.yaml`
- Create: `backend/agent/__init__.py`

- [ ] **Step 1: Create backend directory structure**

Run:
```bash
mkdir -p f:/AI/ai_empursh/backend/agent
```

- [ ] **Step 2: Write requirements.txt**

Write `f:/AI/ai_empursh/backend/requirements.txt`:
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
openai>=1.30.0
pyyaml>=6.0
```

- [ ] **Step 3: Install Python dependencies with proxy**

Run:
```bash
cd f:/AI/ai_empursh/backend
pip install --proxy http://127.0.0.1:7890 -r requirements.txt
```

Expected: Packages install without errors.

- [ ] **Step 4: Write config.yaml**

Write `f:/AI/ai_empursh/backend/config.yaml`:
```yaml
model:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-your-key-here"
  model_name: "deepseek-chat"
  max_tokens: 4096

server:
  host: "127.0.0.1"
  port: 8765

chat:
  max_history_rounds: 20
```

- [ ] **Step 5: Write agent/__init__.py**

Write `f:/AI/ai_empursh/backend/agent/__init__.py`:
```python
# agent package
```

- [ ] **Step 6: Commit**

```bash
cd f:/AI/ai_empursh
git add backend/requirements.txt backend/config.yaml backend/agent/__init__.py
git commit -m "feat: add Python backend skeleton (config, deps, agent package)"
```

---

### Task 2: Backend Chat Engine

**Files:**
- Create: `backend/agent/chat.py`

- [ ] **Step 1: Write chat.py**

Write `f:/AI/ai_empursh/backend/agent/chat.py`:
```python
"""
DeepSeek API streaming chat engine with stop-signal support.

Each WebSocket connection gets its own ChatSession, which maintains
conversation history and coordinates async streaming with cancellation.
"""

import asyncio
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ChatSession:
    """Per-connection session holding conversation history and a stop event."""

    def __init__(self, client: AsyncOpenAI, model_name: str, max_rounds: int = 20):
        self._client = client
        self._model_name = model_name
        self._max_messages = max_rounds * 2  # user + assistant per round
        self._history: list[dict[str, str]] = []
        self._stop_event = asyncio.Event()

    def add_user_message(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self._history.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self) -> None:
        """Keep only the most recent N messages to stay within context window."""
        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages:]

    def request_stop(self) -> None:
        """Signal the streaming loop to stop."""
        self._stop_event.set()

    def clear_stop(self) -> None:
        """Reset stop event for the next request."""
        self._stop_event.clear()

    def stopped(self) -> bool:
        return self._stop_event.is_set()

    async def stream_chat(self) -> AsyncGenerator[str, None]:
        """
        Stream tokens from DeepSeek API, yielding each content delta.
        Checks self._stop_event before each yield; breaks when set.
        """
        try:
            stream = await self._client.chat.completions.create(
                model=self._model_name,
                messages=self._history,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("Failed to create chat completion: %s", exc)
            raise

        collected: list[str] = []
        try:
            async for chunk in stream:
                if self._stop_event.is_set():
                    logger.info("Chat streaming stopped by user request")
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    yield delta.content
        finally:
            # Close the stream to free resources
            await stream.close()

        full_text = "".join(collected)
        if full_text:
            self.add_assistant_message(full_text)
```

- [ ] **Step 2: Verify module imports correctly**

Run:
```bash
cd f:/AI/ai_empursh/backend
python -c "from agent.chat import ChatSession; print('ChatSession imported OK')"
```

Expected: `ChatSession imported OK`

- [ ] **Step 3: Commit**

```bash
cd f:/AI/ai_empursh
git add backend/agent/chat.py
git commit -m "feat: add ChatSession — DeepSeek streaming with stop-signal support"
```

---

### Task 3: Backend WebSocket Server

**Files:**
- Create: `backend/main.py`
- Modify: `backend/agent/__init__.py` (if needed — no, it's fine as-is)

- [ ] **Step 1: Write main.py**

Write `f:/AI/ai_empursh/backend/main.py`:
```python
"""
FastAPI application serving the AI Companion backend.

Start with:  python main.py
Stop with:   Ctrl+C
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from agent.chat import ChatSession

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
from typing import Optional


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


@app.get("/")
async def health_check():
    return {"status": "running", "model": MODEL_CFG["model_name"]}


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

                session.add_user_message(user_text)
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

            elif msg_type == "stop":
                session.request_stop()
                logger.info("Stop requested by client")

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
```

- [ ] **Step 2: Verify FastAPI app starts correctly**

Run (in one terminal):
```bash
cd f:/AI/ai_empursh/backend
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
python main.py
```

Expected output:
```
INFO:     Started server process
INFO:backend:Starting AI Companion backend...
INFO:backend:Model: deepseek-chat @ https://api.deepseek.com/v1
INFO:backend:Server: 127.0.0.1:8765
INFO:backend:OpenAI client ready
INFO:     Uvicorn running on http://127.0.0.1:8765
```

Press Ctrl+C after verifying.

- [ ] **Step 3: Test health check endpoint**

With server running, open another terminal and run:
```bash
curl http://127.0.0.1:8765/
```

Expected: `{"status":"running","model":"deepseek-chat"}`

- [ ] **Step 4: Commit**

```bash
cd f:/AI/ai_empursh
git add backend/main.py
git commit -m "feat: add FastAPI WebSocket server with health check endpoint"
```

---

### Task 4: Frontend Project Scaffold

**Files:**
- Create: `electron-app/package.json`
- Create: `electron-app/forge.config.js`
- Create: `electron-app/vite.main.config.mjs`
- Create: `electron-app/vite.preload.config.mjs`
- Create: `electron-app/vite.renderer.config.mjs`
- Create: `electron-app/index.html`

- [ ] **Step 1: Create electron-app directory**

```bash
mkdir -p f:/AI/ai_empursh/electron-app/src/renderer/components
mkdir -p f:/AI/ai_empursh/electron-app/src/renderer/hooks
mkdir -p f:/AI/ai_empursh/electron-app/src/renderer/styles
mkdir -p f:/AI/ai_empursh/electron-app/assets
```

- [ ] **Step 2: Write package.json**

Write `f:/AI/ai_empursh/electron-app/package.json`:
```json
{
  "name": "desktop-ai-companion",
  "version": "0.1.0",
  "description": "AI Desktop Companion — Phase 1",
  "main": ".vite/build/main.js",
  "scripts": {
    "start": "electron-forge start",
    "package": "electron-forge package",
    "make": "electron-forge make"
  },
  "devDependencies": {
    "@electron-forge/cli": "^7.6.0",
    "@electron-forge/maker-deb": "^7.6.0",
    "@electron-forge/maker-rpm": "^7.6.0",
    "@electron-forge/maker-squirrel": "^7.6.0",
    "@electron-forge/maker-zip": "^7.6.0",
    "@electron-forge/plugin-vite": "^7.6.0",
    "@vitejs/plugin-react": "^4.3.4",
    "electron": "33.2.1"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }
}
```

- [ ] **Step 3: Write forge.config.js**

Write `f:/AI/ai_empursh/electron-app/forge.config.js`:
```js
const { VitePlugin } = require('@electron-forge/plugin-vite');

module.exports = {
  packagerConfig: {
    asar: true,
    name: 'AI Companion',
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      config: {},
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['win32'],
    },
  ],
  plugins: [
    new VitePlugin({
      build: [
        {
          entry: 'src/main.js',
          config: 'vite.main.config.mjs',
          target: 'main',
        },
        {
          entry: 'src/preload.js',
          config: 'vite.preload.config.mjs',
          target: 'preload',
        },
      ],
      renderer: [
        {
          name: 'main_window',
          config: 'vite.renderer.config.mjs',
        },
      ],
    }),
  ],
};
```

- [ ] **Step 4: Write Vite configs**

Write `f:/AI/ai_empursh/electron-app/vite.main.config.mjs`:
```js
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      external: ['electron'],
    },
  },
});
```

Write `f:/AI/ai_empursh/electron-app/vite.preload.config.mjs`:
```js
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      external: ['electron'],
    },
  },
});
```

Write `f:/AI/ai_empursh/electron-app/vite.renderer.config.mjs`:
```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: '.vite/renderer/main_window',
  },
});
```

- [ ] **Step 5: Write index.html**

Write `f:/AI/ai_empursh/electron-app/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws://127.0.0.1:8765" />
  <title>AI 桌面助理</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/renderer/main.jsx"></script>
</body>
</html>
```

- [ ] **Step 6: Install npm dependencies with proxy**

Run:
```bash
cd f:/AI/ai_empursh/electron-app
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
set NODE_EXTRA_CA_CERTS=
npm config set proxy http://127.0.0.1:7890
npm config set https-proxy http://127.0.0.1:7890
npm install
```

Expected: Dependencies install successfully (may take 1-2 minutes).

- [ ] **Step 7: Commit**

```bash
cd f:/AI/ai_empursh
git add electron-app/package.json electron-app/forge.config.js electron-app/vite.*.config.mjs electron-app/index.html
git commit -m "feat: scaffold Electron + Vite + React frontend project"
```

---

### Task 5: Frontend WebSocket Hook

**Files:**
- Create: `electron-app/src/renderer/hooks/useWebSocket.js`

- [ ] **Step 1: Write useWebSocket.js**

Write `f:/AI/ai_empursh/electron-app/src/renderer/hooks/useWebSocket.js`:
```js
import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://127.0.0.1:8765/ws';
const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;

/**
 * useWebSocket — manages a persistent WebSocket connection to the backend.
 *
 * @param {Object} handlers — { onMessage(type, payload) } called for each server message
 * @returns {{ connectionStatus, send }}
 *   connectionStatus: "disconnected" | "connecting" | "connected"
 *   send(type, payload): send a JSON message to the server
 */
export default function useWebSocket(handlers = {}) {
  const { onMessage } = handlers;

  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // Mutable refs so the reconnect logic always sees latest values
  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_MS);
  const reconnectTimerRef = useRef(null);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);

  // Keep handler ref fresh without re-triggering the connection effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    setConnectionStatus('connecting');

    const delay = reconnectDelayRef.current;
    reconnectTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, delay);

    // Exponential backoff
    reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_MS);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnectionStatus('connected');
      reconnectDelayRef.current = INITIAL_RECONNECT_MS;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(event.data);
        if (onMessageRef.current) {
          onMessageRef.current(msg.type, msg.payload);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, reconnect there
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [scheduleReconnect]);

  // Start connection on mount, clean up on unmount
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const send = useCallback((type, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
      return true;
    }
    return false;
  }, []);

  return { connectionStatus, send };
}
```

- [ ] **Step 2: Commit**

```bash
cd f:/AI/ai_empursh
git add electron-app/src/renderer/hooks/useWebSocket.js
git commit -m "feat: add useWebSocket hook with exponential-backoff reconnect"
```

---

### Task 6: Frontend React Components

**Files:**
- Create: `electron-app/src/renderer/main.jsx`
- Create: `electron-app/src/renderer/App.jsx`
- Create: `electron-app/src/renderer/components/StatusBar.jsx`
- Create: `electron-app/src/renderer/components/MessageBubble.jsx`
- Create: `electron-app/src/renderer/components/ChatPanel.jsx`
- Create: `electron-app/src/renderer/App.css`

- [ ] **Step 1: Write main.jsx (React entry point)**

Write `f:/AI/ai_empursh/electron-app/src/renderer/main.jsx`:
```jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './App.css';

const root = createRoot(document.getElementById('root'));
root.render(<App />);
```

- [ ] **Step 2: Write App.css (full styles)**

Write `f:/AI/ai_empursh/electron-app/src/renderer/App.css`:
```css
/* === Reset & Global === */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-input: #0f3460;
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0a0;
  --accent: #e94560;
  --accent-hover: #ff6b81;
  --success: #4ecca3;
  --warning: #f0a500;
  --border: #2a2a4a;
  --bubble-user: #1a3a5c;
  --bubble-assistant: #1e2a3a;
  --radius: 12px;
  --font: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

html, body, #root {
  height: 100%;
  font-family: var(--font);
  background: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
}

/* === App Layout === */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
}

/* === StatusBar === */
.status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.disconnected { background: var(--warning); }
.status-dot.connecting { background: var(--warning); animation: pulse 1s infinite; }
.status-dot.connected { background: var(--success); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* === ChatPanel === */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.messages-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 14px;
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.input-area input {
  flex: 1;
  padding: 10px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  font-family: var(--font);
}
.input-area input:focus {
  border-color: var(--accent);
}
.input-area input::placeholder {
  color: var(--text-secondary);
}

.btn-send {
  padding: 10px 20px;
  border-radius: var(--radius);
  border: none;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  font-family: var(--font);
  white-space: nowrap;
  transition: background 0.2s;
}
.btn-send:hover { background: var(--accent-hover); }
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-stop {
  padding: 10px 20px;
  border-radius: var(--radius);
  border: 1px solid var(--warning);
  background: transparent;
  color: var(--warning);
  font-size: 14px;
  cursor: pointer;
  font-family: var(--font);
  white-space: nowrap;
  transition: background 0.2s;
}
.btn-stop:hover { background: rgba(240, 165, 0, 0.1); }

/* === MessageBubble === */
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 80%;
  animation: fadeIn 0.2s ease-in;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-bubble.user {
  align-self: flex-end;
}
.message-bubble.assistant {
  align-self: flex-start;
}

.bubble-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
  padding: 0 4px;
}

.bubble-content {
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-bubble.user .bubble-content {
  background: var(--bubble-user);
  border-bottom-right-radius: 4px;
}
.message-bubble.assistant .bubble-content {
  background: var(--bubble-assistant);
  border-bottom-left-radius: 4px;
}

.bubble-content.streaming::after {
  content: '▊';
  animation: blink 1s step-end infinite;
  color: var(--accent);
}
@keyframes blink {
  50% { opacity: 0; }
}

.bubble-timestamp {
  font-size: 10px;
  color: var(--text-secondary);
  margin-top: 4px;
  padding: 0 4px;
}
```

- [ ] **Step 3: Write StatusBar.jsx**

Write `f:/AI/ai_empursh/electron-app/src/renderer/components/StatusBar.jsx`:
```jsx
import React from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
  connected: '已连接',
};

export default function StatusBar({ status }) {
  return (
    <div className="status-bar">
      <span className={`status-dot ${status}`} />
      <span>{STATUS_LABELS[status] || status}</span>
    </div>
  );
}
```

- [ ] **Step 4: Write MessageBubble.jsx**

Write `f:/AI/ai_empursh/electron-app/src/renderer/components/MessageBubble.jsx`:
```jsx
import React from 'react';

export default function MessageBubble({ message }) {
  const { role, content, isStreaming, timestamp } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={bubbleClass}>
      <span className="bubble-label">{label}</span>
      <div className={contentClass}>{content}</div>
      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
```

- [ ] **Step 5: Write ChatPanel.jsx**

Write `f:/AI/ai_empursh/electron-app/src/renderer/components/ChatPanel.jsx`:
```jsx
import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';

export default function ChatPanel({ messages, isStreaming, onSend, onStop }) {
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <div className="messages-area">
        {messages.length === 0 && (
          <div className="messages-empty">
            <span>向 AI 助理发送消息开始对话</span>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        <input
          type="text"
          placeholder="输入消息... (Enter 发送)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={false}
          autoFocus
        />
        {isStreaming ? (
          <button className="btn-stop" onClick={onStop}>停止</button>
        ) : (
          <button className="btn-send" onClick={handleSend} disabled={!input.trim()}>
            发送
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Write App.jsx (root component)**

Write `f:/AI/ai_empursh/electron-app/src/renderer/App.jsx`:
```jsx
import React, { useState, useCallback, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import ChatPanel from './components/ChatPanel';

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Use refs for values that onMessage closure needs to see without re-subscribing
  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  messagesRef.current = messages;
  isStreamingRef.current = isStreaming;

  const handleMessage = useCallback((type, payload) => {
    switch (type) {
      case 'message_chunk': {
        const chunk = payload.content || '';
        if (!isStreamingRef.current) {
          // First chunk: create the assistant message
          setMessages((prev) => [
            ...prev,
            {
              id: nextId++,
              role: 'assistant',
              content: chunk,
              isStreaming: true,
              timestamp: Date.now(),
            },
          ]);
          setIsStreaming(true);
        } else {
          // Append to the last (streaming) message
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + chunk,
              };
            }
            return updated;
          });
        }
        break;
      }

      case 'message_complete': {
        // Mark the streaming message as complete
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.isStreaming) {
            updated[updated.length - 1] = {
              ...last,
              isStreaming: false,
            };
          }
          return updated;
        });
        setIsStreaming(false);
        break;
      }

      case 'error': {
        console.error('Server error:', payload.message);
        // Show error as a system message
        setMessages((prev) => [
          ...prev,
          {
            id: nextId++,
            role: 'assistant',
            content: `❌ 错误: ${payload.message}`,
            isStreaming: false,
            timestamp: Date.now(),
          },
        ]);
        setIsStreaming(false);
        break;
      }

      default:
        break;
    }
  }, []);

  const { connectionStatus, send } = useWebSocket({ onMessage: handleMessage });

  const handleSend = useCallback(
    (text) => {
      // Add user message to local state
      const userMsg = {
        id: nextId++,
        role: 'user',
        content: text,
        isStreaming: false,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const sent = send('chat', { message: text });
      if (!sent) {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId++,
            role: 'assistant',
            content: '❌ 无法发送消息：后端未连接',
            isStreaming: false,
            timestamp: Date.now(),
          },
        ]);
      }
    },
    [send],
  );

  const handleStop = useCallback(() => {
    send('stop', {});
  }, [send]);

  return (
    <div className="app-container">
      <StatusBar status={connectionStatus} />
      <ChatPanel
        messages={messages}
        isStreaming={isStreaming}
        onSend={handleSend}
        onStop={handleStop}
      />
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
cd f:/AI/ai_empursh
git add electron-app/src/renderer/
git commit -m "feat: add React components — ChatPanel, MessageBubble, StatusBar, App"
```

---

### Task 7: Electron Main Process & Preload

**Files:**
- Create: `electron-app/src/main.js`
- Create: `electron-app/src/preload.js`

- [ ] **Step 1: Write preload.js**

Write `f:/AI/ai_empursh/electron-app/src/preload.js`:
```js
// Preload script — runs in a sandboxed context before the renderer loads.
// Use contextBridge to expose a safe, minimal API if needed later.
// For Phase 1 the renderer communicates directly via WebSocket, so
// preload only needs to exist for Forge's build pipeline.

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
});
```

- [ ] **Step 2: Write main.js**

Write `f:/AI/ai_empursh/electron-app/src/main.js`:
```js
const { app, BrowserWindow } = require('electron');
const path = require('path');

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 680,
    minWidth: 480,
    minHeight: 400,
    title: 'AI 桌面助理',
    backgroundColor: '#1a1a2e',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // In development, Forge serves the Vite dev server URL.
  // In production, load the built index.html.
  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(
      path.join(__dirname, `../renderer/main_window/index.html`)
    );
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
```

- [ ] **Step 3: Verify Electron app launches**

Before launching, ensure Python backend is NOT running (we want to test the disconnected state first).

Run:
```bash
cd f:/AI/ai_empursh/electron-app
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
npm start
```

Expected:
- A dark-themed window opens with "AI 桌面助理" title
- Status bar shows "未连接 — 请启动后端服务"
- Chat shows placeholder text "向 AI 助理发送消息开始对话"

Close the window (Ctrl+C in terminal).

- [ ] **Step 4: Commit**

```bash
cd f:/AI/ai_empursh
git add electron-app/src/main.js electron-app/src/preload.js
git commit -m "feat: add Electron main process and preload"
```

---

### Task 8: Integration — End-to-End Verification

**Files:**
- Create: `.gitignore`
- Create: `README.md` (project root — brief setup guide)

- [ ] **Step 1: Write .gitignore**

Write `f:/AI/ai_empursh/.gitignore`:
```
# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/

# Build output
electron-app/.vite/
electron-app/out/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Superpowers
.superpowers/

# Config (contains API keys)
backend/config.yaml
```

**Important:** After writing `.gitignore`, remove config.yaml from git tracking if it was already committed:
```bash
cd f:/AI/ai_empursh
git rm --cached backend/config.yaml 2>/dev/null || true
```

- [ ] **Step 2: Create a config.yaml.example (safe to commit)**

Write `f:/AI/ai_empursh/backend/config.yaml.example`:
```yaml
model:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-your-key-here"
  model_name: "deepseek-chat"
  max_tokens: 4096

server:
  host: "127.0.0.1"
  port: 8765

chat:
  max_history_rounds: 20
```

- [ ] **Step 3: Write project README.md**

Write `f:/AI/ai_empursh/README.md`:
```markdown
# AI 桌面助理 (Desktop AI Companion)

阶段 1：项目骨架与基础聊天功能。

## 前置条件

- Python 3.10+ (with pip)
- Node.js 18+ (with npm)
- DeepSeek API Key (or any OpenAI-compatible API)

## 快速开始

### 1. 配置 API Key

```bash
cp backend/config.yaml.example backend/config.yaml
# 编辑 backend/config.yaml，填入你的 api_key
```

### 2. 安装 Python 依赖

```bash
cd backend
pip install --proxy http://127.0.0.1:7890 -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd electron-app
npm config set proxy http://127.0.0.1:7890
npm config set https-proxy http://127.0.0.1:7890
npm install
```

### 4. 启动后端

```bash
# Windows (需要代理时)
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
cd backend
python main.py
```

### 5. 启动前端（另一个终端）

```bash
cd electron-app
npm start
```

### 6. 开始聊天

在 Electron 窗口中输入消息，按 Enter 发送。
```

- [ ] **Step 4: Full integration test**

Terminal 1 — start backend:
```bash
cd f:/AI/ai_empursh/backend
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
python main.py
```

Terminal 2 — start frontend:
```bash
cd f:/AI/ai_empursh/electron-app
npm start
```

**Verify each acceptance criterion:**

1. ✅ Electron 窗口正确显示，标题 "AI 桌面助理"
2. ✅ StatusBar 显示"已连接"（绿色圆点）
3. ✅ 输入 "你好，请用中文回复"，助理流式逐字显示回复
4. ✅ 继续输入 "我刚才说了什么？"，助理正确引用上文
5. ✅ 在回复进行中点击"停止"按钮，生成中断
6. ✅ 关闭后端，StatusBar 变为"未连接"；重新启动后端，自动重连

- [ ] **Step 5: Final commit**

```bash
cd f:/AI/ai_empursh
git add .gitignore backend/config.yaml.example README.md
git commit -m "chore: add .gitignore, config example, and README setup guide
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Summary of All Commits

| # | Commit Message | Files |
|---|---------------|-------|
| 1 | `feat: add Python backend skeleton (config, deps, agent package)` | requirements.txt, config.yaml, agent/__init__.py |
| 2 | `feat: add ChatSession — DeepSeek streaming with stop-signal support` | agent/chat.py |
| 3 | `feat: add FastAPI WebSocket server with health check endpoint` | main.py |
| 4 | `feat: scaffold Electron + Vite + React frontend project` | package.json, forge.config.js, vite configs, index.html |
| 5 | `feat: add useWebSocket hook with exponential-backoff reconnect` | hooks/useWebSocket.js |
| 6 | `feat: add React components — ChatPanel, MessageBubble, StatusBar, App` | main.jsx, App.jsx, components/*, App.css |
| 7 | `feat: add Electron main process and preload` | src/main.js, src/preload.js |
| 8 | `chore: add .gitignore, config example, and README setup guide` | .gitignore, config.yaml.example, README.md |

---

## Environment Notes

**Proxy (127.0.0.1:7890):**

- **npm**: `npm config set proxy http://127.0.0.1:7890` and `npm config set https-proxy http://127.0.0.1:7890`
- **pip**: `pip install --proxy http://127.0.0.1:7890 -r requirements.txt`
- **Python runtime** (for OpenAI SDK): Set before running backend:
  ```bash
  set HTTP_PROXY=http://127.0.0.1:7890
  set HTTPS_PROXY=http://127.0.0.1:7890
  ```

**Python 3.10**: This plan targets Python 3.10 (what's installed). The `t` type parameter syntax (`list[dict]`, `AsyncGenerator[str, None]`) is supported via `from __future__ import annotations` which we don't need since we're using the `typing` module imports. The `X | None` union syntax works in 3.10 via `from __future__ import annotations` — but to be safe, we use `Optional[X]` from typing where needed, or rely on the fact that variable annotations like `openai_client: AsyncOpenAI | None = None` work at runtime without evaluation. Actually, in Python 3.10, you need `from __future__ import annotations` for `X | None` syntax. Let me verify what we use in the code...

Main.py uses `AsyncOpenAI | None` in a variable annotation. In Python 3.10, this would fail at runtime if it's evaluated. But as a module-level annotation, it should be fine because annotations aren't evaluated. However, to be absolutely safe, I should add `from __future__ import annotations` to main.py. Actually, let me just update main.py to use `Optional[AsyncOpenAI]` to be safe with 3.10.

Wait, actually, `X | None` syntax in annotations works differently. In Python 3.10:
- `def foo(x: int | None)` — FAILS (evaluated at definition time)
- `x: int | None = None` at module/class level — this is stored as a string in `__annotations__` and NOT evaluated. So it actually works for variable annotations at module level.

But to be safe, let me add `from __future__ import annotations` to both chat.py and main.py.

Hmm, actually let me check... the chat.py doesn't use `|` syntax. Only main.py uses `AsyncOpenAI | None`. Let me just add the future import.

Let me update the plan's main.py to include `from __future__ import annotations`. I should edit the plan file.

Actually, "from __future__ import annotations" makes ALL annotations strings, which can break things like Pydantic/FastAPI that inspect type annotations at runtime. So I should NOT add it to main.py which uses FastAPI route decorators.

The safest approach for Python 3.10: use `Optional[AsyncOpenAI]` instead of `AsyncOpenAI | None`.

Let me update the plan.<｜end▁of▁thinking｜>Now let me do the self-review of the plan before presenting it.

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="TodoWrite">
<｜｜DSML｜｜parameter name="todos" string="false">[{"activeForm":"Exploring project context","content":"Explore project context","status":"completed"},{"activeForm":"Offering visual companion","content":"Offer visual companion if applicable","status":"completed"},{"activeForm":"Asking clarifying questions","content":"Ask clarifying questions","status":"completed"},{"activeForm":"Proposing approaches","content":"Propose approaches with trade-offs","status":"completed"},{"activeForm":"Presenting design","content":"Present design and get approval","status":"completed"},{"activeForm":"Writing design doc","content":"Write design doc","status":"completed"},{"activeForm":"Reviewing spec","content":"Spec self-review","status":"completed"},{"activeForm":"Transitioning to implementation planning","content":"User reviews spec, transition to writing-plans","status":"completed"},{"activeForm":"Writing implementation plan","content":"Write implementation plan","status":"in_progress"},{"activeForm":"Self-reviewing plan","content":"Self-review plan","status":"pending"},{"activeForm":"Execution handoff","content":"User approves plan, execution handoff","status":"pending"}]