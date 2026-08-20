from __future__ import annotations

import os
from pathlib import Path


class WorkspaceError(ValueError):
    """Invalid or unsafe workspace path."""


class Workspace:
    """File helpers confined to a single directory tree."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str | os.PathLike[str]) -> Path:
        rel = Path(relative)
        if rel.is_absolute():
            raise WorkspaceError("path must be relative to the workspace")
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("path escapes the workspace") from exc
        return candidate

    def write_file(self, relative: str, content: str, *, encoding: str = "utf-8") -> Path:
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return path

    def read_file(self, relative: str, *, encoding: str = "utf-8", max_chars: int = 80_000) -> str:
        path = self.resolve(relative)
        if not path.is_file():
            raise WorkspaceError(f"file not found: {relative}")
        text = path.read_text(encoding=encoding)
        if len(text) > max_chars:
            return text[:max_chars] + f"\n... [truncated, {len(text)} chars total]"
        return text

    def list_files(self, prefix: str = "") -> list[str]:
        base = self.resolve(prefix) if prefix else self.root
        if not base.exists():
            return []
        if base.is_file():
            return [str(base.relative_to(self.root))]
        entries: list[str] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(self.root))
                if rel.startswith(".agent/"):
                    continue
                entries.append(rel)
        return entries
