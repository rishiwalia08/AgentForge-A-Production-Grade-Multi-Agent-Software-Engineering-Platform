from __future__ import annotations

import sys
import pytest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def mock_global_memory_manager(monkeypatch):
    from app.services.memory_manager import MemoryManager, MockMemoryEvaluator
    from tests.mocks import MockEmbeddingProvider
    import app.services.memory_manager as mm_module
    import app.agents.developer_agent as da_module
    import app.agents.specialist_agents as sa_module
    import app.knowledge.retriever as ret_module
    import app.observability.tracer as tracer_module
    import app.observability.reflection as refl_module
    
    evaluator = MockMemoryEvaluator(override_decision="save")
    mock_mm = MemoryManager(
        db_url="sqlite:///:memory:",
        embedding_provider=MockEmbeddingProvider(dimension=128),
        evaluator=evaluator
    )
    
    # Pre-populate some initial project/user context for agent nodes in human loop tests
    mock_mm.store_memory("user", "User likes standard formats", user_id="Rishi", memory_type="preference")
    mock_mm.store_memory("project", "Using LangGraph for routing", project_id="AI platform", memory_type="context")
    
    monkeypatch.setattr(mm_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(da_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(sa_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(ret_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(tracer_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(refl_module, "get_memory_manager", lambda: mock_mm)
    return mock_mm

