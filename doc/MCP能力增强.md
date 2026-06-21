# 桌面助理 MCP 调用交互体验重构需求文档

> 目标：将现有流式对话升级为 **Claude Code 风格** 的非阻塞 MCP 工具调用体验，包括实时状态反馈、并行执行、结果可追溯。

---

## 1. 背景与现状

### 1.1 当前架构
- 后端：Python FastAPI + WebSocket
- 前端：Electron + React
- 对话方式：用户输入 → 后端调用 DeepSeek API（流式）→ 逐字推送文本 → 前端追加显示
- 无任何工具调用可视化反馈

### 1.2 待引入能力
- MCP (Model Context Protocol) 作为工具调用协议
- 后端作为 MCP Client，连接外部 MCP Server（如系统监控、文件操作等）
- AI 自主决策调用工具，用户无需主动触发斜杠命令

### 1.3 痛点
- 现有流式输出无法展示“AI 正在调用工具”的过程
- 工具执行耗时会导致前端无任何反馈，体验差
- 用户不知道 AI 为何停顿，容易误以为卡死

---

## 2. 需求目标

1. **非阻塞工具调用**：MCP 执行不影响对话流，后端异步处理，前端实时更新状态。
2. **透明化执行过程**：前端清晰展示每一步的工具名称、参数、执行结果（可折叠）。
3. **多工具并行/串行支持**：AI 一次可发起多个工具调用，后端支持并行执行并分别反馈。
4. **状态提示**：提供“思考中”、“执行中”、“完成”等状态标识。
5. **兼容现有流式文本**：工具调用前后文本片段正常流式输出。

---

## 3. 整体交互流程（Claude Code 风格）

### 3.1 用户视角流程

```
用户发送消息 "帮我看看系统内存占用最高的进程"
    ↓
界面显示 "🤔 思考中..."
    ↓
界面显示 "🔧 正在调用工具: get_top_processes (参数: {limit:5})"
    ↓
（等待约 1~2 秒）
    ↓
界面显示 "✅ 工具执行完成: get_top_processes" 并展示结果摘要（或折叠详情）
    ↓
AI 根据结果生成回复，流式逐字输出：
    "当前内存占用最高的进程是 Chrome (1.2GB) 和 VS Code (850MB)..."
    ↓
对话结束
```

### 3.2 多工具调用场景

```
用户发送 "清理临时文件并检查磁盘空间"
    ↓
AI 自主决策调用两个工具：
    - clean_temp_files()
    - get_disk_usage()
    ↓
界面显示两个工具并行执行状态（可同时显示多条进度）
    ↓
两个均完成后，AI 综合结果生成回复
```

---

## 4. WebSocket 消息协议设计

前端与后端通过 WebSocket 通信，消息统一为 JSON 格式，包含 `type` 字段区分消息种类。

### 4.1 消息类型清单

| type | 方向 | 说明 | 字段 |
|------|------|------|------|
| `text_chunk` | 后端 → 前端 | 流式文本片段（AI 回复） | `content: string` |
| `thinking` | 后端 → 前端 | 状态提示（非最终回复） | `content: string` |
| `tool_call_start` | 后端 → 前端 | 开始执行某个工具 | `tool: string`, `args: object`, `id: string` |
| `tool_call_progress` | 后端 → 前端 | （可选）工具执行进度 | `id: string`, `progress: number`, `message: string` |
| `tool_call_result` | 后端 → 前端 | 工具执行完成 | `id: string`, `tool: string`, `result: any`, `success: boolean`, `error?: string` |
| `tool_call_error` | 后端 → 前端 | 工具执行失败 | `id: string`, `tool: string`, `error: string` |
| `done` | 后端 → 前端 | 本轮对话结束 | 无 |

### 4.2 消息顺序保证
- 同一轮对话中，所有消息按时间顺序发送。
- `tool_call_start` 必须在对应的 `tool_call_result` 之前。
- `done` 是最后一个消息。

### 4.3 示例消息序列

```json
{"type": "thinking", "content": "正在分析您的请求..."}
{"type": "tool_call_start", "id": "call_1", "tool": "get_top_processes", "args": {"limit": 5}}
{"type": "tool_call_result", "id": "call_1", "tool": "get_top_processes", "success": true, "result": {"processes": [{"name":"Chrome","mem":1200}]}}
{"type": "text_chunk", "content": "当前占用最高的进程是 "}
{"type": "text_chunk", "content": "Chrome"}
{"type": "text_chunk", "content": "..."}
{"type": "done"}
```

---

## 5. 后端改造要点

### 5.1 MCP Client 管理器
- 新建 `backend/mcp/client.py`，负责连接外部 MCP Server（通过 stdio）。
- 支持多 Server 同时连接，统一管理工具列表。
- 提供 `call_tool(server, tool_name, args)` 异步方法。

### 5.2 对话引擎改造（核心）
- 文件位置：`backend/agent/chat.py`
- 改造 `chat_stream` 函数，接收 WebSocket 实例，支持推送消息。

**处理逻辑伪代码：**

