from __future__ import annotations

import json
from typing import Any

import pytest

from coding_agent.cli import build_llm, build_parser
from coding_agent.llm import ChatMessage, OllamaLLM, normalize_ollama_host


def test_normalize_strips_openai_style_suffix() -> None:
    assert normalize_ollama_host("127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert normalize_ollama_host("http://localhost:11434/v1/") == "http://localhost:11434"


def test_ollama_posts_native_chat_payload() -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"message": {"role": "assistant", "content": '{"tool":"finish"}'}}

    llm = OllamaLLM(model="qwen2.5-coder", host="http://127.0.0.1:11434", timeout=12, post=fake_post)
    text = llm.complete([ChatMessage("user", "hi")])
    assert text == '{"tool":"finish"}'
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "qwen2.5-coder"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["timeout"] == 12


def test_ollama_explains_how_to_start_server() -> None:
    def boom(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        raise RuntimeError("could not reach http://127.0.0.1:11434/api/chat: Connection refused")

    llm = OllamaLLM(model="llama3.2", post=boom)
    with pytest.raises(RuntimeError, match="ollama serve"):
        llm.complete([ChatMessage("user", "hi")])


def test_cli_defaults_to_ollama() -> None:
    args = build_parser().parse_args(["print hello"])
    assert args.provider == "ollama"
    llm = build_llm(args)
    assert isinstance(llm, OllamaLLM)
    assert llm.model == "llama3.2"


def test_cli_openai_provider() -> None:
    args = build_parser().parse_args(
        ["--provider", "openai", "--model", "gpt-4o-mini", "--api-key", "sk-test", "task"]
    )
    llm = build_llm(args)
    assert llm.model == "gpt-4o-mini"
    assert llm.api_key == "sk-test"
