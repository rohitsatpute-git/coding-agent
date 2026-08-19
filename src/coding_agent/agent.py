from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from coding_agent.llm import ChatMessage, LLM
from coding_agent.prompts import SYSTEM_PROMPT
from coding_agent.sandbox import Sandbox, SandboxConfig
from coding_agent.types import Observation, StepRecord, ToolCall
from coding_agent.workspace import Workspace, WorkspaceError


@dataclass
class AgentResult:
    success: bool
    summary: str
    steps: list[StepRecord] = field(default_factory=list)
    workspace: str = ""


class AgentError(RuntimeError):
    pass


class CodingAgent:
    """Write → run → observe errors → edit → retry."""

    def __init__(
        self,
        llm: LLM,
        workspace: Workspace,
        sandbox: Sandbox | None = None,
        *,
        max_steps: int = 12,
        sandbox_config: SandboxConfig | None = None,
    ) -> None:
        self.llm = llm
        self.workspace = workspace
        self.sandbox = sandbox or Sandbox(workspace.root, sandbox_config)
        self.max_steps = max(1, max_steps)
        self.messages: list[ChatMessage] = [ChatMessage("system", SYSTEM_PROMPT)]
        self.steps: list[StepRecord] = []

    def run(self, task: str) -> AgentResult:
        self.messages.append(
            ChatMessage(
                "user",
                "Task:\n"
                f"{task.strip()}\n\n"
                "Workspace is empty. Write code, run it, and iterate until the task is solved.",
            )
        )
        for index in range(1, self.max_steps + 1):
            raw = self.llm.complete(self.messages)
            try:
                call = parse_tool_call(raw)
            except AgentError as exc:
                observation = Observation(tool="parse", ok=False, detail=str(exc))
                self._remember(raw, observation)
                self.steps.append(
                    StepRecord(index, thought="", tool="parse", args_summary="", observation=observation)
                )
                continue

            observation = self._dispatch(call)
            self._remember(raw, observation)
            args_summary = _summarize_args(call)
            self.steps.append(
                StepRecord(index, call.thought, call.tool, args_summary, observation)
            )
            if call.tool == "finish":
                success = bool(call.args.get("success")) and observation.ok
                summary = str(call.args.get("summary") or observation.detail)
                return AgentResult(success, summary, self.steps, str(self.workspace.root))

        return AgentResult(
            False,
            f"stopped after {self.max_steps} steps without finish",
            self.steps,
            str(self.workspace.root),
        )

    def _dispatch(self, call: ToolCall) -> Observation:
        try:
            if call.tool == "write_file":
                path = str(call.args.get("path") or "")
                content = call.args.get("content")
                if not path or content is None:
                    raise AgentError("write_file requires path and content")
                written = self.workspace.write_file(path, str(content))
                return Observation("write_file", True, f"wrote {written.relative_to(self.workspace.root)} ({len(str(content))} chars)")

            if call.tool == "read_file":
                path = str(call.args.get("path") or "")
                if not path:
                    raise AgentError("read_file requires path")
                text = self.workspace.read_file(path)
                return Observation("read_file", True, text)

            if call.tool == "list_files":
                prefix = str(call.args.get("prefix") or "")
                files = self.workspace.list_files(prefix)
                listing = "\n".join(files) if files else "(no files)"
                return Observation("list_files", True, listing)

            if call.tool == "run":
                argv = _coerce_argv(call.args)
                result = self.sandbox.run(argv)
                return Observation("run", result.ok, result.render())

            if call.tool == "finish":
                summary = str(call.args.get("summary") or "done")
                success = bool(call.args.get("success", False))
                return Observation("finish", success, summary)

            raise AgentError(f"unknown tool: {call.tool}")
        except (AgentError, WorkspaceError, ValueError, OSError) as exc:
            return Observation(call.tool, False, f"error: {exc}")

    def _remember(self, raw_reply: str, observation: Observation) -> None:
        self.messages.append(ChatMessage("assistant", raw_reply))
        self.messages.append(
            ChatMessage(
                "user",
                "Observation:\n"
                f"tool={observation.tool} ok={observation.ok}\n"
                f"{observation.detail}\n\n"
                "Continue. Reply with the next JSON tool call.",
            )
        )


def parse_tool_call(text: str) -> ToolCall:
    payload = _extract_json_object(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AgentError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentError("model output must be a JSON object")
    tool = data.get("tool")
    allowed = {"write_file", "read_file", "list_files", "run", "finish"}
    if tool not in allowed:
        raise AgentError(f"tool must be one of {sorted(allowed)}")
    args = data.get("args") or {}
    if not isinstance(args, dict):
        raise AgentError("args must be an object")
    thought = str(data.get("thought") or "")
    return ToolCall(thought=thought, tool=tool, args=args, raw=text)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1]
    raise AgentError("no JSON object found in model output")


def _coerce_argv(args: dict[str, Any]) -> list[str]:
    if "argv" in args:
        argv = args["argv"]
        if not isinstance(argv, list) or not argv:
            raise AgentError("argv must be a non-empty list of strings")
        return [str(part) for part in argv]
    command = args.get("command")
    if isinstance(command, str) and command.strip():
        return shlex.split(command)
    raise AgentError("run requires argv (preferred) or command")


def _summarize_args(call: ToolCall) -> str:
    if call.tool == "write_file":
        return str(call.args.get("path") or "")
    if call.tool == "read_file":
        return str(call.args.get("path") or "")
    if call.tool == "run":
        try:
            return " ".join(_coerce_argv(call.args))
        except AgentError:
            return str(call.args)
    if call.tool == "finish":
        return str(call.args.get("success"))
    return json.dumps(call.args, ensure_ascii=False)[:200]
