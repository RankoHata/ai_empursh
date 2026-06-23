# AI 桌面助理 (Desktop AI Companion)

## 项目概述

Electron + React 桌面应用，通过 WebSocket 与 Python FastAPI 后端通信。
支持流式 AI 聊天、语音输入/输出、笔记管理、材料整理、Spine 2D 拟人形象。

## 架构

```
┌─────────────────────────────────┐  IPC (toggle/move/emotion) ┌───────────────────────────────────┐
│  live2dWindow (桌面宠物)        │ ←───────────────────────── │  mainWindow (主应用)               │
│  400×650, 透明无边框, alwaysTop │                             │  1320×780, 启动时隐藏              │
│  ?mode=live2d → Spine Avatar   │  emotion 由主窗口 IPC 推送  │  完整聊天/笔记/设置界面             │
│  仅渲染Avatar，跳过chat消息     │  宠物窗口不自行处理 WS       └──────────┬────────────────────────┘
└─────────────────────────────────┘                                       │ WebSocket
                                                                          ▼
                                                              Python FastAPI (main.py)
                                                ┌─────────────────┼─────────────────────┐
                                                ▼                 ▼                      ▼
                                          agent/chat.py    agent/personality_      agent/skills.py
                                          (ChatSession)    manager.py              (技能路由)
                                                │                 │
                                    ┌───────────┼───────┐         │
                                    ▼           ▼       ▼         ▼
                                tools/       mcp/     db/      voice/
                              (工具注册)  (MCP管理) (SQLite)  (STT/TTS)
```

**双窗口**: Electron 启动两个 BrowserWindow。宠物窗口始终可见（`alwaysOnTop`），主窗口默认隐藏，点击宠物/托盘弹出。两个窗口各有独立 WebSocket 连接，桌宠窗口通过 `isLive2DOnly` 跳过聊天消息处理，仅通过 IPC 接收 emotion 推送。

**页面路由**: `?mode=live2d` 参数区分。宠物模式只渲染 Spine Avatar，跳过聊天/消息处理。主页使用 CSS 滑动页面系统（`page-track` horizontal translate），通过 `BottomNavBar` 切换 chat/notes/secret。

**人格系统**: YAML 种子文件 → 首次启动写入 SQLite → 运行时全走 DB。`PersonalityManager` 统一管理加载、版本聚合（`parent_name` 符号引用）、Jinja2 模板渲染、情绪标签提取。设置面板支持 CRUD 编辑 + `↻ 重载` 按钮从 YAML 强制刷新。

**情绪系统**: AI 在回复末尾输出 `[!emotion:标签!]` → 后端正则剥离 → `message_complete.emotion` 下发 → 主窗口通过 IPC 推送到桌宠 → Spine AnimationController 映射为动画，3 秒后回 idle。

**紧凑模式**: 设置面板切换 → localStorage 持久化 + WebSocket 同步到后端 → 后端注入紧凑指令到 system prompt（避免多余空行、简洁直接）+ 前端 CSS `.compact-md` 收紧垂直间距。

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
| FFmpeg | 4.0+ (shared) | F5-TTS 语音克隆需要；`winget install Gyan.FFmpeg.Shared` |

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

### 4. 安装依赖

#### Python 后端 — 使用 uv（推荐）

```bash
pip install uv
cd backend

# 轻量安装（core + edge-tts，无需 GPU，推荐）
uv sync --extra tts-edge

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
| 要本地语音克隆 | `uv sync --extra tts-f5` | +f5-tts +torch (~2GB) + FFmpeg |
| 全部功能 | `uv sync --extra full` | 以上全部 |

#### 前端

```bash
cd electron-app
npm install
cd ..
```

### 5. 启动

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
# Electron 窗口弹出
```

### 6. 首次使用注意事项

