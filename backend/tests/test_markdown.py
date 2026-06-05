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


def test_blockquote_with_heading():
    assert strip_markdown("> # 标题") == "标题"
    assert strip_markdown("> ## 二级") == "二级"


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


def test_strips_table_formatting():
    text = "| 列A | 列B |\n|-----|-----|\n| 值1 | 值2 |"
    result = strip_markdown(text)
    assert "列A" in result
    assert "列B" in result
    assert "值1" in result
    assert "值2" in result
    assert "|" not in result
    assert "---" not in result


def test_handles_none():
    assert strip_markdown(None) == ""
