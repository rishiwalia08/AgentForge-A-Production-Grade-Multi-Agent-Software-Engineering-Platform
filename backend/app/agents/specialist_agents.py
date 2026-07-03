from __future__ import annotations

from typing import Any
import json
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.graph.supervisor_llm import StructuredOllamaSupervisorLLM
from app.graph.state import PlatformState
from app.services.memory import get_memory_manager


# --- Structured Output Schemas ---

class RequirementAgentOutput(BaseModel):
    requirements: list[str] = Field(..., description="List of requirements gathered")
    scope: str = Field(..., description="Scope statement")
    next_steps: list[str] = Field(..., description="Recommended next steps")


class ArchitectureAgentOutput(BaseModel):
    architecture_plan: str = Field(..., description="High-level architecture design")
    services: list[str] = Field(..., description="List of backend services")
    database_design: str = Field(..., description="Database schema/tables design")
    next_steps: list[str] = Field(..., description="Next steps for development")


class TestingAgentOutput(BaseModel):
    test_status: str = Field(..., description="Status of the tests: success or failed")
    errors: list[str] = Field(..., description="List of test errors if any")


class DebuggingAgentOutput(BaseModel):
    root_cause: str = Field(..., description="Identified root cause of the error")
    fix_plan: str = Field(..., description="Plan to fix the bug")


class SecurityAgentOutput(BaseModel):
    risk_level: str = Field(..., description="Overall risk level: low, medium, high, critical")
    reason: str = Field(..., description="Detailed explanation of the risk assessment")
    requires_human_approval: bool = Field(..., description="Whether this action requires human interrupt approval")
    vulnerabilities: list[str] = Field(default_factory=list, description="List of identified vulnerabilities")
    mitigation_plan: str = Field("", description="Action plan to mitigate security issues")


class ResearchAgentOutput(BaseModel):
    summary: str = Field(..., description="Summary of relevant codebase utilities or documentation found")
    relevant_files: list[str] = Field(..., description="List of files containing matching symbols")
    solution_context: str = Field(..., description="Context for other agents on how to use existing modules")


# --- Client Helper ---

def _get_specialist_llm() -> StructuredOllamaSupervisorLLM:
    settings = get_settings()
    return StructuredOllamaSupervisorLLM(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )


def _execute_specialist_node(
    state: PlatformState, 
    schema: type[BaseModel], 
    agent_name: str, 
    state_key: str,
    config: Any = None
) -> dict[str, Any]:
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
    llm = _get_specialist_llm()
    
    # Establish Context
    context = ToolExecutionContext(
        agent_id=agent_name,
        run_id=run_id,
        user_id="Rishi",
        workspace="/Users/rishiwalia/Desktop/agentic ai"
    )
    token = active_context.set(context)
    
    try:
        # Retrieve relevant memories
        mm = get_memory_manager()
        
        user_mems = mm.retrieve_memory("user", user_id="Rishi")
        proj_mems = mm.retrieve_memory("project", project_id="AI platform")
        
        task_str = state.get("current_task") or state.get("user_request", "")
        semantic_mems = mm.search_memory(task_str, limit=3)
        
        # If agent is debugging_agent, retrieve error memories
        error_context = ""
        if agent_name == "debugging_agent" and state.get("current_error"):
            err_mems = mm.retrieve_memory("error", query=state["current_error"])
            error_context = "\n".join(f"- Error: {m['error']}\n  Cause: {m['cause']}\n  Solution: {m['solution']}" for m in err_mems)

        memory_injection = (
            "=== RETRIEVED AGENT MEMORY ===\n"
            f"User Preferences:\n" + "\n".join(f"- {m['content']}" for m in user_mems) + "\n\n"
            f"Project Context:\n" + "\n".join(f"- {m['content']}" for m in proj_mems) + "\n\n"
            f"Similar Past Solutions:\n" + "\n".join(f"- {m['text']}" for m in semantic_mems) + "\n\n"
            f"Relevant Error Fixes:\n{error_context or 'None'}\n"
            "============================="
        )
        
        rag_context = ""
        if agent_name == "research_agent":
            from app.knowledge.retriever import KnowledgeBase
            kb_rag = KnowledgeBase()
            rag_results = kb_rag.search(task_str, limit=5)
            if rag_results.get("matches"):
                rag_context = "\n".join(
                    f"- File: {m['file_path']} (lines {m['line_start']}-{m['line_end']})\n"
                    f"  Symbol: {m['symbol'] or 'None'} (score: {m['score']})\n"
                    f"  Content:\n{m['content']}"
                    for m in rag_results["matches"]
                )
                
        prompt = (
            f"{memory_injection}\n\n"
            "=== RETRIEVED CODEBASE KNOWLEDGE (RAG) ===\n"
            f"{rag_context or 'No relevant code/docs found.'}\n"
            "==========================================\n\n"
            f"You are the {agent_name} in an autonomous software engineering organization.\n"
            f"User request: {state.get('user_request', '')}\n"
            f"Current error: {state.get('current_error', '')}\n"
            f"Observations: {state.get('observations', [])}\n"
            f"Perform your analysis and return JSON matching the schema."
        )

        start_time = time.time()
        decision = llm.with_structured_output(schema)(prompt)
        output_dict = decision.model_dump()
        elapsed = time.time() - start_time
        
        # Determine RAG tool call logging for research agent
        tool_called = "search_knowledge" if (agent_name == "research_agent" and rag_context) else None
        tool_result = rag_context if tool_called else None
        
        trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent=agent_name,
            parent_trace_id=parent_trace_id,
            input_data=prompt,
            reasoning_summary=json.dumps(output_dict, sort_keys=True),
            tool_called=tool_called,
            tool_result=tool_result,
            latency=elapsed,
            status="SUCCESS"
        )
        
        # Save useful learnings after successful execution
        if agent_name == "requirement_agent":
            mm.store_memory(
                category="project",
                content=f"Requirements gathered for: {task_str}\nScope: {output_dict.get('scope')}",
                metadata={"project_id": "AI platform", "memory_type": "requirements"}
            )
        elif agent_name == "architecture_agent":
            mm.store_memory(
                category="project",
                content=f"Architecture plan for: {task_str}\nPlan: {output_dict.get('architecture_plan')}",
                metadata={"project_id": "AI platform", "memory_type": "architecture"}
            )
        elif agent_name == "debugging_agent":
            mm.store_memory(
                category="error",
                content=state.get("current_error") or "Unknown error",
                metadata={
                    "cause": output_dict.get("root_cause", ""),
                    "solution": output_dict.get("fix_plan", ""),
                    "file_changed": "developer"
                },
                cause=output_dict.get("root_cause", ""),
                solution=output_dict.get("fix_plan", ""),
                file_changed="developer"
            )

        # Append an entry to the agent history
        agent_history_item = {
            "agent": agent_name,
            "decision": "complete",
            "reason": f"{agent_name} analysis complete.",
            "confidence": 1.0,
            "step": current_step,
        }
        
        return {
            "current_step": current_step,
            "agent_history": [agent_history_item],
            state_key: output_dict,
            "run_id": run_id,
            "parent_trace_id": trace_id
        }
    except Exception as exc:
        elapsed = time.time() - start_time
        trace_id = tracer.log_step(
            run_id=run_id,
            thread_id=thread_id,
            agent=agent_name,
            parent_trace_id=parent_trace_id,
            input_data=prompt if 'prompt' in locals() else agent_name,
            reasoning_summary=f"{agent_name} failed: {exc}",
            latency=elapsed,
            status="FAILED",
            error_message=str(exc)
        )
        return {
            "errors": [f"{agent_name} LLM call failed: {exc}"],
            "current_error": f"{agent_name} failed",
            "current_step": current_step,
            "run_id": run_id,
            "parent_trace_id": trace_id
        }
    finally:
        active_context.reset(token)


# --- Node Handlers ---

