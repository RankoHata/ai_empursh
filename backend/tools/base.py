"""ToolDefinition -- data class describing a callable tool for the model."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class ToolDefinition:
    """Describes a function the model can call.

    Attributes:
        name:        Unique tool identifier, e.g. "search_notes".
        description: Natural-language description for the model.
        parameters:  JSON Schema ``properties`` dict (keys are param names).
        required:    List of required parameter names.
        executor:    Async callable that receives **kwargs and returns a dict.
        display_name:Human-readable label for the frontend (defaults to name).
    """

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    executor: Callable[..., Awaitable[dict[str, Any]]]
    display_name: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name
