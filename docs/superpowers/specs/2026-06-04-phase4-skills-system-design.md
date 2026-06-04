# 阶段 4：技能系统与材料整理 — 设计文档

**日期**：2026-06-04
**来源**：《AI 桌面拟人助理 - 项目需求规格说明书》第 9 章 阶段 4
**状态**：已确认

---

## 1. 目标

实现可扩展的技能系统，支持 `.md` 格式技能文件加载和 `/整理` 命令触发的材料整理功能。

---

## 2. 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| 技能格式 | Claude Code `.md` (YAML frontmatter + Markdown) | 行业通用，用户熟悉 |
| 架构 | 内置 Tools（非 MCP） | 阶段 4 暂不引入 MCP，阶段 5+ 考虑 |
| 路由 | `agent/skills.py` 启动时加载，命令前缀匹配 | 简单可靠 |

---

## 3. 技能文件格式

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

# 材料整理助手

你是材料整理助手...
```

---

## 4. 核心文件

```
backend/
├── skills/
│   └── material_organizer.md       # 材料整理技能
├── agent/
│   └── skills.py                    # 技能加载器
│
electron-app/src/renderer/
└── components/
    └── MarkdownPreview.jsx          # Markdown 预览弹窗
```

---

## 5. WebSocket 新增消息

| 方向 | type | payload | 说明 |
|------|------|---------|------|
| 后端→前端 | `markdown_preview` | `{"content":"...", "suggested_filename":"..."}` | 生成的 Markdown |
| 前端→后端 | `save_file` | `{"content":"...", "filename":"..."}` | 确认保存文件 |
| 后端→前端 | `file_saved` | `{"file_path":"..."}` | 保存成功 |

---

## 6. 标签智能匹配流程

1. 用户输入 `/整理 #标签` 时，提取 `#` 后的标签名
2. 与数据库中所有标签进行精确匹配 → 命中则直接使用
3. 模糊匹配（子串）→ 若唯一则使用，若多个则列出选项询问用户
4. 用户回复序号或标签名确认 → 继续执行
5. 命令中包含 `不询问` → 跳过确认，自动选第一个匹配

---

## 7. 验收标准

1. 在 `skills/` 目录新增 `.md` 文件 → 重启后自动加载
2. 输入 `/整理` → 自动检索笔记 → LLM 生成 Markdown → 预览弹窗
3. 输入 `/整理 #标签` → 过滤对应标签笔记
4. 标签模糊时列出选项 → 用户确认后继续
5. `/整理 不询问` → 跳过确认，自动执行

---

## 8. 实现过程中的 Bug 与修复

| # | 问题 | 原因 | 修复 | 提交 |
|---|------|------|------|------|
| 1 | 标签匹配效率低 | 每次发送全量笔记给 LLM，浪费 token | 新增 `_extract_tags()` + `_resolve_tags()` 解析 #tag 并 DB 匹配，只发送相关笔记 | `1a06ebb` |
| 2 | 模糊标签无法确认 | 用户输入 `#工` 匹配到多个标签时无法选择 | 新增确认流程：列出选项 → 用户回复序号/标签名 → 继续执行 | `1a06ebb` |
| 3 | 模型文件 138MB 被误提交 | `git add backend/` 时包含 models/ 目录 | `git filter-branch` 重写历史 + `.gitignore` 排除 `backend/models/` `backend/temp/` | `6e3c176` |
| 4 | Skill/MCP 概念混淆 | 最初想用 MCP 协议但用户想要内置 Tools | 保留内置 Tools，MCP 延后到阶段 5+ | — |

### 经验教训

- 技能文件用 Claude Code `.md` 格式，YAML frontmatter 定义元数据，Markdown 正文为 system prompt
- 标签匹配优先精确，模糊时主动询问用户而不是自动选择
- 推送前必须检查大文件/敏感文件是否在 git 历史中
