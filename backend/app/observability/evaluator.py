from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.graph.supervisor_llm import StructuredOllamaSupervisorLLM
from app.observability.tracer import AgentTracer
from app.observability.models import TraceRecord

class LLMJudgeOutput(BaseModel):
    score: int = Field(..., ge=0, le=10, description="Overall score from 0 to 10")
    issues: list[str] = Field(default_factory=list, description="Issues found during run")
    improvement: str = Field(default="", description="Suggestion for improvement")
    task_success: float = Field(default=1.0, ge=0.0, le=1.0)
    tool_accuracy: float = Field(default=1.0, ge=0.0, le=1.0)
    retrieval_quality: float = Field(default=1.0, ge=0.0, le=1.0)


class AgentEvaluator:
    def __init__(self, tracer: AgentTracer | None = None) -> None:
        self.tracer = tracer or AgentTracer()

    def evaluate(
        self,
        thread_id: str,
        task: str,
        final_result: str,
        state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        state = state or {}
        
        # 1. Compute Rule-based Metrics
        session = self.tracer.Session()
        try:
            records = (
                session.query(TraceRecord)
                .filter(TraceRecord.thread_id == thread_id)
                .all()
            )
        finally:
            session.close()

        total_steps = len(records)
        tool_failures = sum(1 for r in records if r.status == "FAILED" or r.error_message)
        
        # Count human interventions: human agent or approval nodes
        human_intervention_count = sum(
            1 for r in records 
            if r.agent.lower() in ("human", "human_approval", "human_approval_node")
        )
        # Fallback to state checks if traces don't show it explicitly
        if human_intervention_count == 0 and "approval_history" in state:
            human_intervention_count = len(state["approval_history"])

        # Count developer retries (routing decisions back to developer agent)
        developer_count = sum(1 for r in records if r.agent.lower() == "developer" and not r.tool_called)
        number_of_retries = max(0, developer_count - 1)

        # Test status
        test_results = state.get("test_results") or {}
        test_status = test_results.get("status") if isinstance(test_results, dict) else "unknown"
        if not test_status and "errors" in state and state.get("errors"):
            test_status = "failed"
        test_passed = (test_status == "success" or test_status == "passed")

        # Execution time
        execution_time = sum(r.latency or 0.0 for r in records)

        rule_metrics = {
            "number_of_retries": number_of_retries,
            "tool_failures": tool_failures,
            "test_passed": test_passed,
            "human_intervention_count": human_intervention_count,
            "execution_time": execution_time,
        }

        # 2. Compile Agent Actions for LLM Judge
        timeline = self.tracer.get_timeline(thread_id)
        timeline_str = "\n".join(
            f"- Step {s.get('step')}: Agent={s.get('agent')} Routing/Tool={s.get('tool') or s.get('decision')} Reason={s.get('reason', '')}"
            for s in timeline
        )

        # 3. Invoke LLM Judge
        settings = get_settings()
        llm = StructuredOllamaSupervisorLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

        prompt = (
            "You are an expert AI Agent Evaluator. Evaluate the quality of the multi-agent run.\n"
            f"Original Task: {task}\n"
            f"Execution Timeline:\n{timeline_str or 'No execution history.'}\n"
            f"Final Result: {final_result}\n\n"
            "Return JSON matching the LLMJudgeOutput schema."
        )

        try:
            judge_response = llm.with_structured_output(LLMJudgeOutput)(prompt)
            judge_data = judge_response.model_dump()
        except Exception:
            # Fallback evaluation logic if Ollama is unavailable
            score = 10
            issues = []
            if tool_failures > 0:
                score -= min(4, tool_failures * 2)
                issues.append(f"Encountered {tool_failures} tool failure(s).")
            if number_of_retries > 1:
                score -= 1
                issues.append(f"Required {number_of_retries} developer retries.")
            if not test_passed and (test_status == "failed" or state.get("errors")):
                score -= 3
                issues.append("Tests failed or execution finished with errors.")
            score = max(0, score)

            judge_data = {
                "score": score,
                "issues": issues,
                "improvement": "Ensure files are checked before edit." if tool_failures > 0 else "None needed.",
                "task_success": 1.0 if (test_passed or score >= 7) else 0.0,
                "tool_accuracy": max(0.0, 1.0 - (tool_failures / max(1, total_steps))),
                "retrieval_quality": 1.0
            }

        # 4. Combine Metrics
        evaluation_report = {
            "task_success": judge_data.get("task_success", 1.0),
            "tool_accuracy": judge_data.get("tool_accuracy", 1.0),
            "retrieval_quality": judge_data.get("retrieval_quality", 1.0),
            "iterations": total_steps,
            "errors": tool_failures,
            "score": judge_data.get("score", 10),
            "issues": judge_data.get("issues", []),
            "improvement": judge_data.get("improvement", ""),
            "rule_metrics": rule_metrics
        }

        return evaluation_report
