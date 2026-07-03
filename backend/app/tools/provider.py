from __future__ import annotations
from typing import Any, Callable

class ToolProvider:
    def get_tools(self) -> list[Callable[..., Any]]:
        raise NotImplementedError()

class LangChainToolProvider(ToolProvider):
    def __init__(self, tools: list[Callable[..., Any]]):
        self.tools = tools

    def get_tools(self) -> list[Callable[..., Any]]:
        return self.tools

class MCPToolProvider(ToolProvider):
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url

    def get_tools(self) -> list[Callable[..., Any]]:
        raise NotImplementedError("MCP server connection is not implemented yet.")
