from __future__ import annotations

import pytest
import time
from unittest.mock import MagicMock
from app.services.memory_manager import MemoryManager, MockMemoryEvaluator
from tests.mocks import MockEmbeddingProvider
import app.services.memory_manager as mm_module
from app.observability import AgentTracer, AgentEvaluator, ReflectionAgent, is_langsmith_enabled, get_langsmith_config
from app.observability.models import TraceRecord
from app.graph.state import PlatformState
from app.agents.developer_agent import ToolNode
from app.tools.filesystem import read_file


@pytest.fixture(autouse=True)
def setup_test_observability_env(monkeypatch):
    """Sets up an isolated, in-memory SQLite database for testing observability and memory."""
    import app.services.memory_manager as mm_module
    import app.observability.reflection as ref_module
    import app.observability.tracer as tr_module
    import app.observability.evaluator as ev_module

    evaluator = MockMemoryEvaluator(override_decision="save")
    mock_mm = MemoryManager(
        db_url="sqlite:///:memory:",
        embedding_provider=MockEmbeddingProvider(dimension=128),
        evaluator=evaluator
    )
    monkeypatch.setattr(mm_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(ref_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(tr_module, "get_memory_manager", lambda: mock_mm)
    return mock_mm


def test_1_trace_records_agent_flow():
    """Test 1: Verify AgentTracer logs run steps and compiles chronological timelines."""
    tracer = AgentTracer()
    thread_id = "test_thread_1"
    run_id = "run_1"
    
    # Log supervisor decision
    sup_id = tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="supervisor",
        reasoning_summary="Routing to developer for implementation.",
        tool_called="developer"
    )
    
    # Log developer reasoning
    dev_id = tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="developer",
        parent_trace_id=sup_id,
        reasoning_summary="Need to check configuration file."
    )
    
    # Query timeline
    timeline = tracer.get_timeline(thread_id)
    assert len(timeline) == 2
    assert timeline[0]["agent"] == "Supervisor"
    assert timeline[0]["decision"] == "developer"
    assert timeline[0]["reason"] == "Routing to developer for implementation."
    assert timeline[1]["agent"] == "Developer"
    assert timeline[1]["decision"] == "complete"
    assert timeline[1]["reason"] == "Need to check configuration file."


def test_2_tool_execution_logged():
    """Test 2: Verify tool executions are logged with inputs and latency."""
    tracer = AgentTracer()
    thread_id = "test_thread_2"
    run_id = "run_2"
    
    tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="developer",
        tool_called="read_file",
        tool_arguments={"path": "auth.py"},
        tool_result={"stdout": "def login(): pass"},
        latency=0.08,
        status="SUCCESS"
    )
    
    # Retrieve performance summary and timeline
    summary = tracer.get_performance_summary(thread_id)
    assert summary["total_steps"] == 1
    assert "read_file" in summary["tools_used"]
    assert summary["duration"] == 0.08
    
    timeline = tracer.get_timeline(thread_id)
    assert timeline[0]["agent"] == "Developer"
    assert timeline[0]["tool"] == "read_file"


def test_3_evaluator_scores_output():
    """Test 3: Verify AgentEvaluator scores runs and reports metrics."""
    tracer = AgentTracer()
    thread_id = "test_thread_3"
    run_id = "run_3"
    
    # Log steps: 1 supervisor decision, 1 tool execution, 1 test execution
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="supervisor", tool_called="developer", reasoning_summary="coding")
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="developer", tool_called="create_file")
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="testing_agent", reasoning_summary="Testing completed.")
    
    evaluator = AgentEvaluator(tracer=tracer)
    state = {
        "test_results": {"status": "success"},
        "approval_history": []
    }
    
    report = evaluator.evaluate(
        thread_id=thread_id,
        task="Create main.py",
        final_result="Successfully created file and verified execution.",
        state=state
    )
    
    assert report["iterations"] == 3
    assert report["errors"] == 0
    assert report["task_success"] == 1.0
    assert report["score"] >= 8
    assert report["rule_metrics"]["test_passed"] is True
    assert report["rule_metrics"]["human_intervention_count"] == 0


def test_4_reflection_stores_learning():
    """Test 4: Verify ReflectionAgent writes actionable rules to semantic memory on success."""
    ref_agent = ReflectionAgent()
    eval_report = {
        "score": 9,
        "issues": [],
        "errors": 0,
        "task_success": 1.0
    }
    
    res = ref_agent.reflect(
        thread_id="test_thread_4",
        evaluation_report=eval_report,
        task="Gather architecture requirements"
    )
    
    assert res["save_status"] == "saved"
    assert res["memory_id"] is not None
    
    # Verify semantic memory retrieval
    mems = ref_agent.mm.search_memory("requirements", limit=5)
    assert len(mems) > 0
    assert "Reflection rule" in mems[0]["text"]


