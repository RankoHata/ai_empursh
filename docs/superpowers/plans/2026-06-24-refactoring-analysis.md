# 代码重构分析报告

> 生成日期: 2026-06-24 | 基于 `ced6f57` 全量代码审查

---

## 一、无用模块 / 遗留代码

### 1.1 前端 — 已废弃组件（仍在 import，不再渲染）

| 文件 | 状态 | 建议 |
|------|------|------|
| `components/StatusBar.jsx` | App.jsx 中 import 但从未使用 | **删除** |
| `components/TabBar.jsx` | App.jsx 中 import 但从未使用 | **删除** |
| `components/AvatarStatus.jsx` | App.jsx 中 import 但从未使用 | **删除**（或合并到 Avatar.jsx） |

### 1.2 前端 — Live2D 遗留（已被 Spine 替代）

| 路径 | 内容 | 建议 |
|------|------|------|
| `src/live2d/` | ~85 个 Cubism 5 SDK ts 文件 + 我们的 Model.ts | **删除整个目录** |
| `assets/live2d/` | G36 模型 + shaders | **删除整个目录** |
| `CLAUDE.md` 旧版中的 Live2D 安装步骤 | 需手动下载 `live2dcubismcore.min.js` | **已从新 CLAUDE.md 移除** |

### 1.3 后端 — 死代码

| 位置 | 代码 | 建议 |
|------|------|------|
| `chat.py:525` | `if self._on_done: await self._on_done()` | `_on_done` 从未被设置（main.py 注释说明手动处理），这是**永不执行的死代码**。**删除**或改为 assert |
| `chat.py:355` | 同上，`stream_with_tool_loop` 中 no-tools 分支的 `_on_done` 调用 | **删除** |

> ⚠️ **保留**: `agent/skills.py` + `skills/*.md`（技能系统是能力框架，当前仅一个技能不影响其架构价值）、`mcp_servers.yaml` 中的 echo 服务器（测试工具，不影响功能和可读性）

### 1.4 配置残留

| 位置 | 内容 | 建议 |
|------|------|------|
| `config.js:FEATURES.showLive2D` | 设为 `false`，控制右侧栏 | 改为 `showAvatar` 更准确，或直接删除（因为总是 false） |

---

## 二、耦合问题分析

### 2.1 🔴 严重：App.jsx 上帝组件

**文件**: `electron-app/src/renderer/App.jsx` (~900行)

**问题**:
- 25+ 个 `useState`，管理所有应用状态
- 30+ 个 WS 消息类型的 switch-case
- 20+ 个 `useCallback` handler
- 直接操作 localStorage
- 直接操作 DOM（创建 file input 等）
- 消息处理、笔记管理、对话管理、人格管理、TTS 控制全部耦合在一起

**后果**: 修改任何功能都要触碰此文件，测试困难，无法复用，新人难以理解。

### 2.2 🔴 严重：main.py WebSocket 处理器

**文件**: `backend/main.py` (~960行)

**问题**:
- 单文件包含：HTTP 路由、WS 路由、TTS 逻辑、笔记逻辑、对话逻辑、人格逻辑、技能路由、配置管理、文件保存、秘密笔记
- 模块级全局变量：`tool_registry`, `personality_manager`, `tts_engine`, `_tts_streams`
- `_ws_send_safe`, `_send_thinking`, `_send_done` 等工具函数散落文件各处
- 秘密笔记的 WS callback 通过 `tool_registry._ws_sender` 注入——绕过正常的依赖注入

### 2.3 🟡 中等：聊天/对话/笔记逻辑交织

**main.py 中的 chat 消息处理（~80行）**:
- 技能路由
- 工具 schema 构建
- 人格渲染
- 流式处理 + emotion tag 剥离
- TTS 自动合成
- 对话自动创建/持久化
- turn 保存

全部挤在一个代码块里，职责不清。

### 2.4 🟡 中等：秘密笔记的安全模型依赖全局变量

**路径**: `tools/notes.py` → `_registry` 全局 + `_set_registry()` 

