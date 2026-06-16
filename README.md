# 🔍 RepoInsight

**多智能体仓库深度分析平台** — 输入 GitHub URL，5 个 AI Agent 协作输出架构图、代码质量报告、安全风险评估和新人入门文档。

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CrewAI](https://img.shields.io/badge/framework-CrewAI-orange.svg)](https://crewai.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 工作流

```
GitHub URL
    │
    ▼
┌──────────────────┐
│  Repo Crawler    │  clone + AST 解析 + 依赖图
│  → repo_graph    │
└────────┬─────────┘
         │
    ┌────┴────┬─────────┐
    │         │         │
    ▼         ▼         ▼
┌────────┐ ┌──────┐ ┌──────────┐
│Arch    │ │Code  │ │Security  │  三路并行
│Mapper  │ │Review│ │Auditor   │
│→ arch  │ │→ qual│ │→ security│
└───┬────┘ └──┬───┘ └─────┬────┘
    │         │           │
    └────┬────┴───────────┘
         │
         ▼
┌──────────────────┐
│ Doc Synthesizer  │  聚合合成
│ → GUIDE.md       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Eval Loop      │  质量自评
│   < 7分 → 重试   │
└──────────────────┘
```

## 快速开始

```bash
# 1. 创建环境
conda env create -f environment.yml
conda activate repoinsight

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（推荐，便宜）

# 3. 分析仓库
python -m repoinsight.main analyze https://github.com/crewAIInc/crewAI

# 4. 或启动 Web UI
python -m repoinsight.main ui
```

## 五个 Agent

| Agent | 工具 | 产出 |
|-------|------|------|
| **Repo Crawler** | git clone, AST 解析, 依赖图 | `repo_graph.json` |
| **Architecture Mapper** | 依赖图分析, 模式识别 | 架构图 + Mermaid |
| **Code Reviewer** | 复杂度分析, 风格检查 | 质量评分 + 问题清单 |
| **Security Auditor** | 密钥检测, CVE 模式, 危险代码 | 安全风险报告 |
| **Doc Synthesizer** | 模板渲染, 聚合合成 | `GUIDE.md` |

## 技术亮点

| 技术 | 实现 |
|------|------|
| **多智能体编排** | CrewAI + YAML 驱动配置，三路异步并行 |
| **Agentic RAG** | ChromaDB 向量存储，Agent 自主检索相似代码 |
| **Graph-RAG** | NetworkX 依赖图，沿调用链检索上下文 |
| **Eval-Loop** | 6 维度启发式质量自评，不合格自动重试 |
| **成本控制** | LiteLLM 按任务复杂度分配模型（简单→DeepSeek，复杂→Claude） |
| **混合记忆** | CrewAI short-term + ChromaDB 长期向量记忆 |
| **沙箱隔离** | 代码执行在临时目录 + subprocess |
| **可观测性** | Rich 终端面板 + Streamlit Web UI |

## 项目结构

```
repoinsight/
├── environment.yml          # Conda 环境
├── pyproject.toml           # 项目元数据
├── src/repoinsight/
│   ├── main.py              # CLI 入口
│   ├── app.py               # Streamlit UI
│   ├── crew.py              # Crew 编排核心
│   ├── state.py             # Pydantic 状态模型
│   ├── llm.py               # LiteLLM 封装
│   ├── config.py            # 配置加载
│   ├── config/
│   │   ├── agents.yaml      # 5 Agent 定义
│   │   └── tasks.yaml       # 5 Task 定义
│   ├── tools/
│   │   ├── repo_tools.py    # 仓库分析 (4)
│   │   ├── review_tools.py  # 代码审查 (3)
│   │   ├── security_tools.py # 安全扫描 (3)
│   │   └── doc_tools.py     # 文档合成 (2)
│   ├── memory/
│   │   ├── vector_store.py  # ChromaDB 向量记忆
│   │   └── graph_store.py   # Graph-RAG 知识图谱
│   └── eval/
│       └── quality_check.py # Eval-Loop
├── tests/
│   ├── test_tools.py        # 16 个测试用例
│   └── fixtures/            # 测试用示例仓库
└── .github/workflows/ci.yml
```

## 技术栈

| 层 | 选型 |
|---|---|
| Agent 框架 | CrewAI >= 1.0 |
| LLM 接入 | LiteLLM（默认 DeepSeek V3） |
| 向量记忆 | ChromaDB |
| 图分析 | NetworkX |
| Web UI | Streamlit |
| 终端美化 | Rich |
| 环境管理 | Conda |
| 测试 | pytest |
| CI | GitHub Actions + ruff |

## License

MIT
