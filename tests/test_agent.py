from __future__ import annotations

import json
from pathlib import Path

from coding_agent.agent import CodingAgent
from coding_agent.demo import scripted_replies
from coding_agent.llm import FakeLLM
from coding_agent.workspace import Workspace


def _call(tool: str, **args: object) -> str:
    return json.dumps({"thought": "t", "tool": tool, "args": args})


def test_repairs_syntax_error(tmp_path: Path) -> None:
    replies = [
        _call("write_file", path="main.py", content="print('oops'\n"),
        _call("run", argv=["python3", "main.py"]),
        _call("write_file", path="main.py", content="print('ok')\n"),
        _call("run", argv=["python3", "main.py"]),
        _call("finish", success=True, summary="prints ok"),
    ]
    agent = CodingAgent(FakeLLM(replies), Workspace(tmp_path), max_steps=8)
    result = agent.run("Print ok")
    assert result.success
    tools = [step.tool for step in result.steps]
    assert tools == ["write_file", "run", "write_file", "run", "finish"]
    assert not result.steps[1].observation.ok
    assert "SyntaxError" in result.steps[1].observation.detail
    assert result.steps[3].observation.ok
    assert "ok" in result.steps[3].observation.detail
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_demo_script_solves_sum(tmp_path: Path) -> None:
    agent = CodingAgent(FakeLLM(scripted_replies()), Workspace(tmp_path), max_steps=8)
    result = agent.run("sum 1 through 10")
    assert result.success
    assert "55" in result.steps[3].observation.detail
    run_outputs = [s.observation.detail for s in result.steps if s.tool == "run"]
    assert any("45" in text for text in run_outputs)


def test_max_steps_without_finish(tmp_path: Path) -> None:
    replies = [_call("list_files")]
    agent = CodingAgent(FakeLLM(replies * 3), Workspace(tmp_path), max_steps=2)
    result = agent.run("do nothing")
    assert not result.success
    assert len(result.steps) == 2
    assert "stopped after" in result.summary


def test_invalid_json_is_observed_and_continues(tmp_path: Path) -> None:
    replies = [
        "not json at all",
        _call("finish", success=True, summary="recovered"),
    ]
    agent = CodingAgent(FakeLLM(replies), Workspace(tmp_path), max_steps=4)
    result = agent.run("recover")
    assert result.success
    assert result.steps[0].tool == "parse"
    assert not result.steps[0].observation.ok
