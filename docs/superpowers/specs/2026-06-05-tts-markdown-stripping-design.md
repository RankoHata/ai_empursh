# TTS Markdown 剥离 — 设计文档

**日期**: 2026-06-06
**状态**: 待实现

## 问题

AI 返回的响应包含 Markdown 语法（`**粗体**`、`# 标题`、`` `代码` ``、`[链接]()`、代码块等），TTS 直接逐字朗读这些语法字符，用户体验差。

## 方案

新增独立工具模块 `backend/utils/markdown.py`，提供 `strip_markdown()` 纯函数。TTS 合成前调用它将 Markdown 文本转为可读纯文本。正则实现，零依赖。

**定位**: 通用工具函数（Utility Function），非 Agent Tool。决策由代码无条件执行，无需模型参与。

**目录**:
```
backend/utils/
├── __init__.py       # 新建
└── markdown.py       # 新建，strip_markdown() 纯函数
```

## 实现

### 1. 新增 `backend/utils/markdown.py`

`strip_markdown(text: str) -> str` — 纯函数，正则剥离 Markdown 语法。

| Markdown 元素 | 输入示例 | 输出 |
|-------------|---------|------|
| 代码块 | ` ```python\ncode\n``` ` | `（此处有一段代码）` |
| 行内代码 | `` `print()` `` | `print()` |
| 标题 | `## 标题` | `标题` |
| 粗体 | `**文本**` | `文本` |
| 斜体 | `*文本*` | `文本` |
| 删除线 | `~~文本~~` | `文本` |
| 链接 | `[文本](url)` | `文本` |
| 图片 | `![alt](url)` | `[图片]` |
| 引用 | `> 文本` | `文本` |
| 无序列表 | `- 项目` | `项目` |
| 有序列表 | `1. 项目` | `项目` |
| 分隔线 | `---` | 移除 |
| 表格 | 管道符格式 | 逗号分隔内容 |
| HTML 标签 | `<br>` | 移除 |

### 2. 调用点 (`main.py`)

```python
from utils.markdown import strip_markdown

# 在 _synthesize_and_send() 中:
_tts_streams[stream_id] = strip_markdown(text)
```

### 3. 不变部分

- `tts.py` — 只负责 TTS 合成，不嵌入文本处理逻辑
- 前端 — 仍渲染 Markdown
- 笔记 — 保存原始 Markdown

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `backend/utils/__init__.py` | 新建（空文件） |
| `backend/utils/markdown.py` | 新建，`strip_markdown()` |
| `backend/main.py` | `_synthesize_and_send()` 导入并调用 |

## 风险

- **正则误匹配**: 正则可能误匹配普通文本中的 `*` 或 `_`。需注意边界处理（如 `*` 前后不能是字母）
- **非 ASCII 字符**: 中文文本中也可能出现 `**` 标记，正则应处理得当
