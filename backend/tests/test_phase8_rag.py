import pytest
import os
import tempfile
import shutil
from app.services.memory_manager import MemoryManager, MockMemoryEvaluator
from tests.mocks import MockEmbeddingProvider
from app.knowledge.models import KnowledgeChunk
from app.knowledge.indexer import CodeIndexer, RepoMap, CodeGraph
from app.knowledge.parser import DocumentLoader, Chunker
from app.knowledge.retriever import KnowledgeBase, search_knowledge
import app.agents.specialist_agents as sa
from app.agents.specialist_agents import ResearchAgentOutput
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


def test_ast_extraction_works():
    code = (
        "import math\n"
        "from os import path\n\n"
        "class HelperClass:\n"
        "    def method_one(self, x):\n"
        "        \"\"\"Method one docstring.\"\"\"\n"
        "        math.cos(x)\n"
        "        return x\n\n"
        "def top_level_func(a, b):\n"
        "    \"\"\"Top level docstring.\"\"\"\n"
        "    return a + b\n"
    )
    
    info = CodeIndexer.parse_python_ast(code, "test_file.py")
    
    # Assert imports
    assert any("math" in imp["library"] for imp in info["imports"])
    assert any("os.path" in imp["library"] for imp in info["imports"])
    
    # Assert classes
    assert len(info["classes"]) == 1
    cls = info["classes"][0]
    assert cls["name"] == "HelperClass"
    assert len(cls["methods"]) == 1
    assert cls["methods"][0]["name"] == "method_one"
    assert cls["methods"][0]["docstring"] == "Method one docstring."
    
    # Assert functions
    assert len(info["functions"]) == 1
    func = info["functions"][0]
    assert func["name"] == "top_level_func"
    assert func["arguments"] == ["a", "b"]
    assert func["docstring"] == "Top level docstring."


def test_markdown_docs_loader_and_chunking():
    doc_text = "# Header\nThis is paragraph one.\n\n# Second Header\nThis is paragraph two."
    chunks = Chunker.chunk_text(doc_text, chunk_size=30, overlap=5)
    assert len(chunks) > 1
    assert any("Header" in chunk for chunk in chunks)


def test_kb_index_repository_and_exact_symbol_search():
    evaluator = MockMemoryEvaluator(override_decision="save")
    db_mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(dimension=128), evaluator=evaluator)
    kb = KnowledgeBase(db_manager=db_mm)
    
    code = (
        "def create_access_token(username):\n"
        "    \"\"\"Generates JWT access token.\"\"\"\n"
        "    return 'token'\n"
    )
    
    kb.index_file("auth.py", code)
    
    # Symbol search (Test 5: Exact function search)
    results = kb.search("create_access_token")
    assert len(results["matches"]) > 0
    best_match = results["matches"][0]
    assert best_match["symbol"] == "create_access_token"
    assert best_match["file_path"] == "auth.py"
    # Exact symbol score priority check (Test 10: exact beats semantic)
    assert best_match["score"] >= 10.0


def test_repomap_generation():
    # Setup temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        api_dir = os.path.join(temp_dir, "api")
        os.makedirs(api_dir)
        with open(os.path.join(api_dir, "auth.py"), "w") as f:
            f.write("# auth")
            
        with open(os.path.join(temp_dir, "main.py"), "w") as f:
            f.write("# main")
            
        repo_map = RepoMap.generate(temp_dir)
        assert "main.py" in repo_map["files"]
        assert "auth.py" in repo_map["api"]["files"]


def test_codegraph_dependency_extraction():
    # Test 8: Dependency graph extraction
    code = (
        "import json\n"
        "class OrderService:\n"
        "    def create_order(self, item_id):\n"
        "        validate_item(item_id)\n"
        "        return True\n"
    )
    
    info = CodeIndexer.parse_python_ast(code, "orders.py")
    cg = CodeGraph()
    cg.build_from_indexer_info("orders.py", info)
    
    # Assert import dependency
    assert any(imp["imported_module"] == "json" for imp in cg.imports)
    # Assert function call dependency
    assert any(call["caller"] == "OrderService.create_order" and call["callee"] == "validate_item" for call in cg.calls)


