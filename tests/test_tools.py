"""工具层测试：验证所有工具通过公开接口的正确行为。

遵循 TDD 规范：
- 测试 WHAT（行为），不测试 HOW（实现细节）
- 使用公开接口，不 mock 内部协作者
- 每个测试验证一个行为
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repoinsight.tools.repo_tools import (
    ASTParserTool,
    DependencyGraphTool,
    FileSummaryTool,
)
from repoinsight.tools.review_tools import (
    ComplexityAnalyzerTool,
    QualityScoringTool,
)
from repoinsight.tools.security_tools import (
    SecretDetectorTool,
    DangerousCodeDetectorTool,
    RiskAssessmentTool,
)
from repoinsight.eval.quality_check import GuideEvaluator, EvalResult

# ===== 测试夹具路径 =====

FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"
SAMPLE_REPO: Path = FIXTURES_DIR / "sample_repo"
UTILS_FILE: Path = SAMPLE_REPO / "sample_pkg" / "utils.py"
MAIN_FILE: Path = SAMPLE_REPO / "sample_pkg" / "main.py"


class TestASTParserTool:
    """测试 AST 解析器：应正确提取 Python 文件的结构信息。"""

    def test_parses_files_and_extracts_functions(self) -> None:
        """AST 解析应提取文件中的函数和类。"""
        tool = ASTParserTool()
        result_json: str = tool._run(str(SAMPLE_REPO))
        result: dict = json.loads(result_json)

        assert result["total_files"] >= 2
        assert result["total_functions"] > 0
        assert result["total_lines"] > 0

    def test_extracted_module_has_expected_fields(self) -> None:
        """每个解析出的模块应包含 functions, classes, imports 字段。"""
        tool = ASTParserTool()
        result_json: str = tool._run(str(SAMPLE_REPO))
        result: dict = json.loads(result_json)

        modules: dict = result["modules"]
        # 找到 utils.py
        utils_modules: list[str] = [k for k in modules if "utils" in k]
        assert len(utils_modules) > 0

        utils_data: dict = modules[utils_modules[0]]
        assert "functions" in utils_data
        assert "classes" in utils_data
        assert "imports" in utils_data


class TestDependencyGraphTool:
    """测试依赖图构建器：应正确推断模块间关系。"""

    def test_builds_graph_with_nodes_and_edges(self) -> None:
        """从 AST 输出构建的图应有节点和边。"""
        # 先跑 AST
        ast_tool = ASTParserTool()
        ast_json: str = ast_tool._run(str(SAMPLE_REPO))

        # 再跑依赖图
        graph_tool = DependencyGraphTool()
        result_json: str = graph_tool._run(ast_json, "sample_repo")
        result: dict = json.loads(result_json)

        assert result["repo_name"] == "sample_repo"
        assert result["language"] == "Python"
        assert result["files"] >= 2
        # 应有至少一个节点
        nodes: list = result["dependency_graph"]["nodes"]
        assert len(nodes) > 0

    def test_core_files_and_hotspots_returned(self) -> None:
        """应返回 core_files 和 complexity_hotspots 列表。"""
        ast_tool = ASTParserTool()
        ast_json: str = ast_tool._run(str(SAMPLE_REPO))

        graph_tool = DependencyGraphTool()
        result_json: str = graph_tool._run(ast_json, "sample_repo")
        result: dict = json.loads(result_json)

        assert isinstance(result["core_files"], list)
        assert isinstance(result["complexity_hotspots"], list)


class TestFileSummaryTool:
    """测试文件摘要工具：应生成可读的目录概览。"""

    def test_generates_summary_for_valid_directory(self) -> None:
        """有效目录应生成文件统计和目录树。"""
        tool = FileSummaryTool()
        result: str = tool._run(str(SAMPLE_REPO))

        assert "sample_repo" in result
        assert ".py" in result

    def test_returns_error_for_missing_directory(self) -> None:
        """不存在的目录应返回错误信息。"""
        tool = FileSummaryTool()
        result: str = tool._run("/nonexistent/path")

        assert "ERROR" in result


class TestComplexityAnalyzerTool:
    """测试复杂度分析器：应检测代码中的复杂度问题。"""

    def test_detects_long_function(self) -> None:
        """应检测到过长的函数（>50 行）。"""
        tool = ComplexityAnalyzerTool()
        result_json: str = tool._run(str(UTILS_FILE))
        result: dict = json.loads(result_json)

        assert result["functions_found"] > 0
        # process_data 函数应触发多个问题
        issues: list = result["issues"]
        process_data_issues: list = [
            i for i in issues if i["name"] == "process_data"
        ]
        assert len(process_data_issues) > 0
        # 验证至少有一个问题标记
        assert len(process_data_issues[0]["details"]) > 0

    def test_complexity_score_below_max(self) -> None:
        """包含问题的文件的复杂度评分应低于满分。"""
        tool = ComplexityAnalyzerTool()
        result_json: str = tool._run(str(UTILS_FILE))
        result: dict = json.loads(result_json)

        assert result["complexity_score"] < 10.0


class TestSecretDetectorTool:
    """测试密钥检测器：应发现硬编码的密钥和令牌。"""

    def test_finds_hardcoded_api_key(self) -> None:
        """应检测到 API Key 格式的硬编码密钥。"""
        tool = SecretDetectorTool()
        result_json: str = tool._run(str(SAMPLE_REPO))
        result: dict = json.loads(result_json)

        assert result["total_findings"] > 0
        # 至少找到一个 "OpenAI-style API Key"
        types_found: list[str] = [f["type"] for f in result["findings"]]
        assert "OpenAI-style API Key" in types_found


class TestDangerousCodeDetectorTool:
    """测试危险代码检测器：应发现 os.system 等不安全模式。"""

    def test_finds_os_system_call(self) -> None:
        """应检测到 os.system() 调用。"""
        tool = DangerousCodeDetectorTool()
        result_json: str = tool._run(str(SAMPLE_REPO))
        result: dict = json.loads(result_json)

        assert result["total_findings"] > 0
        patterns: list[str] = [f["pattern"] for f in result["findings"]]
        assert "os.system() call" in patterns


class TestQualityScoringTool:
    """测试质量评分计算器：应综合复杂度与风格数据计算评分。"""

    def test_computes_score_from_inputs(self) -> None:
        """传入复杂度和风格数据应返回 0-10 的评分。"""
        complexity_json: str = json.dumps({
            "complexity_score": 7.5,
            "files_checked": 3,
        })
        style_json: str = json.dumps({"total_findings": 5})

        tool = QualityScoringTool()
        result_json: str = tool._run(complexity_json, style_json)
        result: dict = json.loads(result_json)

        assert 0 <= result["overall_score"] <= 10
        assert result["grade"]  # 应有等级评定


class TestRiskAssessmentTool:
    """测试风险评估计算器：应综合密钥和危险代码数据评估风险。"""

    def test_high_secrets_produce_elevated_risk(self) -> None:
        """大量密钥发现应产生 high 或 critical 风险等级。"""
        secret_json: str = json.dumps({
            "findings": [
                {"severity": "critical", "type": "API Key", "file": "test.py", "line": 1},
                {"severity": "high", "type": "Secret", "file": "test.py", "line": 2},
            ]
        })
        dangerous_json: str = json.dumps({"findings": []})

        tool = RiskAssessmentTool()
        result_json: str = tool._run(secret_json, dangerous_json)
        result: dict = json.loads(result_json)

        assert result["risk_level"] in ("high", "critical")
        assert len(result["recommendations"]) > 0


class TestGuideEvaluator:
    """测试 GUIDE.md 质量评估器：应对完整/不完整文档给出合理评分。"""

    def test_complete_guide_scores_high(self) -> None:
        """内容齐全的 GUIDE.md 应获得 >= 7 分的评分。"""
        guide: str = """# sample_repo — Developer Guide

