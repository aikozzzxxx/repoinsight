"""Pydantic state models for cross-agent data passing."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ModuleInfo(BaseModel):
    """Info about a single module/package in the repo."""
    name: str = ""
    files: int = 0
    exports: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)


class RepoGraph(BaseModel):
    """Structured output from Repo Crawler — passed to downstream agents."""
    repo_name: str = ""
    repo_url: str = ""
    language: str = ""
    files: int = 0
    lines: int = 0
    modules: list[ModuleInfo] = Field(default_factory=list)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    core_files: list[str] = Field(default_factory=list)
    complexity_hotspots: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    local_path: str = ""


class QualityReport(BaseModel):
    """Output from Code Reviewer."""
    overall_score: float = 0.0
    issues: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)


class SecurityReport(BaseModel):
    """Output from Security Auditor."""
    risk_level: str = "low"  # low | medium | high | critical
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AnalysisState(BaseModel):
    """Top-level state passed through the entire analysis pipeline."""
    repo_url: str = ""
    repo_graph: RepoGraph | None = None
    architecture_doc: str = ""
    quality_report: QualityReport | None = None
    security_report: SecurityReport | None = None
    guide_doc: str = ""
    eval_score: float = 0.0
    retry_count: int = 0
    errors: list[str] = Field(default_factory=list)
