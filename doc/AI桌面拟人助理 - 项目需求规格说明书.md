# AI 桌面拟人助理 - 项目需求规格说明书

## 1. 项目概述

### 1.1 项目名称
**Desktop AI Companion（桌面AI拟人助理）**

### 1.2 项目目标
构建一个运行于本地的桌面AI助理应用，支持文字/语音对话、笔记记录与检索、材料整理与Markdown导出，并可自定义模型API。助理具备拟人化的Live2D形象，能通过语音与用户交互，整体架构采用组件化、可扩展的Agent范式。

### 1.3 核心价值
- 统一的本地AI助理，整合笔记、语音、材料整理等高频功能。
- 完全可定制的模型后端（支持任何OpenAI兼容API）。
- 模块化设计：技能（Skills）、MCP工具可热插拔，易于扩展。
- 拟人化交互，提升陪伴感与使用体验。

---

## 2. 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 桌面壳 | Electron + HTML/CSS + Live2D Web SDK | 提供窗口、系统托盘、拟人形象、UI |
| 后端服务 | Python 3.11+ | Agent核心、MCP集成、数据库操作 |
| Agent框架 | LangGraph | 状态图编排对话流、工具调用、技能路由 |
| 通信协议 | WebSocket (JSON) | 前后端实时双向通信 |
| 语音识别 | 后端调用Whisper API (或本地faster-whisper) | 通过MCP封装 |
| 语音合成 | edge-tts (或API TTS) | 通过MCP封装 |
| 数据库 | SQLite + FTS5 | 笔记存储与全文搜索 |
| 包管理 | Poetry / pip | 后端依赖管理 |
| AI编程辅助 | Claude Code | 代码生成、调试、迭代 |

---

## 3. 系统架构

### 3.1 整体架构图
```
┌─────────────────────────────────────────────┐
│           Electron 桌面壳                   │
│  · Live2D (Web SDK)                         │
│  · 聊天界面 / 笔记面板 / 设置               │
│  · 音频采集 / 播放                          │
└──────────────────┬──────────────────────────┘
                   │ WebSocket (ws://localhost:8765)
                   ▼
┌─────────────────────────────────────────────┐
│           Python 后端服务                   │
│  ┌───────────────────────────────────────┐  │
│  │  FastAPI / aiohttp WebSocket 端点    │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │       LangGraph Agent 运行器          │  │
│  │  · 技能选择与Prompt注入               │  │
│  │  · 对话图执行 (chat / tool / finalize) │  │
│  │  · 流式输出管理                       │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │       MCP 工具管理器                  │  │
│  │  · 笔记MCP (SQLite + FTS5)           │  │
│  │  · 语音MCP (录音/TTS)                │  │
│  │  · 文件系统MCP (官方)                │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 3.2 关键设计原则
- **前后端分离**：Electron仅负责UI渲染与音频采集/播放，所有AI逻辑与数据处理在Python后端。
- **MCP标准化**：外部工具统一通过MCP协议接入，方便插拔和复用。
- **技能可配置**：技能以Markdown文件形式存储，包含Prompt片段和工具白名单，运行时可动态加载。
- **模型无关**：通过配置文件设置`base_url`和`api_key`，兼容OpenAI、DeepSeek、Ollama等。

---

## 4. 功能需求

### 4.1 聊天与问答
- 用户输入文字，助理以流式方式返回回复。
- 支持多轮对话，保持上下文记忆（最近N轮或token窗口管理）。
- 支持用户中断回答。
- 可将聊天中的任意片段快速保存为笔记（右键菜单或指令）。

### 4.2 笔记记录与检索
- **记录**：用户通过特殊指令（如 `/记 内容 #标签`）或在聊天中右键保存文本。系统自动解析标签并存入SQLite。
- **检索**：提供独立笔记面板，支持全文模糊搜索（利用FTS5）和按标签筛选。
- **编辑与删除**：支持对已有笔记的修改和删除。
- **导出**：选中一条或多条笔记，导出为Markdown文件（含YAML front matter记录标签和日期），保存到指定目录。

### 4.3 材料整理与Markdown生成
- 用户给出零散文本或指定日期范围的笔记，要求“整理成会议纪要/周报/大纲”等。
- 助理调用笔记工具检索相关文本，组装成Prompt，由LLM生成结构清晰的Markdown内容。
- 生成的Markdown可在预览区查看，用户确认后保存为 `.md` 文件。

### 4.4 语音交互
- **语音输入**：
  - 用户点击“语音输入”按钮（或配置快捷键），前端通过Electron采集麦克风音频，通过WebSocket发送给后端。
  - 后端MCP语音工具调用ASR服务（如Whisper API），将语音转为文本，自动填入输入框并发送。
- **语音输出**：
  - 助理回复后，后端调用TTS工具生成语音文件（MP3），返回路径给前端。
  - 前端播放音频，并驱动Live2D模型播放说话动画和口型同步。
