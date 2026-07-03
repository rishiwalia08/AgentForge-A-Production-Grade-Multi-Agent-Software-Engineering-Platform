from __future__ import annotations

import ast
import os
from typing import Any

class CodeIndexer:
    @staticmethod
    def parse_python_ast(code: str, file_path: str = "") -> dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"functions": [], "classes": [], "imports": []}
            
        info = {
            "functions": [],
            "classes": [],
            "imports": []
        }
        
        # Analyze imports
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    info["imports"].append({
                        "library": name.name,
                        "used_by": file_path
                    })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for name in node.names:
                        info["imports"].append({
                            "library": f"{node.module}.{name.name}",
                            "used_by": file_path
                        })

        # Pre-build parent map to check for top-level functions vs class methods
        parent_map = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        args = [arg.arg for arg in child.args.args]
                        dependencies = []
                        for sub_node in ast.walk(child):
                            if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Name):
                                dependencies.append(sub_node.func.id)
                        methods.append({
                            "name": child.name,
                            "arguments": args,
                            "return_type": ast.unparse(child.returns) if getattr(child, "returns", None) and hasattr(ast, "unparse") else "Any",
                            "docstring": ast.get_docstring(child) or "",
                            "dependencies": dependencies,
                            "file_path": file_path,
                            "line_start": child.lineno,
                            "line_end": getattr(child, "end_lineno", child.lineno)
                        })
                
                info["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "inheritance": [ast.unparse(base) for base in node.bases] if hasattr(ast, "unparse") else [b.id for b in node.bases if isinstance(b, ast.Name)],
                    "file_path": file_path
                })
                
            elif isinstance(node, ast.FunctionDef):
                parent = parent_map.get(node)
                if isinstance(parent, ast.Module):
                    args = [arg.arg for arg in node.args.args]
                    dependencies = []
                    for sub_node in ast.walk(node):
                        if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Name):
                            dependencies.append(sub_node.func.id)
                    info["functions"].append({
                        "name": node.name,
                        "arguments": args,
                        "return_type": ast.unparse(node.returns) if getattr(node, "returns", None) and hasattr(ast, "unparse") else "Any",
                        "docstring": ast.get_docstring(node) or "",
                        "dependencies": dependencies,
                        "file_path": file_path,
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno)
                    })

        return info


class RepoMap:
    @staticmethod
    def generate(root_dir: str) -> dict[str, Any]:
        repo_map = {}
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "__pycache__", "data", "docs")]
            rel_path = os.path.relpath(root, root_dir)
            parts = rel_path.split(os.sep) if rel_path != "." else []
            
            current_dict = repo_map
            for part in parts:
                current_dict = current_dict.setdefault(part, {})
            
            filtered_files = [f for f in files if f.endswith((".py", ".js", ".ts", ".md", ".json")) and not f.startswith(".")]
            if filtered_files:
                current_dict["files"] = filtered_files
        return repo_map


class CodeGraph:
    def __init__(self):
        self.calls = []        # list of dict: {"caller": str, "callee": str}
        self.inheritance = []  # list of dict: {"child_class": str, "parent_class": str}
        self.imports = []      # list of dict: {"module": str, "imported_module": str}

    def build_from_indexer_info(self, file_path: str, ast_info: dict[str, Any]):
        # 1. Imports
        for imp in ast_info.get("imports", []):
            self.imports.append({
                "module": file_path,
                "imported_module": imp["library"]
            })
            
        # 2. Inheritance
        for cls in ast_info.get("classes", []):
            for parent in cls.get("inheritance", []):
                self.inheritance.append({
                    "child_class": cls["name"],
                    "parent_class": parent
                })
            # 3. Method calls
            for method in cls.get("methods", []):
                for dep in method.get("dependencies", []):
                    self.calls.append({
                        "caller": f"{cls['name']}.{method['name']}",
                        "callee": dep
                    })

        # 4. Top-level Function calls
        for func in ast_info.get("functions", []):
            for dep in func.get("dependencies", []):
                self.calls.append({
                    "caller": func["name"],
                    "callee": dep
                })