- **语音识别**首次调用会下载 faster-whisper 模型（~140MB），需要能访问 HuggingFace
- **TTS 朗读**默认关闭，可在设置面板中开启
- **设置**：底部导航栏右侧齿轮 ⚙️，从右侧滑出设置抽屉
- **自定义壁纸**：设置 → 显示中选择图片作为聊天背景（8% 透明度）
- **笔记**：右键聊天消息 → "保存为笔记"
- **删除消息**：右键聊天消息 → "删除"
- **材料整理**：聊天中输入 `/整理` 命令
- **应用图标**：首次启动时自动生成在 `userData/icons/app_icon.png`
- **紧凑模式**：设置面板切换，使 AI 回复更简洁、减少空行
- **人格重载**：修改 YAML 种子后，设置面板「↻ 重载」刷新

### 故障排查

| 问题 | 解决方案 |
|------|---------|
| uv sync 超时 | uv 不走系统代理。在代理软件中添加规则代理 `pypi.org`、`files.pythonhosted.org`、`huggingface.co` |
| 后端启动报 `Connection error` | 系统代理拦截 DeepSeek API。已设 `NO_PROXY=api.deepseek.com` |
| npm install 失败 | 检查代理 127.0.0.1:7890 是否运行 |
| F5-TTS 报 torchcodec 找不到 | `winget install Gyan.FFmpeg.Shared` 后重启终端 |
| 录音后 WAV 无声音 | 检查系统麦克风权限 |

## 完整目录地图

### 图例

| 标记 | 含义 |
|------|------|
| ✏️ | 我们的代码，可自由修改 |
| 📦 | 从 SDK/外部原封复制，**禁止修改** |
| 🔧 | 用户需手动下载或生成 |
| ⚠️ | 疑似无用/待清理 |

---

### 后端 `backend/`

```
backend/
├── ✏️  main.py                   FastAPI + WebSocket，所有消息路由 (~960行)
├── ✏️  config.py                 配置类，读取 config.yaml
├── ✏️  config.yaml               用户 API Key（gitignore）
├── ✏️  config.yaml.example       配置模板
├── ✏️  mcp_servers.yaml          MCP 服务器配置（目前只有 echo 测试）
├── 🔧 requirements.txt           Python 依赖
│
├── ✏️  agent/
│   ├── ✏️  __init__.py
│   ├── ✏️  chat.py               ChatSession：流式聊天 + 工具调用循环 + 上下文管理
│   ├── ✏️  skills.py             技能加载器，解析 skills/*.md
│   ├── ✏️  personality.py        人格模块入口，薄包装 → personality_manager
│   └── ✏️  personality_manager.py 人格统一管理：CRUD委托、版本聚合、Jinja2渲染、情绪提取、种子管理
│
├── ✏️  db/
│   ├── ✏️  __init__.py
│   ├── ✏️  init_db.py            SQLite 建表 + FTS5 + 触发器（personalities, notes, secret_notes, conversations）
│   ├── ✏️  notes.py              公开笔记 CRUD + FTS5 搜索
│   ├── ✏️  secret_notes.py       秘密笔记 CRUD + 搜索（本地存储，数据不入 LLM）
│   ├── ✏️  personalities.py      人格 CRUD + YAML 种子导入（支持 force reseed）
│   ├── ✏️  conversations.py      对话管理：CRUD + turn 持久化
│   └── ✏️  workspace_sync.py     工作区文件同步（后台异步）
│
├── ✏️  tools/
│   ├── ✏️  __init__.py           ToolRegistry：工具注册、schema 生成、执行调度
│   ├── ✏️  base.py               ToolDefinition 数据类
│   └── ✏️  notes.py             笔记工具：search_notes, get_notes, add_note, search_secret_notes
│
├── ✏️  mcp/
│   ├── ✏️  __init__.py           MCPManager：多服务器生命周期管理
│   ├── ✏️  adapter.py            MCP 工具适配器：工具名 mcp__<server>__<tool>，结果包装
│   ├── ✏️  protocol.py           JSON-RPC 2.0 协议实现
│   ├── ✏️  stdio_client.py       stdio 传输：子进程 stdin/stdout JSON-RPC
│   ├── ✏️  http_client.py        HTTP 传输：远程 MCP 服务器
│   └── ✏️  errors.py             MCP 异常定义
│
├── ✏️  voice/
│   ├── ✏️  __init__.py
│   ├── ✏️  stt.py                faster-whisper 语音识别 + VAD
│   ├── ✏️  tts.py                TTS 引擎工厂 + 流式合成入口
│   ├── ✏️  tts_base.py           TTS 引擎抽象基类
│   ├── ✏️  tts_edge.py           EdgeTTSEngine（微软云 TTS，默认）
│   └── ✏️  tts_f5.py             F5TTSEngine（零样本语音克隆，需 GPU）
│
├── ✏️  utils/
│   ├── ✏️  __init__.py
│   ├── ✏️  markdown.py           strip_markdown() — Markdown→纯文本，供 TTS 用
│   └── ✏️  template.py           Jinja2 薄封装：render_prompt()
│
├── ✏️  security/
│   └── ✏️  guard.py              build_secret_placeholder() — 秘密笔记脱敏
│
├── ✏️  personalities/            YAML 种子文件（→ 首次启动写入 SQLite）
│   ├── ✏️  default.yaml          默认助手（通用，无版本）
│   ├── ✏️  anis-01-simple.yaml   阿妮斯·简洁
│   ├── ✏️  anis-02-full.yaml     阿妮斯·完整（parent_name: 阿妮斯）
│   └── ✏️  anis-03-arc.yaml      阿妮斯·深度（parent_name: 阿妮斯）
│
├── ✏️  skills/
│   └── ✏️  material_organizer.md /整理 技能定义
│
├── ✏️  tests/
│   ├── ✏️  test_markdown.py      strip_markdown() 单元测试
│   └── ✏️  mcp_echo_server.py    MCP echo 测试服务器（提供 echo + get_time 工具）
│
├── 🔧 data/                      SQLite 数据库（gitignore）
├── 🔧 models/                    faster-whisper 模型（gitignore）
└── 🔧 temp/                      临时音频文件（gitignore）
```

