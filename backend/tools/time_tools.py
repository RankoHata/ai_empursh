"""Time-related tool definitions for LLM function calling."""

from datetime import datetime

from tools.base import ToolDefinition


async def _get_current_time(format: str = "readable", _ws_sender=None) -> dict:
    """Return the current local time with timezone info.

    Args:
        format: 'readable' (中文可读), 'iso' (ISO 8601), 'unix' (Unix timestamp)
    """
    now = datetime.now().astimezone()
    tz_name = now.tzname() or ""

    if format == "unix":
        import time
        ts = int(time.time())
        return {
            "success": True,
            "timestamp": ts,
            "timezone": tz_name,
            "message": f"当前 Unix 时间戳: {ts}",
        }
    elif format == "iso":
        return {
            "success": True,
            "timestamp": now.isoformat(),
            "timezone": tz_name,
            "message": f"当前 ISO 时间: {now.isoformat()}",
        }
    else:
        # readable — 明确标注本地时间，避免 AI 误认为 UTC
        readable = now.strftime("%Y年%m月%d日 %H:%M:%S")
        return {
            "success": True,
            "timestamp": readable,
            "timezone": tz_name,
            "message": (
                f"用户当前本地时间是 {readable}（{tz_name}时区）。"
                f"这已经是本地时间，不需要再换算时区。"
            ),
        }


get_current_time_tool = ToolDefinition(
    name="get_current_time",
    description=(
        "获取用户当前的本地时间。返回的时间已经带有正确的时区信息，"
        "不需要额外换算。当用户询问当前时间、日期、或者需要知道现在几点时使用。"
    ),
    parameters={
        "format": {
            "type": "string",
            "description": "时间格式：'readable'（中文可读，默认），'iso'（ISO 8601），'unix'（Unix 时间戳）",
        },
    },
    required=[],
    executor=_get_current_time,
    display_name="获取当前时间",
)

TIME_TOOLS = [get_current_time_tool]
