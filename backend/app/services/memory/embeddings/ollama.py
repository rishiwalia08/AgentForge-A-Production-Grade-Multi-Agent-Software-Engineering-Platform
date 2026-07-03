from __future__ import annotations

import json
import urllib.request
from app.services.memory.embeddings.base import BaseEmbeddingProvider

class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def get_embedding(self, text: str) -> list[float]:
        payload = {
            "model": self.model,
            "prompt": text
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/embeddings",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json.get("embedding", [])
        except Exception as e:
            raise RuntimeError(f"Ollama embedding request failed: {e}")