def test_5_failed_task_generates_improvement_memory():
    """Test 5: Verify that failed runs trigger error memory storage for rules."""
    ref_agent = ReflectionAgent()
    eval_report = {
        "score": 4,
        "issues": ["Permission denied writing to /etc/hosts"],
        "errors": 1,
        "task_success": 0.0
    }
    
    res = ref_agent.reflect(
        thread_id="test_thread_5",
        evaluation_report=eval_report,
        task="Write to system hosts file"
    )
    
    assert res["save_status"] == "saved"
    
    # Query error memory
    err_mems = ref_agent.mm.retrieve_memory("error", query="Permission denied")
    assert len(err_mems) > 0
    assert "hosts" in err_mems[0]["error"] or "hosts" in err_mems[0]["cause"]


def test_6_nested_trace_hierarchy_works():
    """Test 6: Verify parent_trace_id creates a nested tree tree structure."""
    tracer = AgentTracer()
    thread_id = "test_thread_6"
    run_id = "run_6"
    
    # 1. Supervisor decision (Root)
    root_id = tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="supervisor",
        tool_called="developer",
        reasoning_summary="Route task."
    )
    
    # 2. Developer execution (Child of Supervisor)
    child_id = tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="developer",
        parent_trace_id=root_id,
        reasoning_summary="Start coding."
    )
    
    # 3. Tool execution (Child of Developer)
    grandchild_id = tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="developer",
        parent_trace_id=child_id,
        tool_called="read_file",
        tool_arguments={"path": "package.json"}
    )
    
    # Verify relations in db
    session = tracer.Session()
    try:
        r_child = session.query(TraceRecord).filter(TraceRecord.id == child_id).first()
        r_grandchild = session.query(TraceRecord).filter(TraceRecord.id == grandchild_id).first()
        
        assert r_child.parent_trace_id == root_id
        assert r_grandchild.parent_trace_id == child_id
    finally:
        session.close()


def test_7_failed_tool_call_is_recorded():
    """Test 7: Verify failed tool execution is traced with error state."""
    tracer = AgentTracer()
    thread_id = "test_thread_7"
    run_id = "run_7"
    
    tracer.log_step(
        run_id=run_id,
        thread_id=thread_id,
        agent="developer",
        tool_called="execute_command",
        tool_arguments={"cmd": "bad_command"},
        tool_result={"stderr": "command not found"},
        status="FAILED",
        error_message="Command failed with exit code 127"
    )
    
    session = tracer.Session()
    try:
        record = session.query(TraceRecord).filter(TraceRecord.thread_id == thread_id).first()
        assert record.status == "FAILED"
        assert record.error_message == "Command failed with exit code 127"
    finally:
        session.close()


def test_8_reflection_does_not_store_low_value_memories(monkeypatch):
    """Test 8: Verify guardrails filter out low-value or ignored reflection learnings."""
    ref_agent = ReflectionAgent()
    
    # Configure mock evaluator to reject reflections flagged as unimportant or containing 'ignore'
    mock_evaluator = MockMemoryEvaluator(override_decision="ignore")
    monkeypatch.setattr(ref_agent.mm, "evaluator", mock_evaluator)
    
    eval_report = {
        "score": 9,
        "issues": [],
        "errors": 0,
        "task_success": 1.0
    }
    
    res = ref_agent.reflect(
        thread_id="test_thread_8",
        evaluation_report=eval_report,
        task="Say hello to user (unimportant)"
    )
    
    # Assert save status is ignored
    assert res["save_status"] == "ignored"
    assert res["memory_id"] is None


def test_9_performance_summary_generated():
    """Test 9: Verify dashboard metrics summary generator parses database records."""
    tracer = AgentTracer()
    thread_id = "test_thread_9"
    run_id = "run_9"
    
    # Insert multiple test records
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="supervisor", tool_called="developer", latency=0.1)
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="developer", tool_called="read_file", latency=0.2, status="SUCCESS")
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="developer", tool_called="update_file", latency=0.3, status="FAILED", error_message="Permission error")
    
    summary = tracer.get_performance_summary(thread_id)
    
    assert summary["total_steps"] == 3
    assert "supervisor" in summary["agents_called"]
    assert "developer" in summary["agents_called"]
    assert "read_file" in summary["tools_used"]
    assert "update_file" in summary["tools_used"]
    assert summary["duration"] == pytest.approx(0.6)
    assert summary["success_rate"] == pytest.approx(2/3)
    assert "Permission error" in summary["errors"]


def test_langsmith_checks():
    """Test standard environment configs are properly captured."""
    assert is_langsmith_enabled() is False
    config = get_langsmith_config()
    assert config["tracing"] is False
    assert config["api_key_set"] is False
