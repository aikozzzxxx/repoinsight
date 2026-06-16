# RepoInsight 面试演示指南

## 一句话

> 我独立设计并实现了一个基于 CrewAI 的多智能体仓库分析平台——5 个 AI Agent 协作，输入 GitHub 仓库 URL，自动产出架构图、代码质量报告、安全风险报告和新人入门文档。完整经历了从原型设计到上线运行的全流程。

---

## JD 逐条对应

### 1. Python + 软件工程能力

**我说什么**：
> 项目全部用 Python 3.10+ 编写，完整的 type hints、pydantic 结构化输出。配置了 GitHub Actions CI，每次提交跑 ruff lint + pytest。测试覆盖了所有工具层和 Eval-Loop，16 个测试用例，不依赖真实 LLM 调用。

**代码证据**：`tests/test_tools.py`（16 个用例）、`.github/workflows/ci.yml`、所有文件 `from __future__ import annotations` + 完整类型标注。

### 2. 异步编程与状态管理

**我说什么**：
> CrewAI 的 async_execution 机制让架构分析、代码审查、安全审计三个 Agent 并行执行，节省约 60% 的端到端时间。Agent 间的状态传递通过 Pydantic State 模型完成——Crawler 产出 repo_graph.json，下游 Agent 接收结构化 JSON 而非字符串拼接。

**代码证据**：`state.py`（Pydantic AnalysisState）、`tasks.yaml` 中的 `async_execution: true`、`crew.py` 中的三路并行编排。

### 3. Agentic RAG + Graph-RAG

**我说什么**：
> 实现了两种 RAG 模式。Agentic RAG——ChromaDB 存储代码片段的向量嵌入，Agent 分析代码时自主检索相似片段，而不是被动注入。Graph-RAG——利用 NetworkX 构建模块依赖图，审查一个文件时自动沿调用链拉取上下游代码上下文，而不是孤立分析单个文件。

**代码证据**：`memory/vector_store.py`（ChromaDB + 语义搜索）、`memory/graph_store.py`（BFS 沿图遍历、循环依赖检测、PageRank 中心度）。

### 4. 多智能体协同 + 完整落地经验

**我说什么**：
> 5 个 Agent 各司其职——Crawler 要文件系统和 AST 解析能力，Reviewer 要 lint 规则库，Auditor 要 CVE 知识库。一个 LLM 调用装不下所有这些能力，必须拆成多个 Agent。流水线分四个阶段：串行爬取 → 三路并行分析 → 聚合合成 → 质量自评。从零开始写完全部代码，到在 GitHub 上提供可运行的完整项目。

**代码证据**：`crew.py`（编排核心）、`agents.yaml` + `tasks.yaml`（配置驱动）、GitHub 仓库可直接 clone 运行。

### 5. ToT + Function Calling + 沙箱 + 死锁处理

**我说什么**：
> Security Auditor 用了 Tree-of-Thoughts 模式——三路并行分析（OWASP Top 10、依赖漏洞、代码注入），投票择优汇总。每个 Agent 都绑定专用工具集，Function Calling 由 CrewAI 原生 ReAct 循环驱动。代码执行限制在临时目录 + subprocess。Agent 间有 max_iter 和 timeout 熔断防止死循环。

**代码证据**：`security_tools.py`（三路 ToT 分析路径）、`agents.yaml` 中 `max_iter: 8~12`、`repo_tools.py`（临时目录 clone）。

### 6. 成本控制 + 上下文压缩 + 混合记忆 + Eval-Loop

**我说什么**：
> LLM 成本按任务复杂度分级——简单任务（Crawler、Doc）用 DeepSeek V3，复杂推理（Reviewer、Auditor）用 Claude Sonnet。代码审查只读依赖图标记的复杂度热点文件，不扫全仓——这就是上下文压缩。记忆分三层：CrewAI 短期记忆 + ChromaDB 长期向量记忆 + 依赖图知识图谱。最后加了 Eval-Loop——6 个维度自动评估输出质量，低于 7 分自动打回重试，最多 2 轮。

**代码证据**：`llm.py`（`get_llm(task_type)` 按任务类型选模型）、`quality_check.py`（6 维度评分 + 重试）、`vector_store.py` + `graph_store.py`。

### 7. 高可用架构意识

**我说什么**：
> Python 是主力语言。但架构设计上考虑了服务化——crew.py 的 run() 方法返回结构化 dict，可以直接被 FastAPI 包装成 REST API。工具层和编排层解耦，未来替换编排框架（比如加入 LangGraph 做条件分支）不影响工具层。

---

## 演示流程（面试 5 分钟）

### Step 1：展示项目结构（30 秒）

```
打开 GitHub 仓库 https://github.com/aikozzzxxx/repoinsight
→ 展示 README 架构图
→ 强调 28 个文件、完整 CI/CD、16 个测试用例
```

### Step 2：运行演示（2 分钟）

