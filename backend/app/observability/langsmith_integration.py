from __future__ import annotations

import os

def is_langsmith_enabled() -> bool:
    """Check if LangSmith tracing is active via environment variables."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"

def get_langsmith_config() -> dict[str, Any]:
    """Retrieve the LangSmith configuration parameters."""
    return {
        "tracing": is_langsmith_enabled(),
        "api_key_set": bool(os.environ.get("LANGCHAIN_API_KEY")),
        "project": os.environ.get("LANGCHAIN_PROJECT", "default"),
        "endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    }