### 前端 `electron-app/`

```
electron-app/
├── ✏️  package.json              依赖 + 脚本
├── ✏️  forge.config.js           Electron Forge 打包配置
├── ✏️  vite.main.config.mjs      Vite 主进程构建
├── ✏️  vite.preload.config.mjs   Vite preload 构建
├── ✏️  vite.renderer.config.mjs  Vite 渲染进程构建
├── ✏️  index.html                HTML 入口 + CSP
│
├── ✏️  src/
│   ├── ✏️  main.js               Electron 主进程：双窗口 + 系统托盘 + IPC
│   ├── ✏️  preload.js            安全桥接：exposeInMainWorld electronAPI
│   │
│   ├── ✏️  renderer/
│   │   ├── ✏️  main.jsx           React 入口
│   │   ├── ✏️  config.js          功能开关（FEATURES.showLive2D）
│   │   ├── ✏️  App.jsx            根组件：25+ state、30+ WS handler、全部业务逻辑 (~900行)
│   │   ├── ✏️  App.css            全局样式 (~1822行)，按功能分区组织
│   │   │
│   │   ├── ✏️  hooks/
│   │   │   └── ✏️  useWebSocket.js WS 连接管理 + 指数退避重连 (1s→30s max)
│   │   │
│   │   └── ✏️  components/
│   │       ├── ✏️  ChatPanel.jsx         聊天面板：消息列表 + 输入框 + 右键菜单 + 录音
│   │       ├── ✏️  MessageBubble.jsx     消息气泡：助手 Markdown + 工具卡片 + trace面板
│   │       ├── ✏️  ToolCallCard.jsx      工具调用卡片：可展开/折叠，状态颜色
│   │       ├── ✏️  TracePanel.jsx        调用追踪面板：API/工具时间线
│   │       ├── ✏️  NotesPanel.jsx        公开笔记面板：搜索/筛选/多选导出
│   │       ├── ✏️  SecretNotesPanel.jsx  秘密笔记面板：仅本地，红黑主题
│   │       ├── ✏️  NoteCard.jsx          笔记卡片
│   │       ├── ✏️  SettingsPanel.jsx     设置抽屉：人格/模型/显示/语音
│   │       ├── ✏️  ConversationList.jsx  对话列表侧边栏：可折叠，内联重命名
│   │       ├── ✏️  BottomNavBar.jsx      底部导航栏：三页切换 + 折叠
│   │       ├── ✏️  DisconnectedBanner.jsx 断开连接横幅
│   │       ├── ✏️  NewNoteModal.jsx      新建笔记弹窗
│   │       ├── ✏️  MarkdownPreview.jsx   Markdown 预览弹窗
│   │       ├── ✏️  Avatar.jsx            Spine 2D Avatar React 包装
│   │       ├── ✏️  FeatureGuard.jsx      功能开关条件渲染
│   │       ├── ⚠️ AvatarStatus.jsx       emoji 头像状态（未使用）
│   │       ├── ⚠️ StatusBar.jsx          旧状态栏（未使用）
│   │       └── ⚠️ TabBar.jsx            旧标签栏（未使用）
│   │
│   └── ✏️  avatar/                 Spine 2D 角色系统（当前在用）
│       ├── ✏️  types.ts            类型定义：HitResult, AvatarStatus
│       ├── ✏️  IAvatarModel.ts     抽象接口：load/playAnimation/getAnimationList/destroy
│       ├── ✏️  SpineModel.ts        SpinePlayer 包装：加载骨骼/Atlas，皮肤组合
│       ├── ✏️  AnimationController.ts 情绪→动画映射 + 眼球注视 + 单次动画
│       ├── ✏️  InteractionHandler.ts  拖拽/点击/右键交互
│       └── ✏️  AvatarManager.ts     总控：初始化、状态切换、rAF 循环、销毁
│
├── ✏️  assets/
│   ├── ✏️  spine/                   Spine 模型文件 (.skel, .atlas, .png)
│   │   ├── c017_00/                 默认角色
│   │   └── c017_02/                 换装
│   └── 🔧 icon/                    应用图标（运行时自动生成）
│
└── ⚠️ live2d/                      **已废弃** — Live2D 系统被 Spine 替代
    ├── ✏️  Model.ts                 CubismUserModel 子类
    └── 📦 framework/                Cubism 5 SDK Framework (85 .ts 文件)
```

### 根目录

```
├── ✏️  CLAUDE.md                 本文档
├── ✏️  README.md                 项目说明
├── ✏️  start-backend.bat         Windows 后端启动脚本
├── ✏️  .gitignore
├── ✏️  doc/                      原始需求说明书
└── ✏️  docs/superpowers/
    ├── specs/                     设计文档（含 Bug 记录）
    └── plans/                     实现计划
```

## WebSocket 协议

所有消息 JSON: `{"type": "...", "payload": {...}}`

### 前端 → 后端（共 29 个消息类型）

| 类别 | 消息类型 | Payload | 说明 |
|------|---------|---------|------|
| **聊天** | `chat` | `{message}` | 用户消息 |
| | `stop` | `{}` | 停止当前流式回复 |
| | `voice_input` | `{audio: base64}` | 语音输入 |
| | `tts_enabled` | `{enabled}` | TTS 开关 |
| | `compact_mode` | `{enabled}` | 紧凑模式开关 |
| **笔记** | `add_note` | `{content, tags, title?}` | 创建笔记 |
| | `get_notes` | `{}` | 获取全部笔记 |
| | `search_notes` | `{query, tags}` | 搜索笔记 |
| | `delete_note` | `{note_id}` | 删除笔记 |
| | `export_notes` | `{note_ids}` | 导出 Markdown |
| **秘密笔记** | `secret_add_note` | `{content, tags, title?}` | 创建秘密笔记 |
| | `secret_get_notes` | `{}` | 获取全部秘密笔记 |
| | `secret_search_notes` | `{query, tags}` | 搜索秘密笔记 |
| | `secret_delete_note` | `{note_id}` | 删除秘密笔记 |
| **对话** | `create_conversation` | `{title?}` | 创建对话 |
| | `list_conversations` | `{}` | 列出对话 |
| | `load_conversation` | `{conversation_id}` | 加载历史对话 |
| | `delete_conversation` | `{conversation_id}` | 删除对话 |
| | `rename_conversation` | `{conversation_id, title}` | 重命名 |
| | `get_turns` | `{conversation_id}` | 获取对话回合 |
| | `delete_turn` | `{turn_index, conversation_id}` | 删除回合 |
| **人格** | `get_personalities` | `{}` | 列出人格 |
| | `set_personality` | `{personality_id}` | 切换人格 |
| | `create_personality` | `{name, description, system_prompt, ...}` | 创建 |
| | `update_personality` | `{id, name, description, system_prompt}` | 更新 |
| | `delete_personality` | `{id}` | 删除 |
| | `reseed_personalities` | `{}` | 从 YAML 重载 |
| **配置** | `get_config` | `{}` | 获取配置 |
| | `update_config` | `{updates}` | 更新配置 |
| **文件** | `save_file` | `{content, filename}` | 保存 Markdown 文件 |

