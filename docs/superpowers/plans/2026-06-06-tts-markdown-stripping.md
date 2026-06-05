# TTS Markdown 剥离 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TTS 合成前剥离 AI 响应中的 Markdown 语法字符，输出可读纯文本。

**Architecture:** 新增独立工具模块 `backend/utils/markdown.py`，提供 `strip_markdown()` 纯函数。`main.py` 的 `_synthesize_and_send()` 调用它处理文本后再送入 TTS 流。正则实现，零外部依赖。

**Tech Stack:** Python 3.10, re (标准库), pytest

**Spec:** `docs/superpowers/specs/2026-06-05-tts-markdown-stripping-design.md`

---

### Task 1: Create `strip_markdown()` Function

**Files:**
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/markdown.py`
- Create: `backend/tests/test_markdown.py`

- [ ] **Step 1: Create the utils package**

```bash
mkdir -p backend/utils
```

Write `backend/utils/__init__.py`:

```python
"""General-purpose utility modules."""
```

- [ ] **Step 2: Write the failing tests**

Write `backend/tests/test_markdown.py`:

```python
"""Tests for utils.markdown.strip_markdown."""
import pytest
from utils.markdown import strip_markdown


def test_strips_headers():
    assert strip_markdown("# 标题") == "标题"
    assert strip_markdown("## 二级标题") == "二级标题"
    assert strip_markdown("### 三级") == "三级"


def test_strips_bold():
    assert strip_markdown("这是 **粗体** 文字") == "这是 粗体 文字"
    assert strip_markdown("__双下划线__") == "双下划线"


def test_strips_italic():
    assert strip_markdown("这是 *斜体* 文字") == "这是 斜体 文字"
    assert strip_markdown("_下划线_") == "下划线"


def test_strips_strikethrough():
    assert strip_markdown("~~删除~~ 保留") == "删除 保留"


def test_strips_inline_code():
    assert strip_markdown("用 `print()` 输出") == "用 print() 输出"


def test_strips_code_blocks():
    text = "前面\n```python\ndef hello():\n    print('hi')\n```\n后面"
    result = strip_markdown(text)
    assert "（此处有一段代码）" in result
    assert "def hello" not in result


def test_strips_links():
    assert strip_markdown("[点击](https://example.com)") == "点击"
    assert strip_markdown("看这个 [文档](url) 链接") == "看这个 文档 链接"


def test_strips_images():
    assert strip_markdown("![alt](url)") == "[图片]"


def test_strips_blockquotes():
    assert strip_markdown("> 引用文字") == "引用文字"
    assert strip_markdown("> 第一行\n> 第二行") == "第一行\n第二行"


def test_strips_unordered_lists():
    assert strip_markdown("- 项目一") == "项目一"
    assert strip_markdown("* 星号列表") == "星号列表"


def test_strips_ordered_lists():
    assert strip_markdown("1. 第一步") == "第一步"
    assert strip_markdown("12. 第十二步") == "第十二步"


def test_strips_horizontal_rules():
    assert strip_markdown("文字\n---\n更多") == "文字\n\n更多"
    assert strip_markdown("***") == ""


def test_strips_html_tags():
    assert strip_markdown("换行<br>这里") == "换行这里"
    assert strip_markdown("<div>内容</div>") == "内容"


def test_preserves_normal_text():
    plain = "这是一段普通的中文文本，没有任何标记。"
    assert strip_markdown(plain) == plain


def test_removes_excess_newlines():
    assert strip_markdown("段落一\n\n\n\n段落二") == "段落一\n\n段落二"


def test_handles_empty_string():
    assert strip_markdown("") == ""
    assert strip_markdown("   ") == ""


def test_handles_none():
    assert strip_markdown(None) == ""
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
cd backend && python -m pytest tests/test_markdown.py -v
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'utils.markdown'`

- [ ] **Step 4: Implement `strip_markdown()`**

Write `backend/utils/markdown.py`:

```python
"""
Markdown text stripping for TTS and other plain-text consumers.

Strips Markdown syntax from a string, producing human-readable plain text.
Pure function — no external dependencies, no side effects.
"""
import re

# Code blocks: ```...``` → "（此处有一段代码）"
_CODE_BLOCK_RE = re.compile(r'```[^\n]*\n.*?\n```', re.DOTALL)

# Inline code: `code`
_INLINE_CODE_RE = re.compile(r'`([^`]+)`')

# Images: ![alt](url) → [图片]
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\([^)]+\)')

# Links: [text](url) → text
_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]+\)')

# Bold: **text** or __text__
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*|__(.+?)__')

# Italic: *text* or _text_ (but not ** or __)
_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)')

# Strikethrough: ~~text~~
_STRIKE_RE = re.compile(r'~~(.+?)~~')

# Headings: # ## ### etc at line start
_HEADING_RE = re.compile(r'^#{1,6}\s+', re.MULTILINE)

