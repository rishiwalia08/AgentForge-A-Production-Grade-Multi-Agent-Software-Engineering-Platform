from __future__ import annotations

import asyncio
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db import get_db, DatabaseRepository
from app.core.auth import get_current_user, verify_token
from app.core.event_bus import event_manager
from app.services.run_service import RunService
from app.schemas.run import RunCreate, RunResponse, RunResume
from app.observability import AgentTracer

router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("/create", response_model=dict[str, str], status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> dict[str, str]:
    return RunService.create_run(
        db,
        project_id=payload.project_id,
        task=payload.task,
        user_id=current_user["id"],
        background_tasks=background_tasks
    )

@router.get("/{run_id}", response_model=dict[str, Any])
def get_run(
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
            detail="User does not have access permission for this run."
        )

    # Fetch active agent node from thread
    thread = DatabaseRepository.get_thread(db, run.thread_id)
    current_agent = thread.current_node if thread else ""

    # Fetch timeline and traces
    tracer = AgentTracer()
    timeline = tracer.get_timeline(run.thread_id)
    
    # Retrieve raw trace steps
    session = tracer.Session()
    try:
        from app.observability.models import TraceRecord
        records = (
            session.query(TraceRecord)
            .filter(TraceRecord.run_id == run_id)
            .order_by(TraceRecord.timestamp.asc())
            .all()
        )
        traces = [
            {
                "id": r.id,
                "agent": r.agent,
                "parent_trace_id": r.parent_trace_id,
                "tool_called": r.tool_called,
                "status": r.status,
                "latency": r.latency,
                "timestamp": r.timestamp.isoformat()
            } for r in records
        ]
    finally:
        session.close()

    return {
        "status": run.status,
        "current_agent": current_agent,
        "timeline": timeline,
        "trace": traces
    }

@router.post("/{run_id}/resume", response_model=dict[str, str])
def resume_run(
    run_id: str,
    payload: RunResume,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> dict[str, str]:
    return RunService.resume_run(
        db,
        run_id=run_id,
        approved=payload.approved,
        feedback=payload.feedback,
        user_id=current_user["id"],
        background_tasks=background_tasks
    )

@router.websocket("/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str, db: Session = Depends(get_db)) -> None:
    # 1. Extract and validate JWT token from query parameter or protocol headers
    token = websocket.query_params.get("token")
    if not token:
        # Check standard headers
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["sub"]
    
    # 2. Check run ownership
    run = DatabaseRepository.get_run(db, run_id)
    if not run or run.user_id != user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Accept websocket connection
    await websocket.accept()

    # 4. Setup asynchronous queue to bridge multi-threaded events to the async loop
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def event_callback(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    event_manager.subscribe(run_id, event_callback)

    try:
        while True:
            # Wait for event and stream it to the client
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") == "completed":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "payload": [str(e)]})
        except Exception:
            pass
    finally:
        event_manager.unsubscribe(run_id, event_callback)
        try:
            await websocket.close()
        except Exception:
            pass