### 后端 → 前端（共 33 个消息类型）

| 类别 | 消息类型 | Payload | 说明 |
|------|---------|---------|------|
| **聊天** | `message_chunk` | `{content}` | 流式内容块 |
| | `message_complete` | `{full_content, partial, trace, emotion}` | 回复完成 |
| | `thinking` | `{content}` | 思考状态文字 |
| | `done` | `{}` | 本轮完全结束 |
| | `error` | `{message}` | 错误 |
| **工具** | `tool_call_start` | `{id, name, args}` | 工具开始执行 |
| | `tool_call_result` | `{id, name, result, duration_ms}` | 工具完成 |
| | `tool_call_error` | `{id, name, error}` | 工具失败 |
| **语音** | `voice_result` | `{text}` | 语音识别结果 |
| | `play_audio` | `{audio, stream_id}` | TTS 音频 |
| **笔记** | `notes_list` | `{notes}` | 笔记列表 |
| | `note_saved` | `{note}` | 笔记已保存 |
| | `note_deleted` | `{note_id}` | 笔记已删除 |
| | `search_results` | `{results, query, count}` | 搜索结果 |
| | `notes_exported` | `{path}` | 导出完成 |
| **秘密笔记** | `secret_notes_list` | `{notes}` | 秘密笔记列表 |
| | `secret_note_saved` | `{note}` | 已保存 |
| | `secret_note_deleted` | `{note_id}` | 已删除 |
| | `secret_search_results` | `{results, count, query}` | 搜索结果(真实数据，不走LLM) |
| **对话** | `conversation_created` | `{conversation}` | 对话已创建 |
| | `conversations_list` | `{conversations}` | 对话列表 |
| | `conversation_deleted` | `{conversation_id}` | 已删除 |
| | `conversation_renamed` | `{conversation}` | 已重命名 |
| | `turn_deleted` | `{turn_index, conversation_id}` | 回合已删除 |
| | `conversation_loaded` | `{conversation_id}` | 触发 get_turns |
| | `turns_list` | `{turns, conversation_id}` | 回合数据 |
| **人格** | `personalities_list` | `{personalities, grouped, current}` | 人格列表 |
| | `personalities_reseeded` | `{count, personalities, grouped, current}` | 重载完成 |
| | `personality_set` | `{id}` | 已切换 |
| | `personality_created` | `{personality}` | 已创建 |
| | `personality_updated` | `{personality}` | 已更新 |
| | `personality_deleted` | `{id, ok}` | 已删除 |
| **配置** | `config` | `{model, user, voice}` | 完整配置 |
| | `config_updated` | `{}` | 配置已更新 |
| **其他** | `avatar_state` | `{emotion}` | 角色情绪 |
| | `markdown_preview` | `{content, suggested_filename}` | 预览内容 |
| | `file_saved` | `{path}` | 文件已保存 |