- **可选唤醒词**：未来可扩展语音唤醒功能（如“嘿，小助”）。

### 4.5 拟人形象 (Live2D)
- 使用Live2D Cubism Web SDK在Electron中渲染角色模型。
- 支持根据助理状态切换动画/表情：待机、倾听、说话、思考、高兴等。
- 状态控制通过前端JavaScript API实现，后端通过WebSocket发送状态指令（如 `{"type":"avatar","action":"start_talk"}`）。

### 4.6 设置与自定义
- **模型配置**：API地址、API Key、模型名称。
- **语音配置**：语音识别引擎选择（API/本地）、TTS音色/语速选择。
- **人格设置**：助理的系统Prompt，可自由编辑。
- **技能管理**：查看已加载的技能列表，启用/禁用。
- 配置存储在本地JSON文件，通过设置界面修改。

---

## 5. 非功能需求

### 5.1 性能
- 后端启动时间 < 3秒。
- 语音识别端到端延迟 < 2秒（不含网络传输）。
- 流式回复首字延迟 < 500ms。
- 笔记搜索（1000条以内）响应时间 < 100ms。

### 5.2 可靠性
- 后端与前端WebSocket断开后，自动尝试重连（指数退避）。
- 笔记操作需保证事务性，避免数据损坏。
- 语音文件使用后及时清理临时文件。

### 5.3 可维护性与扩展性
- 新增一个MCP工具只需：编写MCP服务器 → 在配置文件中注册 → 重启后端，无需修改核心代码。
- 新增技能只需：在 `skills/` 目录添加 `.md` 文件，重启生效。
- 前后端通信协议版本化，便于未来升级。

### 5.4 跨平台
- 初期支持 Windows 10+，架构设计上考虑 macOS/Linux 兼容（Electron跨平台，Python跨平台）。

### 5.5 安全性
- API Key 存储于本地配置文件，仅限本机访问。
- WebSocket 仅监听本地回环地址（`127.0.0.1`），不接受外部连接。
- 不自动上传任何用户数据。

---

## 6. 接口与通信协议

### 6.1 WebSocket 消息格式

所有消息均为JSON，基础结构：
```json
{
  "type": "消息类型",
  "payload": { /* 具体数据 */ }
}
```

#### 前端 → 后端

| type | payload | 说明 |
|------|---------|------|
| `chat` | `{"message": "用户输入文本"}` | 发送文字消息 |
| `voice_input` | `{"audio_data": "base64编码的音频"}` | 发送语音数据 |
| `stop` | `{}` | 中断当前生成 |
| `save_note` | `{"content": "文本", "tags": ["标签1"]}` | 从聊天保存笔记 |
| `search_notes` | `{"query": "关键字", "tags": []}` | 搜索笔记 |
| `export_notes` | `{"note_ids": [1,2], "format": "markdown"}` | 导出笔记 |
| `get_notes_list` | `{}` | 获取所有笔记列表 |
| `delete_note` | `{"note_id": 1}` | 删除笔记 |
| `get_config` | `{}` | 获取当前配置 |
| `update_config` | `{"key": "value", ...}` | 更新配置 |

#### 后端 → 前端

| type | payload | 说明 |
|------|---------|------|
| `message_chunk` | `{"content": "增量文本"}` | 流式回复片段 |
| `message_complete` | `{"full_content": "完整回复"}` | 回复完成 |
| `avatar_state` | `{"action": "start_talk" / "idle" / "thinking"}` | 控制Live2D状态 |
| `play_audio` | `{"file_path": "/tmp/tts_xxx.mp3"}` | 请求播放语音 |
| `note_saved` | `{"note_id": 1}` | 笔记保存成功 |
| `notes_list` | `{"notes": [...]}` | 返回笔记列表 |
| `notes_exported` | `{"file_path": "/path/export.md"}` | 导出完成 |
| `search_results` | `{"results": [...]}` | 搜索结果 |
| `config` | `{"api_url": "...", ...}` | 当前配置 |
| `error` | `{"message": "错误描述"}` | 错误信息 |

### 6.2 后端内部 API
- MCP工具注册：后端启动时根据配置文件启动MCP服务器子进程，并建立Client连接，将其封装为LangChain Tool。
- 技能加载：读取 `skills/` 目录，每个`.md`解析为技能对象（name, description, prompt, allowed_tools）。

---

## 7. 数据库设计

SQLite，启用 FTS5。

### 7.1 表结构
```sql
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE note_tag (
    note_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE notes_fts USING fts5(
    content,
    content=notes,
    content_rowid=id
);
```

### 7.2 触发器（保持FTS同步）
```sql
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;
```

---

## 8. 项目结构