def test_incremental_index_updates():
    # Test 9: After modifying file, knowledge index refreshes
    evaluator = MockMemoryEvaluator(override_decision="save")
    db_mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(dimension=128), evaluator=evaluator)
    kb = KnowledgeBase(db_manager=db_mm)
    
    code_v1 = (
        "def login_user():\n"
        "    \"\"\"login v1\"\"\"\n"
        "    return 'v1'\n"
    )
    kb.index_file("auth.py", code_v1)
    
    # Search for login_user
    res_v1 = kb.search("login_user")
    assert len(res_v1["matches"]) == 1
    assert "v1" in res_v1["matches"][0]["content"]
    
    # Modify file, trigger incremental index update
    code_v2 = (
        "def login_user():\n"
        "    \"\"\"login v2\"\"\"\n"
        "    return 'v2'\n"
    )
    kb.update_file_index("auth.py", code_v2)
    
    # Search again
    res_v2 = kb.search("login_user")
    assert len(res_v2["matches"]) == 1
    assert "v2" in res_v2["matches"][0]["content"]
    assert "v1" not in res_v2["matches"][0]["content"]


def test_research_agent_answering_from_docs(monkeypatch):
    # Setup
    evaluator = MockMemoryEvaluator(override_decision="save")
    db_mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(dimension=128), evaluator=evaluator)
    kb = KnowledgeBase(db_manager=db_mm)
    
    kb.index_content("docs/oauth.md", "Google OAuth requires CLIENT_ID and CLIENT_SECRET client setup.", "text")
    
    # Patch get_memory_manager inside specialist_agents
    monkeypatch.setattr(sa, "get_memory_manager", lambda: db_mm)
    
    # Mock LLM for research agent
    class MockResearchLLM:
        def __call__(self, prompt):
            # Assert prompt contains OAuth knowledge
            assert "OAuth" in prompt
            return ResearchAgentOutput(
                summary="OAuth config needs Client ID",
                relevant_files=["docs/oauth.md"],
                solution_context="Set Google OAuth keys."
            )
            
    class MockLLM:
        def with_structured_output(self, schema):
            return MockResearchLLM()
            
    monkeypatch.setattr(sa, "_get_specialist_llm", lambda: MockLLM())
    
    # Run Research Node
    state = _base_state("Summarize OAuth documentation")
    res = sa.research_agent_node(state)
    assert res["research_output"]
    assert res["research_output"]["summary"] == "OAuth config needs Client ID"


def test_developer_avoids_duplicate_implementation(monkeypatch):
    # Test 7: Developer avoids duplicate implementation
    # Patch KnowledgeBase in search_knowledge to return access token function
    evaluator = MockMemoryEvaluator(override_decision="save")
    db_mm = MemoryManager(db_url="sqlite:///:memory:", embedding_provider=MockEmbeddingProvider(dimension=128), evaluator=evaluator)
    kb = KnowledgeBase(db_manager=db_mm)
    
    code = (
        "def create_access_token(user):\n"
        "    \"\"\"Already exists in security.py\"\"\"\n"
        "    return 'jwt'\n"
    )
    kb.index_file("security.py", code)
    
    # Patch get_memory_manager and get_ollama_embedding globally
    import app.knowledge.retriever as ret_module
    monkeypatch.setattr(ret_module, "KnowledgeBase", lambda: kb)
    
    # Run search_knowledge tool directly
    tool_result = search_knowledge("create_access_token")
    assert len(tool_result["matches"]) > 0
    assert tool_result["matches"][0]["symbol"] == "create_access_token"
    assert "security.py" in tool_result["matches"][0]["file_path"]
