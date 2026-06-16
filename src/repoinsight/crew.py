"""Crew 编排核心：将 5 个 Agent、5 个 Task、12 个 Tool 组装为分析流水线。

流水线阶段：
  1. Repo Crawler（串行）→ repo_graph.json
  2. Architecture Mapper + Code Reviewer + Security Auditor（三路并行）
  3. Doc Synthesizer（聚合合成）→ GUIDE.md
  4. Eval Loop（质量自评，不合格打回重试）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from repoinsight.llm import get_llm, token_counter
from repoinsight.state import AnalysisState
from repoinsight.eval.quality_check import evaluate_guide

# 工具导入
from repoinsight.tools.repo_tools import (
    GitCloneTool,
    ASTParserTool,
    DependencyGraphTool,
    FileSummaryTool,
)
from repoinsight.tools.review_tools import (
    ComplexityAnalyzerTool,
    CodeStyleCheckTool,
    QualityScoringTool,
)
from repoinsight.tools.security_tools import (
    SecretDetectorTool,
    DangerousCodeDetectorTool,
    RiskAssessmentTool,
)
from repoinsight.tools.doc_tools import GuideTemplateTool, SaveOutputTool

logger = logging.getLogger(__name__)


@CrewBase
class RepoInsightCrew:
    """RepoInsight 多智能体分析流水线。

    用法:
        crew = RepoInsightCrew(repo_url="https://github.com/xxx/yyy")
        result = crew.run()
        print(result["guide"])
    """

    # YAML 配置文件路径（相对于当前模块）
    agents_config: str = "config/agents.yaml"
    tasks_config: str = "config/tasks.yaml"
    output_dir: Path = Path.cwd()

    def __init__(self, repo_url: str) -> None:
        """初始化流水线。

        Args:
            repo_url: 待分析的 GitHub 仓库 URL 或本地目录路径。
        """
        self.repo_url: str = repo_url
        self.state: AnalysisState = AnalysisState(repo_url=repo_url)

    # ===== Agent 定义 =====

    @agent
    def repo_crawler(self) -> Agent:
        """仓库爬取 Agent：clone + AST + 依赖图。"""
        return Agent(
            config=self.agents_config["repo_crawler"],
            llm=get_llm("simple"),
            tools=[
                GitCloneTool(),
                ASTParserTool(),
                DependencyGraphTool(),
                FileSummaryTool(),
            ],
            verbose=True,
        )

    @agent
    def architecture_mapper(self) -> Agent:
        """架构映射 Agent：依赖图 → 架构模式 + Mermaid 图。"""
        return Agent(
            config=self.agents_config["architecture_mapper"],
            llm=get_llm("complex"),
            verbose=True,
        )

    @agent
    def code_reviewer(self) -> Agent:
        """代码审查 Agent：热点文件 → 质量报告。"""
        return Agent(
            config=self.agents_config["code_reviewer"],
            llm=get_llm("complex"),
            tools=[
                ComplexityAnalyzerTool(),
                CodeStyleCheckTool(),
                QualityScoringTool(),
            ],
            verbose=True,
        )

    @agent
    def security_auditor(self) -> Agent:
        """安全审计 Agent：多路径扫描 → 风险评估。"""
        return Agent(
            config=self.agents_config["security_auditor"],
            llm=get_llm("complex"),
            tools=[
                SecretDetectorTool(),
                DangerousCodeDetectorTool(),
                RiskAssessmentTool(),
            ],
            verbose=True,
        )

    @agent
    def doc_synthesizer(self) -> Agent:
        """文档合成 Agent：聚合报告 → GUIDE.md。"""
        return Agent(
            config=self.agents_config["doc_synthesizer"],
            llm=get_llm("simple"),
            tools=[GuideTemplateTool(), SaveOutputTool()],
            verbose=True,
        )

    # ===== Task 定义 =====

    @task
    def crawl_repo(self) -> Task:
        """Task 1: 克隆仓库并生成依赖图。"""
        return Task(
            config=self.tasks_config["crawl_repo"],
        )

    @task
    def map_architecture(self) -> Task:
        """Task 2a: 架构分析（并行）。"""
        return Task(
            config=self.tasks_config["map_architecture"],
        )

    @task
    def review_code(self) -> Task:
        """Task 2b: 代码审查（并行）。"""
        return Task(
            config=self.tasks_config["review_code"],
        )

    @task
    def audit_security(self) -> Task:
        """Task 2c: 安全审计（并行）。"""
        return Task(
            config=self.tasks_config["audit_security"],
        )

    @task
    def synthesize_docs(self) -> Task:
        """Task 3: 文档合成。"""
        return Task(
            config=self.tasks_config["synthesize_docs"],
        )

    # ===== Crew 组装 =====

    @crew
    def crew(self) -> Crew:
        """完整流水线 Crew。

        编排说明：
        - Process.sequential 保证 Task 按顺序执行
        - 三路并行通过 tasks.yaml 中的 async_execution: true 实现
        - context 字段定义 Task 间的数据依赖关系
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=True,
            verbose=True,
        )

    # ===== 对外接口 =====

    def run(self) -> dict[str, Any]:
        """执行完整分析流水线。

        Returns:
            dict 包含:
            - guide: 生成的 GUIDE.md 内容
            - output_path: 输出文件路径
            - eval_score: 自评分数
            - tokens: token 消耗统计
            - errors: 错误列表
        """
        logger.info("开始分析仓库: %s", self.repo_url)
        print(f"\n🔍 RepoInsight 开始分析: {self.repo_url}\n")

        try:
            raw_result = self.crew().kickoff(inputs={"repo_url": self.repo_url})
            guide = self._extract_guide(raw_result)
        except Exception as e:
            logger.exception("流水线执行失败")
            self.state.errors.append(str(e))
            return self._error_result(str(e))

        # Eval Loop：自评 + 重试
        eval_result = evaluate_guide(guide, retry_count=0)
        print(f"\n📊 质量自评: {eval_result.score}/10 {'✅ 通过' if eval_result.passed else '❌ 需改进'}")
        if eval_result.retry_hint:
            print(f"   → {eval_result.retry_hint}")

        if not eval_result.passed:
            guide = self._retry_with_feedback(guide, eval_result.retry_hint)

        # 保存到文件
        output_path = self.output_dir / "GUIDE.md"
        output_path.write_text(guide, encoding="utf-8")
        logger.info("结果已保存到: %s", output_path)

        return self._success_result(guide, output_path, eval_result.score)

    # ===== 内部方法 =====

    def _extract_guide(self, raw_result: Any) -> str:
        """从 CrewAI 原始结果中提取 GUIDE.md 字符串。"""
        if isinstance(raw_result, str):
            return raw_result
        if hasattr(raw_result, "raw"):
            return str(raw_result.raw)
        if hasattr(raw_result, "tasks_output"):
            # 取最后一个 Task 的输出
            outputs = raw_result.tasks_output
            if outputs:
                return str(outputs[-1])
        return str(raw_result)

    def _retry_with_feedback(self, original_guide: str, hint: str) -> str:
        """带反馈重试文档合成。

        将改进提示作为新的 Task 输入，让 Doc Synthesizer 重新生成。
        """
        retry_count: int = 1
        current_guide: str = original_guide

        while retry_count <= 2:
            print(f"\n🔄 第 {retry_count} 次重试，改进方向: {hint}")

            retry_task = Task(
                description=f"""
最初的 GUIDE.md 需要改进。请根据以下反馈重新生成：

反馈: {hint}

原始文档:
{original_guide[:3000]}

请输出改进后的完整 GUIDE.md。
""",
                expected_output="改进后的完整 GUIDE.md markdown 文档",
                agent=self.doc_synthesizer(),
            )

            retry_crew = Crew(
                agents=[self.doc_synthesizer()],
                tasks=[retry_task],
                process=Process.sequential,
                memory=True,
                verbose=True,
            )

            try:
                raw = retry_crew.kickoff()
                current_guide = self._extract_guide(raw)
            except Exception as e:
                logger.warning("重试 %d 失败: %s", retry_count, e)
                self.state.errors.append(f"重试 {retry_count} 失败: {e}")
                break

            eval_result = evaluate_guide(current_guide, retry_count=retry_count)
            print(f"   重试后评分: {eval_result.score}/10")

            if eval_result.passed:
                break

            retry_count += 1
            if eval_result.retry_hint:
                hint = eval_result.retry_hint

        return current_guide

    def _success_result(
        self, guide: str, output_path: Path, eval_score: float
    ) -> dict[str, Any]:
        """构建成功结果。"""
        return {
            "guide": guide,
            "output_path": str(output_path),
            "eval_score": eval_score,
            "tokens": token_counter.summary(),
            "errors": self.state.errors,
        }

    def _error_result(self, error: str) -> dict[str, Any]:
        """构建错误结果。"""
        return {
            "guide": "",
            "output_path": "",
            "eval_score": 0.0,
            "tokens": token_counter.summary(),
            "errors": [error],
        }
