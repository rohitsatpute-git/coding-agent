from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.workspace import Workspace, WorkspaceError


def test_write_read_list(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    ws.write_file("src/hello.py", "print('hi')\n")
    assert ws.read_file("src/hello.py") == "print('hi')\n"
    assert ws.list_files() == ["src/hello.py"]


def test_rejects_absolute_and_escape(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.write_file("/etc/passwd", "nope")
    with pytest.raises(WorkspaceError):
        ws.resolve("../secret.txt")
    with pytest.raises(WorkspaceError):
        ws.resolve("ok/../../outside")


def test_hides_agent_metadata(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    ws.write_file(".agent/tmp/x", "hidden")
    ws.write_file("visible.py", "x")
    assert ws.list_files() == ["visible.py"]
