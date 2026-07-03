from __future__ import annotations

import numpy as np
import faiss
from app.services.memory.vector.base import BaseVectorStore

class FAISSVectorStore(BaseVectorStore):
    def __init__(self):
        self.index = None
        self.dimension = None
        self.documents = []

    def add(self, vector: list[float], text: str, metadata: dict = None) -> None:
        if self.index is None:
            self.dimension = len(vector)
            self.index = faiss.IndexFlatL2(self.dimension)
        arr = np.array([vector], dtype=np.float32)
        self.index.add(arr)
        self.documents.append({"text": text, "metadata": metadata or {}})

    def search(self, vector: list[float], k: int = 5) -> list[dict]:
        if self.index is None or self.index.ntotal == 0:
            return []
        arr = np.array([vector], dtype=np.float32)
        distances, indices = self.index.search(arr, k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = self.documents[idx]
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": float(dist)
            })
        return results
