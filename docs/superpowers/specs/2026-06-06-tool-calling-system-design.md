# Tool Calling 系统 — 设计文档

**日期**：2026-06-06
**状态**：待确认

---

## 1. 目标

为 AI 桌面助理添加真正的 tool_use / function calling 能力，使模型能够自主调用工具（搜索笔记、创建笔记等），替代当前手动拼接 system prompt + 数据的技能执行方式。

同时将技能系统与工具系统彻底解耦：
- **工具 (Tools)**：可执行的能力函数，模型通过 function calling 自主调用
- **技能 (Skills)**：行为/角色修饰的 system prompt，影响模型如何思考和表达

---

## 2. 架构设计

### 2.1 分层架构

```
┌─ WebSocket 层 (main.py) ──────────────────────────────┐
│  接收 chat 消息 → 技能匹配 → 传给 ChatSession          │
│  ChatSession 通过 callback 通知 tool_call 事件         │
├────────────────────────────────────────────────────────┤
│  新增发送消息类型:                                      │
│    tool_call_start  {name, args}                       │
│    tool_call_result {name, result, duration_ms}        │
│    tool_call_error  {name, error}                      │
└──────────────────────────┬─────────────────────────────┘
                           │
┌─ Agent 层 (agent/chat.py) ─────────────────────────────┐
│  ChatSession.stream_chat_with_tools()                  │
│    → 调 API（带 tools schema）                         │
│    → 收到 delta.content   → yield ("content", token)   │
│    → 收到 delta.tool_calls → 累积完整后:               │
│        → yield ("tool_call", {name, args})             │
│        → ToolRegistry.execute(name, args)              │
│        → 结果回填 history → 循环调 API                  │
│    → stop_event 每次迭代检查 → 立即中断                 │
└──────────────────────────┬─────────────────────────────┘
                           │
┌─ Tool 层 (tools/) ────────────────────────────────────┐
│  ToolRegistry                                          │
│    register(tool)         注册工具                     │
│    get_schemas(names)     生成 OpenAI tools 参数       │
│    execute(name, args)    执行并返回 JSON 字符串       │
│    get_for_skill(skill)   按 allowed_tools 过滤        │
│                                                        │
│  ToolDefinition (数据类)                               │
│    name, description, parameters, required             │
│    executor: async callable                            │
│    display_name                                         │
└────────────────────────────────────────────────────────┘
```

### 2.2 新增/修改文件

```
backend/
├── tools/                     ★ 新增
│   ├── __init__.py            ToolRegistry + 注册入口
│   ├── base.py                ToolDefinition 数据类
│   └── notes.py               search_notes, get_notes, add_note 工具定义
│
├── agent/
│   ├── chat.py                ★ 修改：新增 stream_chat_with_tools()
│   └── skills.py              不变
│
├── skills/                    不变
├── main.py                    ★ 修改：注册 tools，新 WS 消息类型，移除标签确认流程
│
electron-app/src/renderer/
├── App.jsx                    ★ 修改：新增 tool_call 消息处理
└── components/
    ├── ToolCallCard.jsx        ★ 新增：可展开 tool call 卡片
    └── MessageBubble.jsx       ★ 修改：渲染 tool_call 子条目
```

---

## 3. Tool 系统

### 3.1 ToolDefinition

```python
@dataclass
class ToolDefinition:
    name: str                          # "search_notes"
    description: str                   # 模型看到的工具描述
    parameters: dict                   # JSON Schema properties
    required: list[str]                # 必填参数
    executor: Callable                 # async 执行函数
    display_name: str = ""             # 前端显示名，默认取 name
```

### 3.2 ToolRegistry

```python
class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None: ...
    def get_schemas(self, tool_names: list[str] | None = None) -> list[dict]: ...
    async def execute(self, name: str, args: dict) -> str: ...
    def get_for_skill(self, skill: dict) -> list[dict]: ...
```

- `get_schemas()` — 生成 OpenAI Chat API 的 `tools` 参数格式
- `execute()` — 调用 `tool.executor(**args)`，返回 JSON 字符串，捕获异常不抛
- `get_for_skill()` — 按技能文件中的 `allowed_tools` 过滤

### 3.3 工具列表（Phase 1）

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `search_notes` | 全文搜索笔记 | `query`, `tags`, `limit` |
| `get_notes` | 获取指定笔记完整内容 | `note_ids` |
| `add_note` | 创建新笔记 | `content`, `tags` |

