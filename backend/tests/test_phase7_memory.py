import pytest
import os
import tempfile
from app.services.memory_manager import MemoryManager, MockMemoryEvaluator
from tests.mocks import MockEmbeddingProvider
from app.agents.specialist_agents import _execute_specialist_node, DebuggingAgentOutput
from app.graph.state import PlatformState

def _base_state(user_request: str):
    return {
        "user_request": user_request,
        "current_task": user_request,
        "tasks": [],
        "observations": [],
        "approvals_required": [],
        "pending_approval": {},
        "approved_actions": [],
        "rejected_actions": [],
        "agent_history": [],
        "tool_history": [],
        "tool_calls": [],
        "tool_outputs": [],
        "messages": [],
        "errors": [],
        "memory": {},
        "test_results": {},
        "current_error": "",
        "current_step": 0,
    }

def test_user_memory_store_retrieve():
    # Setup
    evaluator = MockMemoryEvaluator(override_decision="save")
    mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(), evaluator=evaluator)
    
    # Store
    result = mm.store_memory(
        category="user",
        content="Uses FastAPI + PostgreSQL",
        user_id="Rishi",
        memory_type="preference"
    )
    assert result["status"] == "saved"
    
    # Retrieve
    records = mm.retrieve_memory("user", user_id="Rishi")
    assert len(records) == 1
    assert records[0]["content"] == "Uses FastAPI + PostgreSQL"
    assert records[0]["user_id"] == "Rishi"
    assert records[0]["memory_type"] == "preference"


def test_project_memory_cross_thread():
    temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_db_fd)
    
    db_url = f"sqlite:///{temp_db_path}"
    
    try:
        evaluator = MockMemoryEvaluator(override_decision="save")
        mm1 = MemoryManager(db_url=db_url, embedding_provider=MockEmbeddingProvider(), evaluator=evaluator)
        
        # Thread/Session 1: Store project context
        result = mm1.store_memory(
            category="project",
            content="backend uses FastAPI",
            project_id="AI platform",
            memory_type="tech_stack"
        )
        assert result["status"] == "saved"
        
        # Thread/Session 2: Instantiate new manager pointing to same DB URL and retrieve
        mm2 = MemoryManager(db_url=db_url, embedding_provider=MockEmbeddingProvider(), evaluator=evaluator)
        records = mm2.retrieve_memory("project", project_id="AI platform")
        assert len(records) == 1
        assert records[0]["content"] == "backend uses FastAPI"
    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_error_memory_store_and_debugging_agent_retrieve(monkeypatch):
    # Setup
    evaluator = MockMemoryEvaluator(override_decision="save")
    mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(), evaluator=evaluator)
    
    # Pre-populate error memory
    mm.store_memory(
        category="error",
        content="ModuleNotFoundError: numpy",
        metadata={
            "cause": "numpy not in virtual environment",
            "solution": "install numpy via pip and add to requirements.txt"
        },
        cause="numpy not in virtual environment",
        solution="install numpy via pip and add to requirements.txt"
    )
    
    # Setup monkeypatch to ensure our specialist agents module uses this mm
    import app.agents.specialist_agents as sa
    monkeypatch.setattr(sa, "get_memory_manager", lambda: mm)
    
    # Mock LLM for debugging agent
    class MockStructuredLLM:
        def __call__(self, prompt):
            # Assert that the prompt contains our retrieved error solution!
            assert "install numpy via pip and add to requirements.txt" in prompt
            return DebuggingAgentOutput(
                root_cause="numpy missing",
                fix_plan="pip install numpy"
            )
            
    class MockLLM:
        def with_structured_output(self, schema):
            return MockStructuredLLM()
            
    monkeypatch.setattr(sa, "_get_specialist_llm", lambda: MockLLM())
    
    # Invoke specialist node
    state = _base_state("Fix numpy error")
    state["current_error"] = "ModuleNotFoundError: numpy"
    
    res = sa.debugging_agent_node(state)
    assert res["debugging_output"]
    assert res["debugging_output"]["root_cause"] == "numpy missing"


def test_vector_similarity_search():
    evaluator = MockMemoryEvaluator(override_decision="save")
    # MockEmbeddingProvider returns deterministic embeddings based on text hashes
    mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(dimension=128), evaluator=evaluator)
    
    mm.store_memory("semantic", "JWT refresh token failing due to expiration mismatch")
    mm.store_memory("semantic", "database connection pool leak in connection.py")
    
    # Search for something similar to JWT
    results = mm.search_memory("JWT refresh token failing", limit=1)
    assert len(results) == 1
    assert "JWT refresh token" in results[0]["text"]


def test_unimportant_memory_ignored():
    evaluator = MockMemoryEvaluator()
    mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(), evaluator=evaluator)
    
    # Try to store unimportant random chat
    result = mm.store_memory("semantic", "hi how are you? ignore this please.")
    assert result["status"] == "ignored"
    
    # Verify not stored in vector store
    assert len(mm.vector_store.documents) == 0