def requirement_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    return _execute_specialist_node(state, RequirementAgentOutput, "requirement_agent", "requirement_output", config=config)


def architecture_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    return _execute_specialist_node(state, ArchitectureAgentOutput, "architecture_agent", "architecture_output", config=config)


def testing_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    print("--- testing_agent_node running ---")
    from app.tools.permission import ToolExecutionContext, active_context
    from app.tools.testing import run_tests
    from uuid import uuid4
    
    run_id = state.get("run_id") or str(uuid4())
    context = ToolExecutionContext(
        agent_id="testing_agent",
        run_id=run_id,
        user_id="Rishi",
        workspace="/Users/rishiwalia/Desktop/agentic ai"
    )
    token = active_context.set(context)
    
    try:
        # 1. Run real tests using restricted TestRunnerTool
        req_lower = state.get("user_request", "").lower()
        framework = "pytest"
        if "vitest" in req_lower:
            framework = "vitest"
        elif "npm test" in req_lower or "npm run test" in req_lower:
            framework = "npm test"
            
        target = None
        # Extract specific file if mentioned
        for word in req_lower.split():
            if "backend/tests/" in word or "test_" in word:
                target = word
                break
                
        test_run = run_tests(framework=framework, target=target)
        
        # 2. Capture outputs
        test_status = test_run.get("status", "failed")
        stdout = test_run.get("stdout", "")
        stderr = test_run.get("stderr", "")
        failures = []
        if test_status != "success":
            failures.append(stderr or stdout or "Test failed")
            
        test_results = {
            "status": test_status,
            "stdout": stdout,
            "stderr": stderr,
            "failures": "\n".join(failures)
        }
        
        # 3. Use LLM reasoning to summarize and validate results
        state_copy = dict(state)
        state_copy["test_results"] = test_results
        if test_status != "success":
            state_copy["current_error"] = stderr or stdout or "Test suite failed"
            
        node_res = _execute_specialist_node(
            state_copy,
            TestingAgentOutput,
            "testing_agent",
            "testing_output",
            config=config
        )
        
        # Merge physical outputs back
        node_res["test_results"] = test_results
        if test_status != "success":
            node_res["current_error"] = stderr or stdout or "Test suite failed"
            
        return node_res
    finally:
        active_context.reset(token)


def debugging_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    return _execute_specialist_node(state, DebuggingAgentOutput, "debugging_agent", "debugging_output", config=config)


def security_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    print("--- security_agent_node running ---")
    from app.tools.terminal import is_dangerous_command
    
    # 1. Run static check
    user_req = state.get("user_request", "")
    current_task = state.get("current_task", "")
    
    is_static_dangerous = is_dangerous_command(user_req) or is_dangerous_command(current_task)
    
    # 2. Run normal LLM security evaluation
    node_res = _execute_specialist_node(
        state,
        SecurityAgentOutput,
        "security_agent",
        "security_output",
        config=config
    )
    
    # 3. Merge static/permission policies with LLM assessment (Hybrid Check)
    if "security_output" in node_res:
        sec_out = node_res["security_output"]
        
        if is_static_dangerous:
            sec_out["risk_level"] = "critical"
            sec_out["requires_human_approval"] = True
            sec_out["reason"] = f"[STATIC RULE TRIGGERED] Action matched dangerous policy. LLM reasoning: {sec_out.get('reason', '')}"
            sec_out["vulnerabilities"].append("Matched dangerous terminal command substrings")
            
        # Permission check
        next_agent = state.get("next_agent", "")
        if next_agent == "testing" and "write_file" in user_req:
            sec_out["risk_level"] = "high"
            sec_out["requires_human_approval"] = True
            sec_out["reason"] = f"[POLICY VIOLATION] Testing agent is not allowed to modify files. LLM reasoning: {sec_out.get('reason', '')}"
            
        node_res["security_output"] = sec_out
        
    return node_res


def research_agent_node(state: PlatformState, config: Any = None) -> dict[str, Any]:
    return _execute_specialist_node(state, ResearchAgentOutput, "research_agent", "research_output", config=config)
