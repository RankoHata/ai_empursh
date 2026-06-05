# TTS Markdown 剥离 — 设计文档

**日期**: 2026-06-05
**状态**: 待实现

## 问题

AI 返回的响应包含 Markdown 语法（`**粗体**`、`# 标题`、`` `代码` ``、`[链接]()`、代码块等），TTS 直接逐字朗读这些语法字符，用户体验差。

## 方案

在 `backend/voice/tts.py` 中添加 `strip_markdown()` 函数，TTS 合成前剥离 Markdown 语法，保留可读纯文本。使用正则实现，不引入新依赖。

## 实现

### 1. 新增 `strip_markdown()` 函数 (`tts.py`)

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

在 `_synthesize_and_send()` 中，文本注册到流之前应用剥离：

```python
# 原来:
_tts_streams[stream_id] = text

# 改为:
_tts_streams[stream_id] = voice_tts.strip_markdown(text)
```

### 3. 不变部分

- `stream_synthesize()` — 只负责流式传输
- 前端消息气泡 — 仍渲染 Markdown
- 笔记保存 — 保存原始 Markdown
- `synthesize()` / `synthesize_sync()` — 调用者自行决定是否剥离

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `backend/voice/tts.py` | 新增 `strip_markdown()` 函数 |
| `backend/main.py` | `_synthesize_and_send()` 一行改动 |

## 风险

- **正则误匹配**: 正则可能误匹配普通文本中的 `*` 或 `_`。需注意边界处理（如 `*` 前后不能是字母）
- **非 ASCII 字符**: 中文文本中也可能出现 `**` 标记，正则应处理得当
