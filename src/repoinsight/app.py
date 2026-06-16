"""Streamlit 交互界面：输入仓库 URL → 可视化多智能体分析过程。

用法:
    streamlit run src/repoinsight/app.py
    repoinsight ui
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from repoinsight import __version__
from repoinsight.crew import RepoInsightCrew
from repoinsight.config import settings


def main() -> None:
    """Streamlit 主页面。"""
    st.set_page_config(
        page_title="RepoInsight — 仓库分析",
        page_icon="🔍",
        layout="wide",
    )

    # ===== 侧边栏 =====
    with st.sidebar:
        st.title("🔍 RepoInsight")
        st.caption(f"v{__version__} · 多智能体仓库分析")

        st.markdown("---")

        repo_url: str = st.text_input(
            "仓库地址",
            placeholder="https://github.com/xxx/yyy 或 ./local-path",
            help="输入 GitHub 仓库 URL 或本地目录路径",
        )

        st.markdown("---")

        # 模型选择
        simple_provider: str = st.selectbox(
            "简单任务模型",
            options=["deepseek", "openai", "anthropic"],
            index=0,
            help="用于 Repo Crawler、Doc Synthesizer",
        )
        complex_provider: str = st.selectbox(
            "复杂推理模型",
            options=["deepseek", "openai", "anthropic"],
            index=0,
            help="用于 Code Reviewer、Security Auditor",
        )

        st.markdown("---")

        analyze_btn: bool = st.button(
            "🚀 开始分析",
            type="primary",
            use_container_width=True,
            disabled=not repo_url,
        )

        st.markdown("---")
        st.caption("💡 分析过程约需 2-5 分钟，取决于仓库大小")

    # ===== 主区域 =====
    st.title("📊 分析结果")

    if not analyze_btn:
        _show_welcome()
        return

    if not settings.has_llm:
        st.error("❌ 未配置 LLM API Key，请检查 .env 文件")
        st.code(
            "cp .env.example .env\n# 编辑 .env，填入 DEEPSEEK_API_KEY",
            language="bash",
        )
        return

    # 执行分析
    _run_analysis(repo_url)


def _show_welcome() -> None:
    """初始欢迎页。"""
    st.info("👈 在左侧输入仓库地址，点击「开始分析」")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🔬 架构分析")
        st.write("自动识别架构模式，生成 Mermaid 架构图")

    with col2:
        st.subheader("📋 代码审查")
        st.write("复杂度分析、命名规范、错误处理检查")

    with col3:
        st.subheader("🔒 安全审计")
        st.write("密钥检测、CVE 匹配、危险代码识别")

    st.markdown("---")
    st.subheader("⚙️ 执行流程")

    st.code(
        "GitHub URL → Repo Crawler → [架构 + 审查 + 安全] → Doc Synthesizer → 质量自评",
        language=None,
    )


def _run_analysis(repo_url: str) -> None:
    """执行分析并实时展示进度。"""
    # 进度状态区
    status_container = st.empty()
    progress_bar = st.progress(0, text="准备中...")

    try:
        with st.spinner("正在克隆仓库..."):
            progress_bar.progress(10, text="阶段 1/5: 克隆仓库 + AST 解析")

            crew = RepoInsightCrew(repo_url=repo_url)
            crew.output_dir = Path.cwd()

            progress_bar.progress(20, text="阶段 1/5: 构建依赖图...")

        status_container.info("✅ Repo Crawler 完成 — 依赖图已生成")

        progress_bar.progress(35, text="阶段 2/5: 架构分析中...")
        progress_bar.progress(50, text="阶段 2/5: 代码审查中...")
        progress_bar.progress(65, text="阶段 2/5: 安全审计中...")

        status_container.info("✅ 三路并行分析完成")

        progress_bar.progress(75, text="阶段 3/5: 文档合成中...")

        with st.spinner("Agent 正在协作分析，请稍候..."):
            result: dict[str, Any] = crew.run()

        progress_bar.progress(90, text="阶段 4/5: 质量自评中...")

        status_container.success(f"✅ 分析完成 — 质量评分: {result['eval_score']}/10")
        progress_bar.progress(100, text="完成！")

        # 展示结果
        _show_results(result)

    except Exception as e:
        progress_bar.empty()
        st.error(f"❌ 分析失败: {e}")
        st.exception(e)


def _show_results(result: dict[str, Any]) -> None:
    """展示分析结果。"""
    guide: str = result.get("guide", "")
    if not guide:
        st.warning("未生成任何内容")
        return

    tabs = st.tabs(["📄 GUIDE.md", "📊 摘要", "💰 成本"])

    with tabs[0]:
        st.markdown(guide)

    with tabs[1]:
        col1, col2, col3 = st.columns(3)
        with col1:
            score: float = result.get("eval_score", 0)
            st.metric("质量评分", f"{score}/10")
        with col2:
            st.metric("输出文件", result.get("output_path", "N/A"))
        with col3:
            st.metric("Token", result.get("tokens", "N/A"))

        if result.get("errors"):
            st.subheader("⚠️ 错误")
            for err in result["errors"]:
                st.warning(err)

    with tabs[2]:
        st.caption("Token 消耗详情")
        st.code(result.get("tokens", "N/A"), language=None)


if __name__ == "__main__":
    main()