### 3.4 工具执行结果格式

```json
{
  "success": true,
  "data": [...],
  "count": 3,
  "message": "找到 3 条笔记"
}
```

错误时:
```json
{
  "success": false,
  "data": null,
  "count": 0,
  "message": "搜索超时",
  "error": "timeout"
}
```

---

## 4. ChatSession 改造

### 4.1 新方法: `stream_chat_with_tools()`

保留原有 `stream_chat()`（无工具模式），新增：

```python
async def stream_chat_with_tools(
    self,
    tool_schemas: list[dict],
) -> AsyncGenerator[tuple[str, str | dict], None]:
    """Yield ("content", token) or ("tool_call", {name, args, id})."""
```

### 4.2 多轮 Tool Loop 流程

```
1. 构建 messages = system_prompt(可选) + history
2. client.chat.completions.create(messages, tools=tool_schemas, stream=True)
3. 遍历 stream chunks:
   a. 检查 stop_event → 中断
   b. delta.content → yield ("content", token)
   c. delta.tool_calls → 累积（跨 chunk 拼接）
4. tool_calls 完整后:
   a. 每个 tool_call → yield ("tool_call", {name, args, id})
   b. 通过 on_tool_call callback 通知上层
   c. ToolRegistry.execute(name, args)
   d. 通过 on_tool_result callback 通知上层
   e. 结果追加到 history (role: "tool")
   f. goto 1（继续循环，让模型基于结果回复）
5. 无 tool_calls 且 content 结束 → 完成
```

### 4.3 回调机制

```python
class ChatSession:
    def __init__(self, ...,
                 tool_registry: ToolRegistry | None = None,
                 on_tool_call: Callable | None = None,
                 on_tool_result: Callable | None = None):
```

main.py 注册回调：

```python
async def on_tool_call(name, args):
    await _ws_send_safe(ws, "tool_call_start", {"name": name, "args": args})

async def on_tool_result(name, result):
    await _ws_send_safe(ws, "tool_call_result", {"name": name, "result": result})
```

### 4.4 安全阀

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `_max_tool_rounds` | 10 | 单次对话最多 tool call 轮次 |
| `_tool_call_timeout` | 30s | 单个工具执行超时 |
| `_stop_event` | — | 用户中断 → 立即停止 |

---

## 5. WebSocket 协议

### 5.1 新增消息（后端 → 前端）

| type | payload | 说明 |
|------|---------|------|
| `tool_call_start` | `{name, args}` | 模型决定调用工具 |
| `tool_call_result` | `{name, result, duration_ms}` | 工具执行完成 |
| `tool_call_error` | `{name, error}` | 工具执行失败 |

### 5.2 不变消息

`message_chunk`、`message_complete` 不变——工具调用过程中的文本 token 仍走传统通道。

### 5.3 典型消息序列

```
用户: "帮我整理工作笔记"
  → message_chunk: ""       (模型还在思考)
  → tool_call_start: {name: "search_notes", args: {tags: ["工作"]}}
  → tool_call_result: {name: "search_notes", result: {success: true, count: 3}, duration_ms: 120}
  → message_chunk: "根据你的"      ← 模型基于工具结果回复
  → message_chunk: "工作笔记"
  → ...
  → message_complete: {full_content: "...", partial: false}
```

---

## 6. 前端设计

### 6.1 新增组件: `ToolCallCard.jsx`

状态展示：

```
┌──────────────────────────────────────────┐
│ 🔧 search_notes    ⏳ 执行中...          │  ← running (绿色边框)
├──────────────────────────────────────────┤
│ (展开后)                                  │
│ 参数: {"tags":["工作"]}                   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ 🔧 search_notes    ✓ 完成 · 0.3s        │  ← completed (默认折叠)
├──────────────────────────────────────────┤
│ 参数: {"tags":["工作"]}                   │  ← 点击展开
│ 结果: 找到 3 条笔记                      │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ 🔧 search_notes    ✗ 超时               │  ← error (红色边框)
├──────────────────────────────────────────┤
│ 错误: 工具执行超时                       │
└──────────────────────────────────────────┘
```

### 6.2 App.jsx 改动

`handleMessage` 新增 3 个 case：