LLM 调用 `search_secret_notes` → 工具内部通过 `_registry._ws_sender` 直接发 WS 消息给前端。

**问题**: 隐式依赖、无法测试、多连接时 `_ws_sender` 指向最后一个连接。

### 2.5 🔴 严重：TTS / STT 与聊天流程深度耦合

**TTS（文字→语音）**:
```python
# main.py: 聊天完成后直接内联 TTS 逻辑
if clean_content.strip() and tts_enabled:
    if tts_task and not tts_task.done():
        tts_task.cancel()
    tts_task = asyncio.create_task(_synthesize_and_send(...))
```

**STT（语音→文字）**:
- `ChatPanel.jsx` 直接操作 `AudioContext` + `getUserMedia` 录音
- base64 WAV 通过 `voice_input` WS 消息发送
- 识别结果通过 `voice_result` 回传，直接触发 `addUserMsgAndSend`

**核心问题**: TTS/STT 不是独立的可插拔能力，而是硬编码在聊天流程中：
- TTS 内嵌在 main.py 的消息完成处理中，无法独立开关/替换引擎
- STT 内嵌在 ChatPanel 组件中，无法复用到其他场景（如语音指令、语音笔记）
- 两个引擎都缺乏统一的抽象接口，替换引擎需要改动核心流程代码

**理想形态 — extension 模式**:
```
voice/
├── extension.py        # VoiceExtension 基类/接口
├── stt_extension.py    # STT 输入扩展
├── tts_extension.py    # TTS 输出扩展
└── engines/
    ├── tts_edge.py     # 引擎实现（不感知聊天）
    ├── tts_f5.py
    └── stt_whisper.py

聊天流程 → pipeline: [STT?] → [LLM] → [TTS?]
                       ↑ 可插拔       ↑ 可插拔
```

### 2.6 🟢 轻微：App.css 过长

**文件**: `electron-app/src/renderer/App.css` (~1822行)

单文件包含所有组件样式。建议拆分为组件级 CSS Module 或 styled-components。

### 2.7 🟢 轻微：Avatar 双系统并存

当前在用 Spine（`src/avatar/`），但 Live2D 代码（`src/live2d/`）仍在仓库中，`Avatar.jsx` 曾用名可能是 `Live2DAvatar.jsx`。

---

## 三、架构问题

### 3.1 语音能力缺乏 extension 抽象（当前最关键的架构缺陷）

TTS 和 STT 是独立于聊天的能力，但当前被硬编码在 chat 流程中。正确做法是设计为 **extension 插件模式**：

```
┌────────────────────────────────────────┐
│            Chat Pipeline               │
│                                        │
│  [STT Extension]  ← 语音输入            │
│       │                                │
│       ▼                                │
│  [LLM ChatSession] ← 文本处理           │
│       │                                │
│       ▼                                │
│  [TTS Extension]  ← 语音输出            │
│                                        │
│  每个 Extension:                        │
│  - 统一接口 (input/output/cancel)       │
│  - 独立配置 (引擎选择、音色、语速)       │
│  - 可单独启用/禁用                      │
│  - 不依赖聊天上下文                     │
└────────────────────────────────────────┘
```

**目标**:
| 能力 | 当前 | 目标 |
|------|------|------|
| STT | ChatPanel 内嵌录音逻辑 | `stt_extension` 可在任何输入场景复用（聊天、笔记、指令） |
| TTS | main.py 聊天完成后内联调用 | `tts_extension` 管线后处理，可独立开关/替换引擎 |
| 引擎 | Edge/F5 通过 `voice/tts.py` 工厂 | 引擎是纯实现，extension 是管线适配层 |

### 3.2 MCP / Tools 缺乏独立模块化，与聊天流程紧耦合

当前 tool 和 MCP 的调用深嵌在 ChatSession 的工具循环中（`chat.py:340-526`），两者的启用/禁用、schema 获取、结果处理全部混杂在一起。

