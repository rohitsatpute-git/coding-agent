from __future__ import annotations

from pathlib import Path

from coding_agent.sandbox import Sandbox, SandboxConfig


def test_captures_stdout(tmp_path: Path) -> None:
    sandbox = Sandbox(tmp_path)
    result = sandbox.run(["python3", "-c", "print('hello-sandbox')"])
    assert result.ok
    assert "hello-sandbox" in result.stdout
    assert result.timed_out is False


def test_captures_traceback(tmp_path: Path) -> None:
    sandbox = Sandbox(tmp_path)
    (tmp_path / "boom.py").write_text("raise ValueError('observed')\n", encoding="utf-8")
    result = sandbox.run(["python3", "boom.py"])
    assert not result.ok
    assert result.exit_code != 0
    assert "ValueError" in result.stderr
    assert "observed" in result.stderr


def test_timeout(tmp_path: Path) -> None:
    sandbox = Sandbox(tmp_path, SandboxConfig(timeout_seconds=1, cpu_seconds=2, isolate_pid=False))
    result = sandbox.run(["python3", "-c", "import time; time.sleep(30)"])
    assert result.timed_out
    assert not result.ok


def test_truncates_output(tmp_path: Path) -> None:
    sandbox = Sandbox(tmp_path, SandboxConfig(max_output_chars=50, isolate_network=False))
    result = sandbox.run(["python3", "-c", "print('x' * 500)"])
    assert result.ok
    assert "truncated" in result.stdout


def test_network_namespace_blocks_connect(tmp_path: Path) -> None:
    sandbox = Sandbox(tmp_path, SandboxConfig(timeout_seconds=3, isolate_network=True))
    result = sandbox.run(
        [
            "python3",
            "-c",
            "import socket; s=socket.socket(); s.settimeout(1); s.connect(('1.1.1.1', 53))",
        ]
    )
    if not result.isolated:
        return
    assert not result.ok
    combined = result.stdout + result.stderr
    assert "Network is unreachable" in combined or "OSError" in combined or "error" in combined.lower()