## 数据流详解

### 聊天请求完整链路

```
用户输入 "你好"
  → ChatPanel.onSend("你好")
    → App.addUserMsgAndSend("你好")  // 前端立即显示用户消息
    → send('chat', {message: "你好"})
      → main.py WebSocket handler
        → 检查技能路由 (/整理 等)
        → personality_manager.render_prompt()  // 渲染 system prompt
        → (compact_enabled 时追加紧凑指令)
        → session.set_system_prompt()
        → session.add_user_message()
        → session.stream_with_tool_loop()
          → [API调用] → 流式 token
            → main.py: message_chunk → 前端追加到 assistant 消息
          → [检测到 tool_calls]
            → on_tool_call → tool_call_start → 前端显示工具卡片
            → 并行执行工具
            → on_tool_result → tool_call_result → 前端更新卡片状态
            → on_thinking("正在根据结果生成回复...")
            → 再次 API 调用...
          → [无 tool_calls] → 退出循环
        → main.py: message_complete (含 trace, emotion)
        → main.py: _send_done
        → (tts_enabled 时) 流式 TTS 合成
        → (非 partial 时) 自动保存对话 turn
```

### 情绪中继链路

```
后端 message_complete.emotion = "happy"
  → App.handleMessage 'message_complete'
    → setAvatarState("happy")                  // 主窗口 Avatar
    → window.electronAPI.setAvatarEmotion("happy")
      → main.js ipcMain 'set-avatar-emotion'
        → live2dWindow.webContents.send('avatar-emotion', 'happy')
          → App (live2d mode) onAvatarEmotion → setAvatarState("happy")
          → 3s timer → setAvatarState("idle")
```

### 工具调用前端链路

```
tool_call_start → 查找最新 isStreaming assistant 消息
  → 附加 ToolCallCard (state='running', 蓝色左边框)
  → 若无流式消息 → 创建占位 assistant 消息

tool_call_result → 查找匹配的 toolCall
  → 更新 state='completed' (绿色左边框)
  → 3s 后自动折叠卡片

tool_call_error → 查找匹配的 toolCall
  → 更新 state='error' (红色左边框)
```

## 状态管理

所有应用状态集中在 `App.jsx`，无外部状态管理库（无 Redux/Zustand）。

**持久化到 localStorage：**
- `emotionFollowEnabled`（默认 `true`）
- `compactMode`（默认 `false`）
- `wallpaper`（默认空）

**WebSocket 连接状态：** `useWebSocket` hook 内部管理 `connectionStatus`

**连接建立时自动同步：**
- `compact_mode` → 后端获知紧凑模式初始状态
- `list_conversations` → 刷新对话列表
- `get_personalities` → 刷新人格列表
- `get_config` → 获取后端配置

## CSS 变量（暗色主题）

```css
--bg-primary: #0f1117;       --bg-secondary: #16181d;
--bg-tertiary: #1c1f26;      --bg-input: #21242b;
--text-primary: #e3e5e8;     --text-secondary: #8e9297;
--text-muted: #5e6268;
--accent: #7289da;            --accent-hover: #8698de;
--accent-soft: rgba(114,137,218,0.12);
--success: #43b581;           --warning: #f0a500;
--danger: #e94560;            --danger-hover: #ff6b81;
--border: #262930;            --border-light: #2e323a;
--bubble-user: #1a2740;       --bubble-assistant: #1c2128;
```

## Markdown 渲染

**聊天显示**: `MessageBubble.jsx` 对助手消息使用 `ReactMarkdown` + `remark-gfm`（支持表格、删除线、任务列表）。用户消息纯文本。