```python
async def chat_stream(user_msg, history, ws, mcp_manager):
    # 1. 合并所有 MCP 工具，转换为 OpenAI tools 格式
    openai_tools = build_openai_tools(mcp_manager.get_all_tools())
    
    # 2. 首次请求 DeepSeek（流式）
    response = await deepseek_api.chat(
        messages=history + [{"role": "user", "content": user_msg}],
        tools=openai_tools,
        stream=True
    )
    
    # 3. 初始化缓冲
    tool_calls_buffer = {}  # index -> {name, arguments}
    text_buffer = ""
    
    # 4. 处理流式响应
    async for chunk in response:
        delta = chunk.choices[0].delta
        
        # 文本片段
        if delta.content:
            text_buffer += delta.content
            await ws.send_json({"type": "text_chunk", "content": delta.content})
        
        # tool_calls 累积
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = {"id": tc.id, "name": "", "arguments": ""}
                if tc.function.name:
                    tool_calls_buffer[idx]["name"] = tc.function.name
                if tc.function.arguments:
                    tool_calls_buffer[idx]["arguments"] += tc.function.arguments
    
    # 5. 如果有工具调用，执行（非阻塞）
    if tool_calls_buffer:
        # 通知开始
        for idx, tc in tool_calls_buffer.items():
            await ws.send_json({
                "type": "tool_call_start",
                "id": tc["id"],
                "tool": tc["name"],
                "args": json.loads(tc["arguments"])
            })
        
        # 并行执行
        tasks = []
        for tc in tool_calls_buffer.values():
            tasks.append(
                execute_mcp_tool(mcp_manager, tc["name"], json.loads(tc["arguments"]))
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 发送结果
        for idx, (tc, result) in enumerate(zip(tool_calls_buffer.values(), results)):
            if isinstance(result, Exception):
                await ws.send_json({
                    "type": "tool_call_error",
                    "id": tc["id"],
                    "tool": tc["name"],
                    "error": str(result)
                })
            else:
                await ws.send_json({
                    "type": "tool_call_result",
                    "id": tc["id"],
                    "tool": tc["name"],
                    "success": True,
                    "result": result
                })
        
        # 6. 将工具结果回传 DeepSeek，获取最终回复
        # 构造 messages 包含 assistant 的 tool_calls 和 tool 角色消息
        final_messages = history + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": None, "tool_calls": list(tool_calls_buffer.values())}
        ]
        for tc, result in zip(tool_calls_buffer.values(), results):
            final_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result if not isinstance(result, Exception) else {"error": str(result)})
            })
        
        # 再次流式请求
        final_response = await deepseek_api.chat(messages=final_messages, stream=True)
        async for chunk in final_response:
            delta = chunk.choices[0].delta
            if delta.content:
                await ws.send_json({"type": "text_chunk", "content": delta.content})
    
    # 7. 结束
    await ws.send_json({"type": "done"})
```

### 5.3 超时与错误处理
- 每个 MCP 调用设置超时（如 30 秒），超时抛出 `TimeoutError`。
- 工具执行异常需捕获并发送 `tool_call_error`，不影响后续工具和最终回复。
- 后端需记录完整调用日志便于调试。

---

## 6. 前端改造要点

### 6.1 对话消息数据结构扩展

为每条对话消息增加 `toolCalls` 子条目，用于存储工具调用记录。

```typescript
interface ToolCall {
  id: string;
  tool: string;
  args: any;
  status: 'running' | 'success' | 'error';
  result?: any;
  error?: string;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;          // 最终显示文本
  toolCalls?: ToolCall[];   // 本轮关联的工具调用
  isStreaming?: boolean;
}
```

### 6.2 UI 组件设计

#### a) 对话气泡内布局

```
┌─────────────────────────────────────────┐
│ 🤖 AI 助手                               │
│                                         │
│  <思考状态显示>                          │
│                                         │
│  ┌─ 工具调用卡片 ───────────────────┐   │
│  │ 🔧 正在执行: get_top_processes   │   │
│  │ 参数: { limit: 5 }               │   │
│  │ [进度条] ██████░░░░ 60%          │   │
│  └──────────────────────────────────┘   │
│                                         │
│  当前占用最高的进程是 Chrome (1.2GB)... │
│                                         │
│  ┌─ 工具结果（折叠）────────────────┐   │
│  │ ✅ get_top_processes 完成        │   │
│  │ ▼ 查看详情                       │   │
│  │   [JSON 格式化展示]              │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

#### b) 状态标识

| 状态 | 图标 | 颜色 |
|------|------|------|
| 思考中 | 🤔 | 灰色 |
| 工具执行中 | 🔧 | 蓝色（动画旋转） |
| 工具成功 | ✅ | 绿色 |
| 工具失败 | ❌ | 红色 |
| 完成 | 无 | 默认 |

#### c) 工具调用卡片（可折叠）

- 执行中显示动态 loading 动画。
- 执行后自动收起，显示摘要（如“查找到 5 个进程”）。
- 用户可点击展开查看完整 JSON 结果。
- 错误时显示红色错误信息。

#### d) 多工具并行

- 同一对话气泡内可同时显示多个工具卡片（纵向排列）。
- 每个卡片独立状态，互不影响。

### 6.3 WebSocket 消息处理器

```typescript
// 伪代码
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  const currentMsg = getCurrentAssistantMessage();
  
  switch (msg.type) {
    case 'thinking':
      setStatus(msg.content);
      break;
      
    case 'tool_call_start':
      currentMsg.toolCalls.push({
        id: msg.id,
        tool: msg.tool,
        args: msg.args,
        status: 'running'
      });
      renderToolCard(msg.id, 'running');
      break;
      
    case 'tool_call_result':
      const tc = currentMsg.toolCalls.find(t => t.id === msg.id);
      tc.status = 'success';
      tc.result = msg.result;
      updateToolCard(msg.id, 'success', msg.result);
      break;
      
    case 'tool_call_error':
      const tc2 = currentMsg.toolCalls.find(t => t.id === msg.id);
      tc2.status = 'error';
      tc2.error = msg.error;
      updateToolCard(msg.id, 'error', msg.error);
      break;
      
    case 'text_chunk':
      currentMsg.content += msg.content;
      appendTextToBubble(msg.content);
      break;
      
    case 'done':
      currentMsg.isStreaming = false;
      enableInput();
      break;
  }
};
```

### 6.4 性能考虑
- 工具结果 JSON 可能很大（如进程列表），前端应使用虚拟滚动或懒加载。
- 结果详情默认折叠，避免 DOM 节点过多。

---

## 7. 状态流转图（前端视角）

```
[用户输入] → 创建空消息气泡（assistant，isStreaming=true）
    ↓
收到 thinking → 显示提示
    ↓
收到 tool_call_start → 添加工具卡片（状态 running）
    ↓
收到 tool_call_result / error → 更新卡片状态
    ↓
（可能多个工具交替）
    ↓
收到 text_chunk → 追加内容到气泡
    ↓
收到 done → 标记 isStreaming=false，启用输入
```

---

## 8. 非功能性需求

| 项目 | 要求 |
|------|------|
| 响应性 | 工具调用开始后，前端必须在 100ms 内收到 `tool_call_start` 消息并更新 UI |
| 超时 | 单个 MCP 工具调用超时 30 秒，超时后发送 `tool_call_error` |
| 并发 | 后端支持同时处理最多 10 个并行工具调用（asyncio.gather） |
| 错误隔离 | 单个工具失败不影响其他工具执行，也不影响最终 AI 回复 |
| 日志 | 后端记录每次工具调用的入参、耗时、出参（脱敏后） |
| 兼容性 | 对话历史（history）需包含 tool_calls 和 tool 角色消息，以便恢复上下文 |

---

## 9. 与现有 Skill（斜杠命令）的关系

- **Skill**（如 `/整理`）保留为快捷入口，由用户主动触发，执行固定流程。
- **MCP 工具调用** 由 AI 自主决策，无缝融入对话。
- 两者互不干扰，共用同一个对话消息历史存储。

---

## 10. 测试用例

| 场景 | 预期结果 |
|------|----------|
| 单工具调用（成功） | 显示 start → result → 最终回复 |
| 单工具调用（超时） | 显示 start → error（超时），AI 仍能生成回复（告知用户超时） |
| 多工具并行（全部成功） | 同时显示多个 start，各自更新 result，最终回复综合结果 |
| 多工具（部分失败） | 失败工具显示 error，成功工具正常，AI 回复中可提及失败信息 |
| 无工具调用（纯对话） | 直接流式输出文本，无工具卡片 |
| 工具结果超大（>1MB） | 前端不卡顿，结果折叠，用户点击才展开 |

---

## 11. 开发阶段划分

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| Phase 1 | 后端：MCP Client 基础框架 + 连接管理 | 2 天 |
| Phase 2 | 后端：对话引擎改造（支持 tool_calls 处理 + 消息推送） | 3 天 |
| Phase 3 | 前端：消息类型扩展 + 工具卡片 UI 组件 | 2 天 |
| Phase 4 | 前端：WebSocket 消息处理器集成 + 状态管理 | 2 天 |
| Phase 5 | 联调测试 + 错误处理完善 | 2 天 |
| Phase 6 | 性能优化 + 边缘场景修复 | 1 天 |

---

## 12. 附录

### A. 参考消息格式（OpenAI API）

DeepSeek 返回的流式 chunk 中 `tool_calls` 结构示例：

```json
{
  "choices": [{
    "delta": {
      "tool_calls": [{
        "index": 0,
        "id": "call_abc123",
        "function": {
          "name": "get_top_processes",
          "arguments": "{\"limit\":5}"
        }
      }]
    }
  }]
}
```

### B. 前端状态管理建议

使用 React Context 或 Zustand 管理当前对话会话，每个消息对象需包含 `toolCalls` 数组和 `content` 字符串。

### C. 安全提示

- 后端应对 MCP 工具调用的参数进行白名单校验（尤其是路径、命令等敏感参数）。
- 限制 MCP Server 可访问的文件系统路径，防止越权。

---

**文档版本**：v1.0  
**最后更新**：2026-06-21