## Architecture
项目使用 MVC 架构模式。

```mermaid
graph TD
  A --> B
```

Pattern: MVC

详细架构分析内容。这里需要足够多的文字来确保 arch_length 超过 500 字符。项目包含多个模块，每个模块都有明确的职责分工。控制器层负责处理用户请求，模型层负责数据访问，视图层负责渲染。它们之间通过依赖注入解耦。系统采用事件驱动的方式，模块间通过消息队列通信。

## Module Navigation
- `sample_pkg.utils` — 工具函数，提供数据处理功能
- `sample_pkg.main` — 主入口，包含 API_KEY 配置

每个模块都有清晰的职责，`utils` 包含 `process_data`、`do_thing` 等函数。

## Development Setup
```bash
git clone https://github.com/user/sample_repo
pip install -e .
```

## Code Quality
Overall score: 7.5/10

| severity | category | file | description | suggestion |
|----------|----------|------|-------------|------------|
| P1 | complexity | utils.py | Long function | Split it |

✅ 代码结构清晰

## Security
Risk Level: high

| id | severity | file | description |
|----|----------|------|-------------|
| VULN-001 | high | main.py | Hardcoded API key |

🔒 建议使用环境变量管理密钥
"""
        evaluator = GuideEvaluator()
        result: EvalResult = evaluator.evaluate(guide, retry_count=0)

        assert result.score >= 7.0
        assert result.passed is True

    def test_empty_guide_scores_low(self) -> None:
        """空文档应获得低评分。"""
        evaluator = GuideEvaluator()
        result: EvalResult = evaluator.evaluate("")

        assert result.score < 7.0
        assert result.passed is False

    def test_max_retries_returns_fallback(self) -> None:
        """超过最大重试次数应返回 5.0 分的兜底结果。"""
        evaluator = GuideEvaluator()
        result: EvalResult = evaluator.evaluate("content", retry_count=3)

        assert result.score == 5.0
        assert result.passed is False

    def test_missing_sections_generate_feedback(self) -> None:
        """缺失必要章节时应返回具体反馈。"""
        evaluator = GuideEvaluator()
        result: EvalResult = evaluator.evaluate("# Only Title\n\nNothing else.")

        assert len(result.feedback) > 0
        assert len(result.strengths) < len(result.feedback)  # 问题比优点多


class TestDependencyGraphStore:
    """测试依赖图知识图谱：Graph-RAG 核心功能。"""

    def test_loads_graph_from_json(self) -> None:
        """应能从 repo_graph JSON 正确加载依赖图。"""
        from repoinsight.memory.graph_store import DependencyGraphStore

        graph_data: dict = {
            "dependency_graph": {
                "nodes": [
                    {"id": "A", "file": "a.py", "loc": 100},
                    {"id": "B", "file": "b.py", "loc": 50},
                    {"id": "C", "file": "c.py", "loc": 30},
                ],
                "edges": [
                    {"source": "A", "target": "B"},
                    {"source": "B", "target": "C"},
                ],
            }
        }

        store = DependencyGraphStore()
        count: int = store.load_from_json(graph_data)

        assert count == 3
        assert store.is_loaded

    def test_impact_zone_returns_affected_modules(self) -> None:
        """修改模块 A 应影响其下游模块 B 和 C。"""
        from repoinsight.memory.graph_store import DependencyGraphStore

        graph_data: dict = {
            "dependency_graph": {
                "nodes": [
                    {"id": "A", "file": "a.py", "loc": 100},
                    {"id": "B", "file": "b.py", "loc": 50},
                    {"id": "C", "file": "c.py", "loc": 30},
                ],
                "edges": [
                    {"source": "A", "target": "B"},
                    {"source": "B", "target": "C"},
                ],
            }
        }

        store = DependencyGraphStore()
        store.load_from_json(graph_data)

        impact: list[dict] = store.get_impact_zone("A", max_depth=3)
        impacted_names: list[str] = [i["name"] for i in impact]

        assert "B" in impacted_names
        assert "C" in impacted_names

    def test_circular_dependency_detection(self) -> None:
        """应检测到循环依赖 A→B→A。"""
        from repoinsight.memory.graph_store import DependencyGraphStore

        graph_data: dict = {
            "dependency_graph": {
                "nodes": [
                    {"id": "A", "file": "a.py", "loc": 100},
                    {"id": "B", "file": "b.py", "loc": 50},
                ],
                "edges": [
                    {"source": "A", "target": "B"},
                    {"source": "B", "target": "A"},
                ],
            }
        }

        store = DependencyGraphStore()
        store.load_from_json(graph_data)

        cycles: list[list[str]] = store.get_circular_dependencies()
        assert len(cycles) > 0
