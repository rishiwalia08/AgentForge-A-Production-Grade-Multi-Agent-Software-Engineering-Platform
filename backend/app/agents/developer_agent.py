from __future__ import annotations

from typing import Any

from langgraph.prebuilt import ToolNode as OfficialToolNode
import json
from app.services.memory_manager import get_memory_manager

class ToolNode(OfficialToolNode):
    def invoke(self, state: dict[str, Any], config: Any = None) -> dict[str, Any]:
        print("--- ToolNode.invoke running ---")
        import time
        from uuid import uuid4
        from app.observability import AgentTracer
        from app.tools.permission import ToolExecutionContext, active_context, ToolPermissionManager
        
        tracer = AgentTracer()
        
        thread_id = "default_thread"
        if config and isinstance(config, dict) and "configurable" in config:
            thread_id = config["configurable"].get("thread_id") or "default_thread"
        elif state.get("thread_id"):
            thread_id = state["thread_id"]

        run_id = state.get("run_id") or str(uuid4())

        # Setup context
        context = ToolExecutionContext(
            agent_id="developer_agent",
            run_id=run_id,
            user_id="Rishi",
            workspace="/Users/rishiwalia/Desktop/agentic ai"
        )
        token = active_context.set(context)

        messages = state.get("messages", [])
        if not messages:
            active_context.reset(token)
            return {}

        tool_calls = []
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]
                break
            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls = msg.tool_calls
                break

        if not tool_calls:
            active_context.reset(token)
            return {}

        new_messages = []
        new_tool_outputs = []
        new_tool_history = []
        new_observations = []
        new_approvals_required = []
        new_errors = []

        try:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("arguments") or {}
                tool_id = tool_call.get("id") or ""
                
                tool = self.tools_by_name.get(tool_name)
                if tool is None:
                    raise ValueError(f"Unknown tool: {tool_name}")
                    
                start_time = time.time()
                status = "SUCCESS"
                error_msg = None
                try:
                    # Check permission
                    if not ToolPermissionManager.check_permission(tool_name, tool_args):
                        raise PermissionError(f"Permission Denied: Agent 'developer_agent' is not authorized to call tool '{tool_name}'.")
                    
                    result = tool.func(**tool_args)
                    elapsed = time.time() - start_time
                    observation = result.get("stdout") or result.get("content") or result.get("stderr") or result.get("status", "")
                    
                    # Check for failure indications in returned result dict
                    if isinstance(result, dict) and (result.get("stderr") or "error" in str(result.get("status", "")).lower()):
                        status = "FAILED"
                        error_msg = result.get("stderr") or result.get("content") or "Tool failed"
                except Exception as exc:
                    elapsed = time.time() - start_time
                    status = "FAILED"
                    error_msg = str(exc)
                    result = {"status": "error", "stderr": error_msg, "stdout": ""}
                    observation = error_msg

                # Log tool step under developer agent, child of developer node
                tracer.log_step(
                    run_id=run_id,
                    thread_id=thread_id,
                    agent="developer",
                    parent_trace_id=state.get("parent_trace_id"),
                    input_data=json.dumps(tool_args, sort_keys=True),
                    reasoning_summary=f"Executing tool: {tool_name}",
                    tool_called=tool_name,
                    tool_arguments=tool_args,
                    tool_result=result,
                    latency=elapsed,
                    status=status,
                    error_message=error_msg
                )
                
                new_tool_outputs.append({
                    "tool": tool_name,
                    "input": tool_args,
                    "output": result,
                    "observation": observation
                })
                new_tool_history.append({
                    "tool": tool_name,
                    "action": json.dumps(tool_args, sort_keys=True),
                    "result": json.dumps(result, sort_keys=True),
                    "requires_approval": str(bool(result.get("requires_approval"))),
                })
                new_messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": str(observation),
                })
                new_observations.append(str(observation))
                
                if result.get("requires_approval"):
                    new_approvals_required.append(tool_name)
                stderr = result.get("stderr")
                if stderr:
                    new_errors.append(str(stderr))
        finally:
            active_context.reset(token)

        return {
            "messages": new_messages,
            "tool_outputs": new_tool_outputs,
            "tool_history": new_tool_history,
            "observations": new_observations,
            "errors": new_errors,
            "approvals_required": new_approvals_required
        }


from app.agents import developer_llm

from app.agents.developer_llm import DeveloperTurn, ToolCall
from app.graph.state import PlatformState
from app.tools import (
    create_file, read_file, update_file, execute_command,
    git_status, git_diff, git_create_branch, git_commit, create_agent_checkpoint, restore_agent_checkpoint,
    run_tests
)
from app.knowledge.retriever import search_knowledge

DEVELOPER_TOOLS = [
    create_file, read_file, update_file, execute_command, search_knowledge,
    git_status, git_diff, git_create_branch, git_commit, create_agent_checkpoint, restore_agent_checkpoint,
    run_tests
]


def _append_message(state: PlatformState, role: str, content: str, **extra: Any) -> None:
    state["messages"].append({"role": role, "content": content, **extra})


