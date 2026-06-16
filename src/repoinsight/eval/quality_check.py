"""Eval-Loop：对最终 GUIDE.md 输出进行启发式质量自评。

评估完整性、准确性、可操作性。若评分 < 7/10，
返回定向反馈，Doc Synthesizer 可据此重试（最多 2 轮）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    """单次评估的结构化结果。"""

    score: float  # 0.0 ~ 10.0
    passed: bool  # score >= 7.0 为通过
    feedback: list[str] = field(default_factory=list)  # 需要改进的点
    strengths: list[str] = field(default_factory=list)  # 做得好的地方
    retry_hint: str = ""  # 下一轮重试应重点改进什么


class GuideEvaluator:
    """GUIDE.md 质量评估器。

    设计原则：对外只有一个 evaluate() 方法，全部评分逻辑封装在内部。
    """

    PASS_THRESHOLD: float = 7.0
    MAX_RETRIES: int = 2

    # 各项检查的满分权重，总和 = 10.0
    WEIGHTS: dict[str, float] = {
        "architecture": 2.5,
        "navigation": 2.0,
        "setup": 1.5,
        "quality": 1.5,
        "security": 1.5,
        "formatting": 1.0,
    }

    def evaluate(self, content: str, retry_count: int = 0) -> EvalResult:
        """对所有检查项打分，返回 EvalResult。

        Args:
            content: 待评估的 GUIDE.md 全文。
            retry_count: 当前是第几次重试（0 = 首轮）。
        """
        # 超过最大重试次数，放弃治疗
        if retry_count > self.MAX_RETRIES:
            return EvalResult(
                score=5.0,
                passed=False,
                feedback=["已达最大重试次数，接受当前输出。"],
                retry_hint="",
            )

        checks = self._run_checks(content)
        score = self._compute_score(checks)
        passed = score >= self.PASS_THRESHOLD

        feedback: list[str] = [c.feedback for c in checks if c.feedback]
        strengths: list[str] = [c.strength for c in checks if c.strength]

        retry_hint: str = ""
        if not passed:
            # 找出得分不到满分 60% 的弱项
            weak_sections: list[str] = [
                c.section for c in checks if c.score < c.max_score * 0.6
            ]
            if weak_sections:
                retry_hint = f"改进以下章节: {', '.join(weak_sections)}。 "

            # 找出完全缺失的章节
            missing: list[str] = [c.section for c in checks if c.score == 0]
            if missing:
                retry_hint += f"缺失章节: {', '.join(missing)}。请补充。"

        return EvalResult(
            score=round(score, 1),
            passed=passed,
            feedback=feedback,
            strengths=strengths,
            retry_hint=retry_hint,
        )

    def _run_checks(self, content: str) -> list[_CheckResult]:
        """运行全部 6 项检查。统一用小写文本做匹配，避免大小写不一致。"""
        lower: str = content.lower()
        return [
            self._check_architecture(lower),
            self._check_navigation(lower),
            self._check_setup(lower),
            self._check_quality(content, lower),
            self._check_security(content, lower),
            self._check_formatting(content),
        ]

    # ===== 单项检查 =====

    def _check_architecture(self, lower: str) -> _CheckResult:
        """检查架构章节：是否有章节标题、Mermaid 图、架构模式识别。"""
        max_s: float = self.WEIGHTS["architecture"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_section: bool = "## 架构" in lower or "## architecture" in lower
        has_mermaid: bool = "```mermaid" in lower
        has_pattern: bool = any(
            kw in lower
            for kw in (
                "mvc", "layered", "微服务", "microservice", "plugin",
                "event", "hexagonal", "monolith", "分层", "单体",
            )
        )

        # 提取架构章节文本长度（统一用小写版本切割，避免大小写 bug）
        arch_text: str = self._extract_section(lower, ["## architecture", "## 架构"])
        arch_length: int = len(arch_text)

        if has_section:
            score += 0.5
        if has_mermaid:
            score += 1.0
            strength = "包含 Mermaid 架构图"
        if has_pattern:
            score += 0.5
        if arch_length > 500:
            score += 0.5

        if not has_section:
            feedback = "缺少架构章节（## Architecture）"
        elif not has_mermaid:
            feedback = "架构章节存在但缺少 Mermaid 图"

        return _CheckResult("architecture", score, max_s, feedback, strength)

    def _check_navigation(self, lower: str) -> _CheckResult:
        """检查模块导航章节：是否有具体文件引用和足够长的描述。"""
        max_s: float = self.WEIGHTS["navigation"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_section: bool = "## 模块导航" in lower or "## module navigation" in lower
        section_text: str = self._extract_section(
            lower, ["## module navigation", "## 模块导航"]
        )

        file_refs: int = sum(1 for line in section_text.splitlines() if "`" in line)
        has_descriptions: bool = len(section_text) > 200

        if has_section:
            score += 0.5
        if file_refs >= 3:
            score += 0.75
        if has_descriptions:
            score += 0.75
            strength = "模块导航包含详细描述"

        if not has_section:
            feedback = "缺少模块导航章节（## Module Navigation）"
        elif file_refs < 3:
            feedback = "模块导航缺少具体的文件/模块引用"

        return _CheckResult("navigation", score, max_s, feedback, strength)

    def _check_setup(self, lower: str) -> _CheckResult:
        """检查开发环境搭建章节：是否有代码块和可执行命令。"""
        max_s: float = self.WEIGHTS["setup"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_section: bool = "## 开发环境" in lower or "## development setup" in lower
        section_text: str = self._extract_section(
            lower, ["## development setup", "## 开发环境"]
        )
        has_code_block: bool = "```" in section_text
        has_commands: bool = any(
            kw in lower for kw in ("pip install", "git clone", "conda", "python", "npm")
        )

        if has_section:
            score += 0.5
        if has_code_block:
            score += 0.5
        if has_commands:
            score += 0.5
            strength = "环境搭建章节包含可执行命令"

        if not has_section:
            feedback = "缺少开发环境章节（## Development Setup）"

        return _CheckResult("setup", score, max_s, feedback, strength)

    def _check_quality(self, content: str, lower: str) -> _CheckResult:
        """检查代码质量章节：是否有评分、结构化表格、优点列举。"""
        max_s: float = self.WEIGHTS["quality"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_section: bool = "## 代码质量" in lower or "## code quality" in lower
        has_score: bool = any(
            kw in lower for kw in ("overall_score", "score:", "quality score", "得分", "评分")
        )
        has_table: bool = "| severity" in lower or "| 严重度" in lower or "| category" in lower
        has_strengths: bool = ("strength" in lower or "优点" in lower) and "✅" in content

        if has_section:
            score += 0.3
        if has_score:
            score += 0.4
        if has_table:
            score += 0.4
            strength = "质量问题以结构化表格呈现"
        if has_strengths:
            score += 0.4

        if not has_section:
            feedback = "缺少代码质量章节（## Code Quality）"

        return _CheckResult("quality", score, max_s, feedback, strength)

    def _check_security(self, content: str, lower: str) -> _CheckResult:
        """检查安全章节：是否有风险等级、漏洞列表、修复建议。"""
        max_s: float = self.WEIGHTS["security"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_section: bool = "## 安全" in lower or "## security" in lower
        section_text: str = self._extract_section(lower, ["## security", "## 安全"])
        has_risk: bool = any(kw in lower for kw in ("risk level", "risk_level", "风险等级"))
        has_vulns: bool = "vuln" in section_text or "漏洞" in section_text
        has_recs: bool = ("recommend" in lower or "建议" in lower) and "🔒" in content

        if has_section:
            score += 0.3
        if has_risk:
            score += 0.4
        if has_vulns:
            score += 0.4
            strength = "漏洞以结构化格式列出"
        if has_recs:
            score += 0.4

        if not has_section:
            feedback = "缺少安全章节（## Security）"

        return _CheckResult("security", score, max_s, feedback, strength)

    def _check_formatting(self, content: str) -> _CheckResult:
        """检查 Markdown 格式规范：标题层级、代码块、表格、段落间距。"""
        max_s: float = self.WEIGHTS["formatting"]
        score: float = 0.0
        feedback: str = ""
        strength: str = ""

        has_title: bool = content.strip().startswith("# ")
        has_h2: bool = "## " in content
        has_code: bool = "```" in content
        has_table: bool = "| " in content
        proper_spacing: bool = "\n\n" in content  # 章节间有空行分隔

        if has_title:
            score += 0.2
        if has_h2:
            score += 0.2
        if has_code:
            score += 0.2
        if has_table:
            score += 0.2
        if proper_spacing:
            score += 0.2
            strength = "Markdown 格式规范，章节间距合理"

        if not has_h2:
            feedback = "文档缺少二级标题"

        return _CheckResult("formatting", score, max_s, feedback, strength)

    # ===== 工具方法 =====

    @staticmethod
    def _extract_section(text: str, headings: list[str]) -> str:
        """从文本中提取某个标题下的内容。

        统一用小写版本文本和标题做匹配，避免大小写不一致导致提取失败。
        取第一个匹配到的标题，截取到下一个 ## 标题为止。
        """
        for heading in headings:
            idx: int = text.find(heading)
            if idx != -1:
                start: int = idx + len(heading)
                rest: str = text[start:]
                next_section: int = rest.find("\n## ")
                if next_section != -1:
                    return rest[:next_section]
                return rest
        return ""

    @staticmethod
    def _compute_score(checks: list[_CheckResult]) -> float:
        """累加所有检查项的得分。权重已内置在各 check 的 max_score 中。"""
        return sum(c.score for c in checks)


@dataclass
class _CheckResult:
    """内部类型：单项检查结果。"""
    section: str
    score: float
    max_score: float
    feedback: str
    strength: str


# ===== 对外公开的便捷函数 =====

# 模块级单例，避免每次调用都 new 对象
_evaluator: GuideEvaluator = GuideEvaluator()


def evaluate_guide(content: str, retry_count: int = 0) -> EvalResult:
    """评估 GUIDE.md 文档质量。对外唯一公开接口。

    Args:
        content: 生成好的 GUIDE.md 全文。
        retry_count: 当前重试次数（0 = 首次评估）。

    Returns:
        EvalResult，包含评分、是否通过、改进建议。
    """
    return _evaluator.evaluate(content, retry_count)
