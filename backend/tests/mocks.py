from __future__ import annotations

from app.services.memory.embeddings.base import BaseEmbeddingProvider

class MockEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def get_embedding(self, text: str) -> list[float]:
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        embedding = []
        for i in range(self.dimension):
            val = (h[i % len(h)] + i) / 256.0
            embedding.append(val)
        return embedding
