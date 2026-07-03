from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from langgraph.types import interrupt

from app.graph.state import PlatformState
from app.tools.terminal import is_dangerous_command


def _last_tool_call(state: PlatformState) -> dict[str, Any] | None:
    for message in reversed(state.get("messages", [])):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                first_call = tool_calls[0]
                return first_call if isinstance(first_call, dict) else first_call.model_dump()
    return None


def _approval_risk_level(action: str) -> str:
    normalized = action.lower()
    if "drop table" in normalized or "delete" in normalized:
        return "high"
    if "rm -rf" in normalized or "sudo" in normalized:
        return "critical"
    if is_dangerous_command(action):
        return "medium"
    return "low"


def _approval_request(state: PlatformState) -> dict[str, Any]:
    tool_call = _last_tool_call(state) or {}
    arguments = tool_call.get("arguments", {}) or {}
    action = arguments.get("command") or arguments.get("path") or state.get("current_task", state.get("user_request", ""))
    tool_name = tool_call.get("name", "unknown_tool")
    request_id = str(uuid4())

    return {
        "id": request_id,
        "action": action,
        "tool": tool_name,
        "reason": "The requested action is considered dangerous and requires human approval.",
        "risk_level": _approval_risk_level(str(action)),
    }


def safety_check_node(state: PlatformState) -> dict[str, Any]:
    print("--- safety_check_node running ---")
    tool_call = _last_tool_call(state)
    if not tool_call:
        return {"pending_approval": {}}

    arguments = tool_call.get("arguments", {}) or {}
    command = str(arguments.get("command", ""))

    if tool_call.get("name") == "execute_command" and is_dangerous_command(command):
        approval_request = _approval_request(state)
        return {
            "pending_approval": approval_request,
            "approvals_required": [approval_request["id"]]
        }
    
    return {"pending_approval": {}}


def human_approval_node(state: PlatformState) -> dict[str, Any]:
    print("--- human_approval_node running ---")
    pending = state.get("pending_approval") or {}
    if not pending:
        return {}

    decision = pending.get("decision")
    if not decision:
        decision_payload = interrupt({
            "action": pending.get("action"),
            "tool": pending.get("tool"),
            "reason": pending.get("reason"),
            "risk_level": pending.get("risk_level")
        })
        
        if isinstance(decision_payload, dict):
            if "approved" in decision_payload:
                decision = "approved" if decision_payload["approved"] else "rejected"
            else:
                decision = decision_payload.get("decision")
        elif isinstance(decision_payload, bool):
            decision = "approved" if decision_payload else "rejected"
        else:
            decision = decision_payload

    from datetime import datetime, timezone

    if decision == "approved":
        action_id = str(pending.get("id", ""))
        updated_pending = dict(pending)
        updated_pending["decision"] = "approved"
        
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "developer",
            "tool": pending.get("tool", "unknown_tool"),
            "action": pending.get("action", "unknown_action"),
            "decision": "approved",
            "reason": pending.get("reason", "The requested action is considered dangerous and requires human approval."),
        }
        
        return {
            "approved_actions": [action_id] if action_id else [],
            "messages": [
                {
                    "role": "human",
                    "content": f"Approved: {pending.get('action', '')}",
                    "name": "human_approval",
                }
            ],
            "observations": [f"Human approved action {pending.get('id', '')}"],
            "pending_approval": updated_pending,
            "approval_history": [audit_entry]
        }

    if decision == "rejected":
        action_id = str(pending.get("id", ""))
        updated_pending = dict(pending)
        updated_pending["decision"] = "rejected"
        
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "developer",
            "tool": pending.get("tool", "unknown_tool"),
            "action": pending.get("action", "unknown_action"),
            "decision": "rejected",
            "reason": pending.get("reason", "The requested action is considered dangerous and requires human approval."),
        }
        
        return {
            "rejected_actions": [action_id] if action_id else [],
            "messages": [
                {
                    "role": "human",
                    "content": f"Rejected: {pending.get('action', '')}",
                    "name": "human_approval",
                }
            ],
            "observations": [f"Human rejected action {pending.get('id', '')}"],
            "pending_approval": updated_pending,
            "approval_history": [audit_entry]
        }

    return {}


def route_after_safety(state: PlatformState) -> str:
    pending = state.get("pending_approval") or {}
    if pending:
        return "human"
    return "tools"


def route_after_human(state: PlatformState) -> str:
    pending = state.get("pending_approval") or {}
    if pending.get("decision") == "approved":
        return "tools"
    if pending.get("decision") == "rejected":
        return "developer"
    return "human"