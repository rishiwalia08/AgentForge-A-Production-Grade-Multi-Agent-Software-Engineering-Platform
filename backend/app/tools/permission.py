from __future__ import annotations

from dataclasses import dataclass, field
import contextvars
from typing import Any

@dataclass
class ToolExecutionContext:
    agent_id: str
    run_id: str
    user_id: str
    permissions: list[str] = field(default_factory=list)
    workspace: str | None = None

active_context = contextvars.ContextVar[ToolExecutionContext | None]("active_context", default=None)

class ToolPermissionManager:
    # RBAC matrix for agents
    POLICY = {
        "research_agent": {"read_file", "search_knowledge", "git_status", "git_diff"},
        "developer_agent": {"read_file", "create_file", "update_file", "execute_command", 
                            "git_status", "git_diff", "git_create_branch", "git_commit", "git_rollback", 
                            "search_knowledge", "run_tests", "create_agent_checkpoint", "restore_agent_checkpoint"},
        "testing_agent": {"git_status", "git_diff", "run_tests"},
        "debugging_agent": {"read_file", "git_status", "git_diff"},
        "security_agent": {"read_file", "git_status", "git_diff"},
        "requirement_agent": {"read_file", "git_status", "git_diff"},
        "architecture_agent": {"read_file", "git_status", "git_diff"},
    }

    @classmethod
    def check_permission(cls, tool_name: str, tool_args: dict[str, Any] | None = None) -> bool:
        context = active_context.get()
        if context is None:
            # If no context is set (e.g. running outside agent loop), allow it
            return True
            
        agent_id = context.agent_id
        if agent_id not in cls.POLICY:
            return False
            
        allowed_tools = cls.POLICY[agent_id]
        if tool_name not in allowed_tools:
            return False
            
        return True
