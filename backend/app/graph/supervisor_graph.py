from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.approval_flow import human_approval_node, route_after_human, route_after_safety, safety_check_node
from app.agents.developer_agent import DEVELOPER_TOOLS, developer_react_node, ToolNode
from app.agents.specialist_agents import (
    requirement_agent_node,
    architecture_agent_node,
    testing_agent_node,
    debugging_agent_node,
    security_agent_node,
    research_agent_node,
)
from app.graph.state import PlatformState
from app.graph import supervisor_llm


VALID_AGENT_ROUTES = {
    "requirement": "requirement_agent",
    "architecture": "architecture_agent",
    "developer": "developer_agent",
    "testing": "testing_agent",
    "debugging": "debugging_agent",
    "security": "security_agent",
    "research": "research_agent",
    "human": "human_approval",
    "end": END,
}

ROUTE_ALIASES = {
    "requirement_agent": "requirement",
    "architecture_agent": "architecture",
    "developer_agent": "developer",
    "testing_agent": "testing",
    "debugging_agent": "debugging",
    "security_agent": "security",
    "research_agent": "research",
    "human_approval": "human",
}


def _normalize_route(route: str) -> str:
    return ROUTE_ALIASES.get(route, route)


def _build_supervisor_prompt(state: PlatformState) -> str:
    task_titles = [task.get("title", "") for task in state.get("tasks", [])]
    approval_status = "pending" if state.get("approvals_required") else "clear"
    test_status = state.get("test_results", {}).get("status", "unknown")
    current_error = state.get("current_error", "")

    return (
        "You are the supervisor agent for an autonomous software engineering organization.\n"
        f"User request: {state.get('user_request', '')}\n"
        f"Current tasks: {task_titles}\n"
        f"Current error: {current_error}\n"
        f"Test status: {test_status}\n"
        f"Approval status: {approval_status}\n"
        "Choose the next specialist agent from: requirement, architecture, developer, testing, debugging, security, human, end.\n"
        "Return JSON with next_agent, reason, and confidence."
    )


def supervisor_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    print("--- supervisor_node running ---")
    import time
    from uuid import uuid4
    from app.observability import AgentTracer

    tracer = AgentTracer()
    
    # Resolve thread_id and run_id
    thread_id = "default_thread"
    if config and isinstance(config, dict) and "configurable" in config:
        thread_id = config["configurable"].get("thread_id") or "default_thread"
    elif state.get("thread_id"):
        thread_id = state["thread_id"]

    run_id = state.get("run_id") or str(uuid4())
    
    llm = supervisor_llm.get_supervisor_llm()
    prompt = _build_supervisor_prompt(state)

    start_time = time.time()
    try:
        decision = llm.with_structured_output(supervisor_llm.SupervisorDecision)(prompt)
        normalized_next_agent = _normalize_route(decision.next_agent)
        reason = decision.reason
        confidence = decision.confidence
        elapsed = time.time() - start_time
        
        # Log successful supervisor step
        trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent="supervisor",
            parent_trace_id=None,
            input_data=prompt,
            reasoning_summary=reason,
            tool_called=normalized_next_agent,
            latency=elapsed,
            status="SUCCESS"
        )
    except Exception as exc:
        elapsed = time.time() - start_time
        current_step = int(state.get("current_step", 0)) + 1
        
        # Log failed supervisor step
        trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent="supervisor",
            parent_trace_id=None,
            input_data=prompt,
            reasoning_summary=f"Supervisor LLM call failed: {exc}",
            tool_called="end",
            latency=elapsed,
            status="FAILED",
            error_message=str(exc)
        )
        
        return {
            "errors": [f"Supervisor LLM call failed: {exc}"],
            "current_error": "LLM unavailable",
            "next_agent": "end",
            "route": "end",
            "current_step": current_step,
            "run_id": run_id,
            "parent_trace_id": trace_id,
            "agent_history": [
                {
                    "agent": "supervisor",
                    "decision": "end",
                    "reason": f"Supervisor LLM failed: {exc}",
                    "confidence": 0.0,
                    "step": current_step,
                }
            ]
        }

    current_step = int(state.get("current_step", 0)) + 1
    
    agent_history_item = {
        "agent": "supervisor",
        "decision": normalized_next_agent,
        "reason": reason,
        "confidence": confidence,
        "step": current_step,
    }

    return {
        "next_agent": normalized_next_agent,
        "supervisor_reason": reason,
        "current_step": current_step,
        "route": normalized_next_agent,
        "run_id": run_id,
        "parent_trace_id": trace_id,
        "agent_history": [agent_history_item]
    }



def route_agent(state: PlatformState) -> str:
    return state.get("next_agent", "requirement")


def route_developer_tools(state: PlatformState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]
    if isinstance(last_message, dict) and last_message.get("tool_calls"):
        return "safety"
    return "end"


def build_supervisor_graph(checkpointer: Any = None) -> Any:
    graph = StateGraph(PlatformState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("requirement_agent", requirement_agent_node)
    graph.add_node("architecture_agent", architecture_agent_node)
    graph.add_node("developer_agent", developer_react_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("tools", ToolNode(DEVELOPER_TOOLS))
    graph.add_node("testing_agent", testing_agent_node)
    graph.add_node("debugging_agent", debugging_agent_node)
    graph.add_node("security_agent", security_agent_node)
    graph.add_node("research_agent", research_agent_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_agent,
        VALID_AGENT_ROUTES,
    )

    graph.add_conditional_edges(
        "developer_agent",
        route_developer_tools,
        {
            "safety": "safety_check",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "human": "human_approval",
            "tools": "tools",
        },
    )

    graph.add_conditional_edges(
        "human_approval",
        route_after_human,
        {
            "tools": "tools",
            "developer": "developer_agent",
            "human": "human_approval",
        },
    )

    graph.add_edge("tools", "developer_agent")

    static_specialists = [
        "requirement_agent",
        "architecture_agent",
        "testing_agent",
        "debugging_agent",
        "security_agent",
        "research_agent",
    ]
    for node_name in static_specialists:
        graph.add_edge(node_name, "supervisor")

    if checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
