from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Iterable


DANGEROUS_PREFIXES = (
    "rm ",
    "rm-",
    "sudo ",
    "chmod ",
    "chown ",
    "mv ",
    "dd ",
    "kill ",
    "pkill ",
)

DANGEROUS_SUBSTRINGS = (
    "pip install",
    "python -m pip install",
    "uv pip install",
    "poetry add",
    "git push",
    "git reset --hard",
    "docker push",
    "curl | bash",
    "wget | bash",
    "drop table",
    "delete",
)


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    requires_approval: bool = False
    approval_reason: str = ""


def is_dangerous_command(command: str) -> bool:
    normalized = command.strip().lower()
    return normalized.startswith(DANGEROUS_PREFIXES) or any(token in normalized for token in DANGEROUS_SUBSTRINGS)


def requires_human_approval(command: str) -> bool:
    return is_dangerous_command(command)


def execute_command(command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, str | int | bool]:
    """Execute a shell command in a subprocess and return output."""
    if requires_human_approval(command):
        return {
            "command": command,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command blocked pending human approval.",
            "requires_approval": True,
            "approval_reason": "Command matched safety policy",
        }

    args = shlex.split(command)
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "requires_approval": False,
        "approval_reason": "",
    }