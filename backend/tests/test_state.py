from app.graph.state import PlatformState


def test_platform_state_can_store_tasks() -> None:
    state: PlatformState = {
        "user_request": "Build a login flow",
        "route": "supervisor",
        "tasks": [{"id": "1", "title": "Analyze requirements", "owner": "requirement_agent", "status": "todo"}],
        "observations": ["Initial request captured"],
        "approvals_required": [],
        "memory": {
            "short_term": ["conversation started"],
            "long_term": [],
            "semantic": [],
            "error_memory": [],
        },
        "messages": [],
        "test_results": {},
        "current_error": "",
        "approved_actions": [],
    }

    assert state["tasks"][0]["owner"] == "requirement_agent"
