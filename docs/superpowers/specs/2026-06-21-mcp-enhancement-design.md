# MCP 能力增强 — 详细设计

> 将现有流式对话升级为 **Claude Code 风格**的非阻塞 MCP 工具调用体验。

**日期**：2026-06-21
**状态**：已确认
**关联需求**：`doc/MCP能力增强.md`

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        Electron 前端                              │
│  App.jsx                                                        │
│  ├── handleMessage()   ← 新增 thinking / done 处理               │
│  ├── ToolCallCard      ← UI 升级（图标、动画、自动折叠）          │
│  └── MessageBubble     ← 新增 ThinkingIndicator                   │
│       │                                                          │
│       │ WebSocket (协议 v2)                                       │
│       ▼                                                          │
│  Python FastAPI (main.py)                                        │
│  ├── on_tool_call()    ← 补 id 字段                              │
│  ├── on_tool_result()  ← 补 id 字段                              │
│  ├── _send_thinking()  ← 新增                                    │
│  └── _send_done()      ← 新增                                    │
│       │                                                          │
│       ▼                                                          │
│  agent/chat.py                                                   │
│  ├── ChatSession       ← 注入 mcp_manager + thinking/done 回调    │
│  ├── stream_with_tool_loop() ← 工具并行执行 + thinking/done 推送  │
│  └── _execute_tool()   ← 统一路由（内置/MCP）                     │
│       │                                                          │
│       ├──────────────┬──────────────────────┐                    │
│       ▼              ▼                      ▼                    │
│  tools/          mcp/                   DeepSeek API             │
│  ToolRegistry    MCPManager             (OpenAI 兼容)            │
│  (内置工具)       ├── MCPStdioClient                              │
│                  ├── MCPHTTPClient                                │
│                  ├── MCPAdapter                                  │
│                  └── MCPProtocol (JSON-RPC)                       │
│                       │                      │                   │
│                       ▼                      ▼                   │
│                  MCP Server A          MCP Server B               │
│                  (stdio 子进程)        (HTTP/SSE 远程)            │
└──────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **MCP 工具 = 另一种"工具来源"**。`ChatSession` 不关心工具来自内置还是 MCP，拿到统一的 OpenAI tools schema 列表执行。执行时按名称前缀路由。
2. **双工具体系并行**。`ToolRegistry` 保持不变，`MCPManager` 新增。两者在 `main.py` 中合并。
3. **协议 v2 向前兼容**。新增 `thinking`/`done` 类型，`tool_call_start` 补 `id` 字段。`message_chunk`/`message_complete` 保留不改名。
4. **MCP 配置独立**。放在 `backend/mcp_servers.yaml`，不污染 `config.yaml`，类似 Claude Code 的 `.mcp.json`。

---

## 2. MCP Client 模块

### 2.1 目录结构

```
backend/mcp/
├── __init__.py          # MCPManager — 多 Server 生命周期管理
├── protocol.py          # JSON-RPC 消息编解码 + MCP 协议常量
├── stdio_client.py      # MCPStdioClient — stdio 子进程传输
├── http_client.py       # MCPHTTPClient — HTTP/SSE 传输
├── adapter.py           # MCP tool schema → OpenAI tools 格式
└── errors.py            # MCP 专用异常
```

### 2.2 MCPManager (`__init__.py`)

核心接口：

```python
class MCPManager:
    """管理多个 MCP Server 的连接生命周期"""

    @classmethod
    def from_config(cls, config_path: str) -> "MCPManager"
        # 从 mcp_servers.yaml 加载配置，创建对应的 Client 实例

    async def connect_all() -> None
        # 启动所有 Server 连接（stdio: 启动子进程; http: 验证连通性）

    async def disconnect_all() -> None
        # 关闭所有连接，清理子进程

    def get_all_tools() -> list[dict]
        # 返回所有 MCP Server 的工具列表，OpenAI function calling 格式

    async def call_tool(name: str, args: dict) -> dict
        # 按 "mcp__<server>__<tool>" 前缀路由到对应 Server

    async def list_servers() -> list[dict]
        # 返回各 Server 连接状态（name, transport, connected, tool_count）
```

