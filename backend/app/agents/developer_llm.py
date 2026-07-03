from __future__ import annotations

import inspect
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class DeveloperTurn(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


@dataclass
class OllamaDeveloperLLM:
    base_url: str
    model: str

    def bind_tools(self, tools: list[Callable[..., Any]]) -> "BoundDeveloperLLM":
        return BoundDeveloperLLM(self, tools)


@dataclass
class BoundDeveloperLLM:
    llm: OllamaDeveloperLLM
    tools: list[Callable[..., Any]]

    def _tool_manifest(self) -> str:
        parts: list[str] = []
        for tool in self.tools:
            signature = str(inspect.signature(tool))
            docstring = (tool.__doc__ or "").strip()
            parts.append(f"- {tool.__name__}{signature}: {docstring}")
        return "\n".join(parts)

    def _messages_payload(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tool_names = ", ".join(tool.__name__ for tool in self.tools)
        system_message = {
            "role": "system",
            "content": (
                "You are a ReAct developer agent in a software engineering platform. "
                "Use tools when needed and continue reasoning after observations. "
                "Return only valid JSON with keys 'content' and 'tool_calls'. "
                f"Allowed tools: {tool_names}.\n\nTool manifest:\n{self._tool_manifest()}"
            ),
        }
        return [system_message, *messages]

    def invoke(self, messages: list[dict[str, Any]]) -> DeveloperTurn:
        payload = {
            "model": self.llm.model,
            "messages": self._messages_payload(messages),
            "format": "json",
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.llm.base_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw.get("message", {}).get("content", "{}")
            return DeveloperTurn.model_validate_json(content)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError("Ollama developer LLM request failed") from exc


def get_developer_llm() -> OllamaDeveloperLLM:
    settings = get_settings()
    return OllamaDeveloperLLM(base_url=settings.ollama_base_url, model=settings.ollama_model)