**当前问题**:
```
main.py
├── tool_registry = create_default_registry()   ← 模块级单例
├── mcp_manager = app.state.mcp_manager         ← 挂 app state
│
└── chat 消息处理:
    ├── active_tool_schemas = tool_registry.get_schemas() + mcp_tools  ← 手动拼接
    ├── session.stream_with_tool_loop(schemas)   ← 不区分来源
    └── ChatSession 内部: _execute_tool() 通过 is_mcp_tool() 分支判断
```

**核心问题**:
- ToolRegistry 和 MCPManager 是完全不同的两个系统，但 schema 在 main.py 中手动拼接
- ChatSession 需要同时感知两种工具来源，`_execute_tool()` 内部用字符串前缀 `mcp__` 做分支
- 添加第三种工具来源（如 HTTP API 工具、本地脚本工具）需要修改 ChatSession 核心代码
- 模块级单例的 `_ws_sender` 是多连接安全隐患

**理想形态 — 统一 ToolProvider 接口**:
```
tools/
├── provider.py         # ToolProvider 抽象接口
│                       #   get_schemas() → list[dict]
│                       #   execute(name, args, context) → dict
│                       #   can_handle(name) → bool
│
├── registry_provider.py # 内置工具提供者 (ToolRegistry)
├── mcp_provider.py      # MCP 工具提供者 (MCPManager)
│
└── dispatcher.py        # ToolDispatcher
                          #   注册多个 provider
                          #   自动聚合 schemas
                          #   按 name 路由到对应 provider
                          #   统一错误处理

ChatSession → ToolDispatcher (只认一个接口)
               ├── RegistryProvider (内置笔记工具)
               ├── MCPProvider (echo, 未来更多)
               └── (未来) HttpToolProvider, ScriptProvider ...
```

**目标**: 添加新工具来源 = 实现一个 Provider + 注册到 Dispatcher，ChatSession 无需改动。

### 3.3 Prompt 拼接存在硬编码，缺乏可配置的组装机制

当前 system prompt 由多处硬编码字符串拼接而成，分散在多个文件中：

| 硬编码位置 | 内容 | 文件 |
|-----------|------|------|
| 情绪标签指令 | `"[系统指令] 在每次回复的最后一行..."` | `personality_manager.py:123-127` |
| 紧凑模式指令 | `"[系统指令-紧凑模式] 回复尽量紧凑简洁..."` | `main.py:449-453` |
| 时间上下文 | （曾添加后回退） | — |

**当前问题**:
1. **分散不可见**: 无法一眼看到发给 AI 的完整 prompt 长什么样
2. **硬编码中文**: 指令字符串直接写在 Python 代码中，修改需要改代码
3. **拼接顺序隐式**: `模板渲染 → 情绪指令 → 紧凑指令`，这个顺序隐含在代码执行流中，不是显式声明的
4. **条件注入逻辑散落**: `if compact_enabled:` 在 main.py，`if personality_prompt:` 也在 main.py，各自为政
5. **无法预览/调试**: 没有机制能输出最终组装好的完整 prompt（对调试至关重要）

**理想形态 — Prompt Pipeline**:
```
prompt/
├── pipeline.py          # PromptPipeline: 有序的 prompt 片段列表
│                         #   build(context) → 按序渲染所有片段 → 拼接 → 返回完整 prompt
│
├── segments/            # 每个文件一个独立 prompt 片段（纯数据/模板，不含逻辑）
│   ├── personality.py   #   人格模板片段（从 DB 加载，Jinja2 渲染）
│   ├── emotion.py       #   情绪标签指令片段
│   ├── compact.py       #   紧凑模式指令片段
│   ├── time_info.py     #   时间上下文片段（条件：enable_time_context）
│   └── system.py        #   全局系统约束片段
│
└── context.py           # PromptContext 数据类
                          #   - personality_name, user_name, current_time
                          #   - compact_enabled, emotion_required
                          #   - 所有条件 flag 集中在一处

Pipeline 执行:
  context = PromptContext(user_name="张三", compact_enabled=True, ...)
  prompt = pipeline.build(context)
  # → 人格模板渲染
  # → + "\n\n[系统指令] 情绪标签..."
  # → + "\n\n[系统指令-紧凑模式] 回复尽量紧凑..."
  # → 返回完整字符串
  # → logger.debug(prompt)  # 可预览
```

