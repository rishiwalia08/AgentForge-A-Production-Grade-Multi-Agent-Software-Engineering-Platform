from app.graph.state import PlatformState
from app.graph import supervisor_graph as sg
from langgraph.graph.state import CompiledStateGraph


class FakeStructuredLLM:
    def __init__(self, decision: dict[str, object]):
        self.decision = decision

    def with_structured_output(self, schema):
        def invoke(prompt: str):
            return schema.model_validate(self.decision)

        return invoke


def make_state(**overrides) -> PlatformState:
    state: PlatformState = {
        "user_request": "Create a FastAPI backend",
        "tasks": [],
        "observations": [],
        "approvals_required": [],
        "memory": {},
        "messages": [],
        "test_results": {},
        "current_error": "",
        "approved_actions": [],
        "agent_history": [],
        "current_step": 0,
    }
    state.update(overrides)
    return state


def test_build_supervisor_graph_returns_stategraph():
    g = sg.build_supervisor_graph()
    assert isinstance(g, CompiledStateGraph)


def test_supervisor_routes_to_requirement_or_architecture(monkeypatch):
    monkeypatch.setattr(
        sg.supervisor_llm,
        "get_supervisor_llm",
        lambda: FakeStructuredLLM(
            {"next_agent": "architecture", "reason": "Design first", "confidence": 0.91}
        ),
    )

    state = make_state(user_request="Create ecommerce website")
    new_state = sg.supervisor_node(state)

    assert new_state["next_agent"] in {"requirement", "architecture"}
    assert new_state["supervisor_reason"] == "Design first"
    assert new_state["current_step"] == 1
    assert new_state["agent_history"][-1]["agent"] == "supervisor"


def test_supervisor_routes_to_debugging(monkeypatch):
    monkeypatch.setattr(
        sg.supervisor_llm,
        "get_supervisor_llm",
        lambda: FakeStructuredLLM(
            {
                "next_agent": "debugging",
                "reason": "Runtime error detected",
                "confidence": 0.98,
            }
        ),
    )

    state = make_state(user_request="Error: ModuleNotFoundError numpy", current_error="ModuleNotFoundError: numpy")
    new_state = sg.supervisor_node(state)

    assert new_state["next_agent"] == "debugging"
    assert new_state["supervisor_reason"] == "Runtime error detected"


def test_supervisor_routes_to_testing(monkeypatch):
    monkeypatch.setattr(
        sg.supervisor_llm,
        "get_supervisor_llm",
        lambda: FakeStructuredLLM(
            {"next_agent": "testing", "reason": "User wants to run tests", "confidence": 0.97}
        ),
    )

    state = make_state(user_request="Run pytest")
    new_state = sg.supervisor_node(state)

    assert new_state["next_agent"] == "testing"
    assert new_state["supervisor_reason"] == "User wants to run tests"
