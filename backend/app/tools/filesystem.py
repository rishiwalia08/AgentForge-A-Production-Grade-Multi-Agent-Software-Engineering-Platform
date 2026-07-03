from __future__ import annotations

from pathlib import Path


def _resolve_safe_path(path: str, base_dir: str | Path | None = None) -> Path:
    base_path = Path(base_dir or Path.cwd()).resolve()
    target_path = Path(path)
    if not target_path.is_absolute():
        target_path = base_path / target_path
    target_path = target_path.resolve()

    if target_path != base_path and base_path not in target_path.parents:
        raise ValueError(f"Refusing to access path outside base directory: {path}")

    return target_path


def create_file(path: str, content: str, base_dir: str | Path | None = None, overwrite: bool = False) -> dict[str, str]:
    """Create a new file with the specified content."""
    target_path = _resolve_safe_path(path, base_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {target_path}")

    target_path.write_text(content, encoding="utf-8")
    
    try:
        from app.knowledge.retriever import KnowledgeBase
        kb = KnowledgeBase()
        kb.update_file_index(str(target_path), content)
    except Exception:
        pass

    return {"path": str(target_path), "status": "created", "content": content}


def read_file(path: str, base_dir: str | Path | None = None, start_line: int = 1, end_line: int | None = None) -> dict[str, str]:
    """Read content from a file, optionally specifying line boundaries."""
    target_path = _resolve_safe_path(path, base_dir)
    lines = target_path.read_text(encoding="utf-8").splitlines()
    start_index = max(start_line - 1, 0)
    end_index = len(lines) if end_line is None else max(end_line, 0)
    content = "\n".join(lines[start_index:end_index])
    return {"path": str(target_path), "status": "read", "content": content}


def update_file(
    path: str,
    search_text: str,
    replace_text: str,
    base_dir: str | Path | None = None,
) -> dict[str, str]:
    """Update a file by replacing search_text with replace_text."""
    target_path = _resolve_safe_path(path, base_dir)
    original_content = target_path.read_text(encoding="utf-8")

    if search_text not in original_content:
        raise ValueError(f"Search text not found in file: {search_text}")

    updated_content = original_content.replace(search_text, replace_text, 1)
    target_path.write_text(updated_content, encoding="utf-8")

    try:
        from app.knowledge.retriever import KnowledgeBase
        kb = KnowledgeBase()
        kb.update_file_index(str(target_path), updated_content)
    except Exception:
        pass

    return {"path": str(target_path), "status": "updated", "content": updated_content}