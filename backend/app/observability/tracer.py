from __future__ import annotations

import json
from uuid import uuid4
import datetime
from typing import Any
from app.services.memory_manager import get_memory_manager
from app.observability.models import TraceRecord, Base

class AgentTracer:
    def __init__(self) -> None:
        self.mm = get_memory_manager()
        # Create table if not exists using the shared memory manager's engine
        Base.metadata.create_all(self.mm.engine)
        self.Session = self.mm.Session

    def log_step(
        self,
        run_id: str,
        thread_id: str,
        agent: str,
        parent_trace_id: str | None = None,
        input_data: str | None = None,
        reasoning_summary: str | None = None,
        tool_called: str | None = None,
        tool_arguments: str | dict[str, Any] | None = None,
        tool_result: str | dict[str, Any] | None = None,
        latency: float | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
        status: str = "SUCCESS",
        error_message: str | None = None,
    ) -> str:
        trace_id = str(uuid4())
        
        # Serialize dict arguments or results to string
        if isinstance(tool_arguments, dict):
            tool_args_str = json.dumps(tool_arguments, sort_keys=True)
        else:
            tool_args_str = tool_arguments

        if isinstance(tool_result, dict):
            tool_res_str = json.dumps(tool_result, sort_keys=True)
        else:
            tool_res_str = tool_result

        session = self.Session()
        try:
            record = TraceRecord(
                id=trace_id,
                run_id=run_id,
                thread_id=thread_id,
                parent_trace_id=parent_trace_id,
                agent=agent,
                input_data=input_data,
                reasoning_summary=reasoning_summary,
                tool_called=tool_called,
                tool_arguments=tool_args_str,
                tool_result=tool_res_str,
                latency=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                status=status,
                error_message=error_message,
                timestamp=datetime.datetime.utcnow()
            )
            session.add(record)
            session.commit()
            return trace_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_timeline(self, thread_id: str) -> list[dict[str, Any]]:
        session = self.Session()
        try:
            records = (
                session.query(TraceRecord)
                .filter(TraceRecord.thread_id == thread_id)
                .order_by(TraceRecord.timestamp.asc(), TraceRecord.id.asc())
                .all()
            )
            
            timeline = []
            for idx, rec in enumerate(records, 1):
                agent_name = rec.agent.capitalize() if rec.agent else "Unknown"
                
                if rec.agent.lower() == "supervisor":
                    timeline.append({
                        "step": idx,
                        "agent": "Supervisor",
                        "decision": rec.tool_called or "end",
                        "reason": rec.reasoning_summary or ""
                    })
                elif rec.tool_called:
                    timeline.append({
                        "step": idx,
                        "agent": agent_name,
                        "tool": rec.tool_called
                    })
                else:
                    timeline.append({
                        "step": idx,
                        "agent": agent_name,
                        "decision": "complete",
                        "reason": rec.reasoning_summary or ""
                    })
            return timeline
        finally:
            session.close()

    def get_performance_summary(self, thread_id: str) -> dict[str, Any]:
        session = self.Session()
        try:
            records = (
                session.query(TraceRecord)
                .filter(TraceRecord.thread_id == thread_id)
                .all()
            )
            
            if not records:
                return {
                    "total_steps": 0,
                    "agents_called": [],
                    "tools_used": [],
                    "duration": 0.0,
                    "success_rate": 0.0,
                    "errors": []
                }
            
            total_steps = len(records)
            agents = list(set(r.agent for r in records if r.agent))
            tools = list(set(r.tool_called for r in records if r.tool_called))
            duration = sum(r.latency or 0.0 for r in records)
            
            success_count = sum(1 for r in records if r.status == "SUCCESS")
            success_rate = success_count / total_steps if total_steps > 0 else 0.0
            
            errors = list(set(r.error_message for r in records if r.error_message))
            
            return {
                "total_steps": total_steps,
                "agents_called": agents,
                "tools_used": tools,
                "duration": duration,
                "success_rate": success_rate,
                "errors": errors
            }
        finally:
            session.close()
