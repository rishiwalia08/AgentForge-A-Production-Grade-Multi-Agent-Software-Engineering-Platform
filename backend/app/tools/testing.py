from __future__ import annotations

import subprocess
from typing import Any

def run_tests(framework: str, target: str | None = None, cwd: str | None = None) -> dict[str, Any]:
    """Execute unit/integration tests using an approved framework (pytest, vitest, npm test)."""
    if framework not in {"pytest", "vitest", "npm test"}:
        raise ValueError(f"Unauthorized test framework: {framework}. Only 'pytest', 'vitest', and 'npm test' are allowed.")
        
    cmd = [framework]
    if framework == "npm test":
        cmd = ["npm", "test"]
        if target:
            cmd.extend(["--", target])
    elif target:
        cmd.append(target)
        
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd or "/Users/rishiwalia/Desktop/agentic ai",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return {
            "status": "success" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr
        }
    except Exception as exc:
        return {
            "status": "error",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Failed to execute tests: {exc}"
        }
