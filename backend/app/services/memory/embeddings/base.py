from __future__ import annotations

class BaseEmbeddingProvider:
    def get_embedding(self, text: str) -> list[float]:
        raise NotImplementedError()
