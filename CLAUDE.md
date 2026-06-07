# AI 桌面助理 (Desktop AI Companion)

## 项目概述

Electron + React 桌面应用，通过 WebSocket 与 Python FastAPI 后端通信。
支持流式 AI 聊天、语音输入/输出、笔记管理、材料整理、Live2D 拟人形象。

## 架构

```
┌─────────────────────────────────┐     IPC      ┌───────────────────────────┐
│  live2dWindow (桌面宠物)        │ ←──────────→ │  mainWindow (主应用)       │
│  400×600, 透明, 无边框, 置顶    │  toggle/move │  1320×780, 启动时隐藏      │
│  ?mode=live2d → 仅Live2D+拖拽  │              │  完整聊天/笔记/设置界面    │
└─────────────────────────────────┘              └──────────┬────────────────┘
                                                          │ WebSocket
                                                          ▼
                                              Python FastAPI (main.py)
                                                ├── agent/chat.py
                                                ├── agent/skills.py
                                                ├── db/notes.py
                                                ├── utils/markdown.py   (Markdown→纯文本)
                                                └── voice/stt.py, tts.py
```

**双窗口**: Electron 启动时创建两个 BrowserWindow。宠物窗口始终可见（`alwaysOnTop`），主窗口默认隐藏，点击宠物弹出。

**页面路由**: 同 HTML，`?mode=live2d` 参数区分。宠物模式不加载 WebSocket/聊天，只渲染 Live2D + JS 拖拽。

## 环境搭建（新机器从零开始）

### 1. 前置依赖

| 依赖 | 最低版本 | 验证命令 |
|------|---------|---------|
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Python | 3.10+ | `python --version` |
| pip | 22+ | `pip --version` |
| Git | 任意 | `git --version` |
| 代理工具 | — | 需要能访问外网（本机 127.0.0.1:7890 或系统代理） |

### 2. 克隆项目

```bash
git clone git@github.com:RankoHata/ai_empursh.git
cd ai_empursh
```

### 3. 配置 API Key

```bash
cp backend/config.yaml.example backend/config.yaml
```

编辑 `backend/config.yaml`，将 `sk-your-key-here` 替换为真实的 DeepSeek API Key：

```yaml
model:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-你的真实key"
  model_name: "deepseek-chat"
```

### 4. 下载 Live2D Cubism SDK Core

1. 打开 https://www.live2d.com/download/cubism-sdk/
2. 下载 **Cubism SDK for Web** (最新版)
3. 解压，找到 `Core/live2dcubismcore.min.js`
4. 复制到 `electron-app/assets/live2d/live2dcubismcore.min.js`

```bash
# 示例（假设 SDK 解压到 C:\Users\xxx\Downloads\CubismSdkForWeb-5-r.5\）
cp "CubismSdkForWeb-5-r.5/Core/live2dcubismcore.min.js" electron-app/assets/live2d/
```

### 5. 安装依赖

#### Python 后端 — 使用 uv（推荐）

```bash
# 安装 uv（如果没有）
pip install uv

cd backend

# 轻量安装（core + edge-tts，无需 GPU，推荐）
uv sync --extra tts-edge

# 或：完整安装（含 XTTS-v2 语音克隆，需 torch ~2GB）
#   uv sync --extra full

# 或：使用脚本
#   sync.bat            → 轻量
#   sync.bat full       → 完整
#   sync.bat xtts       → XTTS-v2
#   sync.bat bare       → 仅核心 API

# 国内加速：
#   $env:UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
#   uv sync --extra tts-edge
cd ..
```

**按需安装对照**：

| 场景 | 命令 | 额外依赖 |
|------|------|---------|
| 只用 edge-tts 语音 | `uv sync --extra tts-edge` | edge-tts |
| 要语音识别 (STT) | `uv sync --extra tts-edge --extra stt` | +faster-whisper |
| 要本地语音克隆 | `uv sync --extra tts-xtts` | +TTS +torch (~2GB) |
| 全部功能 | `uv sync --extra full` | 以上全部 |

#### 前端

```bash
cd electron-app
npm install
cd ..
```

### 6. 启动

**终端 1 — 启动后端：**

```bash
cd backend
python main.py
# 看到 "Uvicorn running on http://127.0.0.1:8765" 即就绪
```

