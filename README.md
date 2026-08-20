# Autonomous coding agent

A small Python agent that **writes code**, **runs it in a sandbox**, **reads stdout/stderr**, and **edits until the task succeeds**. Chat defaults to a **local Ollama** model (no API key).

```
task → Ollama writes files → sandbox run → observe errors → Ollama patches → run again → finish
```

## Install

```bash
python3 -m pip install -e ".[dev]"
```

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull llama3.2
# or a coding-focused model:
# ollama pull qwen2.5-coder
```

## Run with Ollama (default)

Ollama must be listening on `127.0.0.1:11434` (`ollama serve`).

```bash
python3 -m coding_agent "Write a Python program that prints the 10th Fibonacci number (1-indexed, F1=1)."
```

```bash
python3 -m coding_agent --model qwen2.5-coder \
  "Write tests and a function that checks if a string is a palindrome."
```

If Ollama is on another host:

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_MODEL=llama3.2
python3 -m coding_agent "Print hello from a Python script."
```

## Offline scripted demo (no Ollama)

```bash
python3 -m coding_agent.demo
```

## OpenAI-compatible APIs (optional)

```bash
export OPENAI_API_KEY=sk-...
python3 -m coding_agent --provider openai --model gpt-4o-mini \
  "Write a Python program that prints hello."
```

Useful flags:

| Flag | Meaning |
| --- | --- |
| `--provider ollama\|openai` | Chat backend (default `ollama`) |
| `--model NAME` | Ollama tag or OpenAI model name |
| `--base-url URL` | Ollama host or OpenAI-compatible base URL |
| `--workspace DIR` | Only directory the agent may write |
| `--max-steps N` | Cap on write/run/finish iterations (default 12) |
| `--timeout SECONDS` | Wall clock limit per sandbox run |
| `--llm-timeout SECONDS` | HTTP timeout for the chat model (default 180) |
| `--memory-mb N` | Address-space cap for the child process |
| `--allow-network` | Skip network namespace isolation |
| `--json` | Machine-readable result on stdout |

## Sandbox

Each `run` starts the command with `cwd` set to the workspace and a stripped environment (`HOME`/`TMPDIR` inside the workspace). The child gets:

- wall-clock timeout and `RLIMIT_CPU`
- `RLIMIT_AS` memory cap
- `RLIMIT_NPROC` / `RLIMIT_FSIZE` / no core dumps
- Linux user namespace + **no network** via `unshare` when that works (optional PID namespace)

This is a **developer sandbox**, not a multi-tenant jail. The agent process itself can still see the host filesystem; only the *tools* (`write_file` / `read_file`) reject path traversal, and the *child* is namespace-limited.

## Library

```python
from coding_agent import CodingAgent, OllamaLLM, Workspace

agent = CodingAgent(OllamaLLM(model="llama3.2"), Workspace("./ws"), max_steps=10)
result = agent.run("Print hello from a Python script.")
print(result.success, result.summary)
```

## Tests

```bash
python3 -m pytest -q
```
