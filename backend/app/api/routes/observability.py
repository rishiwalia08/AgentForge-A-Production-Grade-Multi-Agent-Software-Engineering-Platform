from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, DatabaseRepository
from app.core.auth import get_current_user
from app.observability import AgentTracer, AgentEvaluator
from app.services.memory_manager import ErrorMemory, VectorMemory

router = APIRouter(prefix="/runs", tags=["observability"])

@router.get("/{run_id}/timeline", response_model=list[dict[str, Any]])
def get_timeline(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> list[dict[str, Any]]:
    run = DatabaseRepository.get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution run not found."
        )
    if run.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access permission."
        )

    tracer = AgentTracer()
    return tracer.get_timeline(run.thread_id)

@router.get("/{run_id}/metrics", response_model=dict[str, Any])
def get_metrics(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    run = DatabaseRepository.get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution run not found."
        )
    if run.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access permission."
        )

    tracer = AgentTracer()
    evaluator = AgentEvaluator(tracer=tracer)
    
    # Generate full metrics report
    report = evaluator.evaluate(
        thread_id=run.thread_id,
        task=run.input_message,
        final_result=str(run.final_state or "Running"),
        state={"test_results": run.final_state.get("test_results") if run.final_state else {}}
    )
    return report

@router.get("/{run_id}/reflection", response_model=dict[str, Any])
def get_reflection(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    run = DatabaseRepository.get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution run not found."
        )
    if run.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access permission."
        )

    thread_id = run.thread_id

    # 1. Search in Error memories
    err_record = db.query(ErrorMemory).filter(ErrorMemory.error.like(f"%{thread_id}%")).first()
    if err_record:
        return {
            "type": "error_reflection",
            "what_went_wrong": err_record.error,
            "cause": err_record.cause,
            "solution": err_record.solution,
            "timestamp": err_record.timestamp.isoformat()
        }

    # 2. Search in Semantic memories
    sem_record = db.query(VectorMemory).filter(VectorMemory.text.like(f"%{thread_id}%")).first()
    if sem_record:
        return {
            "type": "semantic_reflection",
            "reflection": sem_record.text,
            "metadata": sem_record.metadata_json,
            "created_at": sem_record.created_at.isoformat()
        }

    return {
        "status": "pending_reflection",
        "detail": "No reflection guidelines stored yet for this thread."
    }
