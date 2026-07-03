from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.graph.supervisor_llm import StructuredOllamaSupervisorLLM
from app.services.memory_manager import get_memory_manager

class ReflectionOutput(BaseModel):
    what_went_wrong: str = Field(..., description="Analysis of what went wrong or could be optimized")
    what_improved: str = Field(..., description="What worked well in this run")
    reflection_rule: str = Field(..., description="Actionable guideline or experience rule for future runs")


class ReflectionAgent:
    def __init__(self) -> None:
        self.mm = get_memory_manager()

    def reflect(self, thread_id: str, evaluation_report: dict[str, Any], task: str) -> dict[str, Any]:
        score = evaluation_report.get("score", 10)
        issues = evaluation_report.get("issues", [])
        errors = evaluation_report.get("errors", 0)
        
        # 1. Prepare context for reflection LLM
        issues_str = "\n".join(f"- {issue}" for issue in issues)
        prompt = (
            "You are an AI Agent Reflection assistant. Analyze the following evaluation report of a run.\n"
            f"Original Task: {task}\n"
            f"Score: {score}/10\n"
            f"Issues:\n{issues_str or 'None'}\n"
            f"Errors count: {errors}\n\n"
            "Identify what went wrong, what improved, and formulate a general actionable guideline (reflection rule) for future runs. "
            "Return JSON matching the ReflectionOutput schema."
        )

        settings = get_settings()
        llm = StructuredOllamaSupervisorLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model
        )

        try:
            reflection_res = llm.with_structured_output(ReflectionOutput)(prompt)
            reflection_data = reflection_res.model_dump()
        except Exception:
            # Fallback reflection logic if Ollama is unavailable
            if score < 7 or errors > 0:
                what_went_wrong = f"Execution had issues: {', '.join(issues) if issues else 'Unknown error'}."
                what_improved = "Completed initial supervisor routing."
                reflection_rule = "Always search repo before modifying auth"
            else:
                what_went_wrong = "None, task completed successfully."
                what_improved = "Efficient tool selection and correct resolution."
                reflection_rule = "Use search_knowledge tool early to find code context"

            reflection_data = {
                "what_went_wrong": what_went_wrong,
                "what_improved": what_improved,
                "reflection_rule": reflection_rule
            }

        rule = reflection_data.get("reflection_rule", "")
        
        # 2. Store memory with Importance Evaluator Guardrail
        # If the task had failures, store in "error" memory.
        # Otherwise, store in "semantic" (vector) memory.
        save_status = "ignored"
        memory_id = None
        
        if score < 7 or errors > 0:
            # Error Memory
            res = self.mm.store_memory(
                category="error",
                content=f"Thread {thread_id} failure: {reflection_data.get('what_went_wrong')}",
                error=reflection_data.get("what_went_wrong", "Execution Failure"),
                cause=reflection_data.get("what_went_wrong", "unknown"),
                solution=rule,
                file_changed="unknown"
            )
            save_status = res.get("status", "ignored")
            memory_id = res.get("id")
        else:
            # Semantic Memory
            res = self.mm.store_memory(
                category="semantic",
                content=f"Reflection rule for {task}: {rule}",
                metadata={"thread_id": thread_id, "type": "reflection_learning"}
            )
            save_status = res.get("status", "ignored")
            memory_id = res.get("id")

        return {
            "reflection": reflection_data,
            "save_status": save_status,
            "memory_id": memory_id
        }
