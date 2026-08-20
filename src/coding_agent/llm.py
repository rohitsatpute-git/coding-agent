from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

JsonPoster = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


@dataclass
class ChatMessage:
    role: str
    content: str


class LLM(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str: ...


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def normalize_ollama_host(host: str) -> str:
    value = host.strip().rstrip("/")
    if value.endswith("/v1"):
        value = value[:-3]
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value.rstrip("/")


class OllamaLLM:
    """Local Ollama chat client (`/api/chat`). No API key required."""

    def __init__(
        self,
        *,
        model: str = "llama3.2",
        host: str | None = None,
        timeout: float = 180.0,
        temperature: float = 0.1,
        post: JsonPoster | None = None,
    ) -> None:
        self.model = model
        self.host = normalize_ollama_host(
            host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        )
        self.timeout = timeout
        self.temperature = temperature
        self._post = post or post_json

    def complete(self, messages: list[ChatMessage]) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "options": {"temperature": self.temperature},
        }
        try:
            body = self._post(
                url,
                payload,
                {"Content-Type": "application/json"},
                self.timeout,
            )
        except RuntimeError as exc:
            raise RuntimeError(
                f"{exc}. Start Ollama (`ollama serve`) and pull a model "
                f"(`ollama pull {self.model}`)."
            ) from exc
        try:
            return str(body["message"]["content"] or "")
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"unexpected Ollama response: {body!r}") from exc


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