# Blockquotes: > at line start
_BLOCKQUOTE_RE = re.compile(r'^>\s?', re.MULTILINE)

# Unordered lists: - * + at line start
_UL_RE = re.compile(r'^[\-\*\+]\s+', re.MULTILINE)

# Ordered lists: 1. 2. etc at line start
_OL_RE = re.compile(r'^\d+\.\s+', re.MULTILINE)

# Horizontal rules: --- *** ___ (line containing only these)
_HR_RE = re.compile(r'^[\-\*\_]{3,}\s*$', re.MULTILINE)

# HTML tags: <...>
_HTML_RE = re.compile(r'<[^>]+>')

# Table formatting: strip leading/trailing | and separator rows
_TABLE_SEP_RE = re.compile(r'^[\|\s\-:]+$', re.MULTILINE)
_TABLE_PIPE_RE = re.compile(r'\s*\|\s*')

# Excess blank lines: 3+ → 2
_EXCESS_NL_RE = re.compile(r'\n{3,}')


def strip_markdown(text: str | None) -> str:
    """Strip Markdown syntax, returning human-readable plain text.

    Args:
        text: Markdown-formatted text, or None.

    Returns:
        Plain text with Markdown syntax removed.
    """
    if text is None:
        return ""

    # 1. Code blocks — replace with hint
    text = _CODE_BLOCK_RE.sub('（此处有一段代码）', text)

    # 2. Inline code — strip backticks
    text = _INLINE_CODE_RE.sub(r'\1', text)

    # 3. Images — replace with placeholder
    text = _IMAGE_RE.sub('[图片]', text)

    # 4. Links — keep text
    text = _LINK_RE.sub(r'\1', text)

    # 5. Bold
    text = _BOLD_RE.sub(r'\1\2', text)

    # 6. Italic (after bold to avoid ** conflicts)
    text = _ITALIC_RE.sub(r'\1\2', text)

    # 7. Strikethrough
    text = _STRIKE_RE.sub(r'\1', text)

    # 8. HTML tags
    text = _HTML_RE.sub('', text)

    # 9. Headings — strip # markers
    text = _HEADING_RE.sub('', text)

    # 10. Blockquotes — strip > markers
    text = _BLOCKQUOTE_RE.sub('', text)

    # 11. Horizontal rules — remove
    text = _HR_RE.sub('', text)

    # 12. Table separators (|---|---|)
    text = _TABLE_SEP_RE.sub('', text)

    # 13. Table pipes → comma
    text = _TABLE_PIPE_RE.sub('，', text)

    # 14. Ordered lists
    text = _OL_RE.sub('', text)

    # 15. Unordered lists (after HR to avoid --- conflicts)
    text = _UL_RE.sub('', text)

    # 16. Collapse 3+ blank lines → 2
    text = _EXCESS_NL_RE.sub('\n\n', text)

    # 17. Trim leading/trailing whitespace
    text = text.strip()

    return text
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_markdown.py -v
```

Expected: All 18 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/utils/__init__.py backend/utils/markdown.py backend/tests/test_markdown.py
git commit -m "feat: add strip_markdown() utility for TTS plain-text conversion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Wire into TTS Pipeline

**Files:**
- Modify: `backend/main.py` (the `_synthesize_and_send` function, around line 282)

- [ ] **Step 1: Add import**

At the top of `backend/main.py`, after the existing voice imports (around line 33):

```python
from utils.markdown import strip_markdown
```

- [ ] **Step 2: Apply stripping in `_synthesize_and_send()`**

In the `_synthesize_and_send()` function, change line 282 from:

```python
_tts_streams[stream_id] = text
```

To:

```python
_tts_streams[stream_id] = strip_markdown(text)
```

- [ ] **Step 3: Verify backend starts**

```bash
cd backend && timeout 3 python main.py 2>&1 || true
```

Expected: No import errors, server starts normally.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: strip markdown from TTS text before synthesis

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: End-to-End Verification

- [ ] **Step 1: Start backend and frontend**

```bash
# Terminal 1
cd backend && python main.py

# Terminal 2
cd electron-app && npm start
```

- [ ] **Step 2: Enable TTS and send a Markdown-rich message**

Ensure TTS toggle is ON in status bar, then send:

```
请用markdown格式介绍Python，包含**粗体**、`代码`、列表和>引用。
```

- [ ] **Step 3: Verify TTS output**

Listen to the audio — should hear natural speech WITHOUT:
- [ ] Star characters `**` — should not hear "星号星号"
- [ ] Hash marks `#` — should not hear "井号"
- [ ] Backticks — should not hear "反引号"
- [ ] Code block content — should hear "此处有一段代码" instead
- [ ] Link URLs — should hear only link text
- [ ] Blockquote `>` — should not hear "大于号"
- [ ] List markers `-`, `1.` — should not be read