**紧凑模式**: 助手消息用 `compactMarkdown()` 压缩空白（3+空行→2）+ CSS `.compact-md` 收紧间距。

**TTS 语音**: `strip_markdown()` 在合成前剥离 Markdown 语法。代码块→"（此处有一段代码）"，链接→去URL留文字，图片→"[图片]"。

**笔记保存**: 保存原始 Markdown（未经渲染），以便编辑和导出。

## 技能系统

技能文件 `backend/skills/*.md`，格式:

```markdown
---
name: skill-name
description: 描述
command: /命令
allowed_tools: [search_notes, get_notes]
---

system prompt 正文
```

当前技能: `/整理` (material_organizer.md) — 搜索笔记并整理归类。

## MCP 系统

MCP (Model Context Protocol) 允许接入外部工具服务器。配置在 `backend/mcp_servers.yaml`。

**当前服务器：**
- `echo` (stdio) — 测试用，提供 `echo` 和 `get_time` 工具

**工具命名规则：** `mcp__<server_name>__<tool_name>`（如 `mcp__echo_echo`）

**支持传输：** stdio（子进程 JSON-RPC）、HTTP（远程端点）

## 秘密笔记安全模型

```
用户查秘密笔记
  → LLM 调用 search_secret_notes
    → _search_secret_notes() 查询真实 DB
    → WS 推送 secret_search_results → 前端安全面板（真实数据）
    → 返回 build_secret_placeholder() → LLM 只看到 "已检索到 N 条秘密记录"
    → 真实内容 NEVER 进入 LLM 上下文
```

## 环境约束

- **代理**: 本机 127.0.0.1:7890。Python 运行时 `NO_PROXY=api.deepseek.com`
- **Python 3.10**: 不用 `X | None`，统一 `Optional[X]`
- **Electron**: 不支持 `prompt()`/`alert()`，用 React Modal
- **CSP**: 允许 `ws://127.0.0.1:8765` 和 `http://127.0.0.1:8765`

## Spine Avatar 关键知识

1. 使用 `@esotericsoftware/spine-player` 4.1（非 Live2D）
2. 骨骼+Atlas 从 `assets/spine/c017_00/` 加载
3. 皮肤组合：`default` + `acc`（饰品）
4. 动画探测：`probeAnimations()` 在 init 后运行，按优先级匹配情绪→动画
5. 情绪映射：angry→[angry,rage,mad,no], sad→[sad,pain,cry], happy→[delight,happy,action,laugh,cheer,smile]
6. 眼球注视：lerp 到目标，range -0.15~+0.15 弧度
7. 交互：拖拽=移动窗口，点击=单次 action，右键=弹出主窗口

## Live2D（已废弃）

~~Cubism 5 SDK Framework 85 个 .ts 文件~~
~~G36 模型 (Cubism 3) motion 不兼容 Cubism 5~~

已被 Spine 2D 系统替代。`src/live2d/` 和 `assets/live2d/` 目录可安全删除。

## 已知坑

- React `onContextMenu` 在 Electron 中不触发 → 用原生 `addEventListener('contextmenu')`
- 流式响应 + 尾标签剥离：`chat.py` 的 `on_done` 回调先于 main.py 的 flush 触发 → 已移除 `on_done`，由 main.py 手动 `_send_done`
- 双窗口各有一个 React 实例 + WS 连接，桌宠窗口需跳过 chat 消息 → `isLive2DOnly` 检查
- 情绪标签 `!emotion:happy!`（可能无 `[]`）→ 正则兼容可选方括号
- `parent_name` 符号引用 → 需文件名排序与 `name` 字段一致
- 工具调用在前端无流式消息时 → `tool_call_start` 创建占位 assistant 消息
- `message_complete` 和 `done` 顺序固定 → `thinking` 在 `message_complete` 中清除
- Python 3.10 不用 `X | None` → `Optional[X]`
- TTS task 可取消，WS 断开时 `send_json` 报错 → `_ws_send_safe()`
