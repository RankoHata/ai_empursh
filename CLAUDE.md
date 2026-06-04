# AI 桌面助理 (Desktop AI Companion)

## 项目概述

Electron + React 桌面应用，通过 WebSocket 与 Python FastAPI 后端通信。
支持流式 AI 聊天、语音输入/输出、笔记管理、材料整理、Live2D 拟人形象。

## 架构

```
Electron (main.js)
  └── React 渲染进程 (ChatPanel, NotesPanel, SettingsPanel, Live2DAvatar)
        │ WebSocket ws://127.0.0.1:8765/ws
        ▼
Python FastAPI (main.py)
  ├── agent/chat.py          ChatSession — DeepSeek 流式聊天
  ├── agent/skills.py        技能加载器 (skills/*.md)
  ├── db/notes.py            SQLite + FTS5 笔记 CRUD
  ├── voice/stt.py           faster-whisper 本地语音识别
  ├── voice/tts.py           edge-tts 语音合成
  └── live2d (前端)           Cubism 5 SDK Framework + Model.ts
```

## 启动方式

```bash
# 终端 1 — 后端
cd backend && python main.py

# 终端 2 — 前端
cd electron-app && npm start
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `backend/main.py` | FastAPI + WebSocket，所有消息路由 |
| `backend/agent/chat.py` | ChatSession：流式聊天 + 上下文管理 |
| `backend/agent/skills.py` | 解析 `skills/*.md`，命令→system_prompt 注入 |
| `backend/db/notes.py` | SQLite FTS5 笔记增删查导出 |
| `backend/voice/stt.py` | faster-whisper 语音转文字 + VAD |
| `backend/voice/tts.py` | edge-tts 文字转语音 |
| `electron-app/src/main.js` | Electron 主进程 + 系统托盘 |
| `electron-app/src/renderer/App.jsx` | React 根组件，全部状态 + WS 消息路由 |
| `electron-app/src/renderer/hooks/useWebSocket.js` | WS 连接管理 + 指数退避重连 |
| `electron-app/src/live2d/Model.ts` | 我们的 CubismUserModel 子类 |
| `electron-app/src/live2d/framework/` | Cubism 5 SDK，85 文件，零改动 |

## WebSocket 协议

所有消息 JSON: `{"type": "...", "payload": {...}}`

前端→后端: `chat`, `stop`, `add_note`, `get_notes`, `search_notes`, `delete_note`, `export_notes`, `voice_input`, `voice_mode`, `get_config`, `update_config`, `save_file`, `tts_enabled`

后端→前端: `message_chunk`, `message_complete`, `error`, `voice_result`, `play_audio`, `avatar_state`, `voice_status`, `notes_list`, `note_saved`, `note_deleted`, `search_results`, `notes_exported`, `markdown_preview`, `file_saved`, `config`, `config_updated`

## 环境约束

- **代理**: 用户系统有全局代理 127.0.0.1:7890。pip/npm 安装时需开代理。Python 运行时 `NO_PROXY=api.deepseek.com` 排除 DeepSeek
- **Python 3.10**: 无 `X | None` 语法，用 `Optional[X]`
- **Electron**: 不支持 `window.prompt()` / `alert()`，用 React Modal 替代
- **CSP**: index.html 中配置，需允许 `ws://127.0.0.1:8765` 和 `http://127.0.0.1:8765`

## Live2D 关键知识（重要！）

1. Cubism SDK for Web 5 用 Core 6.0.1，版本号独立
2. `live2dcubismcore.min.js` 需从 Live2D 官网下载，不包含在项目中
3. Framework 85 个 `.ts` 文件从 SDK 原封复制，在 `src/live2d/framework/`
4. 必须调用 `CubismFramework.startUp()` + `initialize()` 后才能加载模型
5. `CubismUserModel.loadModel()` 接受 ArrayBuffer（非 CubismModel 对象）
6. 纹理必须 `gl.pixelStorei(UNPACK_PREMULTIPLY_ALPHA_WEBGL, true)` + `renderer.bindTexture(i, texId)`
7. G36 模型 (Cubism 3) motion 不兼容 Cubism 5，只能显示静态姿势
8. 详见 `docs/superpowers/specs/2026-06-05-phase5-live2d-avatar-design.md`

## 技能系统

技能文件放在 `backend/skills/*.md`，格式:

```markdown
---
name: skill-name
description: 描述
command: /命令
allowed_tools: [search_notes, get_notes]
---

system prompt 正文
```

## 已知坑

- `window.prompt()` / `alert()` 在 Electron 中不可用 → 用 React Modal
- React `onContextMenu` 在 Electron 中不触发 → 用原生 `addEventListener('contextmenu')`
- `fetch().arrayBuffer()` 加载 moc3 可能失败 → 用 `XMLHttpRequest` + `responseType='arraybuffer'`
- `global MODEL_CFG` 不能在函数中途声明 → 用 `dict.clear()` + `update()`
- 后台 TTS task 需可取消，WebSocket 断开时 `send_json` 会报错 → `_ws_send_safe()`
- `git filter-branch` 清理过大文件后需 force push
- 安装 mcp 包可能破坏 pydantic-core → 用 `--force-reinstall` 修复