def _ensure_state(state: PlatformState) -> None:
    state.setdefault("messages", [])
    state.setdefault("tool_calls", [])
    state.setdefault("tool_outputs", [])
    state.setdefault("tool_history", [])
    state.setdefault("agent_history", [])
    state.setdefault("observations", [])
    state.setdefault("approvals_required", [])
    state.setdefault("errors", [])
    state.setdefault("current_task", state.get("current_task", state.get("user_request", "")))


def _message(role: str, content: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": role, "content": content}
    payload.update(extra)
    return payload


def _normalize_turn(turn: Any) -> DeveloperTurn:
    if isinstance(turn, DeveloperTurn):
        return turn
    if hasattr(turn, "model_dump"):
        return DeveloperTurn.model_validate(turn.model_dump())
    if isinstance(turn, dict):
        return DeveloperTurn.model_validate(turn)
    raise TypeError(f"Unsupported developer turn type: {type(turn)!r}")


def _tool_calls_from_turn(turn: DeveloperTurn) -> list[dict[str, Any]]:
    return [call.model_dump() if hasattr(call, "model_dump") else call.dict() for call in turn.tool_calls]


def _append_final_history(state: PlatformState, final_content: str) -> None:
    current_step = int(state.get("current_step", 0))
    state["agent_history"].append(
        {
            "agent": "developer",
            "decision": "complete",
            "reason": final_content or "No further tool use required.",
            "confidence": 1.0,
            "step": current_step,
        }
    )


def developer_node(state: PlatformState) -> dict[str, Any]:
    current_step = int(state.get("current_step", 0)) + 1
    
    local_messages = list(state.get("messages") or [])
    new_messages = []
    new_tool_calls = []
    
    if not local_messages or local_messages[-1].get("role") != "user":
        user_msg = {"role": "user", "content": state.get("current_task") or state.get("user_request", "")}
        local_messages.append(user_msg)
        new_messages.append(user_msg)

    local_state = dict(state)
    local_state["messages"] = local_messages
    local_state["tool_calls"] = list(state.get("tool_calls") or [])
    local_state["tool_outputs"] = []
    local_state["tool_history"] = []
    local_state["observations"] = []
    local_state["errors"] = []
    local_state["approvals_required"] = []

    try:
        bound_llm = developer_llm.get_developer_llm().bind_tools(DEVELOPER_TOOLS)
    except Exception as exc:
        return {
            "errors": [f"Developer LLM init failed: {exc}"],
            "current_error": "LLM unavailable"
        }

    tool_node = ToolNode(DEVELOPER_TOOLS)

    max_iterations = 6
    final_content = ""

    for _ in range(max_iterations):
        try:
            turn = _normalize_turn(bound_llm.invoke(local_state["messages"]))
            turn_tool_calls = _tool_calls_from_turn(turn)
        except Exception as exc:
            return {
                "errors": [f"Developer LLM invoke failed: {exc}"],
                "current_error": "LLM unavailable"
            }

        ast_msg = {"role": "assistant", "content": turn.content, "tool_calls": turn_tool_calls}
        local_state["messages"].append(ast_msg)
        new_messages.append(ast_msg)
        new_tool_calls.extend(turn_tool_calls)

        if not turn_tool_calls:
            final_content = turn.content
            break

        tool_updates = tool_node.invoke(local_state)
        for k, v in tool_updates.items():
            if k in ["messages", "tool_calls", "tool_outputs", "tool_history", "observations", "errors", "approvals_required"]:
                local_state.setdefault(k, []).extend(v)
            else:
                local_state[k] = v
        
        final_content = turn.content

    agent_history_item = {
        "agent": "developer",
        "decision": "complete",
        "reason": final_content or "No further tool use required.",
        "confidence": 1.0,
        "step": current_step,
    }

    return {
        "current_step": current_step,
        "messages": new_messages,
        "tool_calls": new_tool_calls,
        "tool_outputs": local_state["tool_outputs"],
        "tool_history": local_state["tool_history"],
        "observations": local_state["observations"],
        "errors": local_state["errors"],
        "approvals_required": local_state["approvals_required"],
        "agent_history": [agent_history_item]
    }
def developer_react_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    """Phase 6 developer node: think, choose tools, and wait for ToolNode/safety flow."""
    print("--- developer_react_node running ---")
    import time
    from uuid import uuid4
    from app.observability import AgentTracer
    from app.tools.permission import ToolExecutionContext, active_context

    tracer = AgentTracer()

    thread_id = "default_thread"
    if config and isinstance(config, dict) and "configurable" in config:
        thread_id = config["configurable"].get("thread_id") or "default_thread"
    elif state.get("thread_id"):
        thread_id = state["thread_id"]

    run_id = state.get("run_id") or str(uuid4())
    parent_trace_id = state.get("parent_trace_id")

    current_step = int(state.get("current_step", 0)) + 1
    
    # Set context
    context = ToolExecutionContext(
        agent_id="developer_agent",
        run_id=run_id,
        user_id="Rishi",
        workspace="/Users/rishiwalia/Desktop/agentic ai"
    )
    token = active_context.set(context)
    
    updates: dict[str, Any] = {
        "current_step": current_step,
        "messages": [],
        "tool_calls": [],
        "agent_history": [],
        "run_id": run_id,
    }

    # Retrieve memories
    mm = get_memory_manager()

    user_mems = mm.retrieve_memory("user", user_id="Rishi")
    proj_mems = mm.retrieve_memory("project", project_id="AI platform")
    
    task_str = state.get("current_task") or state.get("user_request", "")
    semantic_mems = mm.search_memory(task_str, limit=3)
    
    error_context = ""
    curr_err = state.get("current_error", "")
    if curr_err:
        err_mems = mm.retrieve_memory("error", query=curr_err)
        error_context = "\n".join(f"- Error: {m['error']}\n  Cause: {m['cause']}\n  Solution: {m['solution']}" for m in err_mems)

    # Retrieve RAG knowledge
    from app.knowledge.retriever import KnowledgeBase
    kb = KnowledgeBase()
    rag_results = kb.search(task_str, limit=3)
    
    # Compress context and avoid overflow by formatting compact matches
    knowledge_context = ""
    if rag_results.get("matches"):
        knowledge_context = "\n".join(
            f"- File: {m['file_path']} (lines {m['line_start']}-{m['line_end']})\n"
            f"  Symbol: {m['symbol'] or 'None'} (score: {m['score']})\n"
            f"  Content:\n{m['content']}"
            for m in rag_results["matches"]
        )

    memory_injection = (
        "=== RETRIEVED AGENT MEMORY ===\n"
        f"User Preferences:\n" + "\n".join(f"- {m['content']}" for m in user_mems) + "\n\n"
        f"Project Context:\n" + "\n".join(f"- {m['content']}" for m in proj_mems) + "\n\n"
        f"Similar Past Solutions:\n" + "\n".join(f"- {m['text']}" for m in semantic_mems) + "\n\n"
        f"Relevant Error Fixes:\n{error_context or 'None'}\n"
        "=============================\n\n"
        "=== RETRIEVED CODEBASE KNOWLEDGE (RAG) ===\n"
        f"{knowledge_context or 'No relevant code/docs found.'}\n"
        "=========================================="
    )

    messages_for_llm = list(state.get("messages") or [])
    if not messages_for_llm or messages_for_llm[-1].get("role") != "user":
        user_msg = {"role": "user", "content": state.get("current_task") or state.get("user_request", "")}
        updates["messages"].append(user_msg)
        messages_for_llm.append(user_msg)

    # Prepend retrieved memories to messages list for LLM context
    messages_for_llm_with_memory = [{"role": "system", "content": memory_injection}] + messages_for_llm

    start_time = time.time()
    try:
        bound_llm = developer_llm.get_developer_llm().bind_tools(DEVELOPER_TOOLS)
        turn = _normalize_turn(bound_llm.invoke(messages_for_llm_with_memory))
        turn_tool_calls = _tool_calls_from_turn(turn)
        elapsed = time.time() - start_time
        
        tool_called = turn_tool_calls[0].get("name") if turn_tool_calls else None
        tool_args = turn_tool_calls[0].get("arguments") if turn_tool_calls else None
        
        # Log successful developer turn
        dev_trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent="developer",
            parent_trace_id=parent_trace_id,
            input_data=task_str,
            reasoning_summary=turn.content or "Developer reasoning...",
            tool_called=tool_called,
            tool_arguments=tool_args,
            latency=elapsed,
            status="SUCCESS"
        )
    except Exception as exc:
        elapsed = time.time() - start_time
        dev_trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent="developer",
            parent_trace_id=parent_trace_id,
            input_data=task_str,
            reasoning_summary=f"Developer LLM call failed: {exc}",
            latency=elapsed,
            status="FAILED",
            error_message=str(exc)
        )
        active_context.reset(token)
        return {
            "errors": [f"Developer LLM failed: {exc}"],
            "current_error": "LLM unavailable",
            "run_id": run_id,
            "parent_trace_id": dev_trace_id
        }

    assistant_msg = {"role": "assistant", "content": turn.content, "tool_calls": turn_tool_calls}
    updates["messages"].append(assistant_msg)
    updates["tool_calls"].extend(turn_tool_calls)
    updates["parent_trace_id"] = dev_trace_id

    updates["agent_history"].append(
        {
            "agent": "developer",
            "decision": "tool_call" if turn_tool_calls else "complete",
            "reason": turn.content or "Developer reasoning complete.",
            "confidence": 1.0,
            "step": current_step,
        }
    )

    # Store meaningful learning on task completion
    if not turn_tool_calls:
        mm.store_memory(
            category="semantic",
            content=f"Task: {task_str}\nSolution: {turn.content}",
            metadata={"agent": "developer", "task": task_str}
        )

    active_context.reset(token)
    return updates