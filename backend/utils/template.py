"""System Prompt 模板渲染 — Jinja2 薄封装."""

from jinja2 import Template


def render_prompt(template_str: str, context: dict) -> str:
    """渲染 Jinja2 模板字符串。

    Args:
        template_str: 包含 {{ var }} 占位符的模板字符串
        context: 变量上下文字典

    Returns:
        渲染后的字符串。未定义变量保留原样（Jinja2 默认行为）。
    """
    template = Template(template_str)
    return template.render(context)
