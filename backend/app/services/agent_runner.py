from __future__ import annotations

import json
from typing import Any
from uuid import uuid4
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.graph.supervisor_graph import build_supervisor_graph
from app.db.checkpoints import DatabaseCheckpointSaver
from app.core.event_bus import event_manager
from app.db.session import SessionLocal
from app.db.repositories import DatabaseRepository

class AgentRunner:
    @staticmethod
    def run(run_id: str, thread_id: str, task: str) -> None:
        """Executes the LangGraph agent graph synchronously and publishes updates to EventManager."""
        checkpointer = DatabaseCheckpointSaver()
        graph = build_supervisor_graph(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}
        
        # Build initial state
        initial_state = {
            "user_request": task,
            "current_task": task,
            "run_id": run_id,
            "thread_id": thread_id,
            "messages": [{"role": "user", "content": task}]
        }

        db = SessionLocal()
        try:
            # Update database status to running
            DatabaseRepository.update_run(db, run_id, status="running")
            DatabaseRepository.update_thread(db, thread_id, status="running")
            
            # Start streaming nodes execution
            for event in graph.stream(initial_state, config, stream_mode="updates"):
                # Parse node updates
                for node_name, node_update in event.items():
                    # Update thread's active node
                    DatabaseRepository.update_thread(db, thread_id, current_node=node_name)
                    
                    # 1. Publish Thinking Steps
                    if "agent_history" in node_update and node_update["agent_history"]:
                        history_item = node_update["agent_history"][-1]
                        event_manager.publish(run_id, {
                            "type": "agent_step",
                            "agent": history_item.get("agent", node_name),
                            "content": history_item.get("reason", "")
                        })

                    # 2. Publish Tool Invocations
                    if "tool_calls" in node_update and node_update["tool_calls"]:
                        event_manager.publish(run_id, {
                            "type": "tool_call",
                            "agent": "developer",
                            "payload": node_update["tool_calls"]
                        })

                    # 3. Publish Human Interrupt Event
                    if "approvals_required" in node_update and node_update["approvals_required"]:
                        DatabaseRepository.update_run(db, run_id, status="interrupted")
                        DatabaseRepository.update_thread(db, thread_id, status="interrupted")
                        event_manager.publish(run_id, {
                            "type": "approval_required",
                            "payload": {
                                "tools": node_update["approvals_required"],
                                "run_id": run_id
                            }
                        })

                    # 4. Publish Errors
                    if "errors" in node_update and node_update["errors"]:
                        event_manager.publish(run_id, {
                            "type": "error",
                            "payload": node_update["errors"]
                        })
            
            # Successful completion
            # Verify if run is interrupted
            run_record = DatabaseRepository.get_run(db, run_id)
            if run_record and run_record.status != "interrupted":
                DatabaseRepository.update_run(db, run_id, status="success")
                DatabaseRepository.update_thread(db, thread_id, status="success")
                
                # Fetch final state to save
                state_val = graph.get_state(config)
                if state_val and state_val.values:
                    DatabaseRepository.update_run(db, run_id, final_state=state_val.values)
                    
                event_manager.publish(run_id, {
                    "type": "completed",
                    "payload": {"status": "success"}
                })
        except Exception as exc:
            DatabaseRepository.update_run(db, run_id, status="failed", error=str(exc))
            DatabaseRepository.update_thread(db, thread_id, status="failed", last_error=str(exc))
            event_manager.publish(run_id, {
                "type": "error",
                "payload": [str(exc)]
            })
            event_manager.publish(run_id, {
                "type": "completed",
                "payload": {"status": "failed", "error": str(exc)}
            })
        finally:
            db.close()

    @staticmethod
    def resume(run_id: str, thread_id: str, approved: bool, feedback: str | None = None) -> None:
        """Resumes a paused LangGraph agent run using Command(resume) feedback."""
        checkpointer = DatabaseCheckpointSaver()
        graph = build_supervisor_graph(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": thread_id}}
        
        decision_val = "approved" if approved else "rejected"
        resume_payload = {"decision": decision_val}
        if feedback:
            resume_payload["feedback"] = feedback

        db = SessionLocal()
        try:
            # Update database status to running
            DatabaseRepository.update_run(db, run_id, status="running")
            DatabaseRepository.update_thread(db, thread_id, status="running")
            
            # Resume graph execution using Command
            command = Command(resume=resume_payload)
            
            # Start streaming nodes from resume command
            for event in graph.stream(command, config, stream_mode="updates"):
                for node_name, node_update in event.items():
                    DatabaseRepository.update_thread(db, thread_id, current_node=node_name)
                    
                    if "agent_history" in node_update and node_update["agent_history"]:
                        history_item = node_update["agent_history"][-1]
                        event_manager.publish(run_id, {
                            "type": "agent_step",
                            "agent": history_item.get("agent", node_name),
                            "content": history_item.get("reason", "")
                        })

                    if "tool_calls" in node_update and node_update["tool_calls"]:
                        event_manager.publish(run_id, {
                            "type": "tool_call",
                            "agent": "developer",
                            "payload": node_update["tool_calls"]
                        })

                    if "approvals_required" in node_update and node_update["approvals_required"]:
                        DatabaseRepository.update_run(db, run_id, status="interrupted")
                        DatabaseRepository.update_thread(db, thread_id, status="interrupted")
                        event_manager.publish(run_id, {
                            "type": "approval_required",
                            "payload": {
                                "tools": node_update["approvals_required"],
                                "run_id": run_id
                            }
                        })

                    if "errors" in node_update and node_update["errors"]:
                        event_manager.publish(run_id, {
                            "type": "error",
                            "payload": node_update["errors"]
                        })

            # Successful completion
            run_record = DatabaseRepository.get_run(db, run_id)
            if run_record and run_record.status != "interrupted":
                DatabaseRepository.update_run(db, run_id, status="success")
                DatabaseRepository.update_thread(db, thread_id, status="success")
                
                state_val = graph.get_state(config)
                if state_val and state_val.values:
                    DatabaseRepository.update_run(db, run_id, final_state=state_val.values)
                    
                event_manager.publish(run_id, {
                    "type": "completed",
                    "payload": {"status": "success"}
                })
        except Exception as exc:
            DatabaseRepository.update_run(db, run_id, status="failed", error=str(exc))
            DatabaseRepository.update_thread(db, thread_id, status="failed", last_error=str(exc))
            event_manager.publish(run_id, {
                "type": "error",
                "payload": [str(exc)]
            })
            event_manager.publish(run_id, {
                "type": "completed",
                "payload": {"status": "failed", "error": str(exc)}
            })
        finally:
            db.close()