### 2.3 MCPProtocol (`protocol.py`)

纯函数模块，处理 JSON-RPC 2.0：

```python
# MCP 标准方法常量
INITIALIZE = "initialize"
TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"

def build_request(id: int, method: str, params: dict) -> dict
def build_notification(method: str, params: dict) -> dict
def parse_response(data: str) -> dict
def is_error(response: dict) -> bool
```

### 2.4 MCPStdioClient (`stdio_client.py`)

```
职责：管理一个 stdio MCP Server 子进程

  生命周期：
    1. asyncio.create_subprocess_exec() 启动子进程
    2. 发送 initialize request → 等待响应
    3. 发送 tools/list → 缓存工具列表
    4. 主循环：接收 tool_call → 发送 tools/call → 返回结果

  关键实现：
    - 通过 stdin 写 JSON-RPC request（每行一条）
    - 通过 stdout 读 JSON-RPC response（行分隔）
    - stderr 重定向到 Python logging
    - 维护 _pending: dict[int, asyncio.Future] 做请求-响应匹配
    - 自动重连（最多 3 次，指数退避）
    - 超时控制（默认 30s，可在 mcp_servers.yaml 中按 Server 配置）
```

### 2.5 MCPHTTPClient (`http_client.py`)

```
职责：通过 HTTP 连接远程 MCP Server

  与 stdio 的区别：
    - 使用 httpx.AsyncClient 发 POST 请求
    - 请求-响应模型，每个 tools/call 是一次 HTTP POST
    - 预留 SSE 推送接口（服务器→客户端通知）

  简化设计：初期只做请求-响应模式。SSE 推送预留给未来使用场景（如工具列表变更通知）。
```

### 2.6 MCPAdapter (`adapter.py`)

```
职责：MCP 工具 schema ↔ OpenAI function calling 格式转换

  1. MCP tools/list 响应 → OpenAI tools 参数：
     将 MCP 的 inputSchema (JSON Schema) 转为 function.parameters
     提取 required 字段

  2. 工具名命名空间：
     MCP 工具名加前缀 "mcp__<server_name>__<tool_name>"
     示例：filesystem Server 的 read_file → "mcp__filesystem__read_file"

  3. call_tool 路由：
     解析前缀 → 找到目标 Server → 调用原始 tool_name
```

### 2.7 配置格式 (`backend/mcp_servers.yaml`)

```yaml
servers:
  - name: filesystem
    transport: stdio
    command: npx
    args: ["-y", "@anthropic/mcp-server-filesystem", "C:\\Users\\san33"]
    timeout: 30

  - name: web-search
    transport: http
    url: http://localhost:9000/mcp
    timeout: 15
```

---

## 3. WebSocket 协议 v2

### 3.1 消息类型清单

| type | 方向 | 说明 | 关键字段 |
|------|------|------|---------|
| `message_chunk` | ← | 流式文本片段 | `content: string` |
| `thinking` | ← | AI 思考状态 | `content: string` |
| `tool_call_start` | ← | 工具开始执行 | `id: string`, `name: string`, `args: object` |
| `tool_call_result` | ← | 工具执行成功 | `id: string`, `name: string`, `result: any`, `duration_ms: int` |
| `tool_call_error` | ← | 工具执行失败 | `id: string`, `name: string`, `error: string` |
| `message_complete` | ← | 流式文本结束 | `full_content`, `partial`, `trace` |
| `done` | ← | 本轮对话彻底结束 | 无 |

### 3.2 消息顺序

同一轮对话中，消息按时间顺序发送：

```
thinking → tool_call_start → tool_call_result → thinking → message_chunk ... → message_complete → done
                                                                                    ↑ 可能在循环中重复
```