- `tool_call_start` → 在当前 streaming assistant 消息下追加 tool_call 子条目（state: "running"）
- `tool_call_result` → 更新子条目为完成，记录结果
- `tool_call_error` → 更新子条目为失败，记录错误

### 6.3 MessageBubble.jsx 改动

对 assistant 消息，在其 `bubble-content` 下方渲染 tool_call 卡片列表（如果有）。

### 6.4 用户交互模式：B+C 组合

- **状态提示条**（方案 B）：tool call 发生时在聊天区顶/底部显示浮动提示 "🔧 正在调用 search_notes..."
- **可展开面板**（方案 C）：消息内嵌折疊卡片，可查看参数和结果

---

## 7. 技能系统调整

### 7.1 技能文件格式不变

```markdown
---
name: material-organizer
description: 将指定范围的笔记整理为结构化 Markdown 文档
command: /整理
allowed_tools:
  - search_notes
  - get_notes
  - add_note
---
(system prompt 正文)
```

### 7.2 执行流程变化

**现在**：
1. 匹配 `/整理` 命令
2. 提取 `#tag`，数据库匹配，确认对话框
3. 将笔记数据注入 prompt
4. 发送给模型 → 生成整理结果

**改后**：
1. 匹配 `/整理` 命令
2. 加载 skill 的 system_prompt 作为上下文
3. 按 `allowed_tools` 过滤工具集
4. 发送给模型 → **模型自主决定**调 search_notes → 拿到数据 → 生成整理结果
5. 标签由模型从工具返回结果中自行理解、可能调用 add_note 保存

### 7.3 标签确认流程

移除现有的标签模糊匹配+确认对话框逻辑（`_resolve_tags`, `_parse_confirmation`, `_tag_confirm_msg`）。模型通过工具返回的笔记数据自行理解标签，必要时可通过自然语言向用户确认。

### 7.4 触发方式

| 方式 | Phase | 示例 | 行为 |
|------|-------|------|------|
| 命令触发 | Phase 1 | `/整理 #工作` | 加载 system_prompt + 过滤工具 |
| 自然语言+默认工具 | Phase 1 | "帮我搜索工作笔记" | 默认工具集 + 无额外 system_prompt |
| 自然语言+技能匹配 | Phase 2 | "帮我整理一下笔记" | 语义匹配 → 加载技能 prompt |

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| 工具执行超时 | 返回 `{success: false, error: "timeout"}`，模型自行决定重试或放弃 |
| 工具执行异常 | 捕获异常，返回错误 JSON，模型可见 |
| 模型返回无效参数 | 工具校验参数 → 返回 descriptive error → 模型通常能自我纠正 |
| Tool loop 超过 10 轮 | 强制注入 system 消息 "请基于已有信息回复用户"，不再提供工具 |
| 用户点击停止 | `stop_event` 中断当前 API 调用和工具执行 |
| WebSocket 断开 | `_ws_send_safe` 忽略发送失败，tool loop 继续完成（结果仍回填 history） |

---

## 9. 未来迁移到 Agent Loop

当前 ToolRegistry 的接口设计已为 Agent Loop 预留：

```
将来新增 agent/loop.py:

class AgentLoop:
    def __init__(self, tool_registry, chat_session):
        ...

    async def run(self, user_message):
        # Plan → Act → Observe → Reflect 循环
        # 内部使用 tool_registry.execute()
        # 复现 on_tool_call / on_tool_result 回调
```

ChatSession 的 tool loop 逻辑可抽取到 AgentLoop 中，ToolRegistry 完全不用改。

---

## 10. 验收标准

1. 用户输入 "帮我搜索工作相关的笔记" → 模型自动调用 `search_notes` → 显示结果
2. 用户输入 `/整理 #工作` → 加载 skill + 过滤工具 → 模型调 search_notes → 生成整理 → 预览
3. 工具调用显示为可展开卡片（运行中 → 完成/失败状态）
4. 用户点击 "停止" 能在工具执行中中断
5. 工具执行出错时模型能自我纠正或向用户解释
6. `message_chunk` 流式渲染不受 tool call 穿插影响
7. 原有聊天功能（无工具调用时）保持不变

---

## 11. 不做什么（Phase 1）

- 不实现 MCP 远程工具集成
- 不实现自然语言自动匹配技能（仅 `/command` 触发）
- 不实现并行工具调用的前端特殊展示
- 不改动语音、Live2D、设置等无关模块
