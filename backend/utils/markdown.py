"""
Markdown text stripping for TTS and other plain-text consumers.

Strips Markdown syntax from a string, producing human-readable plain text.
Pure function -- no external dependencies, no side effects.
"""
import re
from typing import Optional

# Code blocks: ```...``` -> "（此处有一段代码）"
_CODE_BLOCK_RE = re.compile(r'```[^\n]*\n.*?\n```', re.DOTALL)

# Inline code: `code`
_INLINE_CODE_RE = re.compile(r'`([^`]+)`')

# Images: ![alt](url) -> [图片]
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\([^)]+\)')

# Links: [text](url) -> text
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

# Table formatting: strip separator rows and pipes
_TABLE_SEP_RE = re.compile(r'^[\|\s\-:]+$', re.MULTILINE)
_TABLE_PIPE_RE = re.compile(r'\s*\|\s*')

# Excess blank lines: 3+ -> 2
_EXCESS_NL_RE = re.compile(r'\n{3,}')


def strip_markdown(text: Optional[str]) -> str:
    """Strip Markdown syntax, returning human-readable plain text.

    Args:
        text: Markdown-formatted text, or None.

    Returns:
        Plain text with Markdown syntax removed.
    """
    if text is None:
        return ""

    # 1. Code blocks -- replace with hint
    text = _CODE_BLOCK_RE.sub('（此处有一段代码）', text)

    # 2. Images -- replace with placeholder
    text = _IMAGE_RE.sub('[图片]', text)

    # 3. Links -- keep text
    text = _LINK_RE.sub(r'\1', text)

    # 4. Bold
    text = _BOLD_RE.sub(r'\1\2', text)

    # 5. Italic (after bold to avoid ** conflicts)
    text = _ITALIC_RE.sub(r'\1\2', text)

    # 6. Strikethrough
    text = _STRIKE_RE.sub(r'\1', text)

    # 7. Inline code -- strip backticks
    #    (after bold/italic/strikethrough so that markers inside backticks
    #     are already cleaned -- producing more speech-friendly output)
    text = _INLINE_CODE_RE.sub(r'\1', text)

    # 8. HTML tags
    text = _HTML_RE.sub('', text)

    # 9. Blockquotes -- strip > markers (before headings so that
    #    "> # text" correctly yields "text", not "# text")
    text = _BLOCKQUOTE_RE.sub('', text)

    # 10. Headings -- strip # markers
    text = _HEADING_RE.sub('', text)

    # 11. Horizontal rules -- remove
    text = _HR_RE.sub('', text)

    # 12. Table separators (|---|---|)
    text = _TABLE_SEP_RE.sub('', text)

    # 13. Table pipes -> comma
    text = _TABLE_PIPE_RE.sub('，', text)

    # Strip leading/trailing commas from table rows
    text = re.sub(r'^\s*，\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*，\s*$', '', text, flags=re.MULTILINE)

    # 14. Ordered lists
    text = _OL_RE.sub('', text)

    # 15. Unordered lists (after HR to avoid --- conflicts)
    text = _UL_RE.sub('', text)

    # 16. Collapse 3+ blank lines -> 2
    text = _EXCESS_NL_RE.sub('\n\n', text)

    # 17. Trim leading/trailing whitespace
    text = text.strip()

    return text
