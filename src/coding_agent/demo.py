"""Offline demo: a scripted model writes buggy code, sees the error, and repairs it."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coding_agent.agent import CodingAgent
from coding_agent.llm import FakeLLM
from coding_agent.workspace import Workspace


def _call(thought: str, tool: str, **args: object) -> str:
    return json.dumps({"thought": thought, "tool": tool, "args": args})


def scripted_replies() -> list[str]:
    buggy = "print(sum(range(10)))\n"
    fixed = "print(sum(range(1, 11)))\n"
    return [
        _call("Write a first attempt that is off-by-one.", "write_file", path="sum.py", content=buggy),
        _call("Run the program.", "run", argv=["python3", "sum.py"]),
        _call("The sum of 1..10 should be 55, not 45. Fix the range.", "write_file", path="sum.py", content=fixed),
        _call("Re-run after the fix.", "run", argv=["python3", "sum.py"]),
        _call("Output is 55 as required.", "finish", success=True, summary="Printed sum(1..10)=55"),
    ]


def run_demo(workspace_dir: Path | None = None) -> int:
    cleanup = False
    if workspace_dir is None:
        workspace_dir = Path(tempfile.mkdtemp(prefix="coding-agent-demo-"))
        cleanup = False
    workspace = Workspace(workspace_dir)
    agent = CodingAgent(FakeLLM(scripted_replies()), workspace, max_steps=8)
    task = "Write a Python program that prints the sum of integers from 1 through 10 inclusive."
    print(f"task: {task}")
    print(f"workspace: {workspace.root}")
    result = agent.run(task)
    for step in result.steps:
        print(f"\n=== step {step.index}: {step.tool} {step.args_summary} ===")
        if step.thought:
            print(f"thought: {step.thought}")
        print(step.observation.detail)
    print(f"\n{'SUCCESS' if result.success else 'FAILED'}: {result.summary}")
    return 0 if result.success else 1


def main() -> int:
    return run_demo()


if __name__ == "__main__":
    raise SystemExit(main())