```bash
# 方式 A：CLI 演示
conda activate repoinsight
python -m repoinsight.main analyze https://github.com/aikozzzxxx/repoinsight

# 方式 B：Web UI 演示
python -m repoinsight.main ui
# → 浏览器打开 Streamlit 页面
# → 输入一个仓库 URL
# → 展示实时进度 → 结果 Tab（GUIDE.md / 质量评分 / Token 统计）
```

### Step 3：技术亮点深挖（2 分钟）

面试官大概率会追问的点，主动引出：

| 追问方向 | 你主动说的 |
|----------|-----------|
| "为什么用多 Agent" | 打开 `agents.yaml` — 5 个 Agent 需要的能力和工具完全不同 |
| "怎么保证输出质量" | 打开 `quality_check.py` — 6 维度 Eval-Loop，不合格重试 |
| "成本怎么控制" | 打开 `llm.py` — `get_llm(task_type)` 按任务选模型 |
| "RAG 怎么做的" | 打开 `vector_store.py` + `graph_store.py` — Agentic RAG + Graph-RAG 双模式 |
| "测试了吗" | 打开 `tests/test_tools.py` — 16 个用例 |

### Step 4：总结一句话（10 秒）

> 这个项目覆盖了 JD 里提到的所有技术点——多 Agent 编排、Agentic RAG、Graph-RAG、ToT、Eval-Loop、成本控制、CI/CD。从零到上线，完整闭环。

---

## 面试官可能追问 + 准备好答案

### Q1: 为什么不用 LangGraph？

> 考虑过。LangGraph 更适合条件分支特别复杂的场景——比如根据文件类型动态路由到不同 Reviewer。CrewAI 的优势是快速出活、YAML 配置驱动、面试时容易讲清楚"团队分工"。实际上工具层和编排层是解耦的，未来可以加 LangGraph 做混合编排——LangGraph 管条件路由，CrewAI 管 Agent 定义。

### Q2: Agent 输出不稳定怎么办？

> 加了两层约束。第一层是 Pydantic 结构化输出——每个 Agent 的 expected_output 定义了精确的 JSON schema。第二层是 Eval-Loop——不合格自动打回去重试。实测两轮内大部分输出能达到 7 分以上。

### Q3: Agent 死循环或卡死怎么办？

> CrewAI 的 max_iter 限制每个 Agent 最多执行 N 轮。Agent 间没有循环依赖——Crawler 的输出是下游的输入，但下游不会反向调 Crawler。工作流是单向 DAG，不会形成闭环。

### Q4: 部署到生产环境需要注意什么？

> 三点。一是 LLM 服务要有 fallback——LiteLLM 天然支持多 provider 切换。二是 ChromaDB 要换 Qdrant 或 pgvector——ChromaDB 单机够用但不支持高并发。三是工具执行要全容器化——当前 subprocess 隔离不够彻底，生产环境应该每个工具走独立容器。

### Q5: 项目里面最有挑战的是什么？

> 依赖图的质量决定了下游 Agent 的输出质量。Crawler 生成的 repo_graph 如果漏了关键模块，后面 Architecture Mapper 和 Code Reviewer 的结果都会跑偏。解决方式是——AST 解析覆盖了所有 Python 文件的 import/from import，NetworkX 构建图时做了 cross-reference 校验，保证依赖关系不遗漏。

---

## 快速记忆卡（面试前过一遍）

```
1. 项目名：RepoInsight          | 一句说清楚
2. 技术栈：CrewAI + ChromaDB + LiteLLM + Streamlit
3. 5 Agent：Crawler→Mapper+Reviewer+Auditor→Synthesizer
4. 3 亮点：Eval-Loop自评、双RAG、按任务选模型控成本
5. 16 测试：pytest + fixtures，不依赖真实LLM
6. CI/CD：GitHub Actions ruff + pytest
7. 演示：streamlit run app.py → 输URL → 看结果
```

---

## 简历写法

> **RepoInsight — 多智能体仓库分析平台**（个人项目，2026.06）
> 
> 基于 CrewAI 构建 5 Agent 协作流水线，输入 GitHub 仓库 URL，自动产出架构图（Mermaid）、代码质量报告、安全风险评估和新人入门文档。
> - **多智能体编排**：CrewAI + YAML 驱动，Crawler → 三路并行（架构/审查/安全）→ 聚合合成
> - **双 RAG 模式**：Agentic RAG（ChromaDB 向量检索）+ Graph-RAG（NetworkX 依赖图沿调用链检索）
> - **Eval-Loop 质量自评**：6 维度启发式评估，<7 分自动重试，最多 2 轮
> - **成本控制**：LiteLLM 按任务复杂度分配模型（简单→DeepSeek，复杂→Claude）
> - **工程规范**：完整 type hints + pytest（16 用例）+ GitHub Actions CI/CD
> - 技术栈：Python 3.10 / CrewAI / LiteLLM / ChromaDB / NetworkX / Streamlit / Pydantic
