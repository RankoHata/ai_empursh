# 阶段 1：项目骨架与基础聊天 — 设计文档

**日期**：2026-06-03
**来源**：《AI 桌面拟人助理 - 项目需求规格说明书》第 9 章 阶段 1
**状态**：已确认

---

## 1. 目标

实现 Electron 桌面应用与 Python 后端的 WebSocket 通信，跑通 DeepSeek API 流式聊天链路。

**产出物：**
- Electron + React 桌面窗口，含聊天界面
- Python FastAPI WebSocket 服务端
- 与 DeepSeek API 的流式对话能力
- 多轮对话上下文管理 + 用户中断功能

---

## 2. 技术选型

| 层 | 选择 | 理由 |
|---|------|------|
| 桌面壳 | Electron + Vite + React | electron-forge 官方 React 模板，Vite 热更新 |
| 后端服务 | Python 3.11+ / FastAPI | WebSocket + 未来 REST API 统一框架 |
| AI SDK | openai (Python) | DeepSeek 兼容 OpenAI 格式 |
| 通信 | WebSocket (JSON) | 实时双向，流式传输 |
| 模型 | deepseek-chat | 中文效果好，已有 API Key |

---

## 3. 项目结构

```
f:/AI/ai_empursh/
├── electron-app/                    # Electron + React 前端
│   ├── package.json
│   ├── forge.config.js
│   ├── vite.main.config.mjs
│   ├── vite.preload.config.mjs
│   ├── vite.renderer.config.mjs
│   ├── src/
│   │   ├── main.js                  # Electron 主进程
│   │   ├── preload.js               # Preload 安全桥接
│   │   └── renderer/
│   │       ├── index.html
│   │       ├── App.jsx              # 根组件，状态中心
│   │       ├── components/
│   │       │   ├── ChatPanel.jsx    # 消息列表 + 输入区
│   │       │   ├── MessageBubble.jsx# 单条消息（流式追加）
│   │       │   └── StatusBar.jsx    # 连接状态指示
│   │       ├── hooks/
│   │       │   └── useWebSocket.js  # WS 连接管理
│   │       └── styles/
│   │           └── app.css
│   └── assets/
│
├── backend/                         # Python FastAPI 后端
│   ├── main.py                      # 入口 + WebSocket 端点
│   ├── agent/
│   │   ├── __init__.py
│   │   └── chat.py                  # DeepSeek 流式调用
│   ├── config.yaml                  # 配置文件
│   └── requirements.txt
│
└── doc/                             # 需求说明书
```

---

## 4. WebSocket 协议（阶段 1）

### 前端 → 后端

| type | payload | 说明 |
|------|---------|------|
| `chat` | `{"message": "..."}` | 发送聊天消息 |
| `stop` | `{}` | 中断当前生成 |

### 后端 → 前端

| type | payload | 说明 |
|------|---------|------|
| `message_chunk` | `{"content": "..."}` | 流式增量文本 |
| `message_complete` | `{"full_content": "..."}` | 回复完成 |
| `error` | `{"message": "..."}` | 错误信息 |

---

## 5. 组件与数据流

### 5.1 React 组件树

```
App.jsx
├── connectionStatus: "disconnected" | "connecting" | "connected"
├── messages: Array<{role, content, id, timestamp}>
├── isStreaming: boolean
│
├── <StatusBar status={connectionStatus} />
├── <ChatPanel
│     messages={messages}
│     isStreaming={isStreaming}
│     onSend(msg) → ws.send({type:"chat", payload:{message: msg}})
│     onStop()    → ws.send({type:"stop", payload:{}})
│   />
```

### 5.2 useWebSocket hook 职责

- 建立 WebSocket 连接到 `ws://127.0.0.1:8765/ws`
- 断开后自动重连（指数退避，初始 1s，最大 30s）
- 注册消息回调：`onMessage(type, payload)`
- 暴露 `send(type, payload)` 方法
- 暴露 `connectionStatus` 状态

