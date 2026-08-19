from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


class LLM(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str: ...


class OpenAICompatibleLLM:
    """Chat completions client for OpenAI and compatible servers (Ollama, vLLM, etc.)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        temperature: float = 0.1,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def complete(self, messages: list[ChatMessage]) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export an API key, or run: python -m coding_agent.demo"
            )
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        try:
            return str(body["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected LLM response: {body!r}") from exc


class FakeLLM:
    """Deterministic scripted model used by tests and the offline demo."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0
        self.history: list[list[ChatMessage]] = []

    def complete(self, messages: list[ChatMessage]) -> str:
        self.history.append(list(messages))
        if self.calls >= len(self.replies):
            raise RuntimeError("FakeLLM has no remaining replies")
        reply = self.replies[self.calls]
        self.calls += 1
        return reply
