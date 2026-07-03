from langgraph.graph import StateGraph, START, END

from app.graph.state import PlatformState


def build_graph() -> StateGraph:
    graph = StateGraph(PlatformState)
    graph.add_node("supervisor", lambda state: state)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", END)
    return graph