### 5.3 一次聊天的完整数据流

```
用户输入 "你好" → ChatPanel.onSend()
  → ws.send({type:"chat", payload:{message:"你好"}})
  → WebSocket → Python FastAPI /ws
  → chat.py: stream_chat()
     → openai.chat.completions.create(stream=True)
     → async for chunk: yield content
  → websocket.send_json({type:"message_chunk", payload:{content: "你"}})
  → websocket.send_json({type:"message_chunk", payload:{content: "好"}})
  → ...
  → websocket.send_json({type:"message_complete", ...})
  → React: setMessages → MessageBubble 实时刷新
```

### 5.4 中断流程

```
用户点击"停止" → ChatPanel.onStop()
  → ws.send({type:"stop", payload:{}})
  → Python: stop_event.set()
  → chat.py 循环检测到 stop_event.is_set() → break
  → websocket.send_json({type:"message_complete", payload:{partial: true}})
```

---

## 6. 后端设计

### 6.1 main.py — FastAPI 应用

```
- lifespan: 启动加载 config.yaml → 初始化 OpenAI client
- GET  /          → {"status": "running"}
- WS   /ws        → 聊天 WebSocket 端点
```

### 6.2 agent/chat.py — 聊天引擎

```
stream_chat(client, model, messages_history, stop_event)
  输入：OpenAI client, 模型名, 历史消息列表, asyncio.Event
  输出：AsyncGenerator[str] 逐 token yield
  上下文：每个 WS 连接独立维护 messages_history（最近 20 轮）
```

### 6.3 config.yaml

```yaml
model:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-your-key"
  model_name: "deepseek-chat"
  max_tokens: 4096

server:
  host: "127.0.0.1"
  port: 8765

chat:
  max_history_rounds: 20
```

### 6.4 依赖 (requirements.txt)

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
openai>=1.30.0
pyyaml>=6.0
```

---

## 7. 非功能需求

- WebSocket 仅监听 `127.0.0.1`，不接受外部连接
- 重连策略：指数退避 1s → 2s → 4s → ... → 最大 30s
- 流式首字延迟目标 < 500ms（取决于 API 响应速度）
- API Key 仅存储在本地 config.yaml，不硬编码

---

## 8. 不在阶段 1 范围内的内容

- Live2D 模型（仅有占位 UI）
- 语音输入/输出
- 笔记系统
- 技能/MCP 系统
- 设置界面（配置手动编辑 YAML）
- 系统托盘
- 应用打包

---

## 9. 验收标准

1. 启动 Electron 应用，显示聊天窗口
2. 启动 Python 后端，前端自动连接
3. 输入文字发送，助理以流式方式逐字显示回复
4. 多轮对话，助理记住上文
5. 点击停止按钮，中断当前生成
6. 若后端未启动，前端显示"未连接"状态；后端启动后自动重连

---

## 10. 实现过程中的 Bug 与修复

| # | 问题 | 原因 | 修复 | 提交 |
|---|------|------|------|------|
| 1 | DeepSeek API 连接失败 `Connection error` | 系统全局代理拦截了对 `api.deepseek.com` 的请求 | 在 `main.py` 中设置 `os.environ["NO_PROXY"] = "api.deepseek.com"` | `15719a6` |
| 2 | Electron 安装不完整 | 代理/镜像问题导致 Electron 二进制下载失败 | 终止残留进程 → 删除损坏目录 → `ELECTRON_MIRROR` 国内镜像重装 | `875102d` |

### 经验教训

- 系统全局代理会影响 Python httpx 出站请求，需用 `NO_PROXY` 排除国内 API
- `git rm --cached` 排除 config.yaml 后需创建 `.example` 模板供参考
- 安装大二进制包（Electron）时注意残留进程锁文件问题

---

**此文档是阶段 1 的唯一设计来源，后续实现规划将基于此文档展开。**