- `tool_call_start` 必在对应的 `tool_call_result` 之前
- `done` 永远是最后一个消息
- 多工具调用时，多个 `tool_call_start` 可连续出现，随后各自 `tool_call_result`

### 3.3 完整序列示例

```json
// 用户发送 "帮我看看系统内存占用最高的进程"
{"type": "thinking", "payload": {"content": "正在分析您的请求..."}}
{"type": "tool_call_start", "payload": {"id": "call_1", "name": "mcp__monitor__get_top_processes", "args": {"limit": 5}}}
{"type": "tool_call_result", "payload": {"id": "call_1", "name": "mcp__monitor__get_top_processes", "result": {"processes": [{"name":"Chrome","mem":1200}]}, "duration_ms": 1234}}
{"type": "thinking", "payload": {"content": "正在根据结果生成回复..."}}
{"type": "message_chunk", "payload": {"content": "当前占用最高的进程是 "}}
{"type": "message_chunk", "payload": {"content": "Chrome (1.2GB)..."}}
{"type": "message_complete", "payload": {"full_content": "当前占用最高的进程是 Chrome (1.2GB)...", "partial": false, "trace": [...]}}
{"type": "done", "payload": {}}
```

### 3.4 向后兼容

- 前端同时识别 `message_chunk`（v1/v2）和预留的 `text_chunk`
- `tool_call_start` 缺 `id` 时前端自动生成
- `done` 为新增类型，旧前端忽略不识别的 type

---

## 4. 后端改造

### 4.1 `agent/chat.py` — ChatSession

**改造 1：注入 MCP 能力**

```python
class ChatSession:
    def __init__(self, ..., mcp_manager=None, on_thinking=None, on_done=None):
        self._mcp_manager = mcp_manager
        self._on_thinking = on_thinking
        self._on_done = on_done
```

**改造 2：统一工具路由**

```python
async def _execute_tool(self, name: str, args: dict):
    """根据名称前缀路由到 MCP 或内置 registry"""
    if name.startswith("mcp__") and self._mcp_manager:
        return await self._mcp_manager.call_tool(name, args)
    else:
        return json.loads(await self._tool_registry.execute(name, args))
```

**改造 3：stream_with_tool_loop 增加 thinking/done**

```
执行流程：
  1. 发射 thinking("正在分析您的请求...")
  2. 调用 stream_chat_with_tools(tool_schemas)
  3. 如果模型返回 tool_calls：
     a. 每个 tool_call 发射 tool_call_start（含 id）—— 通过 on_tool_call 回调
     b. 收集所有 tool_call → asyncio.gather 并行执行
     c. 每个结果发射 tool_call_result 或 tool_call_error —— 通过 on_tool_result 回调
     d. 发射 thinking("正在根据结果生成回复...")
     e. 回到步骤 2
  4. 如果没有 tool_calls：
     - 流式输出文本（message_chunk）
     - 发射 message_complete
     - 发射 done()
```

**改造 4：工具并行执行**

当前代码在 `stream_with_tool_loop` 中是 for 循环逐个串行执行工具。改为先收集本轮所有 tool_call，再 `asyncio.gather(*tasks, return_exceptions=True)` 并行执行，大幅减少多工具调用时的等待时间。

### 4.2 `main.py` — WebSocket 处理器

**新增辅助函数：**

```python
async def _send_thinking(websocket, content: str):
    await _ws_send_safe(websocket, "thinking", {"content": content})

async def _send_done(websocket):
    await _ws_send_safe(websocket, "done", {})
```

**修改回调签名（补 id 字段）：**

```python
async def on_tool_call(name: str, args: dict, call_id: str = ""):
    await _ws_send_safe(websocket, "tool_call_start", {
        "id": call_id,
        "name": name,
        "args": args,
    })

async def on_tool_result(name: str, result: dict, call_id: str = ""):
    # 同样补 id
```

**ChatSession 构造传入 MCP：**

