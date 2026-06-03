# 阶段 2：笔记系统 — 设计文档

**日期**：2026-06-04
**来源**：《AI 桌面拟人助理 - 项目需求规格说明书》第 9 章 阶段 2
**状态**：设计中 → 待确认

---

## 1. 目标

为桌面 AI 助理添加笔记记录与检索功能。用户可以：
- 通过指令或右键将聊天内容保存为笔记
- 在独立笔记面板中搜索、筛选、浏览笔记
- 删除笔记、导出选中笔记为 Markdown 文件

**架构决策**：笔记功能作为内置 Python 工具实现（非 MCP 子进程），数据库直接在 FastAPI 后端进程中操作。

---

## 2. 技术选型

| 层 | 选择 | 理由 |
|---|------|------|
| 数据库 | SQLite + FTS5 | 规格书定义，零配置，全文搜索 |
| 笔记后端 | Python 内置模块 `db/notes.py` | 简单直接，无需 MCP 协议开销 |
| 前端布局 | 标签页切换 (聊天/笔记) | App.jsx 中加 TabBar，空间充足 |
| 导出格式 | Markdown (YAML front matter) | 规格书定义 |

---

## 3. 项目结构（新增/修改）

```
backend/
├── main.py                       # [修改] WebSocket 路由中增加 notes 消息处理
├── db/
│   ├── __init__.py                # [新增]
│   ├── init_db.py                 # [新增] 建表 + FTS + 触发器
│   └── notes.py                   # [新增] 笔记 CRUD + 搜索 + 导出工具

electron-app/src/renderer/
├── App.jsx                        # [修改] 加 Tab 切换 (tab: "chat" | "notes")
├── App.css                        # [修改] 加 Tab 样式
├── components/
│   ├── TabBar.jsx                 # [新增] 顶部标签栏
│   ├── ChatPanel.jsx              # [修改] 消息右键菜单
│   ├── NotesPanel.jsx             # [新增] 笔记列表 + 搜索 + 导出
│   └── NoteCard.jsx               # [新增] 单条笔记卡片
```

---

## 4. 数据库设计

直接使用规格书 §7 定义的表结构：

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

含 3 个触发器（INSERT / DELETE / UPDATE）同步 FTS 索引。

---

## 5. 笔记工具函数 (db/notes.py)

| 函数 | 签名 | 说明 |
|------|------|------|
| `add_note` | `(content: str, tags: list[str]) → dict` | 新增笔记，返回完整 note 对象 |
| `search_notes` | `(query: str, tags: list[str]) → list[dict]` | FTS5 全文搜索 + 标签筛选 |
| `get_all_notes` | `() → list[dict]` | 获取所有笔记（按时间倒序） |
| `delete_note` | `(note_id: int) → bool` | 删除笔记（级联删除关联标签） |
| `export_notes` | `(note_ids: list[int], output_dir: str) → str` | 导出为 Markdown 文件，返回文件路径 |

---

## 6. WebSocket 协议（阶段 2 新增）

### 前端 → 后端

| type | payload | 说明 |
|------|---------|------|
| `add_note` | `{"content":"...", "tags":["标签"]}` | 添加笔记 |
| `get_notes` | `{}` | 获取全部笔记列表 |
| `search_notes` | `{"query":"...", "tags":[]}` | 搜索笔记 |
| `delete_note` | `{"note_id": 1}` | 删除笔记 |
| `export_notes` | `{"note_ids":[1,2]}` | 导出选中的笔记 |

### 后端 → 前端

| type | payload | 说明 |
|------|---------|------|
| `notes_list` | `{"notes": [...]}` | 笔记列表 |
| `note_saved` | `{"note": {...}}` | 单条笔记保存成功 |
| `note_deleted` | `{"note_id": 1}` | 删除确认 |
| `search_results` | `{"results": [...]}` | 搜索结果（复用 notes_list 同样的结构） |
| `notes_exported` | `{"file_path": "..."}` | 导出文件路径 |

---

## 7. 前端组件

### 7.1 App.jsx（修改）

```
新增状态：
├── activeTab: "chat" | "notes"

渲染：
├── <TabBar activeTab, onTabChange />
├── <StatusBar status />
├── {activeTab === "chat" ? <ChatPanel ... /> : <NotesPanel ... />}
```

### 7.2 TabBar.jsx（新增）

两个标签按钮：`[💬 聊天]` `[📝 笔记]`，当前激活的加高亮样式。

### 7.3 NotesPanel.jsx（新增）

```
├── 顶部工具栏：搜索框 + 标签筛选下拉
├── 笔记列表（可滚动）
│   └── <NoteCard /> × N
├── 底部操作栏：全选复选框 + "导出选中"按钮
```

### 7.4 NoteCard.jsx（新增）

显示：笔记内容（截断预览）、标签列表、创建时间、删除按钮。带复选框用于多选导出。

### 7.5 ChatPanel 右键菜单（修改）

在 MessageBubble 上 `onContextMenu` → 弹出原生菜单项"保存为笔记"→ 弹出简单 prompt 输入标签 → `send("add_note", {content, tags})`。

---

## 8. 导出格式

```markdown
---
tags: [标签1, 标签2]
date: 2026-06-04
---

笔记正文内容...
```

---

## 9. 不在阶段 2 范围

- 笔记编辑（update）
- 材料整理/Markdown 生成（阶段 4）
- MCP 协议封装
- 导出目录选择器（硬编码到桌面或使用默认目录）

---

## 10. 验收标准

1. 在聊天中右键消息 → "保存为笔记"→ 输入标签 → 笔记出现在笔记面板中
2. 切换到笔记标签页，看到所有已保存笔记
3. 在搜索框中输入关键字，笔记列表实时过滤
4. 按标签筛选笔记
5. 选中一条或多条笔记 → 导出 → 本地生成 `.md` 文件
6. 删除笔记后列表更新

---

## 11. 实现过程中的 Bug 与修复

| # | 问题 | 原因 | 修复 | 提交 |
|---|------|------|------|------|
| 1 | 右键消息无反应 | `display: contents` 使包裹 div 无法接收鼠标事件；React `onContextMenu` 在 Electron 中不可靠 | 改用原生 `addEventListener('contextmenu')` + `closest('[data-msg-id]')` 事件委托 | `6804579` |
| 2 | `prompt() is and will not be supported` | Electron 渲染进程不支持 `window.prompt()` | 替换为自定义 React 弹窗（遮罩 + 内容预览 + 标签输入 + 保存/取消按钮） | `c60ade5` |
| 3 | 右键菜单点击"保存为笔记"后菜单先关闭导致点击无效 | 全局 click 监听器在 onClick 之前触发 | 用 `setTimeout(0)` 延迟绑定 click 关闭监听器 | `6804579` |

### 经验教训

- Electron 渲染进程中避免使用 `window.prompt()`、`window.alert()`、`window.confirm()` 等原生弹窗 API，用 React 组件替代
- 右键菜单优先使用原生 DOM 事件 + 事件委托，而非 React 合成事件
- 事件委托需要目标元素上有 data 属性（如 `data-msg-id`）来定位数据
