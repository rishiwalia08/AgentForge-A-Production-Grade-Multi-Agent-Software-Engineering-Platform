from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict


def list_append(existing: list, new_items: list) -> list:
    return existing + new_items


class AgentTask(TypedDict, total=False):
    id: str
    title: str
    owner: str
    status: Literal["todo", "in_progress", "done", "blocked"]
    tool: str
    tool_args: dict[str, Any]
    thought: str


class MemorySnapshot(TypedDict, total=False):
    short_term: list[str]
    long_term: list[str]
    semantic: list[str]
    error_memory: list[dict[str, str]]


class AgentHistoryItem(TypedDict, total=False):
    agent: str
    decision: str
    reason: str
    confidence: float
    step: int


class ToolHistoryItem(TypedDict, total=False):
    tool: str
    action: str
    result: str
    requires_approval: str


class MessageItem(TypedDict, total=False):
    role: str
    content: str
    name: str
    tool_call_id: str
    tool_calls: list[dict[str, Any]]


class ToolCallItem(TypedDict, total=False):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolOutputItem(TypedDict, total=False):
    tool: str
    input: dict[str, Any]
    output: dict[str, Any]
    observation: str


class PlatformState(TypedDict, total=False):
    user_request: str
    current_task: str
    route: str
    next_agent: str
    supervisor_reason: str
    current_step: int
    pending_approval: dict[str, Any]
    approved_actions: Annotated[list[str], list_append]
    rejected_actions: Annotated[list[str], list_append]
    approval_history: Annotated[list[dict[str, Any]], list_append]
    agent_history: Annotated[list[AgentHistoryItem], list_append]
    tool_history: Annotated[list[ToolHistoryItem], list_append]
    tool_calls: Annotated[list[ToolCallItem], list_append]
    tool_outputs: Annotated[list[ToolOutputItem], list_append]
    tasks: Annotated[list[AgentTask], list_append]
    observations: Annotated[list[str], list_append]
    approvals_required: Annotated[list[str], list_append]
    errors: Annotated[list[str], list_append]
    memory: MemorySnapshot
    messages: Annotated[list[MessageItem], list_append]
    test_results: dict[str, str]
    current_error: str
    run_id: str
    parent_trace_id: str

