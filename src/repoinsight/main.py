"""CLI 入口：repoinsight analyze <url> → 多智能体协作分析仓库。

用法:
    repoinsight analyze https://github.com/xxx/yyy
    repoinsight analyze ./local-project
    repoinsight ui
    repoinsight --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel

from repoinsight import __version__
from repoinsight.crew import RepoInsightCrew
from repoinsight.config import settings

console = Console()


def cmd_analyze(args: argparse.Namespace) -> int:
    """analyze 子命令：分析仓库并生成 GUIDE.md。

    Returns:
        0 表示成功，1 表示失败。
    """
    repo_url: str = args.repo
    output_dir: str = args.output or "."

    # 检查 API Key
    if not settings.has_llm:
        console.print(
            "[bold red]❌ 未配置 LLM API Key[/bold red]\n\n"
            "请复制 .env.example 为 .env，填入至少一个 API Key:\n"
            "  - DEEPSEEK_API_KEY（推荐，便宜）\n"
            "  - OPENAI_API_KEY\n"
            "  - ANTHROPIC_API_KEY"
        )
        return 1

    console.print(Panel.fit(
        f"[bold cyan]RepoInsight[/bold cyan] v{__version__}\n"
        f"多智能体仓库深度分析平台",
        border_style="cyan",
    ))

    # 构建 Crew
    crew = RepoInsightCrew(repo_url=repo_url)
    crew.output_dir = Path(output_dir)

    # 执行
    try:
        result = crew.run()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ 用户中断[/bold yellow]")
        return 130

    # 输出结果
    if result["errors"]:
        for err in result["errors"]:
            console.print(f"[red]❌ {err}[/red]")
        if not result["guide"]:
            return 1

    _print_result(result)
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """ui 子命令：启动 Streamlit 交互界面。"""
    import subprocess

    app_path: Path = Path(__file__).parent / "app.py"
    if not app_path.exists():
        console.print(f"[red]❌ 找不到 app.py: {app_path}[/red]")
        return 1

    console.print("[cyan]🚀 启动 Streamlit UI...[/cyan]")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
    return 0


def _print_result(result: dict) -> None:
    """用 Rich 美化输出分析结果。"""
    console.print("")

    # Token 统计
    console.print(f"[dim]💰 {result['tokens']}[/dim]")

    # 评分
    score: float = result.get("eval_score", 0.0)
    color: str = "green" if score >= 7.0 else "yellow" if score >= 5.0 else "red"
    console.print(f"[{color}]📊 质量评分: {score}/10[/{color}]")

    # 输出路径
    output_path: str = result.get("output_path", "")
    if output_path:
        console.print(f"[green]📄 报告已保存: {output_path}[/green]")

    console.print("")

    # 预览 GUIDE.md 前 40 行
    guide: str = result.get("guide", "")
    if guide:
        lines: list[str] = guide.splitlines()[:40]
        preview: str = "\n".join(lines)
        console.print(Panel(
            preview,
            title="[bold]GUIDE.md 预览[/bold]",
            border_style="green",
        ))
        if len(guide.splitlines()) > 40:
            console.print(f"[dim]... (共 {len(guide.splitlines())} 行，查看完整内容请打开 {output_path})[/dim]")


def main(argv: Sequence[str] | None = None) -> int:
    """主入口：解析参数，分发子命令。

    Args:
        argv: 命令行参数列表，None 表示从 sys.argv 读取。

    Returns:
        退出码（0 成功，非 0 失败）。
    """
    parser = argparse.ArgumentParser(
        prog="repoinsight",
        description="RepoInsight — 多智能体仓库深度分析平台",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  repoinsight analyze https://github.com/crewAIInc/crewAI
  repoinsight analyze ./my-project -o ./reports
  repoinsight ui
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"repoinsight v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # analyze 子命令
    analyze_parser = subparsers.add_parser("analyze", help="分析仓库")
    analyze_parser.add_argument(
        "repo",
        help="GitHub 仓库 URL 或本地目录路径",
    )
    analyze_parser.add_argument(
        "-o", "--output",
        default=".",
        help="输出目录（默认: 当前目录）",
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # ui 子命令
    ui_parser = subparsers.add_parser("ui", help="启动 Streamlit 交互界面")
    ui_parser.set_defaults(func=cmd_ui)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
