from __future__ import annotations

import json
import os

class DocumentLoader:
    @staticmethod
    def load_file(file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


class Chunker:
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> list[str]:
        chunks = []
        if not text:
            return chunks
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks
