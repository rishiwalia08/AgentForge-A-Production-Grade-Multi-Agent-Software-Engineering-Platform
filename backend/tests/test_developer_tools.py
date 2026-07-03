from __future__ import annotations

import shlex
import sys

from app.agents import developer_agent as da
from app.agents.developer_llm import DeveloperTurn, ToolCall
from app.graph.state import PlatformState
from app.tools.filesystem import create_file, read_file, update_file
from app.tools.terminal import execute_command


class FakeBoundLLM:
    def __init__(self, turns: list[DeveloperTurn]):
        self.turns = turns
        self.index = 0

    def invoke(self, messages):
        turn = self.turns[min(self.index, len(self.turns) - 1)]
        self.index += 1
        return turn


class FakeDeveloperLLM:
    def __init__(self, turns: list[DeveloperTurn]):
        self.turns = turns

    def bind_tools(self, tools):
        return FakeBoundLLM(self.turns)


def make_state(**overrides) -> PlatformState:
    state: PlatformState = {
        "user_request": "Create a file",
        "current_task": "Create a file",
        "tasks": [],
        "observations": [],
        "approvals_required": [],
        "memory": {},
        "messages": [],
        "tool_calls": [],
        "tool_outputs": [],
        "test_results": {},
        "current_error": "",
        "approved_actions": [],
        "agent_history": [],
        "current_step": 0,
        "tool_history": [],
        "errors": [],
    }
    state.update(overrides)
    return state


def test_filesystem_tools_create_read_and_update(tmp_path):
    create_result = create_file("demo.txt", "hello world", base_dir=tmp_path)
    assert create_result["status"] == "created"

    read_result = read_file("demo.txt", base_dir=tmp_path)
    assert read_result["content"] == "hello world"

    update_result = update_file("demo.txt", "hello", "hi", base_dir=tmp_path)
    assert update_result["content"] == "hi world"


def test_execute_command_blocks_dangerous_commands():
    result = execute_command("rm -rf /tmp/unsafe-path")

    assert result["requires_approval"] is True
    assert result["returncode"] == -1


def test_developer_node_selects_create_file_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: FakeDeveloperLLM(
            [
                DeveloperTurn(
                    content="Need to create the requested file.",
                    tool_calls=[
                        ToolCall(
                            name="create_file",
                                arguments={
                                    "path": "hello.py",
                                    "content": "print('Hello World')\n",
                                    "base_dir": str(tmp_path),
                                },
                        )
                    ],
                ),
                DeveloperTurn(content="Created hello.py.", tool_calls=[]),
            ]
        ),
    )

    state = make_state(user_request="Create hello.py", current_task="Create hello.py")
    new_state = da.developer_node(state)

    assert (tmp_path / "hello.py").exists()
    assert new_state["tool_history"][-1]["tool"] == "create_file"
    assert new_state["messages"][-1]["role"] == "assistant"


def test_developer_node_selects_read_file_tool(monkeypatch, tmp_path):
    config_path = tmp_path / "config.py"
    config_path.write_text("APP_NAME = 'demo'\n", encoding="utf-8")

    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: FakeDeveloperLLM(
            [
                DeveloperTurn(
                    content="Reading config file.",
                    tool_calls=[ToolCall(name="read_file", arguments={"path": "config.py", "base_dir": str(tmp_path)})],
                ),
                DeveloperTurn(content="Config file inspected.", tool_calls=[]),
            ]
        ),
    )

    state = make_state(user_request="Read config file", current_task="Read config file")
    new_state = da.developer_node(state)

    assert any(output["tool"] == "read_file" for output in new_state["tool_outputs"])


def test_developer_node_selects_execute_command_tool(monkeypatch):
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: FakeDeveloperLLM(
            [
                DeveloperTurn(
                    content="Run the command.",
                    tool_calls=[
                            ToolCall(
                                name="execute_command",
                                arguments={"command": f"{shlex.quote(sys.executable)} -c \"print('ok')\""},
                            )
                    ],
                ),
                DeveloperTurn(content="Command finished.", tool_calls=[]),
            ]
        ),
    )

    state = make_state(user_request="Run pytest", current_task="Run pytest")
    new_state = da.developer_node(state)

    assert any(tool_call["name"] == "execute_command" for tool_call in new_state["tool_calls"])
    assert any("ok" in output["observation"] for output in new_state["tool_outputs"])


def test_developer_node_requests_human_approval_for_dangerous_action(monkeypatch):
    monkeypatch.setattr(
        da.developer_llm,
        "get_developer_llm",
        lambda: FakeDeveloperLLM(
            [
                DeveloperTurn(
                    content="This action needs approval.",
                    tool_calls=[ToolCall(name="execute_command", arguments={"command": "rm -rf /tmp/agentic-ai-risk"})],
                ),
                DeveloperTurn(content="Waiting for approval.", tool_calls=[]),
            ]
        ),
    )

    state = make_state(user_request="Delete the temp directory", current_task="Delete the temp directory")
    new_state = da.developer_node(state)

    assert new_state["approvals_required"]
    assert new_state["tool_history"][-1]["requires_approval"] == "True"