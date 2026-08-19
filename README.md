# Autonomous coding agent

A small Python agent that **writes code**, **runs it in a sandbox**, **reads stdout/stderr**, and **edits until the task succeeds**.

```
task → LLM writes files → sandbox run → observe errors → LLM patches → run again → finish
```

The core loop does not depend on a particular model vendor. Production runs talk to any OpenAI-compatible chat API. Tests and `python -m coding_agent.demo` use a scripted model so you can see the write/run/repair cycle with no API key.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Offline demo (no API key)

```bash
python3 -m coding_agent.demo
```

The scripted model first prints `sum(range(10))` (45), sees that this is not 1..10, rewrites the file, re-runs, and finishes when stdout is `55`.

## Live agent

```bash
export OPENAI_API_KEY=sk-...
python3 -m coding_agent "Write a Python program that prints the 10th Fibonacci number (1-indexed, F1=1)."
```

Useful flags:

| Flag | Meaning |
| --- | --- |
| `--workspace DIR` | Only directory the agent may write |
| `--max-steps N` | Cap on write/run/finish iterations (default 12) |
| `--timeout SECONDS` | Wall clock limit per sandbox run |
| `--memory-mb N` | Address-space cap for the child process |
| `--model NAME` | Chat model (default `gpt-4o-mini`) |
| `--base-url URL` | OpenAI-compatible endpoint (Ollama, vLLM, …) |
| `--allow-network` | Skip network namespace isolation |
| `--json` | Machine-readable result on stdout |

Local models example:

```bash
export OPENAI_API_KEY=ollama
python3 -m coding_agent --base-url http://127.0.0.1:11434/v1 --model llama3.2 \
  "Write tests and a function that checks if a string is a palindrome."
```

## Sandbox

Each `run` starts the command with `cwd` set to the workspace and a stripped environment (`HOME`/`TMPDIR` inside the workspace). The child gets:

- wall-clock timeout and `RLIMIT_CPU`
- `RLIMIT_AS` memory cap
- `RLIMIT_NPROC` / `RLIMIT_FSIZE` / no core dumps
- Linux user namespace + **no network** + PID namespace via `unshare` when that works

This is a **developer sandbox**, not a multi-tenant jail. The agent process itself can still see the host filesystem; only the *tools* (`write_file` / `read_file`) reject path traversal, and the *child* is namespace-limited.

## Library

```python
from coding_agent import CodingAgent, OpenAICompatibleLLM, Workspace

agent = CodingAgent(OpenAICompatibleLLM(), Workspace("./ws"), max_steps=10)
result = agent.run("Print hello from a Python script.")
print(result.success, result.summary)
```

## Tests

```bash
python3 -m pytest -q
```
