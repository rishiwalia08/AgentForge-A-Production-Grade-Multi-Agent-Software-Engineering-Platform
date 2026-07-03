from __future__ import annotations

import subprocess
import os
import shutil
from typing import Any

# Global dictionary to store backup of files for safe agent checkpoints
# Key: run_id, Value: dict of {file_path: content_or_none}
_AGENT_CHECKPOINTS: dict[str, dict[str, str | None]] = {}

def get_workspace_dir() -> str:
    return "/Users/rishiwalia/Desktop/agentic ai"

def _run_git_command(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git"] + args,
            cwd=get_workspace_dir(),
            capture_output=True,
            text=True,
            check=False
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
            "stderr": str(exc)
        }

def git_status() -> dict[str, Any]:
    """Check git status of the project workspace."""
    return _run_git_command(["status"])

def git_diff() -> dict[str, Any]:
    """Check git diff in the project workspace."""
    return _run_git_command(["diff"])

def git_create_branch(branch_name: str) -> dict[str, Any]:
    """Create and checkout a new git branch."""
    return _run_git_command(["checkout", "-b", branch_name])

def git_commit(message: str) -> dict[str, Any]:
    """Add all changed files and commit them with a message."""
    add_res = _run_git_command(["add", "."])
    if add_res["status"] != "success":
        return add_res
    return _run_git_command(["commit", "-m", message])

def create_agent_checkpoint() -> dict[str, Any]:
    """Create a backup checkpoint of files changed (modified or untracked) by the agent."""
    from app.tools.permission import active_context
    context = active_context.get()
    run_id = context.run_id if context else "default_run"
    
    workspace = get_workspace_dir()
    
    status_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False
    )
    if status_res.returncode != 0:
        return {"status": "error", "message": f"Git status failed: {status_res.stderr}"}
        
    checkpoint_data: dict[str, str | None] = {}
    
    for line in status_res.stdout.splitlines():
        if len(line) < 4:
            continue
        file_path = line[3:].strip()
        abs_path = os.path.join(workspace, file_path)
        
        if line.startswith("??"):
            checkpoint_data[file_path] = None
        elif os.path.exists(abs_path) and os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    checkpoint_data[file_path] = f.read()
            except Exception:
                pass
        else:
            checkpoint_data[file_path] = None
            
    _AGENT_CHECKPOINTS[run_id] = checkpoint_data
    return {
        "status": "success",
        "checkpoint_files": list(checkpoint_data.keys()),
        "message": f"Created agent checkpoint for run {run_id} with {len(checkpoint_data)} files."
    }

def restore_agent_checkpoint() -> dict[str, Any]:
    """Restore project workspace to the previously created agent checkpoint, only rolling back agent changes."""
    from app.tools.permission import active_context
    context = active_context.get()
    run_id = context.run_id if context else "default_run"
    
    if run_id not in _AGENT_CHECKPOINTS:
        return {"status": "error", "message": f"No agent checkpoint found for run {run_id}."}
        
    checkpoint_data = _AGENT_CHECKPOINTS[run_id]
    workspace = get_workspace_dir()
    restored = []
    deleted = []
    
    # 1. First, process all checkpointed files
    for file_path, original_content in checkpoint_data.items():
        abs_path = os.path.join(workspace, file_path)
        if original_content is None:
            if os.path.exists(abs_path):
                if os.path.isdir(abs_path):
                    shutil.rmtree(abs_path)
                else:
                    os.remove(abs_path)
                deleted.append(file_path)
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            restored.append(file_path)
            
    # 2. Second, find any new untracked files created after checkpoint
    status_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False
    )
    if status_res.returncode == 0:
        for line in status_res.stdout.splitlines():
            if len(line) < 4:
                continue
            file_path = line[3:].strip()
            abs_path = os.path.join(workspace, file_path)
            if line.startswith("??") and file_path not in checkpoint_data:
                if os.path.exists(abs_path):
                    if os.path.isdir(abs_path):
                        shutil.rmtree(abs_path)
                    else:
                        os.remove(abs_path)
                    deleted.append(file_path)
            
    if run_id in _AGENT_CHECKPOINTS:
        del _AGENT_CHECKPOINTS[run_id]
    
    return {
        "status": "success",
        "restored_files": restored,
        "deleted_files": deleted,
        "message": f"Restored checkpoint: restored {len(restored)} files, deleted {len(deleted)} files."
    }
