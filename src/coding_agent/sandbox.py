from __future__ import annotations

import os
import resource
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import which


@dataclass(frozen=True)
class SandboxConfig:
    timeout_seconds: float = 15.0
    memory_mb: int = 512
    cpu_seconds: int = 15
    max_output_chars: int = 16_000
    isolate_network: bool = True
    isolate_pid: bool = True


@dataclass
class SandboxResult:
    argv: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    isolated: bool

    @property
    def ok(self) -> bool:
        return (not self.timed_out) and self.exit_code == 0

    def render(self) -> str:
        status = "timeout" if self.timed_out else f"exit {self.exit_code}"
        isolation = "unshare" if self.isolated else "process-limits"
        parts = [
            f"command: {' '.join(self.argv)}",
            f"status: {status} in {self.duration_seconds:.2f}s ({isolation})",
            "--- stdout ---",
            self.stdout if self.stdout else "(empty)",
            "--- stderr ---",
            self.stderr if self.stderr else "(empty)",
        ]
        return "\n".join(parts)


class Sandbox:
    """Run a command inside the workspace with time, memory, and namespace limits."""

    def __init__(self, workspace_root: str | os.PathLike[str], config: SandboxConfig | None = None) -> None:
        self.root = Path(workspace_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = config or SandboxConfig()
        self._tmp = self.root / ".agent" / "tmp"
        self._tmp.mkdir(parents=True, exist_ok=True)

    def run(self, argv: list[str], *, extra_env: dict[str, str] | None = None) -> SandboxResult:
        if not argv:
            raise ValueError("command must not be empty")
        if any(not isinstance(part, str) or part == "" for part in argv):
            raise ValueError("command arguments must be non-empty strings")

        isolated_argv, isolated = self._wrap_isolation(argv)
        env = self._environment(extra_env)
        memory_bytes = max(64, self.config.memory_mb) * 1024 * 1024
        cpu_seconds = max(1, self.config.cpu_seconds)

        def preexec() -> None:
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

        started = time.monotonic()
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code: int | None = None
        proc: subprocess.Popen[str] | None = None
        try:
            proc = subprocess.Popen(
                isolated_argv,
                cwd=str(self.root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=preexec,
            )
            try:
                stdout, stderr = proc.communicate(timeout=self.config.timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                self._kill_group(proc)
                leftover = proc.communicate(timeout=2)
                stdout = leftover[0] or ""
                stderr = leftover[1] or ""
                exit_code = proc.returncode
        except Exception as exc:  # isolation wrapper or spawn failure
            stderr = f"failed to start sandbox process: {exc}"
            exit_code = 127
        duration = time.monotonic() - started
        return SandboxResult(
            argv=list(argv),
            exit_code=exit_code,
            stdout=self._clip(stdout),
            stderr=self._clip(stderr),
            timed_out=timed_out,
            duration_seconds=duration,
            isolated=isolated,
        )

    def _environment(self, extra_env: dict[str, str] | None) -> dict[str, str]:
        path = os.environ.get("PATH", "/usr/bin:/bin")
        env = {
            "PATH": path,
            "HOME": str(self.root),
            "TMPDIR": str(self._tmp),
            "TEMP": str(self._tmp),
            "TMP": str(self._tmp),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        if extra_env:
            env.update(extra_env)
        return env

    def _wrap_isolation(self, argv: list[str]) -> tuple[list[str], bool]:
        unshare = which("unshare")
        if not unshare:
            return list(argv), False
        flags = [unshare, "--user", "--map-root-user"]
        if self.config.isolate_network:
            flags.append("--net")
        if self.config.isolate_pid:
            flags.extend(["--pid", "--fork", "--mount-proc"])
        try:
            probe = subprocess.run(
                flags + ["true"],
                check=False,
                capture_output=True,
                timeout=2,
            )
            if probe.returncode != 0:
                return list(argv), False
        except (OSError, subprocess.TimeoutExpired):
            return list(argv), False
        return flags + list(argv), True

    def _clip(self, text: str) -> str:
        limit = self.config.max_output_chars
        if text is None:
            return ""
        if len(text) <= limit:
            return text
        omitted = len(text) - limit
        return text[:limit] + f"\n... [truncated {omitted} more chars]"

    @staticmethod
    def _kill_group(proc: subprocess.Popen[str]) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.kill()
        except ProcessLookupError:
            pass
