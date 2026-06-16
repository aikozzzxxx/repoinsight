"""Code review tools — complexity analysis, lint patterns, quality scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ComplexityAnalyzerInput(BaseModel):
    """Input for ComplexityAnalyzerTool."""
    file_path: str = Field(..., description="Absolute path to a Python file to analyze")


class ComplexityAnalyzerTool(BaseTool):
    """Analyze a single Python file for complexity signals without full AST parsing."""

    name: str = "Complexity Analyzer"
    description: str = (
        "Analyze a Python file for cyclomatic complexity signals: "
        "deep nesting, long functions, many branches, too many parameters"
    )
    args_schema: Type[BaseModel] = ComplexityAnalyzerInput

    def _run(self, file_path: str) -> str:
        """Run complexity analysis and return JSON."""
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as e:
            return json.dumps({"error": f"Read error: {e}"})

        issues: list[dict] = []
        current_func: dict | None = None
        indent_level = 0
        nesting_depth = 0
        func_start_line = 0

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Detect function definition
            if stripped.startswith("def ") and not stripped.startswith("def __"):
                if current_func:
                    self._finalize_func(current_func, issues, i - 1)
                current_func = {
                    "name": stripped[4:].split("(")[0].strip(),
                    "start_line": i,
                    "end_line": i,
                    "lines": 0,
                    "args_count": self._count_args(stripped),
                    "max_nesting": 0,
                    "branches": 0,
                    "has_docstring": False,
                }
                indent_level = len(line) - len(line.lstrip())
                nesting_depth = 0

            # Track function body
            if current_func:
                current_func["end_line"] = i
                current_func["lines"] += 1

                # Track nesting
                current_indent = len(line) - len(line.lstrip()) if stripped else indent_level
                if current_indent > indent_level:
                    nesting_depth += 1
                    current_func["max_nesting"] = max(
                        current_func["max_nesting"], nesting_depth
                    )
                elif current_indent < indent_level:
                    nesting_depth = max(0, nesting_depth - 1)

                # Count branches
                if any(
                    stripped.startswith(kw)
                    for kw in ("if ", "elif ", "for ", "while ", "except ", "with ")
                ):
                    current_func["branches"] += 1

                # Check docstring
                if i == current_func["start_line"] + 1 and '"""' in stripped:
                    current_func["has_docstring"] = True

        # Finalize last function
        if current_func:
            self._finalize_func(current_func, issues, len(lines))

        complexity_hotspots = sorted(issues, key=lambda x: -x.get("score", 0))

        result = {
            "file": str(path),
            "lines": len(lines),
            "functions_found": len(issues),
            "functions": [i.get("name", "") for i in issues],
            "issues": complexity_hotspots,
            "complexity_score": max(0, 10 - sum(i.get("score", 0) * 0.5 for i in issues)),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _count_args(self, func_line: str) -> int:
        """Count function arguments from def line."""
        try:
            args_part = func_line.split("(")[1].split(")")[0]
            if not args_part.strip():
                return 0
            return len([a.strip() for a in args_part.split(",") if a.strip()])
        except IndexError:
            return 0

    def _finalize_func(self, func: dict, issues: list[dict], end_line: int) -> None:
        """Evaluate function metrics and add issues if needed."""
        score = 0
        details = []

        if func["lines"] > 50:
            points = min(3, (func["lines"] - 50) // 20)
            score += points
            details.append(f"Long function ({func['lines']} lines)")

        if func["max_nesting"] > 3:
            points = func["max_nesting"] - 3
            score += points
            details.append(f"Deep nesting (depth {func['max_nesting']})")

        if func["branches"] > 10:
            points = min(3, (func["branches"] - 10) // 5)
            score += points
            details.append(f"High branch count ({func['branches']})")

        if func["args_count"] > 5:
            points = min(2, func["args_count"] - 5)
            score += points
            details.append(f"Too many params ({func['args_count']})")

        if func["lines"] > 5 and not func["has_docstring"]:
            score += 0.5
            details.append("Missing docstring")

        if details:
            issues.append({
                "name": func["name"],
                "lines": func["lines"],
                "score": round(score, 1),
                "details": details,
            })


class CodeStyleCheckInput(BaseModel):
    """Input for CodeStyleCheckTool."""
    directory: str = Field(..., description="Directory to scan for style issues")


class CodeStyleCheckTool(BaseTool):
    """Check code style patterns across a directory."""

    name: str = "Code Style Checker"
    description: str = "Scan Python files for common style issues: naming, line length, blank lines"
    args_schema: Type[BaseModel] = CodeStyleCheckInput

    STYLE_CHECKS = [
        ("line > 120 chars", lambda l: len(l.rstrip()) > 120),
        ("trailing whitespace", lambda l: l.rstrip() != l.rstrip() + " " if l.rstrip() != l else False),
        # Simplified: just check trailing space existence
        ("uses tabs", lambda l: "\t" in l),
        ("bare except", lambda l: l.strip() == "except:"),
        ("print statement", lambda l: "print(" in l.replace(" ", "") and not l.strip().startswith("#")),
    ]

    def _run(self, directory: str) -> str:
        """Run style checks and return JSON."""
        base = Path(directory)
        if not base.exists():
            return json.dumps({"error": f"Directory not found: {directory}"})

        findings: list[dict] = []
        files_checked = 0

        for py_file in base.rglob("*.py"):
            if "__pycache__" in str(py_file) or "test" in str(py_file).lower():
                continue

            files_checked += 1
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, start=1):
                for check_name, check_fn in self.STYLE_CHECKS:
                    try:
                        if check_fn(line):
                            findings.append({
                                "file": str(py_file.relative_to(base)),
                                "line": i,
                                "issue": check_name,
                            })
                    except Exception:
                        continue

        # Group by issue type
        issue_count: dict[str, int] = {}
        for f in findings:
            issue_count[f["issue"]] = issue_count.get(f["issue"], 0) + 1

        result = {
            "files_checked": files_checked,
            "total_findings": len(findings),
            "by_type": issue_count,
            "findings": findings[:50],  # Cap at 50 for context limit
        }
        return json.dumps(result, indent=2, ensure_ascii=False)


class QualityScoreInput(BaseModel):
    """Input for QualityScoringTool."""
    complexity_json: str = Field(..., description="JSON from ComplexityAnalyzerTool")
    style_json: str = Field(default="{}", description="JSON from CodeStyleCheckTool")
    repo_graph_json: str = Field(default="{}", description="JSON repo_graph for file count context")


class QualityScoringTool(BaseTool):
    """Compute a composite quality score from complexity and style data."""

    name: str = "Quality Score Calculator"
    description: str = "Calculate an overall code quality score from complexity and style analysis results"
    args_schema: Type[BaseModel] = QualityScoreInput

    def _run(
        self,
        complexity_json: str,
        style_json: str = "{}",
        repo_graph_json: str = "{}",
    ) -> str:
        """Compute score and return JSON."""
        try:
            complexity = json.loads(complexity_json)
        except json.JSONDecodeError:
            complexity = {}
        try:
            style = json.loads(style_json)
        except json.JSONDecodeError:
            style = {}
        try:
            repo = json.loads(repo_graph_json)
        except json.JSONDecodeError:
            repo = {}

        comp_score = complexity.get("complexity_score", 10)
        style_findings = style.get("total_findings", 0)
        total_files = repo.get("files", 1)

        # Style penalty: 0.1 per finding per file, capped at 5
        style_penalty = min(5, (style_findings / max(total_files, 1)) * 2)

        # Overall: complexity (60%) + style (40%)
        overall = round(comp_score * 0.6 + max(0, 10 - style_penalty) * 0.4, 1)

        result = {
            "overall_score": overall,
            "complexity_score": comp_score,
            "style_score": round(max(0, 10 - style_penalty), 1),
            "files_analyzed": total_files,
            "style_findings_count": style_findings,
            "grade": self._grade(overall),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 9:
            return "A — Excellent"
        elif score >= 7.5:
            return "B — Good"
        elif score >= 6:
            return "C — Acceptable"
        elif score >= 4:
            return "D — Needs Improvement"
        return "F — Critical Issues"