**终端 2 — 启动前端：**

```bash
cd electron-app
npm start
# Electron 窗口弹出，状态栏显示绿色 "已连接"
```

### 7. 首次使用注意事项

- **语音识别**首次调用会下载 faster-whisper 模型（~140MB），需要能访问 HuggingFace
- **TTS 朗读**默认开启，可在状态栏 `朗读 ○/●` 开关控制
- **笔记**右键聊天消息 → "保存为笔记"
- **材料整理**在聊天中输入 `/整理` 命令
- **Live2D 模型**默认使用 Haru（SDK 示例），可在 `Live2DAvatar.jsx` 中切换 MODEL_URL

### 故障排查

| 问题 | 解决方案 |
|------|---------|
| 后端启动报 `Connection error` | 系统代理拦截了 DeepSeek API。代码已设 `NO_PROXY=api.deepseek.com`，如仍失败，在终端 `set NO_PROXY=api.deepseek.com` 后重启 |
| npm install 失败 | 检查代理 127.0.0.1:7890 是否运行，或关闭代理直连 |
| pip install SSL 错误 | 代理干扰了 SSL。用 `no_proxy="*" pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
| Live2D 显示"加载中"不消失 | 确认 `electron-app/assets/live2d/live2dcubismcore.min.js` 存在 |
| 录音后 WAV 无声音 | 检查系统麦克风权限设置 |
| Electron 启动报 `@pixi/core` 找不到 | `npm install` 未成功安装 pixi-live2d-display 的子依赖。删除 `node_modules/` 重装 |

## 目录地图

### 图例

| 标记 | 含义 |
|------|------|
| ✏️  | 我们的代码，可自由修改 |
| 📦 | 从 SDK/外部原封复制，**禁止修改** |
| 🔧 | 用户需手动下载或生成 |

---

### 后端 `backend/`

```
backend/
├── ✏️  main.py                 FastAPI + WebSocket，所有消息路由
├── ✏️  requirements.txt         Python 依赖
├── ✏️  config.yaml             用户 API Key（gitignore，不入库）
├── ✏️  config.yaml.example     配置模板
├── ✏️  agent/
│   ├── ✏️  __init__.py
│   ├── ✏️  chat.py             ChatSession：流式聊天 + 上下文管理
│   └── ✏️  skills.py           技能加载器，解析 skills/*.md
├── ✏️  db/
│   ├── ✏️  __init__.py
│   ├── ✏️  init_db.py          SQLite 建表 + FTS5 + 触发器
│   └── ✏️  notes.py            笔记 CRUD + 搜索 + Markdown 导出
├── ✏️  voice/
│   ├── ✏️  __init__.py
│   ├── ✏️  stt.py              faster-whisper 语音识别 + VAD
│   └── ✏️  tts.py              edge-tts 语音合成
├── ✏️  utils/
│   ├── ✏️  __init__.py
│   └── ✏️  markdown.py         strip_markdown() — 剥离 Markdown 语法，供 TTS 用
├── ✏️  skills/
│   └── ✏️  material_organizer.md   /整理 技能定义
├── ✏️  tests/
│   └── ✏️  test_markdown.py    strip_markdown() 单元测试（19 个）
├── 🔧 data/                    SQLite 数据库文件（gitignore）
├── 🔧 models/                  faster-whisper 下载的模型（gitignore）
└── 🔧 temp/                    临时音频文件（gitignore）
```

### 前端 `electron-app/`

```
electron-app/
├── ✏️  package.json            依赖 + 脚本（含 react-markdown, remark-gfm）
├── ✏️  forge.config.js         Electron Forge 打包配置
├── ✏️  vite.*.config.mjs       Vite 构建配置
├── ✏️  index.html              HTML 入口 + CSP
│
├── ✏️  src/
│   ├── ✏️  main.js             Electron 主进程 + 系统托盘
│   ├── ✏️  preload.js          安全桥接
│   │
│   ├── ✏️  renderer/
│   │   ├── ✏️  main.jsx         React 入口
│   │   ├── ✏️  App.jsx          根组件：全部状态 + WS 消息路由
│   │   ├── ✏️  App.css          全局样式
│   │   ├── ✏️  hooks/
│   │   │   └── ✏️  useWebSocket.js   WS 连接管理 + 指数退避重连
│   │   └── ✏️  components/
│   │       ├── ✏️  ChatPanel.jsx       聊天面板 + 右键菜单 + 录音
│   │       ├── ✏️  MessageBubble.jsx   消息气泡（助手 Markdown 渲染，用户纯文本）
│   │       ├── ✏️  StatusBar.jsx       连接状态 + TTS/常开开关
│   │       ├── ✏️  TabBar.jsx          标签栏
│   │       ├── ✏️  NotesPanel.jsx      笔记面板
│   │       ├── ✏️  NoteCard.jsx        笔记卡片
│   │       ├── ✏️  SettingsPanel.jsx   设置面板
│   │       ├── ✏️  MarkdownPreview.jsx Markdown 预览弹窗
│   │       ├── ✏️  Live2DAvatar.jsx    Live2D React 包装（~100 行）
│   │       └── ✏️  AvatarStatus.jsx    emoji 头像状态
│   │
│   └── ✏️  live2d/
│       ├── ✏️  Model.ts          我们的 CubismUserModel 子类（~230 行）
│       ├── 📦 framework/         **Cubism 5 SDK Framework**（85 个 .ts 文件）
│       │   ├── 📦 live2dcubismframework.ts
│       │   ├── 📦 model/         CubismMoc, CubismModel, CubismUserModel
│       │   ├── 📦 motion/        动画系统
│       │   ├── 📦 rendering/     WebGL 渲染器 + Shader
│       │   ├── 📦 effect/        眨眼、呼吸、物理
│       │   ├── 📦 physics/       物理模拟
│       │   ├── 📦 math/          矩阵运算
│       │   ├── 📦 utils/         工具函数
│       │   ├── 📦 id/            参数 ID 管理
│       │   ├── 📦 type/          类型定义
│       │   └── 📦 Shaders/       着色器源码（来自 SDK）
│       └── 📦 framework/Shaders/  WebGL shader 文件（来自 Framework）
│
├── ✏️  assets/live2d/
│   ├── 🔧 live2dcubismcore.min.js  用户从 Live2D 官网下载
│   ├── 📦 haru/                    SDK 示例模型 Haru
│   ├── 📦 g36_1904/               用户提供的 G36 模型 (GitHub)
│   ├── ✏️  shaders/                我们复制的 shader 副本（运行时加载用）
│   └── 🔧 icon/                    应用图标
│
└── ✏️  assets/                    其他静态资源
```

### 根目录

```
├── ✏️  CLAUDE.md               本文档
├── ✏️  README.md               项目说明
├── ✏️  start-backend.bat        Windows 后端启动脚本
├── ✏️  .gitignore
├── ✏️  doc/                    原始需求说明书
└── ✏️  docs/superpowers/
    ├── specs/                   5 份阶段设计文档（含 Bug 记录）
    └── plans/                   实现计划
```

## WebSocket 协议

所有消息 JSON: `{"type": "...", "payload": {...}}`

前端→后端: `chat`, `stop`, `add_note`, `get_notes`, `search_notes`, `delete_note`, `export_notes`, `voice_input`, `voice_mode`, `get_config`, `update_config`, `save_file`, `tts_enabled`

后端→前端: `message_chunk`, `message_complete`, `error`, `voice_result`, `play_audio`, `avatar_state`, `voice_status`, `notes_list`, `note_saved`, `note_deleted`, `search_results`, `notes_exported`, `markdown_preview`, `file_saved`, `config`, `config_updated`

## Markdown 渲染

**聊天显示**: `MessageBubble.jsx` 对助手消息使用 `ReactMarkdown` + `remark-gfm` 渲染。支持 GFM 扩展（表格、删除线、任务列表）。用户消息保持纯文本。暗色主题 CSS 样式在 `App.css` 的 `.bubble-content` 区。

**TTS 语音播报**: `backend/utils/markdown.py` 中的 `strip_markdown()` 在 TTS 合成前剥离 Markdown 语法字符。代码块替换为"（此处有一段代码）"，链接保留文字去掉 URL，图片替换为"[图片]"。`main.py` 的 `_synthesize_and_send()` 自动调用。

**笔记保存**: 右键"保存为笔记"保存原始 Markdown 文本（未经渲染），以便编辑和导出。

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