```
desktop-ai-companion/
├── electron-app/                # Electron 前端
│   ├── main.js                  # 主进程
│   ├── preload.js
│   ├── renderer/                # 渲染进程
│   │   ├── index.html
│   │   ├── styles.css
│   │   ├── app.js               # WebSocket客户端，UI逻辑
│   │   ├── live2d/              # Live2D模型与SDK
│   │   └── components/          # Vue/React组件（可选，也可原生JS）
│   └── package.json
├── backend/                     # Python 后端
│   ├── main.py                  # 入口，启动WebSocket服务
│   ├── agent/
│   │   ├── graph.py             # LangGraph 图定义
│   │   ├── skills.py            # 技能加载与管理
│   │   └── tools.py             # MCP工具封装（LangChain Tool）
│   ├── mcp_servers/             # MCP服务器实现
│   │   ├── notes_server.py      # 笔记MCP服务器
│   │   └── voice_server.py      # 语音MCP服务器
│   ├── db/
│   │   └── init_db.py           # 数据库初始化
│   ├── config.yaml              # 配置文件
│   ├── skills/                  # 技能Markdown文件
│   │   ├── material_organizer.md
│   │   └── daily_note_taker.md
│   └── requirements.txt
└── README.md
```

---

## 9. 开发任务分解（按阶段）

### 阶段1：项目骨架与基础通信
1. 初始化 Electron 项目，创建简单窗口，加载 Live2D 占位。
2. 初始化 Python 后端，用 `websockets` 或 FastAPI 搭建 WebSocket 服务。
3. 实现 Electron 与后端的 WebSocket 连接，前端发送消息，后端原样返回（回声测试）。
4. 配置基础模型调用（OpenAI SDK），实现单轮问答并流式返回给前端。

### 阶段2：笔记系统
1. 实现 SQLite 数据库初始化脚本（含 FTS 和触发器）。
2. 编写 MCP 笔记服务器：提供 `add_note`, `search_notes`, `export_notes` 工具。
3. 在 LangGraph 中集成笔记工具，支持聊天中通过指令或右键保存笔记。
4. 开发前端笔记面板：列表、搜索栏、标签筛选、导出按钮。

### 阶段3：语音交互
1. 编写 MCP 语音服务器：录音转文字、文字转语音。
2. 前端实现音频采集（MediaRecorder API）并通过 WebSocket 发送至后端。
3. 后端调用语音MCP进行识别，结果注入聊天流。
4. 后端回复后调用 TTS 工具，返回音频路径，前端播放并驱动 Live2D 动画。

### 阶段4：材料整理与技能系统
1. 创建技能加载器：解析 `skills/*.md`，提取 name, prompt, tools。
2. 在 LangGraph 中添加技能选择节点，根据用户输入动态切换技能。
3. 实现“材料整理”技能：调用笔记搜索 → LLM生成Markdown → 文件系统MCP保存。
4. 前端预览生成的 Markdown，支持编辑和确认保存。

### 阶段5：拟人形象与系统整合
1. 集成 Live2D SDK，加载默认模型，实现基本状态切换（待机、说话、倾听）。
2. 同步语音播放与口型动画。
3. 添加系统托盘、开机自启、通知功能。
4. 设置界面：模型配置、语音配置、人格编辑、技能列表。

### 阶段6：测试、打包与文档
1. 端到端测试所有功能。
2. 使用 `electron-builder` 打包桌面应用，`pyinstaller` 打包后端（或提供启动脚本）。
3. 编写用户手册和开发者文档。

---

## 10. 配置文件示例

### config.yaml
```yaml
model:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-your-key"
  model_name: "deepseek-chat"
  max_tokens: 4096

server:
  host: "127.0.0.1"
  port: 8765

mcp_servers:
  notes:
    command: "python"
    args: ["backend/mcp_servers/notes_server.py"]
  voice:
    command: "python"
    args: ["backend/mcp_servers/voice_server.py"]
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/notes"]

skills_dir: "backend/skills"

voice:
  asr_engine: "whisper_api"   # 或 "local_whisper"
  tts_engine: "edge_tts"     # 或 "openai_tts"
  tts_voice: "zh-CN-XiaoxiaoNeural"
```

---

## 11. 验收标准

1. 用户能输入文字与助理进行多轮对话，助理的回答流式显示。
2. 可通过指令或右键将聊天内容保存为笔记，添加标签，在面板中搜索和导出。
3. 选择“材料整理”技能后，助理能检索笔记并生成结构良好的Markdown文件。
4. 点击语音输入按钮，说出的话被正确识别并发送；助理的回复能被朗读出来，同时Live2D模型做出相应口型和动作。
5. 在设置中修改API地址后，助理能立即使用新模型进行回复。
6. 应用可打包为独立安装程序，启动后系统托盘出现图标，可常驻后台。

---

**此文档作为项目唯一事实来源，所有后续开发均以此为准。请Claude Code根据本规范生成代码，遵循模块化、可测试原则，并在每个阶段结束时提供运行说明。**