```python
session = ChatSession(
    client=client,
    model_name=config.model["model_name"],
    max_rounds=config.chat["max_history_rounds"],
    tool_registry=tool_registry,
    mcp_manager=app.state.mcp_manager,         # 新增
    on_tool_call=on_tool_call,
    on_tool_result=on_tool_result,
    on_thinking=lambda c: _send_thinking(websocket, c),  # 新增
    on_done=lambda: _send_done(websocket),              # 新增
)
```

**lifespan 中管理 MCP：**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有 startup 逻辑 ...
    mcp_manager = MCPManager.from_config("mcp_servers.yaml")
    await mcp_manager.connect_all()
    app.state.mcp_manager = mcp_manager
    yield
    await mcp_manager.disconnect_all()
    # ... 现有 shutdown 逻辑 ...
```

**工具合并：**

```python
mcp_tools = mcp_manager.get_all_tools() if mcp_manager else []
active_tool_schemas = tool_registry.get_schemas() + mcp_tools
# 技能限制时：
# active_tool_schemas = tool_registry.get_for_skill(skill) + mcp_tools
```

### 4.3 MCP Server 中途崩溃处理

- stdio 子进程退出 → `MCPStdioClient` 自动重连 3 次（指数退避 1s/2s/4s）
- 3 次均失败 → 标记 Server 为 `unavailable`
- 调用不可用 Server 的工具 → 返回 error result
- 不影响其他 Server 和内置工具

---

## 5. 前端改造

### 5.1 `App.jsx` — 消息处理器

**新增 `thinking` 处理：**

```javascript
case 'thinking': {
  setMessages(prev => {
    const updated = [...prev];
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].role === 'assistant' && updated[i].isStreaming) {
        updated[i] = { ...updated[i], thinking: payload.content };
        break;
      }
    }
    return updated;
  });
  break;
}
```

**新增 `done` 处理：**

```javascript
case 'done': {
  setIsStreaming(false);
  setMessages(prev => prev.map(m =>
    m.isStreaming ? { ...m, isStreaming: false, thinking: null } : m
  ));
  break;
}
```

**修改 `tool_call_start`（使用后端传来的 id）：**

```javascript
case 'tool_call_start': {
  const callId = payload.id || `${payload.name}_${Date.now()}`;
  // ... 其余类似，但 id 来源从 payload.id 取，不再前端生成
}
```

### 5.2 `ToolCallCard.jsx` — UI 升级

```
┌──────────────────────────────────────────────┐
│ 🔧 get_top_processes    ⏳ 执行中...      ▾ │  ← header（始终可见）
├──────────────────────────────────────────────┤
│ 参数: {"limit": 5}                           │  ← 展开后
│ ┌──────────────────────────────────┐         │
│ │ ████████████░░░░░░ 60%           │         │  ← 进度条（收到 progress 消息时显示）
│ └──────────────────────────────────┘         │
│ 结果: 找到 5 个进程                           │  ← 摘要
│ ▼ 查看详情                                   │
│   [{"name": "Chrome", "mem": 1200}, ...]     │  ← JSON 格式化
└──────────────────────────────────────────────┘
```

改造点：
- **图标更新**：🔧 → ⏳(running) / ✅(success) / ❌(error)，蓝色脉冲动画
- **自动折叠**：成功完成后 1.5s 自动收起，用户可手动展开
- **结果摘要**：从 result 中提取 `message` 字段作为单行摘要
- **JSON 格式化**：`JSON.stringify(result, null, 2)` + 等宽字体 + 暗色背景
- **进度条**（预留）：如果收到 `tool_call_progress` 消息则显示百分比

### 5.3 ThinkingIndicator（内嵌于 MessageBubble）

在助手气泡内工具卡片上方显示：

```jsx
{message.thinking && (
  <div className="thinking-indicator">
    <span className="thinking-dot" />  {/* CSS 呼吸动画 */}
    <span>{message.thinking}</span>
  </div>
)}
```

状态对应：

| 状态 | 图标 | 颜色 | 说明 |
|------|------|------|------|
| 思考中 | 🤔 | 灰色 | 模型正在决策，尚未调用工具 |
| 工具执行中 | ⏳ | 蓝色脉冲 | 工具正在运行 |
| 工具成功 | ✅ | 绿色 | 执行完成 |
| 工具失败 | ❌ | 红色 | 出错或超时 |
| 完成 | 无 | 默认 | `done` 后清除 |

### 5.4 多工具并行展示

`MessageBubble` 已有 `toolCalls.map(...)` 渲染多个 `ToolCallCard`。并行执行时自然纵向排列，各自独立状态。

---

## 6. 错误处理矩阵

| 场景 | 后端处理 | 前端表现 |
|------|---------|---------|
| MCP Server 启动失败 | `connect_all` 捕获，记日志，跳过该 Server | 该 Server 工具不出现在工具列表中 |
| 单个工具超时 (30s) | `asyncio.wait_for` → 捕获 `TimeoutError` → `tool_call_error` | 红色卡片 "工具执行超时" |
| 工具执行抛异常 | 捕获 → `tool_call_error` | 红色卡片 + 错误详情 |
| MCP Server 中途崩溃 | stdio 进程退出 → 自动重连 3 次 → 标记 `unavailable` | 调用该 Server 工具时返回 error |
| 工具结果 >1MB | 后端不做截断 | 默认折叠，展开用懒渲染 |
| 用户点击停止 | `request_stop()` → 取消 asyncio 任务 | `done` 到达后清理状态 |
| 多个工具同时超时 | `asyncio.gather(return_exceptions=True)` 各自处理 | 各自显示红色卡片 |
| DeepSeek 不调用工具 | 正常流式文本 | 纯文本显示，无工具卡片 |
| 工具循环死循环 | `max_tool_rounds=10` 上限 | 第 10 轮后强制文本回复 |
| WebSocket 断连 | `_ws_send_safe` 静默忽略 | 自动重连后从服务器拉历史 |

---

## 7. 开发阶段

| 阶段 | 内容 | 涉及文件 | 预估 |
|------|------|---------|------|
| **P1** | MCP 基础：`protocol.py` + `stdio_client.py` + `adapter.py` + 单测 | `backend/mcp/` 4个新文件 | 2天 |
| **P2** | MCP HTTP + `MCPManager` + `mcp_servers.yaml` 加载 + `errors.py` | `backend/mcp/` 3个新文件 | 1天 |
| **P3** | 协议对齐：补 `id`、`thinking`、`done`；工具并行执行改造 | `chat.py`, `main.py` | 1.5天 |
| **P4** | 前端：消息处理 + ThinkingIndicator + ToolCallCard 升级 + CSS | `App.jsx`, `MessageBubble.jsx`, `ToolCallCard.jsx`, `App.css` | 2天 |
| **P5** | 联调：搭建 MCP echo server 验证全链路 | 测试用 mock server | 1.5天 |
| **P6** | 边缘场景：超时、重连、大结果、崩溃恢复 | 已有文件补漏 | 1天 |

---

## 8. 测试策略

| 层级 | 测试对象 | 测试文件 | 方法 |
|------|---------|---------|------|
| 单元 | `protocol.py` JSON-RPC 编解码 | `tests/test_mcp_protocol.py` | 合法/非法消息构造 |
| 单元 | `adapter.py` schema 转换 | `tests/test_mcp_adapter.py` | MCP schema → OpenAI schema 对拍 |
| 单元 | `MCPManager` 路由 | `tests/test_mcp_manager.py` | Mock stdio client |
| 集成 | stdio 真进程通信 | `tests/test_mcp_stdio.py` | 启动 MCP echo server 验证全握手 |
| 集成 | HTTP MCP 通信 | `tests/test_mcp_http.py` | pytest-httpserver |
| 端到端 | 全链路 | 手动/自动化 | 前端发消息 → 调 MCP → 展示工具卡片 |
| 边缘 | 超时/崩溃/大结果 | 各测试文件 | 造慢 Server / 崩溃 Server |
