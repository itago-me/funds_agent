# Funds Agent

一个面向基金场景的入门 Agent 项目，用于自动获取基金基础信息并生成简短日报，帮助初学者从一个可运行的小项目开始，逐步学习 Agent 应用开发。

> 本项目仅用于信息辅助、研究与学习，不构成投资建议，也不直接提供交易执行能力。

## 项目目标

- 先做出一个能运行的最小基金日报 Agent
- 用尽量简单的方式理解 Agent 的输入、处理和输出
- 在能讲清楚的前提下逐步迭代
- 后续再慢慢扩展成更完整的项目

## 当前阶段

当前项目已经进入 `重新收敛阶段`，现在按初学者路线推进，优先完成最小版本。

当前文档：

- [开发路线图](docs/development-roadmap.md)
- [技术架构设计](docs/architecture.md)
- [合规与免责声明](docs/compliance-and-disclaimer.md)
- [产品概览](docs/product-overview.md)

当前已经进入第二阶段的最小拆分版本，保留简单结构，但不再把所有逻辑都写在一个文件里。

当前优先关注：

- `main.py`
- 示例数据
- 模块拆分
- Markdown 报告输出
- DeepSeek LLM 分析接入
- AkShare 真实基金数据接入
- AkShare 历史净值指标增强
- 基础风险提示
- Watchlist 自选基金列表
- 历史报告索引
- 历史对比分析
- 基金数据历史快照
- 统一报告模板
- 每日任务日志

## 核心能力规划

第一阶段重点能力只有 3 个：

- 读取基金代码或示例数据
- 调用模型生成简短分析
- 输出日报文件

## 为什么用 Agent

这个项目对初学者来说，Agent 的最小形态可以先理解成下面这个流程：

1. 读入任务
2. 收集基础信息
3. 调用模型生成分析
4. 输出结果

先把这个最小流程做出来，再逐步扩展成更完整的工作流。

## 建议的仓库结构

当前建议保持在这个程度：

```text
funds_agent/
├── README.md
├── main.py
├── requirements.txt
├── watchlist.json
├── docs/
├── src/
│   ├── data_loader.py
│   ├── report_writer.py
│   └── simple_analyzer.py
├── reports/
└── sample_data/
```

## 开发路线摘要

- 阶段 1：单文件最小版
- 阶段 2：拆分成小项目
- 阶段 3：增加真实分析价值
- 阶段 4：再做工程化

详细内容见 [开发路线图](docs/development-roadmap.md)。

## 当前阶段建议

当前闭环已经是：

1. 输入基金代码
2. 读取示例数据
3. 生成基础风险提示
4. 生成基础分析或 LLM 分析
5. 输出 Markdown 报告

现在新增了一个小改进：

- 可以通过命令行只生成指定基金的报告
- 可以通过参数切换是否使用 LLM
- 可以尝试使用真实基金数据，并在失败时回退到示例数据
- 报告会展示净值日期、风险等级和变化摘要
- 报告会展示 7 日收益、30 日收益、7 日趋势、7 日最大波动和 30 日回撤
- 可以通过 `watchlist.json` 管理自选基金列表
- 关键失败路径会输出 warning，方便知道当前用了真实数据还是回退数据
- 每次生成报告后，会追加一条记录到 `reports/index.jsonl`
- 报告会读取上一条索引记录，生成一段轻量历史对比
- 每次生成报告后，会把实际用于分析的基金数据追加到 `data/fund_snapshots.jsonl`
- 规则报告和 DeepSeek 报告都按统一日报结构输出
- 每次运行任务后，会追加一条任务日志到 `logs/task_runs.jsonl`

## GitHub 展示重点

这个项目未来在 GitHub 上最应突出以下几点：

- 是一个能跑通的真实小项目
- 路线清晰，适合持续迭代
- 代码复杂度控制得住
- 你自己能完整讲清楚

## 下一步待办

- 用 `main.py` 串起整体流程
- 把逻辑拆到 3 个小模块
- 支持按基金代码筛选
- 接入一个最小 LLM 分析入口

## 本地运行

第一版不建议先启动 API，建议先把脚本跑通。

后续最小运行方式建议类似：

```bash
python main.py
python main.py --codes 000001
python main.py --codes 000001 --use-llm
python main.py --codes 000001 --use-real-data
python main.py --codes 000001 --use-real-data --use-llm
python main.py --use-watchlist
python main.py --use-watchlist --use-real-data --use-llm
```

## 环境变量

如果要使用 DeepSeek 模型分析，需要在项目根目录创建 `.env` 文件，内容可以参考 `.env.example`：

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

程序启动时会自动读取 `.env`。如果没有配置这个变量，即使传了 `--use-llm`，程序也会自动回退到规则分析模式。

## 说明

当前版本已经可以直接从 `sample_data/funds.json` 读取示例基金数据，并把报告输出到 `reports/` 目录。`main.py` 负责流程控制，`src/` 里的小模块分别负责读取数据、生成分析和写报告。

如果设置了 `DEEPSEEK_API_KEY`，可以加上 `--use-llm` 参数调用 DeepSeek 生成分析；如果没有设置，项目仍然会继续使用当前的规则分析版本。

如果安装了 `akshare`，可以加上 `--use-real-data` 参数尝试获取真实基金数据。当前版本只在你传入基金代码时尝试获取真实数据；如果接口不可用、依赖未安装或基金代码无效，程序会自动回退到本地示例数据。

真实数据模式会基于 AkShare 的历史净值计算增强字段，包括 `seven_day_return_percent`、`thirty_day_return_percent`、`max_daily_change_7d`、`trend_7d` 和 `drawdown_30d`。这些字段会进入风险判断、报告模板和 DeepSeek prompt。

如果不想每次手动输入基金代码，可以维护 `watchlist.json`：

```json
{
  "fund_codes": ["000001", "000002"]
}
```

使用 `--use-watchlist` 时，程序会从这个文件读取基金代码。优先级是：`--codes` 命令行参数优先，其次是 `--use-watchlist`，两者都没有时使用全部示例数据。

运行时如果真实数据、watchlist 或 DeepSeek 调用失败，程序会打印 `warning:` 提示，并尽量回退到可用的本地规则报告。

每次报告生成后，程序会在 `reports/index.jsonl` 里记录一次运行信息，包括报告日期、报告路径、数据来源、分析模式、基金代码和 warning。这个文件后续可以用于做历史报告列表、对比分析或定时任务检查。

当前历史对比基于上一条 `reports/index.jsonl` 记录，比较数据来源、分析模式、基金代码和 warning 数量。它不是基金净值级别的精确历史收益对比，而是先帮助你跟踪每次日报任务的运行变化。

基金数据历史快照记录在 `data/fund_snapshots.jsonl`。每次生成报告时，程序会保存每只基金的代码、名称、净值、净值日期、日涨跌、风险等级和变化摘要。下一次再生成报告时，程序会读取同一基金上一条快照，并在报告中加入净值变化和风险等级变化。

报告模板由 `src/report_template.py` 管理。规则模式会直接使用这个模板，DeepSeek 模式会在 prompt 中收到同样的结构要求，保证两种分析模式的输出风格尽量一致。

每日任务日志记录在 `logs/task_runs.jsonl`。它关注任务本身是否运行成功，包括开始时间、结束时间、耗时、状态、数据来源、分析模式、基金代码、报告路径和 warning 数量。这个文件适合后续配合 cron 或其他定时任务排查问题。

后续遇到数据源选择、提示词设计、代码拆分、报告模板和迭代顺序等问题，可以继续在这个仓库里逐步完善。
