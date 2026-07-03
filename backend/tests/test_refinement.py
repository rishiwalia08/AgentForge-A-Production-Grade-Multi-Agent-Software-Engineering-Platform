from __future__ import annotations

import os
import shutil
import pytest
from unittest.mock import MagicMock, patch

from app.services.memory import MemoryManager, get_memory_manager
from tests.mocks import MockEmbeddingProvider
from app.services.memory.evaluator import MockMemoryEvaluator
from app.tools.permission import ToolExecutionContext, active_context, ToolPermissionManager
from app.tools.testing import run_tests
from app.tools.git import (
    git_status,
    git_diff,
    create_agent_checkpoint,
    restore_agent_checkpoint,
    get_workspace_dir
)
from app.agents.specialist_agents import (
    requirement_agent_node,
    architecture_agent_node,
    security_agent_node,
    debugging_agent_node,
    RequirementAgentOutput,
    SecurityAgentOutput
)


# --- 1. Memory Refactoring Tests ---

def test_memory_manager_refactored_operations():
    """Test: MemoryManager package operations under sqlite:///:memory:."""
    evaluator = MockMemoryEvaluator(override_decision="save")
    embedding = MockEmbeddingProvider(dimension=64)
    
    mm = MemoryManager(
        db_url="sqlite:///:memory:",
        embedding_provider=embedding,
        evaluator=evaluator
    )
    
    # Store User Memory
    res_user = mm.store_memory("user", "Likes Dark Mode", user_id="Rishi", memory_type="theme")
    assert res_user["status"] == "saved"
    
    # Store Project Memory
    res_proj = mm.store_memory("project", "Python 3.11 target", project_id="agentic_ai", memory_type="config")
    assert res_proj["status"] == "saved"
    
    # Retrieve Memories
    users = mm.retrieve_memory("user", user_id="Rishi")
    assert len(users) == 1
    assert users[0]["content"] == "Likes Dark Mode"
    
    projects = mm.retrieve_memory("project", project_id="agentic_ai")
    assert len(projects) == 1
    assert projects[0]["content"] == "Python 3.11 target"


# --- 2. Permission Manager Tests ---

def test_permission_manager_rules():
    """Test: ToolPermissionManager blocks unauthorized tools per active_context."""
    # Context 1: Research Agent
    ctx_research = ToolExecutionContext(
        agent_id="research_agent",
        run_id="run-research-123",
        user_id="user-rishi"
    )
    t = active_context.set(ctx_research)
    try:
        assert ToolPermissionManager.check_permission("read_file") is True
        assert ToolPermissionManager.check_permission("search_knowledge") is True
        assert ToolPermissionManager.check_permission("create_file") is False
        assert ToolPermissionManager.check_permission("execute_command") is False
    finally:
        active_context.reset(t)

    # Context 2: Testing Agent
    ctx_testing = ToolExecutionContext(
        agent_id="testing_agent",
        run_id="run-testing-123",
        user_id="user-rishi"
    )
    t = active_context.set(ctx_testing)
    try:
        assert ToolPermissionManager.check_permission("run_tests") is True
        assert ToolPermissionManager.check_permission("execute_command") is False
        assert ToolPermissionManager.check_permission("create_file") is False
    finally:
        active_context.reset(t)

    # Context 3: Developer Agent
    ctx_dev = ToolExecutionContext(
        agent_id="developer_agent",
        run_id="run-dev-123",
        user_id="user-rishi"
    )
    t = active_context.set(ctx_dev)
    try:
        assert ToolPermissionManager.check_permission("create_file") is True
        assert ToolPermissionManager.check_permission("execute_command") is True
        assert ToolPermissionManager.check_permission("git_commit") is True
    finally:
        active_context.reset(t)


# --- 3. Git Operations & Safe Rollback Tests ---

def test_safe_git_checkpoints(tmp_path):
    """Test: create_agent_checkpoint and restore_agent_checkpoint rollback changes cleanly."""
    workspace = str(tmp_path)
    
    # Mock get_workspace_dir to return our temp workspace path
    with patch("app.tools.git.get_workspace_dir", return_value=workspace):
        # 1. Initialize git repo in tmp folder to allow git status calls
        import subprocess
        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=workspace, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True)
        
        # Write an initial file and commit it
        init_file = os.path.join(workspace, "init.txt")
        with open(init_file, "w") as f:
            f.write("Initial File Content")
        subprocess.run(["git", "add", "init.txt"], cwd=workspace, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=workspace, capture_output=True)
        
        # 2. Modify existing file and create an untracked file
        with open(init_file, "w") as f:
            f.write("Modified content by developer")
            
        new_file = os.path.join(workspace, "new_file.txt")
        with open(new_file, "w") as f:
            f.write("Untracked content")
            
        # Verify status shows both files
        status_raw = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True)
        assert "init.txt" in status_raw.stdout
        assert "new_file.txt" in status_raw.stdout
        
        # 3. Create Agent Checkpoint
        ctx = ToolExecutionContext(agent_id="developer_agent", run_id="run-checkpoint-test", user_id="Rishi")
        token = active_context.set(ctx)
        
        try:
            checkpoint_res = create_agent_checkpoint()
            assert checkpoint_res["status"] == "success"
            assert "init.txt" in checkpoint_res["checkpoint_files"]
            assert "new_file.txt" in checkpoint_res["checkpoint_files"]
            
            # 4. Make further developer modifications
            with open(init_file, "w") as f:
                f.write("Second developer modification")
            with open(new_file, "w") as f:
                f.write("Untracked content modified")
                
            # 5. Restore Checkpoint (Rollback)
            restore_res = restore_agent_checkpoint()
            assert restore_res["status"] == "success"
            assert "init.txt" in restore_res["restored_files"]
            assert "new_file.txt" in restore_res["deleted_files"]
            
            # Verify init.txt rolled back to checkpoint state (Modified content by developer)
            with open(init_file, "r") as f:
                content = f.read()
            assert content == "Modified content by developer"
            
            # Verify new_file.txt was deleted because it was untracked at checkpoint creation time
            assert not os.path.exists(new_file)
        finally:
            active_context.reset(token)


# --- 4. Specialist Agent Node Execution Tests ---

@patch("app.agents.specialist_agents._get_specialist_llm")
def test_specialist_agent_node_executions(mock_llm_factory):
    """Test: Specialist agent nodes run structured LLM outputs and record to memory."""
    # Mock LLM decision output
    mock_llm = MagicMock()
    mock_llm_factory.return_value = mock_llm
    
    state = {
        "user_request": "FastAPI OAuth config",
        "current_task": "Gather specifications",
        "run_id": "test-run-spec",
        "messages": []
    }
    
    # 1. Test RequirementAgent
    mock_llm.with_structured_output.return_value = lambda prompt: RequirementAgentOutput(
        requirements=["Require OAuth2 support"],
        scope="OAuth2 integrations",
        next_steps=["Design DB schemas"]
    )
    
    req_res = requirement_agent_node(state)
    assert "requirement_output" in req_res
    assert req_res["requirement_output"]["scope"] == "OAuth2 integrations"
    
    # 2. Test SecurityAgent Hybrid Safety Check
    mock_llm.with_structured_output.return_value = lambda prompt: SecurityAgentOutput(
        risk_level="low",
        reason="No immediate risks detected in code request",
        requires_human_approval=False,
        vulnerabilities=[]
    )
    
    # Test standard security run
    sec_res = security_agent_node(state)
    assert sec_res["security_output"]["risk_level"] == "low"
    assert sec_res["security_output"]["requires_human_approval"] is False
    
    # Test static danger trigger
    state_dangerous = dict(state)
    state_dangerous["user_request"] = "rm -rf /usr/local"
    sec_dangerous_res = security_agent_node(state_dangerous)
    
    assert sec_dangerous_res["security_output"]["risk_level"] == "critical"
    assert sec_dangerous_res["security_output"]["requires_human_approval"] is True
    assert "[STATIC RULE TRIGGERED]" in sec_dangerous_res["security_output"]["reason"]
