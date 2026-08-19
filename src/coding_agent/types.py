from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ToolName = Literal["write_file", "read_file", "list_files", "run", "finish"]


@dataclass
class ToolCall:
    thought: str
    tool: ToolName
    args: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class Observation:
    tool: str
    ok: bool
    detail: str


@dataclass
class StepRecord:
    index: int
    thought: str
    tool: str
    args_summary: str
    observation: Observation
