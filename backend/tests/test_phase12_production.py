from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import get_settings
from app.core.celery_app import run_agent_task, resume_agent_task
from app.db import get_db, DatabaseRepository, SessionLocal
import app.db.session as session_module

client = TestClient(app)

def test_1_health_endpoint_detects_services():
    """Test: Health endpoint detects services and returns expected structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "api" in data
    assert "database" in data
    assert "redis" in data
    assert "worker" in data
    assert data["api"] == "healthy"

def test_2_environment_variables_load_correctly():
    """Test: Settings helper correctly loads values from environment overrides."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+psycopg2://usr:pwd@host/db",
        "REDIS_URL": "redis://my-redis-host:6379/1"
    }):
        # Evict lru_cache for settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.environment == "production"
        assert settings.database_url == "postgresql+psycopg2://usr:pwd@host/db"
        assert settings.redis_url == "redis://my-redis-host:6379/1"
        
        # Reset settings
        get_settings.cache_clear()

def test_3_docker_compose_validation():
    """Test: Verify structure validity of the docker-compose.yml configuration."""
    compose_path = "docker-compose.yml"
    assert os.path.exists(compose_path), "docker-compose.yml file is missing from root"
    
    with open(compose_path, "r") as f:
        content = f.read()
        
    # Check that compose contains all requested services and healthchecks
    assert "postgres:" in content
    assert "redis:" in content
    assert "backend:" in content
    assert "agent-worker:" in content
    assert "frontend:" in content
    assert "healthcheck:" in content
    assert "python:3.11-slim" in open("backend/Dockerfile").read()

def test_4_celery_task_retry_configuration():
    """Test: Celery tasks are configured for automatic retries on exceptions."""
    assert run_agent_task.autoretry_for == (Exception,)
    assert run_agent_task.max_retries == 3
    assert resume_agent_task.autoretry_for == (Exception,)
    assert resume_agent_task.max_retries == 3

def test_5_worker_failure_updates_run_status():
    """Test: Worker task failure updates database execution state to failed."""
    # Create mock DB session
    db = session_module.SessionLocal()
    
    # 1. Create a dummy project and run
    from uuid import uuid4
    user_id = "test-user-p12"
    project_id = "test-proj-p12-" + str(uuid4())[:8]
    run_id = str(uuid4())
    thread_id = f"thread_{run_id}"
    
    # Mock project and thread
    user = DatabaseRepository.get_user_by_email(db, "user@p12.com")
    if not user:
        user = DatabaseRepository.create_user(db, email="user@p12.com", name="User P12", google_sub=user_id)
    user_id = user.id
    
    DatabaseRepository.create_project(db, user_id=user_id, name="Test P12", description="Desc")
    DatabaseRepository.create_thread(db, thread_id=thread_id, user_id=user_id, project_id=project_id)
    DatabaseRepository.create_run(db, run_id=run_id, thread_id=thread_id, user_id=user_id, project_id=project_id, input_message="Do something")
    
    # 2. Mock AgentRunner.run to raise exception
    with patch("app.services.agent_runner.AgentRunner.run", side_effect=ValueError("Execution crash simulation")):
        # 3. Invoke Celery task (mocked as bind=True, request.retries=3 to trigger final failure)
        run_agent_task.max_retries = 3
        run_agent_task.request.retries = 3
        
        # Execute Celery task bound context block manually
        with pytest.raises(ValueError):
            run_agent_task.run(run_id, thread_id, "Do something")
            
    # 4. Verify run status in database updated to failed with error message
    run = DatabaseRepository.get_run(db, run_id)
    assert run is not None
    assert run.status == "failed"
    assert "Execution crash simulation" in run.error
    
    db.close()
