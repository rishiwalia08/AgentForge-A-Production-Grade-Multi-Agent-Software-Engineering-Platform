from __future__ import annotations

import json
import urllib.request
import urllib.error

class LLMMemoryEvaluator:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def evaluate(self, content: str, category: str) -> str:
        prompt = (
            f"You are a memory evaluator for an AI software engineering agent.\n"
            f"Category: {category}\n"
            f"Content: {content}\n"
            f"Decide if this content is important to remember (e.g. user preferences, bug solutions, architecture choices) "
            f"or should be ignored (e.g. random conversational chat, temporary script outputs, generic greetings).\n"
            f"Return JSON with key 'important' (boolean)."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the schema: {'important': bool}"},
                {"role": "user", "content": prompt}
            ],
            "format": "json",
            "stream": False
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                content_str = res_json.get("message", {}).get("content", "{}")
                data = json.loads(content_str)
                is_important = bool(data.get("important", True))
                return "save" if is_important else "ignore"
        except Exception:
            return "evaluation_pending"

class MockMemoryEvaluator:
    """Used in unit tests to simulate evaluator decisions without faking production code."""
    def __init__(self, override_decision: str = "save"):
        self.override_decision = override_decision

    def evaluate(self, content: str, category: str) -> str:
        normalized = content.lower()
        if "ignore" in normalized or "unimportant" in normalized:
            return "ignore"
        return self.override_decision
