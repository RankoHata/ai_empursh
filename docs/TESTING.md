# 测试文档

## 快速开始

```bash
# 后端全部测试 (200 tests)
cd backend
python -m pytest tests/ -v

# 后端快速 (仅结果)
python -m pytest tests/ -q

# 单个测试文件
python -m pytest tests/test_integration_ws.py -v

# 前端全部测试 (34 tests)
cd electron-app
npm test

# 一次性全跑
cd backend && python -m pytest tests/ -q && cd ../electron-app && npx vitest run
```

## 测试总览

| 层 | 框架 | 文件数 | 用例数 | 类型 |
|----|------|--------|--------|------|
| 后端 | pytest + pytest-asyncio | 20 | 200 | 单元/集成/WS |
| 前端 | vitest + jsdom + RTL | 5 | 34 | Hook/组件 |
| **合计** | | **25** | **234** | |

---

## 后端测试清单

### 单元测试

| 文件 | 用例 | 覆盖 |
|------|------|------|
| `test_tool_registry.py` | 15 | 注册/覆盖/卸载/schema生成/执行/超时/异常/ws_sender注入/默认注册表 |
| `test_personality_manager.py` | 14 | Jinja2模板渲染(6)/情绪标签提取(7)/reseed |
| `test_chat.py` | 13 | 历史管理/trimming/stop信号/trace/thinking回调/load_history |
| `test_prompt_pipeline.py` | 15 | Pipeline组装/条件开关/段跳过/错误优雅降级/PromptContext默认值 |
| `test_time_tools.py` | 7 | get_current_time(readable/iso/unix)/默认格式/工具定义/注册表集成 |
| `test_markdown.py` | 19 | strip_markdown 全语法剥离 |
| `test_markdown_parser.py` | 10 | Markdown 解析/front matter |
| `test_mcp.py` | 22 | MCP协议/stdio客户端/管理器/echo工具调用 |
| `test_guard.py` | 10 | 秘密笔记脱敏/LLM输出清理 |

### 集成测试

| 文件 | 用例 | 覆盖 |
|------|------|------|
| `test_public_notes.py` | 14 | 笔记新增/搜索/标签/删除 |
| `test_secret_notes.py` | 8 | 秘密笔记增删搜/物理隔离 |
| `test_conversation_service.py` | 5 | **SQLite真实DB** — 对话保存/轮次/列表/删除/加载历史 |
| `test_routers_notes.py` | 14 | Mock WS — 公开+秘密笔记 CRUD |
| `test_routers_personalities.py` | 12 | Mock WS — 人格列表/切换/CRUD/reseed |
| `test_routers_conversations.py` | 7 | Mock WS — 对话CRUD/加载/删除重置 |
| `test_integration_ws.py` | 12 | **FastAPI TestClient + 真实WS** — 全链路 |

### 集成测试层级说明

```
Unit (mock)           → 函数级，不依赖外部
Mock WS (mock db)     → 路由级，mock DB 但走真实 handler
SQLite 集成 (真实DB)  → 服务级，真实 SQLite 但独立连接
FastAPI WS (全栈)     → 端到端，真实 app + WebSocket + DB
```

---

## 前端测试清单

| 文件 | 用例 | 覆盖 |
|------|------|------|
| `useChat.test.js` | 13 | 消息状态/发送/停止/chunk拼接/complate清除thinking/tool_call生命周期/删除 |
| `useNotes.test.js` | 8 | 笔记状态/保存弹窗/秘密笔记/搜索通知/新建笔记 |
| `ToolCallCard.test.jsx` | 5 | running/completed/error状态渲染/mcp__前缀剥离/展开折叠 |
| `Avatar.test.jsx` | 6 | 加载态/model prop/skelUrl/atlasUrl/state/fallback |
| `avatar-urls.test.js` | 2 | 资产URL静态验证(非undefined) |

---

## 运行方式详解

### 后端

```bash
# 全部
cd backend && python -m pytest tests/ -v

# 指定目录
python -m pytest tests/ -k "test_integration" -v

# 单个文件
python -m pytest tests/test_integration_ws.py -v

# 单个测试类
python -m pytest tests/test_integration_ws.py::TestProtocolFormat -v

# 单个用例
python -m pytest tests/test_integration_ws.py::TestProtocolFormat::test_conversation_created_payload_is_flat_object -v
```

### 前端

```bash
# 全部
cd electron-app && npm test

# watch 模式 (开发时用)
npm run test:watch
```

---

## 依赖

| 包 | 用途 |
|----|------|
| pytest >= 8.0 | 后端测试框架 |
| pytest-asyncio >= 0.24 | 异步测试支持 |
| vitest 4.x | 前端测试框架 |
| @testing-library/react | React 组件测试 |
| @testing-library/jest-dom | DOM 断言扩展 |
| jsdom | 浏览器环境模拟 |

## 编写新测试的约定

1. **文件名**: `test_<模块>.py` (后端) / `<模块>.test.js` (前端)
2. **类名**: `Test<功能描述>` (PascalCase)
3. **方法名**: `test_<场景描述>` (snake_case)
4. **后端 fixture**: 共享的放 `conftest.py`，专属的放测试文件内
5. **前端 mock**: 用 `vi.mock()` / `vi.fn()`，避免真实副作用
6. **关键原则**: mock 测试测逻辑，集成测试测协议
