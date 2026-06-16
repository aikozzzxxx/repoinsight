"""Repository analysis tools — clone, AST parse, dependency graph generation."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Any, Type

import networkx as nx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from git import Repo, GitCommandError

from repoinsight.config import settings


class CloneRepoInput(BaseModel):
    """Input schema for GitCloneTool."""
    repo_url: str = Field(..., description="GitHub repository URL to clone")


class GitCloneTool(BaseTool):
    """Clone a GitHub repository to a temporary directory."""

    name: str = "Git Clone Tool"
    description: str = "Clone a GitHub repository to a local temporary directory for analysis"
    args_schema: Type[BaseModel] = CloneRepoInput

    def _run(self, repo_url: str) -> str:
        """Clone repo and return the local path."""
        tmp_dir = Path(settings.tmp_repos_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        target = tmp_dir / repo_name

        # Remove if already exists
        if target.exists():
            shutil.rmtree(target)

        try:
            Repo.clone_from(repo_url, target, depth=1)
            return str(target.absolute())
        except GitCommandError as e:
            return f"ERROR: Failed to clone {repo_url} — {e}"


class ASTParseInput(BaseModel):
    """Input schema for ASTParserTool."""
    directory: str = Field(..., description="Directory path containing Python source code")


class ASTParserTool(BaseTool):
    """Parse Python files in a directory using AST, extract structure info."""

    name: str = "AST Parser Tool"
    description: str = (
        "Parse all Python files in a directory and extract "
        "functions, classes, imports, and module-level info"
    )
    args_schema: Type[BaseModel] = ASTParseInput

    def _run(self, directory: str) -> str:
        """Parse directory and return JSON summary."""
        base = Path(directory)
        if not base.exists():
            return json.dumps({"error": f"Directory not found: {directory}"})

        modules: dict[str, dict[str, Any]] = {}
        total_lines = 0
        total_functions = 0
        total_classes = 0

        for py_file in sorted(base.rglob("*.py")):
            if "test" in str(py_file).lower():
                continue
            if "__pycache__" in str(py_file):
                continue

            rel_path = str(py_file.relative_to(base))
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = source.splitlines()
                total_lines += len(lines)

                tree = ast.parse(source)
                visitor = _ModuleVisitor(str(rel_path))
                visitor.visit(tree)

                modules[rel_path] = {
                    "functions": visitor.functions,
                    "classes": visitor.classes,
                    "imports": visitor.imports,
                    "loc": len(lines),
                    "comment_lines": sum(1 for l in lines if l.strip().startswith("#")),
                }
                total_functions += len(visitor.functions)
                total_classes += len(visitor.classes)
            except SyntaxError:
                modules[rel_path] = {"error": "Parse failed", "loc": 0, "functions": [], "classes": [], "imports": []}

        result = {
            "directory": directory,
            "total_files": len(modules),
            "total_lines": total_lines,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "modules": modules,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    async def _arun(self, directory: str) -> str:
        return self._run(directory)


class _ModuleVisitor(ast.NodeVisitor):
    """AST visitor that extracts structural info from a Python module."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.functions: list[dict[str, Any]] = []
        self.classes: list[dict[str, Any]] = []
        self.imports: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "args": [a.arg for a in node.args.args],
            "decorators": [
                d.id if isinstance(d, ast.Name) else str(getattr(d, "func", d))
                for d in node.decorator_list
            ],
        })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "methods": methods,
            "bases": [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases],
        })
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(f"import {alias.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        names = ", ".join(a.name for a in node.names)
        self.imports.append(f"from {module} import {names}")


class DepGraphInput(BaseModel):
    """Input schema for DependencyGraphTool."""
    ast_result_json: str = Field(..., description="JSON string from ASTParserTool output")
    repo_name: str = Field(default="unknown", description="Repository name for labeling")


class DependencyGraphTool(BaseTool):
    """Build a module dependency graph using NetworkX from AST import data."""

    name: str = "Dependency Graph Builder"
    description: str = "Build module dependency graph from parsed AST import data"
    args_schema: Type[BaseModel] = DepGraphInput

    def _run(self, ast_result_json: str, repo_name: str = "unknown") -> str:
        """Build graph and return as JSON."""
        try:
            data = json.loads(ast_result_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})

        modules = data.get("modules", {})

        # Infer top-level module name from paths
        top_level = self._infer_top_level(list(modules.keys()))

        G = nx.DiGraph()
        for mod_path, mod_data in modules.items():
            mod_name = self._path_to_module(mod_path)
            G.add_node(
                mod_name,
                file=mod_path,
                functions=mod_data.get("functions", []),
                classes=mod_data.get("classes", []),
                loc=mod_data.get("loc", 0),
            )

        # Build edges from imports
        all_modules = set(G.nodes())
        for mod_path, mod_data in modules.items():
            mod_name = self._path_to_module(mod_path)
            for imp in mod_data.get("imports", []):
                target = self._resolve_import_target(imp, top_level, all_modules)
                if target and target != mod_name:
                    G.add_edge(mod_name, target)

        # Export graph
        graph_json = {
            "nodes": [
                {"id": node, "file": G.nodes[node]["file"], "loc": G.nodes[node]["loc"]}
                for node in G.nodes()
            ],
            "edges": [
                {"source": u, "target": v} for u, v in G.edges()
            ],
        }

        # Identify core files and hotspots
        node_out_edges = {n: G.out_degree(n) for n in G.nodes()}
        node_in_edges = {n: G.in_degree(n) for n in G.nodes()}

        core_files = sorted(node_in_edges, key=node_in_edges.get, reverse=True)[:10]
        hotspots = sorted(
            G.nodes(),
            key=lambda n: G.nodes[n].get("loc", 0) * (1 + G.out_degree(n) + G.in_degree(n)),
            reverse=True,
        )[:10]

        # Extract dependencies from imports
        all_deps = set()
        for mod_data in modules.values():
            for imp in mod_data.get("imports", []):
                if "import" in imp:
                    parts = imp.replace("from ", "").split(" import ")[0].strip()
                    if parts and parts.startswith(top_level or ""):
                        all_deps.add(parts)

        result = {
            "repo_name": repo_name,
            "language": "Python",
            "files": len(modules),
            "lines": data.get("total_lines", 0),
            "top_level_module": top_level or "",
            "modules": [
                {
                    "name": self._path_to_module(p),
                    "file": p,
                    "exports": [f["name"] for f in m.get("functions", [])]
                    + [c["name"] for c in m.get("classes", [])],
                    "imports": m.get("imports", [])[:10],  # limit for readability
                }
                for p, m in modules.items()
            ],
            "dependency_graph": graph_json,
            "core_files": core_files,
            "complexity_hotspots": hotspots,
            "dependencies": sorted(all_deps),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def _path_to_module(path: str) -> str:
        """Convert file path to Python module notation."""
        return path.replace("/", ".").replace("\\", ".").replace(".py", "").strip(".")

    @staticmethod
    def _infer_top_level(paths: list[str]) -> str:
        """Infer the top-level package name from file paths."""
        if not paths:
            return ""
        parts = [p.replace("\\", "/").split("/") for p in paths]
        prefix = parts[0][0] if parts[0] else ""
        for p in parts:
            if not p or p[0] != prefix:
                return ""
        return prefix

    @staticmethod
    def _resolve_import_target(import_stmt: str, top_level: str, known_modules: set[str]) -> str | None:
        """Resolve an import statement to a known module node."""
        if import_stmt.startswith("from "):
            # "from X.Y import Z" -> X.Y
            parts = import_stmt[5:].split(" import ")[0].strip()
            return parts if parts in known_modules else None
        else:
            # "import X" or "import X.Y"
            parts = import_stmt[7:].strip()
            # Try exact match first, then prefix match
            if parts in known_modules:
                return parts
            for mod in known_modules:
                if mod.startswith(parts) or parts.startswith(mod):
                    return mod
            return None


class FileSummaryInput(BaseModel):
    """Input schema for FileSummaryTool."""
    directory: str = Field(..., description="Directory path to summarize")


class FileSummaryTool(BaseTool):
    """Generate a high-level file/directory summary for context."""

    name: str = "File Summary Tool"
    description: str = "Generate a directory tree and file statistics for a codebase"
    args_schema: Type[BaseModel] = FileSummaryInput

    def _run(self, directory: str) -> str:
        """Generate summary and return as text."""
        base = Path(directory)
        if not base.exists():
            return f"ERROR: Directory not found: {directory}"

        lines: list[str] = [f"# Repository Summary: {base.name}", ""]
        lines.append(f"**Path**: {directory}")
        lines.append("")

        # Count files by extension
        ext_counts: dict[str, int] = {}
        total_py_lines = 0
        py_file_count = 0

        for f in base.rglob("*"):
            if f.is_file():
                if "__pycache__" in str(f) or ".git" in str(f) or "node_modules" in str(f):
                    continue
                suffix = f.suffix or "no-ext"
                ext_counts[suffix] = ext_counts.get(suffix, 0) + 1

                if f.suffix == ".py":
                    try:
                        count = sum(1 for _ in open(f, encoding="utf-8", errors="ignore"))
                        total_py_lines += count
                        py_file_count += 1
                    except Exception:
                        pass

        lines.append("## File Distribution")
        for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- `{ext}`: {count} files")

        if py_file_count > 0:
            lines.append("")
            lines.append(f"**Python files**: {py_file_count}, **Total lines**: {total_py_lines}")

        # Top-level directory listing
        lines.append("")
        lines.append("## Top-Level Structure")
        for item in sorted(base.iterdir()):
            prefix = "📁" if item.is_dir() else "📄"
            name = item.name
            if name.startswith(".") or name == "tmp_repos" or name == "chroma_db":
                continue
            lines.append(f"- {prefix} {name}")

        return "\n".join(lines)
