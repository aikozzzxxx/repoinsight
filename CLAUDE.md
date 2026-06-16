# RepoInsight — 多智能体仓库深度分析平台

输入 GitHub 仓库 URL → 5 个 Agent 协作 → 输出架构图 + 代码质量 + 安全风险 + 新人入门文档。

## 技术栈

| 层 | 选型 |
|---|---|
| Agent 框架 | CrewAI (>=1.0) |
| LLM 接入 | LiteLLM (默认 DeepSeek V3，便宜) |
| Web 搜索 | DuckDuckGo (免费，无需 API Key) |
| UI | Streamlit |
| 终端美化 | Rich |
| 向量记忆 | ChromaDB |
| 依赖图 | NetworkX |
| 环境 | Conda (environment.yml) |
| Python | 3.10 |
| 测试 | pytest + pytest-asyncio |
| CI | GitHub Actions |

## 项目结构

```
repoinsight/
├── .env.example
├── .gitignore
├── environment.yml
├── README.md
├── pyproject.toml
├── CLAUDE.md
├── src/
│   └── repoinsight/
│       ├── __init__.py
│       ├── main.py              # CLI 入口
│       ├── app.py               # Streamlit UI
│       ├── crew.py              # Crew 编排核心
│       ├── state.py             # Pydantic State 跨 Agent 传递
│       ├── config/
│       │   ├── agents.yaml      # 5 Agent 定义
│       │   └── tasks.yaml       # 5+1 Task 定义(含 eval)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── repo_tools.py    # clone, AST, 依赖图
│       │   ├── review_tools.py  # 代码质量检查
│       │   ├── security_tools.py # 安全扫描
│       │   └── doc_tools.py     # 文档生成
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── vector_store.py  # ChromaDB 封装
│       │   └── graph_store.py   # Graph-RAG
│       └── eval/
│           ├── __init__.py
│           └── quality_check.py # Eval-Loop
├── tests/
│   ├── test_tools.py
│   ├── test_crew.py
│   └── fixtures/
├── demos/
│   └── sample_output.md
└── .github/workflows/ci.yml
```

## 五个 Agent

| Agent | 工具 | 输入 | 输出 |
|-------|------|------|------|
| Repo Crawler | git clone, AST, 依赖图 | GitHub URL | `repo_graph.json` |
| Architecture Mapper | 依赖图算法, 模式识别 | repo_graph.json | architecture.md + Mermaid 图 |
| Code Reviewer | lint, 复杂度分析 | repo_graph.json 核心文件 | quality_report.json |
| Security Auditor | CVE 匹配, 敏感信息, ToT | repo_graph.json + 依赖 | security_report.json |
| Doc Synthesizer | 模板渲染, 聚合 | 前四个 Agent 输出 | GUIDE.md |

## 工作流

```
GitHub URL → Repo Crawler (串行)
                ↓
    Architecture Mapper ─┬─ Code Reviewer ─┬─ Security Auditor
    (三路并行)           │                 │
                ↓         ↓                 ↓
              Doc Synthesizer (聚合合成)
                    ↓
                Eval Loop (质量自评, <7分重试最多2轮)
```

## 编码规范

- Python 文件用 UTF-8 编码
- 所有函数加 type hints
- Agent/Task 定义用 YAML，不走纯 Python 硬编码
- 工具类继承 CrewAI BaseTool
- 错误不吞——该抛就抛，在 Crew 层统一处理
- 中文注释/文档用中文，代码/变量/日志用英文

## LLM 策略

- 简单任务(Crawler) → DeepSeek V3 (便宜)
- 复杂推理(Reviewer, Auditor) → Claude Sonnet (推理强)
- 通过 LiteLLM 统一接入，环境变量切模型
- 每次运行结束统计并打印 token 消耗

## 关键约束

- 不提交 .env 文件
- 不提交 clone 下来的仓库(临时目录)
- 测试不依赖真实 LLM 调用，用 Mock
- Streamlit 只做展示，业务逻辑全在 crew.py 和 tools 里
