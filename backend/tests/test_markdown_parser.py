"""Unit tests for the Markdown file parser."""

import os
import tempfile

import pytest
from parsers.markdown_parser import parse_md


def _write_temp_md(content: str) -> str:
    """Write content to a temp .md file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".md", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestParseMd:
    def test_basic_parsing(self):
        path = _write_temp_md("# Hello\n\nThis is a **test**.")
        try:
            result = parse_md(path)
            assert result["title"] == "Hello"
            assert result["content_raw"].startswith("# Hello")
            assert "test" in result["content_plain"]
            assert "**" not in result["content_plain"]
            assert len(result["hash"]) == 64
            assert isinstance(result["mtime"], int)
        finally:
            os.unlink(path)

    def test_front_matter_title_and_tags(self):
        path = _write_temp_md(
            "---\ntitle: My Document\ntags: [python, tutorial]\n---\n\n"
            "# Should NOT be title\n\nSome content."
        )
        try:
            result = parse_md(path)
            assert result["title"] == "My Document"
            assert result["tags"] == ["python", "tutorial"]
            # Body should NOT include front matter
            assert "---" not in result["content_plain"]
            assert "Should NOT be title" in result["content_plain"]
        finally:
            os.unlink(path)

    def test_tags_as_comma_string(self):
        path = _write_temp_md(
            "---\ntags: work, life, hobby\n---\n\n# Doc\n\nText."
        )
        try:
            result = parse_md(path)
            assert result["tags"] == ["work", "life", "hobby"]
        finally:
            os.unlink(path)

    def test_title_from_h1_fallback(self):
        path = _write_temp_md("# Actual Title\n\nContent here.")
        try:
            result = parse_md(path)
            assert result["title"] == "Actual Title"
        finally:
            os.unlink(path)

    def test_title_from_filename_fallback(self):
        path = _write_temp_md("No heading here.\n\nJust content.")
        try:
            result = parse_md(path)
            # Title should be the filename stem
            expected = os.path.basename(path).replace(".md", "")
            assert result["title"] == expected
        finally:
            os.unlink(path)

    def test_hash_consistency(self):
        content = "# Test\n\nAlways the same."
        path = _write_temp_md(content)
        try:
            r1 = parse_md(path)
            r2 = parse_md(path)
            assert r1["hash"] == r2["hash"]
        finally:
            os.unlink(path)

    def test_hash_differs_on_change(self):
        path = _write_temp_md("Content v1")
        try:
            r1 = parse_md(path)
            # Rewrite
            with open(path, "w", encoding="utf-8") as f:
                f.write("Content v2")
            r2 = parse_md(path)
            assert r1["hash"] != r2["hash"]
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = _write_temp_md("")
        try:
            result = parse_md(path)
            assert result["content_raw"] == ""
            assert result["content_plain"] == ""
            assert len(result["hash"]) == 64  # SHA-256 of empty string
        finally:
            os.unlink(path)

    def test_no_front_matter(self):
        path = _write_temp_md("# Just a heading\n\nAnd some text.")
        try:
            result = parse_md(path)
            assert result["tags"] == []
            assert result["title"] == "Just a heading"
        finally:
            os.unlink(path)

    def test_invalid_front_matter(self):
        """Malformed YAML should not crash the parser."""
        path = _write_temp_md(
            "---\nkey: [unclosed\n---\n\n# Title\n\nBody."
        )
        try:
            result = parse_md(path)
            # Should still work, front matter may be skipped
            assert result["content_raw"] is not None
        finally:
            os.unlink(path)
