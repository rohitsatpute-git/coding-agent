from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from coding_agent.agent import CodingAgent
from coding_agent.llm import OpenAICompatibleLLM
from coding_agent.sandbox import SandboxConfig
from coding_agent.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="Autonomous coding agent: write, run in a sandbox, observe errors, retry.",
    )
    parser.add_argument("task", nargs="?", help="Natural-language programming task")
    parser.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="Directory the agent may write and run in (default: ./.agent-runs/<id>)",
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-run wall timeout in seconds")
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI-compatible API base URL",
    )
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--allow-network", action="store_true", help="Do not unshare the network namespace")
    parser.add_argument("--json", action="store_true", help="Print a JSON result at the end")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.task:
        print("Provide a task, or run the offline demo: python -m coding_agent.demo", file=sys.stderr)
        return 2

    workspace_path = Path(args.workspace) if args.workspace else _default_workspace()
    workspace = Workspace(workspace_path)
    llm = OpenAICompatibleLLM(api_key=args.api_key, model=args.model, base_url=args.base_url)
    sandbox_config = SandboxConfig(
        timeout_seconds=args.timeout,
        memory_mb=args.memory_mb,
        cpu_seconds=max(1, int(args.timeout)),
        isolate_network=not args.allow_network,
    )
    agent = CodingAgent(llm, workspace, max_steps=args.max_steps, sandbox_config=sandbox_config)

    print(f"workspace: {workspace.root}", file=sys.stderr)
    result = agent.run(args.task)
    for step in result.steps:
        print(f"\n=== step {step.index}: {step.tool} {step.args_summary} ===", file=sys.stderr)
        if step.thought:
            print(f"thought: {step.thought}", file=sys.stderr)
        print(step.observation.detail, file=sys.stderr)

    if args.json:
        print(
            json.dumps(
                {
                    "success": result.success,
                    "summary": result.summary,
                    "workspace": result.workspace,
                    "steps": [
                        {
                            "index": s.index,
                            "tool": s.tool,
                            "thought": s.thought,
                            "args": s.args_summary,
                            "ok": s.observation.ok,
                        }
                        for s in result.steps
                    ],
                },
                indent=2,
            )
        )
    else:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"\n{status}: {result.summary}", file=sys.stderr)
        print(f"files in {result.workspace}:", file=sys.stderr)
        for name in Workspace(result.workspace).list_files():
            print(f"  {name}", file=sys.stderr)
    return 0 if result.success else 1


def _default_workspace() -> Path:
    stamp = str(os.getpid())
    return Path.cwd() / ".agent-runs" / stamp


if __name__ == "__main__":
    raise SystemExit(main())