**核心原则**:
- **所有 prompt 文本集中在 `prompt/segments/` 目录**，不在业务代码中散落
- **每个 segment 是纯数据/模板**，不含条件逻辑（条件由 pipeline 根据 context 决定是否启用）
- **Pipeline 顺序显式声明**，不依赖代码执行流
- **完整 prompt 可日志预览**，便于调试

### 3.4 前端没有分层

```
当前:  App.jsx (一切)
        ├── ChatPanel.jsx
        ├── SettingsPanel.jsx
        ├── NotesPanel.jsx
        └── ...

理想:  App.jsx (路由+布局)
        ├── pages/ChatPage.jsx    (聊天状态+逻辑)
        ├── pages/NotesPage.jsx   (笔记状态+逻辑)
        ├── pages/SecretPage.jsx  (秘密笔记状态+逻辑)
        └── hooks/
            ├── useChat.js        (聊天 WS 逻辑)
            ├── useNotes.js       (笔记 WS 逻辑)
            ├── usePersonalities.js
            └── useConversations.js
```

### 3.5 后端没有路由分层

```
当前:  main.py (所有消息处理在一个 while 循环)

理想:  main.py (WebSocket 连接管理 + 路由分发)
        ├── routers/chat.py       (chat, stop, delete_turn)
        ├── routers/notes.py      (add_note, get_notes, search_notes, ...)
        ├── routers/conversations.py
        ├── routers/personalities.py
        ├── routers/config.py
        └── services/
            ├── chat_service.py   (ChatSession 工厂 + 流式逻辑)
            ├── tts_service.py    (TTS 后处理)
            └── conversation_service.py
```

### 3.6 工具注册使用模块级单例

```python
# main.py
tool_registry = create_default_registry()  # 模块级
personality_manager = get_manager(config)  # 模块级
```

多连接共享同一 registry，`_ws_sender` 每次连接覆盖——最后连接的客户端接收所有秘密笔记推送。

### 3.7 人格模板的 `current_time` 永不被渲染

`personality_manager.py` 的 `render_prompt()` 在 Jinja2 上下文中提供 `current_time`，但**所有 YAML 模板都不引用 `{{ current_time }}`**。这导致 AI 无法获得真实时间。需要等 `get_current_time` MCP 工具实现后才能解决。

---

## 四、重构方案

### 阶段 1: 清理（低风险，立即可做）

1. **删除废弃组件**: `StatusBar.jsx`, `TabBar.jsx`, `AvatarStatus.jsx`
2. **删除 Live2D 遗留**: `src/live2d/`, `assets/live2d/`
3. **删除死代码**: `chat.py` 中的 `_on_done` 调用
4. **清理 config.js**: `showLive2D` flag 改名为 `showAvatar`

### 阶段 2: 前端拆分（中风险，逐步进行）

1. **抽取自定义 hooks**:
   - `useChat(ws)` — 聊天消息状态 + send/receive 逻辑
   - `useNotes(ws)` — 笔记列表 + CRUD 操作
   - `usePersonalities(ws)` — 人格列表 + 切换
   - `useConversations(ws)` — 对话列表 + 加载
   - `useSettings(ws)` — 配置 + 用户设置

2. **App.jsx 瘦身到 ~150行**: 只负责布局 + 页面路由 + hook 组合

3. **CSS 拆分**: 每个组件独立 CSS 文件（或 CSS Module）

### 阶段 3: 后端拆分（中高风险）

1. **工具系统模块化 — ToolProvider 统一接口**:
   - 定义 `ToolProvider` 抽象（`get_schemas`, `execute`, `can_handle`）
   - 现有 `ToolRegistry` 和 `MCPManager` 分别实现 `ToolProvider`
   - 新增 `ToolDispatcher` 聚合多个 provider，统一路由
   - ChatSession 只依赖 `ToolDispatcher`，不感知工具来源

