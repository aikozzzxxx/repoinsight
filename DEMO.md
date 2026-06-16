# RepoInsight 演示操作指南（新手向）

## 前置准备

### 你需要什么

| 东西 | 用途 | 去哪搞 |
|------|------|--------|
| DeepSeek API Key | 驱动 AI Agent（便宜，几块钱够演示几十次） | [platform.deepseek.com](https://platform.deepseek.com) 注册 → API Keys → 创建 |
| 电脑有 conda | 创建隔离 Python 环境 | 你已经有 Anaconda 了 |

### 10 分钟准备

**第一步：搞到 API Key**

1. 打开 https://platform.deepseek.com
2. 注册账号（手机号就行）
3. 点左侧「API Keys」→「创建 API Key」→ 复制 `sk-xxxx` 那串
4. **最低充值 1 块钱就行，够演示几十次**

**第二步：配置项目**

打开终端（PowerShell），逐条执行：

```powershell
# 1. 进入项目目录
cd D:\AICoding\hello\repoinsight

# 2. 复制配置文件
copy .env.example .env

# 3. 用记事本打开 .env，把刚才的 sk-xxxx 粘贴进去
notepad .env
```

`.env` 文件长这样，**只改第一行**：

```
DEEPSEEK_API_KEY=sk-你的密钥粘贴在这里
DEEPSEEK_MODEL=deepseek-chat
# 下面几行不用管
```

```powershell
# 4. 创建 conda 环境（第一次要等 3-5 分钟，以后不用了）
conda env create -f environment.yml

# 5. 激活环境
conda activate repoinsight

# 6. 验证装好了
python -c "import crewai; print('OK')"
# 屏幕输出 OK 就对了
```

---

## 演示 A：CLI 命令行模式（最简单，面试首选）

### 演示前确认

```powershell
conda activate repoinsight         # 确认环境
cd D:\AICoding\hello\repoinsight   # 确认目录
```

### 开始演示

```powershell
# 分析我们自己的项目（3-5 分钟）
python -m repoinsight.main analyze https://github.com/aikozzzxxx/repoinsight

# 也可以分析一个小点的仓库做测试（30 秒）
python -m repoinsight.main analyze D:\AICoding\hello\repoinsight
```

### 这个过程中你会看到

```
🔍 RepoInsight 开始分析: https://github.com/aikozzzxxx/repoinsight

[Agent 执行日志...]
  - Repo Crawler: 正在 clone 仓库...
  - Repo Crawler: AST 解析中...
  - Architecture Mapper: 分析依赖图...
  - Code Reviewer: 审查热点文件...
  - Security Auditor: 三路安全扫描...

📊 质量自评: 8.2/10 ✅ 通过
💰 Tokens — prompt: 15230, completion: 8241, total: 23471
📄 报告已保存: D:\AICoding\hello\repoinsight\GUIDE.md
```

### 演示时说什么

> "这是完整的分析流水线。5 个 Agent 协作——第一个克隆仓库并解析代码结构，接下来三个并行分析架构、代码质量、安全问题，最后一个汇总生成文档。最后还有一个自动质量检查，如果评分太低会打回去重试。"

### 演示后展示产物

```powershell
# 在 VS Code 或记事本打开生成的报告
code GUIDE.md
```

报告包含 6 个章节：项目概述、架构图（Mermaid）、模块导航、开发环境、代码质量评分、安全风险评估。

---

## 演示 B：Streamlit Web UI（面试加分项）

### 启动

```powershell
conda activate repoinsight
cd D:\AICoding\hello\repoinsight

# 启动 Web UI
python -m repoinsight.main ui
```

浏览器会自动打开 `http://localhost:8501`

### 操作步骤

1. **左侧栏**：输入 `https://github.com/aikozzzxxx/repoinsight`
2. 模型选择保持默认（DeepSeek）
3. 点「🚀 开始分析」
4. 等 2-5 分钟，右侧出现结果

### 结果三个 Tab 切换演示

| Tab | 展示内容 | 说什么 |
|-----|---------|--------|
| 📄 GUIDE.md | 完整渲染的 Markdown 文档 | "最终产物，完全可以给新人当入门文档用" |
| 📊 摘要 | 质量评分、token 消耗 | "质量自评 8.2 分，这次分析花了 2.3 万 token，几毛钱" |
| 💰 成本 | Token 详情 | "按任务选模型——简单任务用 DeepSeek 便宜的，复杂审查用 Claude" |

### 演示时说什么

> "CLI 适合开发调试，Web UI 适合给非技术人员用。同一个后端引擎，两种交互方式。侧边栏可以切换模型——成本敏感的时候全用 DeepSeek 一次分析几毛钱，追求质量的时候复杂任务切 Claude。"

---

## 演示时可能遇到的问题 + 解决方案

| 问题 | 原因 | 解决 |
|------|------|------|
| `No module named repoinsight` | 没在正确目录 / 没装包 | `cd D:\AICoding\hello\repoinsight` 然后 `pip install -e .` |
| `API key not found` | .env 没配 | `notepad .env` 检查是否填了 DEEPSEEK_API_KEY |
| `git clone failed` | 网络问题 | 改用本地目录 `python -m repoinsight.main analyze .` |
| Streamlit 页面空白 | 第一次加载慢 | 等 10 秒，刷新 |
| 分析到一半卡住 | LLM API 超时 | 正常，等 30 秒会自动重试，不用管 |
| 提示 `crewai` 找不到 | 没激活 conda 环境 | `conda activate repoinsight` |

---

## 快速演示版（面试前练 3 遍）

整个演示控制在 3 分钟内，步骤：

```
1. 打开终端，cd 到项目，ls 展示文件结构（15 秒）
2. python -m repoinsight.main analyze . （等 30 秒，过程中讲架构）
3. code GUIDE.md 打开结果（30 秒）
4. python -m repoinsight.main ui （15 秒启动）
5. 浏览器展示 Streamlit 结果 Tab （30 秒）
```

---

## 备用：不依赖 API 也能展示的部分

如果现场网络有问题、API Key 失效，这样兜底：

1. **展示项目结构**：`ls src/repoinsight/` 讲文件分工
2. **展示配置文件**：`code config/agents.yaml` 讲 Agent 设计思路
3. **展示测试**：`pytest tests/ -v` 跑测试（不依赖 LLM）
4. **展示 README**：打开 GitHub 仓库，指架构图讲流程
5. **展示源码**：打开 `crew.py` 讲编排逻辑
