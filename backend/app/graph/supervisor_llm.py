from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class SupervisorDecision(BaseModel):
    next_agent: str = Field(..., description="Next specialist agent to run")
    reason: str = Field(..., description="Why this agent should run next")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0 to 1")


@dataclass
class StructuredOllamaSupervisorLLM:
    """Small Ollama-backed adapter with a structured-output style interface.

    It talks to Ollama's local HTTP API and requests JSON output, then parses the
    response into a Pydantic model. If the server is unavailable, the caller can
    fall back to a deterministic rule-based decision.
    """

    base_url: str
    model: str

    def with_structured_output(self, schema: type[T]) -> Callable[[str], T]:
        def invoke(prompt: str) -> T:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a supervisor router for a software engineering multi-agent system. "
                            "Return only valid JSON that matches the schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "format": "json",
                "stream": False,
            }
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url.rstrip('/')}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise RuntimeError("Ollama supervisor request failed") from exc

            content = raw.get("message", {}).get("content", "{}")
            parsed = schema.model_validate_json(content)
            return parsed

        return invoke


def get_supervisor_llm() -> StructuredOllamaSupervisorLLM:
    settings = get_settings()
    return StructuredOllamaSupervisorLLM(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )
