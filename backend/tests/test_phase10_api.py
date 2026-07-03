from __future__ import annotations

import os
import time
import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import get_settings
from app.db import Base, get_db, SessionLocal, engine, init_db, DatabaseRepository
import app.db.session as session_module
import app.services.agent_runner as runner_module
from app.core.auth import get_current_user, create_access_token, verify_token
from app.core.event_bus import event_manager
from app.db.checkpoints import DatabaseCheckpointSaver
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata

# Use a temporary file-based SQLite database for testing, so that background threads can share state.
TEST_DB_URL = "sqlite:///./data/test_agent_memory.db"

@pytest.fixture(autouse=True)
def override_memory_manager_for_integration(monkeypatch):
    # Override conftest's mock_global_memory_manager to use the same test database file!
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
        db_url=TEST_DB_URL,
        embedding_provider=MockEmbeddingProvider(dimension=128),
        evaluator=evaluator
    )
    
    monkeypatch.setattr(mm_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(da_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(sa_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(ret_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(tracer_module, "get_memory_manager", lambda: mock_mm)
    monkeypatch.setattr(refl_module, "get_memory_manager", lambda: mock_mm)
    return mock_mm

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # 1. Clean up/drop tables in test database instead of deleting the file
    test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    from app.db.models import Base as DbBase
    from app.services.memory_manager import Base as MemBase
    from app.observability.models import Base as ObsBase
    
    try:
        DbBase.metadata.drop_all(bind=test_engine)
        MemBase.metadata.drop_all(bind=test_engine)
        ObsBase.metadata.drop_all(bind=test_engine)
    except Exception:
        pass
            
    # 3. Create all tables
    DbBase.metadata.create_all(bind=test_engine)
    MemBase.metadata.create_all(bind=test_engine)
    ObsBase.metadata.create_all(bind=test_engine)

    # 4. Override FastAPI DB dependency
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    import app.db.checkpoints as checkpoints_module
    import app.core.celery_app as celery_module

    # Patch session_module SessionLocal/engine so other code imports use test database
    orig_engine = session_module.engine
    orig_session_local = session_module.SessionLocal
    orig_runner_session_local = runner_module.SessionLocal
    orig_checkpoints_session_local = checkpoints_module.SessionLocal
    orig_celery_session_local = celery_module.SessionLocal

    session_module.engine = test_engine
    session_module.SessionLocal = TestSessionLocal
    runner_module.SessionLocal = TestSessionLocal
    checkpoints_module.SessionLocal = TestSessionLocal
    celery_module.SessionLocal = TestSessionLocal

    yield

    # Clean up overrides
    app.dependency_overrides.pop(get_db, None)
    session_module.engine = orig_engine
    session_module.SessionLocal = orig_session_local
    runner_module.SessionLocal = orig_runner_session_local
    checkpoints_module.SessionLocal = orig_checkpoints_session_local
    celery_module.SessionLocal = orig_celery_session_local



def test_1_user_authentication():
    """Test 1: Verify mock Google token login registers user and issues valid JWT."""
    client = TestClient(app)
    response = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    
    payload = verify_token(data["access_token"])
    assert payload is not None
    assert payload["email"] == "rishi@example.com"
    assert payload["name"] == "Rishi"


def test_2_expired_jwt_rejected():
    """Test 2: Verify that expired JWTs are rejected with 401 status."""
    settings = get_settings()
    # Create an expired token by setting exp to past
    past_exp = datetime.now(timezone.utc) - timedelta(seconds=10)
    expired_token = jwt.encode(
        {"sub": "some_id", "email": "test@example.com", "name": "Test", "exp": past_exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/projects", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_3_create_run():
    """Test 3: Verify starting a run creates db records and returns IDs."""
    client = TestClient(app)
    # Auth Rishi
    auth_res = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    proj_res = client.post(
        "/projects",
        json={"name": "SaaS Platform", "description": "FastAPI agent system"},
        headers=headers
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]
    
    # Create run
    run_res = client.post(
        "/runs/create",
        json={"project_id": project_id, "task": "Verify routing functionality"},
        headers=headers
    )
    assert run_res.status_code == 201
    data = run_res.json()
    assert "run_id" in data
    assert "thread_id" in data


def test_4_user_isolation():
    """Test 4: Verify User B cannot view or delete User A's project."""
    client = TestClient(app)
    # Auth User A (Rishi)
    auth_a = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token_a = auth_a.json()["access_token"]
    
    # Auth User B (Bob)
    auth_b = client.post("/auth/google-login", json={"id_token": "mock_token_bob"})
    token_b = auth_b.json()["access_token"]
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # User A creates project
    proj_res = client.post("/projects", json={"name": "Rishi Secret Proj"}, headers=headers_a)
    project_id = proj_res.json()["id"]
    
    # User B lists projects - shouldn't see User A's project
    list_b = client.get("/projects", headers=headers_b)
    project_ids_b = [p["id"] for p in list_b.json()]
    assert project_id not in project_ids_b
    
    # User B deletes User A's project - should receive 403 Forbidden
    del_b = client.delete(f"/projects/{project_id}", headers=headers_b)
    assert del_b.status_code == 403


def test_5_user_cannot_access_another_run_trace():
    """Test 5: Verify User B receives 403 Forbidden when trying to access User A's run data."""
    client = TestClient(app)
    
    # User A (Rishi)
    auth_a = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token_a = auth_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # User B (Bob)
    auth_b = client.post("/auth/google-login", json={"id_token": "mock_token_bob"})
    token_b = auth_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # Create project and run under User A
    proj = client.post("/projects", json={"name": "Isolating Runs"}, headers=headers_a).json()
    run = client.post("/runs/create", json={"project_id": proj["id"], "task": "Check isolation"}, headers=headers_a).json()
    
    run_id = run["run_id"]
    
    # User B attempts to access run details
    get_b = client.get(f"/runs/{run_id}", headers=headers_b)
    assert get_b.status_code == 403
    
    # User B attempts to access run timeline
    timeline_b = client.get(f"/runs/{run_id}/timeline", headers=headers_b)
    assert timeline_b.status_code == 403


def test_6_checkpoint_persists_after_restart_simulation():
    """Test 6: Verify DatabaseCheckpointSaver retrieves state after connection restarts."""
    # 1. First Saver Instance
    saver1 = DatabaseCheckpointSaver()
    thread_id = "restart_thread_test"
    config = {"configurable": {"thread_id": thread_id}}
    
    mock_checkpoint: Checkpoint = {
        "v": 1,
        "ts": "2026-06-25T12:00:00Z",
        "id": "chk-12345",
        "parent_id": None,
        "channel_values": {"messages": ["System initialized"]},
        "channel_versions": {},
        "versions_seen": {},
        "pending_sends": []
    }
    mock_metadata: CheckpointMetadata = {"source": "test"}
    
    saver1.put(config, mock_checkpoint, mock_metadata, {})
    
    # 2. Simulate Connection Restart (New instance querying database)
    saver2 = DatabaseCheckpointSaver()
    tup = saver2.get_tuple(config)
    
    assert tup is not None
    assert tup.checkpoint["id"] == "chk-12345"
    assert tup.checkpoint["channel_values"]["messages"] == ["System initialized"]


def test_7_resume_approval(monkeypatch):
    """Test 7: Verify posting human approval resume triggers run service resumption."""
    client = TestClient(app)
    
    # Mock AgentRunner to prevent background threads from modifying DB state
    monkeypatch.setattr(runner_module.AgentRunner, "run", lambda run_id, thread_id, task: None)
    monkeypatch.setattr(runner_module.AgentRunner, "resume", lambda run_id, thread_id, approved, feedback=None: None)
    
    auth_a = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token = auth_a.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project and run
    proj = client.post("/projects", json={"name": "Resume Project"}, headers=headers).json()
    run = client.post("/runs/create", json={"project_id": proj["id"], "task": "Human interruption test"}, headers=headers).json()
    run_id = run["run_id"]
    
    # Mock run state in DB to interrupted
    db = session_module.SessionLocal()
    try:
        DatabaseRepository.update_run(db, run_id, status="interrupted")
    finally:
        db.close()
        
    # Resume run
    resume_res = client.post(
        f"/runs/{run_id}/resume",
        json={"approved": True, "feedback": "Code changes look good"},
        headers=headers
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "resuming"


def test_8_timeline_retrieval():
    """Test 8: Verify timeline retrieves sequential steps properly."""
    client = TestClient(app)
    
    auth_a = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token = auth_a.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project and run
    proj = client.post("/projects", json={"name": "Timeline Project"}, headers=headers).json()
    run = client.post("/runs/create", json={"project_id": proj["id"], "task": "Timeline test"}, headers=headers).json()
    run_id = run["run_id"]
    thread_id = run["thread_id"]
    
    # Pre-populate some traces
    from app.observability import AgentTracer
    tracer = AgentTracer()
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="supervisor", tool_called="developer", reasoning_summary="routed")
    tracer.log_step(run_id=run_id, thread_id=thread_id, agent="developer", tool_called="read_file")
    
    # Fetch timeline
    timeline_res = client.get(f"/runs/{run_id}/timeline", headers=headers)
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()
    assert len(timeline) == 2
    assert timeline[0]["agent"] == "Supervisor"
    assert timeline[0]["decision"] == "developer"
    assert timeline[1]["agent"] == "Developer"
    assert timeline[1]["tool"] == "read_file"


def test_9_multiple_websocket_clients_receive_events():
    """Test 9: Verify multiple websocket subscribers receive published run updates."""
    client = TestClient(app)
    
    # Authenticate Rishi
    auth_res = client.post("/auth/google-login", json={"id_token": "mock_token_rishi"})
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project and run
    proj = client.post("/projects", json={"name": "WebSocket Project"}, headers=headers).json()
    run = client.post("/runs/create", json={"project_id": proj["id"], "task": "WS Broadcast test"}, headers=headers).json()
    run_id = run["run_id"]
    
    # Connect multiple clients
    with client.websocket_connect(f"/runs/{run_id}/stream?token={token}") as ws1:
        with client.websocket_connect(f"/runs/{run_id}/stream?token={token}") as ws2:
            
            # Publish event
            event_manager.publish(run_id, {
                "type": "agent_step",
                "agent": "developer",
                "content": "Thinking about next action."
            })
            
            # Publish completion event to close loops
            event_manager.publish(run_id, {
                "type": "completed",
                "payload": {"status": "success"}
            })
            
            # Verify ws1 receives events
            evt1_ws1 = ws1.receive_json()
            assert evt1_ws1["type"] == "agent_step"
            assert evt1_ws1["content"] == "Thinking about next action."
            evt2_ws1 = ws1.receive_json()
            assert evt2_ws1["type"] == "completed"
            
            # Verify ws2 receives events
            evt1_ws2 = ws2.receive_json()
            assert evt1_ws2["type"] == "agent_step"
            assert evt1_ws2["content"] == "Thinking about next action."
            evt2_ws2 = ws2.receive_json()
            assert evt2_ws2["type"] == "completed"
