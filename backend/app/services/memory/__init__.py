from __future__ import annotations

from app.services.memory.models import Base, UserMemory, ProjectMemory, ErrorMemory, VectorMemory
from app.services.memory.manager import MemoryManager
from app.services.memory.embeddings.ollama import OllamaEmbeddingProvider
from app.services.memory.evaluator import LLMMemoryEvaluator

_memory_manager_instance = None

def get_memory_manager() -> MemoryManager:
    global _memory_manager_instance
    if _memory_manager_instance is None:
        from app.core.config import get_settings
        settings = get_settings()
        # In test environments, embedding_provider and evaluator can be patched or fallback
        embedding_provider = None
        evaluator = None
        
        # Don't initialize Ollama in test mode to allow clean offline runs
        if settings.environment != "test":
            try:
                embedding_provider = OllamaEmbeddingProvider(settings.ollama_base_url, settings.ollama_model)
                evaluator = LLMMemoryEvaluator(settings.ollama_base_url, settings.ollama_model)
            except Exception:
                pass
                
        _memory_manager_instance = MemoryManager(
            db_url=settings.database_url,
            embedding_provider=embedding_provider,
            evaluator=evaluator
        )
    return _memory_manager_instance
