"""Autonomous coding agent: write code, run it in a sandbox, observe, retry."""

from coding_agent.agent import AgentResult, CodingAgent
from coding_agent.llm import FakeLLM, OllamaLLM, OpenAICompatibleLLM
from coding_agent.sandbox import Sandbox, SandboxConfig, SandboxResult
from coding_agent.workspace import Workspace

__all__ = [
    "AgentResult",
    "CodingAgent",
    "FakeLLM",
    "OllamaLLM",
    "OpenAICompatibleLLM",
    "Sandbox",
    "SandboxConfig",
    "SandboxResult",
    "Workspace",
]
__version__ = "0.1.0"
