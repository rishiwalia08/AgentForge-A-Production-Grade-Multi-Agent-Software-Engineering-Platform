from __future__ import annotations

import shlex
import sys

import pytest

from app.agents import developer_agent as da
from app.agents.developer_llm import DeveloperTurn, ToolCall
from app.graph import supervisor_graph as sg
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


class FakeBoundLLM:
    def __init__(self, turns):
        self.turns = turns
        self.index = 0

    def invoke(self, messages):
        turn = self.turns[min(self.index, len(self.turns) - 1)]
        self.index += 1
        return turn


class FakeDeveloperLLM:
    def __init__(self, turns):
        self.bound = FakeBoundLLM(turns)

    def bind_tools(self, tools):
        return self.bound


class FakeSupervisorLLM:
    def __init__(self, decision):
        self.decision = decision

    def with_structured_output(self, schema):
        def invoke(prompt):
            return schema.model_validate(self.decision)

        return invoke


def _base_state(user_request: str):
    return {
        "user_request": user_request,
        "current_task": user_request,
        "tasks": [],
        "observations": [],
        "approvals_required": [],
        "pending_approval": {},
        "approved_actions": [],
        "rejected_actions": [],
        "agent_history": [],
        "tool_history": [],
        "tool_calls": [],
        "tool_outputs": [],
        "messages": [],
        "errors": [],
        "memory": {},
        "test_results": {},
        "current_error": "",
        "current_step": 0,
    }


def test_safe_action_does_not_interrupt(monkeypatch, tmp_path):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Creating the file.",
                tool_calls=[
                    ToolCall(
                        name="create_file",
                        arguments={
                            "path": "hello.py",
                            "content": "print('Hello World')\n",
                            "base_dir": str(tmp_path),
                                "overwrite": True,
                        },
                    )
                ],
            ),
            DeveloperTurn(content="Done.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    result = graph.invoke(_base_state("Create hello.py"), config={"configurable": {"thread_id": "project_safe"}})

    assert "__interrupt__" not in result
    assert (tmp_path / "hello.py").exists()


def test_dangerous_command_pauses_with_approval_request(monkeypatch):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Need to run the command.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": f"rm -rf {shlex.quote('/tmp/agentic-ai-risk')}"},
                    )
                ],
            ),
            DeveloperTurn(content="Waiting.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    result = graph.invoke(_base_state("Delete temp data"), config={"configurable": {"thread_id": "project_pause"}})

    assert "__interrupt__" in result
    assert len(result["__interrupt__"]) > 0
    assert result["__interrupt__"][0].value["tool"] == "execute_command"
    assert result["pending_approval"]["risk_level"] in {"critical", "high", "medium"}


def test_approve_action_resumes_and_executes(monkeypatch, tmp_path):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Need approval before writing.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": "sudo print('ok')"},
                    )
                ],
            ),
            DeveloperTurn(content="Action complete.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    initial = graph.invoke(_base_state("Run a command"), config={"configurable": {"thread_id": "project_resume"}})

    assert "__interrupt__" in initial
    resumed = graph.invoke(Command(resume={"decision": "approved"}), config={"configurable": {"thread_id": "project_resume"}})

    assert "__interrupt__" not in resumed
    assert resumed["approved_actions"]
    assert any(output["tool"] == "execute_command" for output in resumed["tool_outputs"])


def test_reject_action_returns_to_developer(monkeypatch):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Need approval before deleting.",
                tool_calls=[ToolCall(name="execute_command", arguments={"command": "rm -rf /tmp/nope"})],
            ),
            DeveloperTurn(content="I will choose another approach.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    initial = graph.invoke(_base_state("Delete risky data"), config={"configurable": {"thread_id": "project_reject"}})
    
    assert "__interrupt__" in initial
    resumed = graph.invoke(Command(resume={"decision": "rejected"}), config={"configurable": {"thread_id": "project_reject"}})

    assert resumed["rejected_actions"]
    assert any(message.get("role") == "human" for message in resumed["messages"])


def test_approve_with_boolean_resume(monkeypatch):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Dangerous operation required.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": "delete database"},
                    )
                ],
            ),
            DeveloperTurn(content="Action complete.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test_bool_approve"}}
    initial = graph.invoke(_base_state("Run deletion"), config=config)

    assert "__interrupt__" in initial
    resumed = graph.invoke(Command(resume={"approved": True}), config=config)

    assert "__interrupt__" not in resumed
    assert resumed["approved_actions"]
    assert resumed["approval_history"]
    audit = resumed["approval_history"][-1]
    assert audit["decision"] == "approved"
    assert audit["tool"] == "execute_command"
    assert audit["action"] == "delete database"
    assert "timestamp" in audit


