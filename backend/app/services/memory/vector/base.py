from __future__ import annotations

class BaseVectorStore:
    def add(self, vector: list[float], text: str, metadata: dict = None) -> None:
        raise NotImplementedError()

    def search(self, vector: list[float], k: int = 5) -> list[dict]:
        raise NotImplementedError()