2. **Prompt Pipeline — 消除硬编码**:
   - 创建 `prompt/` 模块：`PromptPipeline` + `PromptContext` + `segments/`
   - 将散落在 `main.py`、`personality_manager.py` 中的硬编码 prompt 片段迁移到 `segments/`
   - Pipeline 按显式顺序组装：personality → time_info → compact → emotion → system
   - 每个 segment 通过 `PromptContext` 的条件 flag 决定是否启用
   - 支持日志输出完整 prompt 便于调试

3. **WS 消息路由**:
   ```
   main.py
   ├── WS 连接建立 → 注册 handlers
   └── 消息循环 → dispatcher.dispatch(msg_type, payload, session_context)
   ```

4. **提取 handler 模块**:
   - `routers/chat_router.py`
   - `routers/notes_router.py`
   - `routers/conversation_router.py`
   - `routers/personality_router.py`
   - `routers/config_router.py`

5. **提取服务层**:
   - `services/chat_service.py` — ChatSession 工厂 + 流式编排
   - `services/conversation_service.py` — 对话生命周期

6. **消除全局状态**:
   - `tool_registry._ws_sender` → 改为每次工具执行时传入 callback
   - 秘密笔记 WS 推送 → 通过依赖注入或上下文对象

### 阶段 4: 架构升级（高风险，需充分测试）

1. **语音能力 extension 化**（核心）:
   - 设计 `VoiceExtension` 抽象接口
   - STT pipeline：AudioCapture → STT Engine → text output（独立于聊天，可复用）
   - TTS pipeline：text input → TTS Engine → audio stream output（独立于聊天，可插拔）
   - 引擎替换无需改动聊天核心流程
2. **对话持久化优化**: 当前每次对话都自动创建，可改为显式保存
3. **Spine Avatar 系统独立**: 将 Avatar 相关代码抽取为独立 package，可被主窗口和宠物窗口共享
4. **`get_current_time` 工具**: 创建 MCP 或内置工具，返回带时区的时间

---

## 五、优先级矩阵

| 优先级 | 任务 | 工作量 | 风险 | 收益 |
|--------|------|--------|------|------|
| P0 | 删除废弃前端组件 | 10min | 低 | 清理 import 噪音 |
| P0 | 删除 Live2D 遗留目录 | 5min | 低 | 减少 ~90 个文件 |
| P0 | 删除 chat.py 死代码 | 5min | 低 | 减少困惑 |
| P1 | **Prompt Pipeline — 消除硬编码** | 3-4h | 中 | 所有 prompt 文本可见/可配置/可调试 |
| P1 | **ToolProvider 统一接口** | 3-4h | 中 | 工具来源可插拔，ChatSession 解耦 |
| P1 | **TTS/STT 解耦为 extension** | 4-6h | 中 | 可插拔语音能力，独立测试/替换 |
| P1 | 前端 hooks 抽取 | 2-3h | 中 | App.jsx 瘦身 60% |
| P1 | 后端 handler 拆分 | 3-4h | 中 | main.py 瘦身 70% |
| P1 | 消除全局 _ws_sender | 1h | 中 | 修复多连接 bug |
| P2 | CSS 拆分 | 2h | 中 | 可维护性 |
| P2 | get_current_time 工具 | 30min | 低 | 修复时间 bug |

---

## 六、风险提示

- **阶段 3 后端拆分**需要保持 WS 消息协议的向后兼容，前端不能 break
- **阶段 1 删除 Live2D 目录**前确认 `Avatar.jsx` 和 `vite.renderer.config.mjs` 不引用该目录
- **消除 `_ws_sender`** 需要测试多窗口场景（主窗口 + 宠物窗口各有一个 WS 连接）
- 当前没有自动化测试，重构后需手动回归核心流程：聊天、工具调用、笔记、对话切换、人格切换
