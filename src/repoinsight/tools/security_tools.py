"""Security audit tools — secret detection, vulnerability pattern matching, risk scoring."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SecretDetectorInput(BaseModel):
    """Input for SecretDetectorTool."""
    directory: str = Field(..., description="Directory to scan for hardcoded secrets")


class SecretDetectorTool(BaseTool):
    """Scan source files for hardcoded secrets, tokens, and keys."""

    name: str = "Secret Detector"
    description: str = "Scan files for hardcoded secrets: API keys, tokens, passwords, private keys"
    args_schema: Type[BaseModel] = SecretDetectorInput

    # Patterns for common secrets
    PATTERNS: list[tuple[str, str, str]] = [
        # (pattern, name, severity)
        (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\'][\w\-\.]{20,}["\']', "API Key", "high"),
        (r'(?:secret|token)\s*[:=]\s*["\'][\w\-\.]{20,}["\']', "Secret/Token", "high"),
        (r'(?:password|passwd|pwd)\s*[:=]\s*["\'][^"\']+["\']', "Hardcoded Password", "critical"),
        (r'(?:private[_-]?key|privatekey)\s*[:=]', "Private Key Reference", "high"),
        (r'-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----', "Private Key Block", "critical"),
        (r'(?:access[_-]?key|accesskey)\s*[:=]\s*["\'][\w\-]{16,}["\']', "Access Key", "high"),
        (r'(?:mongodb|mysql|postgres|redis)://[^@]+@', "Database Connection String", "critical"),
        (r'(?:Authorization|Bearer)\s+[\w\-\.]{20,}', "Hardcoded Auth Token", "high"),
        (r'sk-[a-zA-Z0-9]{20,}', "OpenAI-style API Key", "high"),
        (r'AKIA[0-9A-Z]{16}', "AWS Access Key", "critical"),
    ]

    def _run(self, directory: str) -> str:
        """Run secret detection scan and return JSON."""
        base = Path(directory)
        if not base.exists():
            return json.dumps({"error": f"Directory not found: {directory}"})

        findings: list[dict] = []
        files_scanned = 0

        for py_file in base.rglob("*.py"):
            if "__pycache__" in str(py_file) or "test" in str(py_file).lower():
                continue

            files_scanned += 1
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, start=1):
                for pattern, name, severity in self.PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip if it looks like a false positive (template/example)
                        if self._is_likely_false_positive(line):
                            continue
                        findings.append({
                            "file": str(py_file.relative_to(base)),
                            "line": i,
                            "type": name,
                            "severity": severity,
                            "snippet": self._safe_snippet(line),
                        })

        result = {
            "files_scanned": files_scanned,
            "total_findings": len(findings),
            "findings": findings,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def _is_likely_false_positive(line: str) -> bool:
        """Heuristic: skip lines that look like examples/templates."""
        stripped = line.strip().lower()
        indicators = [
            "example", "placeholder", "your-key", "your_api", "xxx",
            "sk-your-", "your-secret", "change_me", "changeme", "<your",
        ]
        return any(ind in stripped for ind in indicators)

    @staticmethod
    def _safe_snippet(line: str) -> str:
        """Return a safe snippet (truncated, masked) for display."""
        # Mask the actual value
        masked = re.sub(r'[:=]\s*["\'][^"\']+["\']', '= "***"', line.strip())
        masked = re.sub(r'[:=]\s*[\w\-]{16,}', '= ***', masked)
        return masked[:120]


class DangerousCodeInput(BaseModel):
    """Input for DangerousCodeDetectorTool."""
    directory: str = Field(..., description="Directory to scan for dangerous code patterns")


class DangerousCodeDetectorTool(BaseTool):
    """Detect dangerous code patterns: eval, exec, unsafe deserialization, etc."""

    name: str = "Dangerous Code Detector"
    description: str = "Detect unsafe code patterns: eval(), exec(), pickle, subprocess shell=True, path traversal"
    args_schema: Type[BaseModel] = DangerousCodeInput

    DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
        (r'\beval\s*\(', "eval() call", "critical"),
        (r'\bexec\s*\(', "exec() call", "critical"),
        (r'\bcompile\s*\(', "compile() call", "medium"),
        (r'pickle\.loads?\s*\(', "Pickle deserialization", "high"),
        (r'subprocess\.\w+\s*\([^)]*shell\s*=\s*True', "subprocess with shell=True", "high"),
        (r'os\.system\s*\(', "os.system() call", "high"),
        (r'os\.popen\s*\(', "os.popen() call", "medium"),
        (r'__import__\s*\(', "Dynamic __import__()", "medium"),
        (r'\.\.\/|\.\.\\', "Path traversal pattern", "high"),
        (r'input\s*\(\s*\)', "Unvalidated user input()", "low"),
        (r'raw_input\s*\(\s*\)', "Unvalidated raw_input()", "low"),
        (r'yaml\.load\s*\((?!.*Loader)', "Unsafe YAML load()", "high"),
        (r'request\.(get|post|put|delete)\s*\([^)]*verify\s*=\s*False', "SSL verification disabled", "medium"),
    ]

    def _run(self, directory: str) -> str:
        """Scan for dangerous code patterns."""
        base = Path(directory)
        if not base.exists():
            return json.dumps({"error": f"Directory not found: {directory}"})

        findings: list[dict] = []
        files_scanned = 0

        for py_file in base.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            files_scanned += 1
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue  # Skip comments

                for pattern, name, severity in self.DANGEROUS_PATTERNS:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(py_file.relative_to(base)),
                            "line": i,
                            "pattern": name,
                            "severity": severity,
                            "code": stripped[:150],
                        })

        result = {
            "files_scanned": files_scanned,
            "total_findings": len(findings),
            "findings": findings,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)


class RiskAssessmentInput(BaseModel):
    """Input for RiskAssessmentTool."""
    secret_json: str = Field(default="{}", description="JSON from SecretDetectorTool")
    dangerous_json: str = Field(default="{}", description="JSON from DangerousCodeDetectorTool")
    repo_graph_json: str = Field(default="{}", description="JSON repo_graph for dependency context")


class RiskAssessmentTool(BaseTool):
    """Compute overall security risk from all scan results."""

    name: str = "Risk Assessment Calculator"
    description: str = "Calculate an overall security risk level from multiple scan results"
    args_schema: Type[BaseModel] = RiskAssessmentInput

    def _run(
        self,
        secret_json: str = "{}",
        dangerous_json: str = "{}",
        repo_graph_json: str = "{}",
    ) -> str:
        """Calculate risk and return JSON."""
        try:
            secret = json.loads(secret_json)
        except json.JSONDecodeError:
            secret = {}
        try:
            dangerous = json.loads(dangerous_json)
        except json.JSONDecodeError:
            dangerous = {}
        try:
            repo = json.loads(repo_graph_json)
        except json.JSONDecodeError:
            repo = {}

        vulnerabilities = []

        # Merge secret findings
        for f in secret.get("findings", []):
            vulnerabilities.append({
                "id": f"SEC-{len(vulnerabilities)+1:03d}",
                "severity": f["severity"],
                "category": "Hardcoded Secret",
                "file": f.get("file", ""),
                "description": f"Found {f['type']} at line {f.get('line', '?')}",
                "remediation": "Move to environment variable or secrets manager",
            })

        # Merge dangerous code findings
        for f in dangerous.get("findings", []):
            vulnerabilities.append({
                "id": f"CODE-{len(vulnerabilities)+1:03d}",
                "severity": f["severity"],
                "category": "Dangerous Pattern",
                "file": f.get("file", ""),
                "description": f"{f['pattern']} at line {f.get('line', '?')}",
                "remediation": self._remediation_for(f.get("pattern", "")),
            })

        # Determine overall risk level
        severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        total_weight = sum(severity_weights.get(v["severity"], 0) for v in vulnerabilities)

        if total_weight >= 15 or any(v["severity"] == "critical" for v in vulnerabilities):
            risk_level = "critical"
        elif total_weight >= 8:
            risk_level = "high"
        elif total_weight >= 3:
            risk_level = "medium"
        else:
            risk_level = "low"

        recommendations = [
            "Run `pip-audit` or `safety check` to scan dependencies for known CVEs",
            "Add a pre-commit hook with `detect-secrets` to prevent future leaks",
            "Review all 'critical' findings immediately before deployment",
        ]
        if any(v["category"] == "Hardcoded Secret" for v in vulnerabilities):
            recommendations.append(
                "Replace all hardcoded secrets with environment variables or a secrets manager"
            )

        result = {
            "risk_level": risk_level,
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "recommendations": recommendations,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def _remediation_for(pattern: str) -> str:
        """Get remediation advice for a dangerous pattern."""
        remediations = {
            "eval() call": "Replace eval() with safer alternatives like ast.literal_eval() or custom parsing",
            "exec() call": "Avoid exec(); use explicit code or plugin architecture instead",
            "Pickle deserialization": "Use JSON or a safer serialization format",
            "subprocess with shell=True": "Use shell=False with a list of arguments",
            "os.system() call": "Use subprocess.run() with shell=False and argument list",
            "os.popen() call": "Use subprocess module instead",
            "Unsafe YAML load()": "Use yaml.safe_load() or specify SafeLoader",
            "Path traversal pattern": "Use pathlib to validate paths, restrict to safe directories",
            "SSL verification disabled": "Remove verify=False; configure proper certs if needed",
        }
        return remediations.get(pattern, "Review this pattern for security implications")
