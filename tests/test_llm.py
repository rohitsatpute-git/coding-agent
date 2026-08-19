from __future__ import annotations

import json

import pytest

from coding_agent.agent import parse_tool_call, AgentError


def test_parses_plain_json() -> None:
    call = parse_tool_call('{"thought": "t", "tool": "run", "args": {"argv": ["python3", "a.py"]}}')
    assert call.tool == "run"
    assert call.args["argv"] == ["python3", "a.py"]


def test_parses_fenced_json() -> None:
    raw = """here you go
```json
{"thought": "x", "tool": "finish", "args": {"success": true, "summary": "done"}}
```
"""
    call = parse_tool_call(raw)
    assert call.tool == "finish"
    assert call.args["success"] is True


def test_rejects_unknown_tool() -> None:
    with pytest.raises(AgentError):
        parse_tool_call(json.dumps({"tool": "rm_rf", "args": {}}))