def test_reject_with_boolean_resume(monkeypatch):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Risky command.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": "delete database"},
                    )
                ],
            ),
            DeveloperTurn(content="Alternate approach taken.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test_bool_reject"}}
    initial = graph.invoke(_base_state("Run deletion"), config=config)

    assert "__interrupt__" in initial
    resumed = graph.invoke(Command(resume=False), config=config)

    assert "__interrupt__" not in resumed
    assert resumed["rejected_actions"]
    assert resumed["approval_history"]
    audit = resumed["approval_history"][-1]
    assert audit["decision"] == "rejected"
    assert audit["action"] == "delete database"


def test_state_inspection_before_approval(monkeypatch):
    fake_dev_llm = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Risky step.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": "delete database"},
                    )
                ],
            ),
            DeveloperTurn(content="Action complete.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: fake_dev_llm,
    )
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    config = {"configurable": {"thread_id": "inspect_thread"}}
    initial = graph.invoke(_base_state("Run inspection"), config=config)

    assert "__interrupt__" in initial

    # State Inspection
    state_info = graph.get_state(config)
    assert "human_approval" in state_info.next
    values = state_info.values
    assert values["pending_approval"]
    assert values["pending_approval"]["action"] == "delete database"
    assert values["pending_approval"]["tool"] == "execute_command"
    assert len(values["messages"]) > 0

    # Resume
    resumed = graph.invoke(Command(resume=True), config=config)
    assert "__interrupt__" not in resumed
    assert resumed["approved_actions"]


def test_thread_isolation(monkeypatch, tmp_path):
    fake_dev_llm_A = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Deleting db.",
                tool_calls=[
                    ToolCall(
                        name="execute_command",
                        arguments={"command": "delete database"},
                    )
                ],
            ),
            DeveloperTurn(content="A complete.", tool_calls=[]),
        ]
    )
    fake_dev_llm_B = FakeDeveloperLLM(
        [
            DeveloperTurn(
                content="Creating file.",
                tool_calls=[
                    ToolCall(
                        name="create_file",
                        arguments={
                            "path": "hello_b.py",
                            "content": "print('B')\n",
                            "base_dir": str(tmp_path),
                            "overwrite": True,
                        },
                    )
                ],
            ),
            DeveloperTurn(content="B complete.", tool_calls=[]),
        ]
    )
    
    active_llm_holder = {"llm": None}
    
    def mock_get_llm():
        return active_llm_holder["llm"]
        
    monkeypatch.setattr(da.developer_llm, "get_developer_llm", mock_get_llm)
    monkeypatch.setattr(sg.supervisor_llm, "get_supervisor_llm", lambda: FakeSupervisorLLM({"next_agent": "developer", "reason": "Proceed", "confidence": 1.0}))

    graph = sg.build_supervisor_graph(MemorySaver())
    
    # Run Thread A (Dangerous)
    active_llm_holder["llm"] = fake_dev_llm_A
    config_A = {"configurable": {"thread_id": "thread_A"}}
    initial_A = graph.invoke(_base_state("Delete DB"), config=config_A)
    assert "__interrupt__" in initial_A

    # Run Thread B (Safe)
    active_llm_holder["llm"] = fake_dev_llm_B
    config_B = {"configurable": {"thread_id": "thread_B"}}
    initial_B = graph.invoke(_base_state("Create hello_b.py"), config=config_B)
    assert "__interrupt__" not in initial_B
    assert (tmp_path / "hello_b.py").exists()

    # Verify Thread A is STILL paused
    state_A = graph.get_state(config_A)
    assert "human_approval" in state_A.next

    # Resume Thread A
    active_llm_holder["llm"] = fake_dev_llm_A
    resumed_A = graph.invoke(Command(resume=True), config=config_A)
    assert "__interrupt__" not in resumed_A
    assert resumed_A["approved_actions"]