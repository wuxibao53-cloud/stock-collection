# 缠论交易系统 v2.0 —— 从数据采集到回测的完整端到端实战

*发布日期：2026-01-20*

作者 | 项目地址：<REPO_URL>（请替换为你的仓库链接）

---

导语

在过去几周里，我构建并验证了一个可在 GitHub Actions 上自动运行的 A 股“缠论”交易系统——从异步数据采集、缠论三类买卖点识别，到回测与风险管理，最后实现了一键端到端管道（collect → analyze → backtest）。本文为该系统的实现要点、运行方法与实测结果总结，适合想把策略工程化并在线部署的同学。

一、项目目标

- 支持热模式（26 只常用标的，极速验证）与全量模式（5000+ A 股，离线积累历史数据）。
- 实现缠论三类买卖点：第一类（线段完成）、第二类（中枢突破）、第三类（多周期共振）。
- 提供回测与风险管理（Kelly 类仓位 + 止损/止盈），并在 GitHub Actions 上自动化运行、生成报告。

二、核心架构（高层）

- 异步采集层：`async_stock_collector.py` / `full_a_stock_collector.py`
  - aiohttp 并发 20，支持 Sina → Tencent 自动降级、代理和 UA 轮换。
- 存储层：SQLite（WAL 模式）
  - `minute_bars` 表，启用 WAL、synchronous= NORMAL、cache_size 优化，写入性能提升 3-5 倍。
- 信号识别层：`chan_theory_3point_signals.py`
  - 分形检测、中枢识别、三类买卖点判断、多周期板块同步检测。
  - 强化了数据校验，避免因字段格式差异导致崩溃。
- 回测与风控层：`backtest_system.py`
  - `Position`、`RiskManager`、`BacktestEngine`，支持 Kelly 仓位、止损/止盈、Sharpe 评估。
- 自动化与报告：GitHub Actions 工作流 (`.github/workflows/full-a-stock-cloud.yml`) 自动采集 → 分析 → 上传 `signals_report.txt` 与日志工件。

三、关键实现细节

1) 异步采集与写入
- 最大并发 20，分批发送请求（batch_size=50），对单次网络异常做重试与降级到备用源。
- 使用 SQLite WAL 模式减少写等待，批量写入以降低事务开销。

2) 缠论三类买卖点
- 分型检测（顶/底分型）使用相邻三根 K 线比较最高/最低值；对数据类型做 `safe_value` 转换以容忍不同来源字段类型。
- 中枢识别基于区间内高低点重叠，并使用 `pivot_threshold`（默认 2%）判断中枢范围。
- 第三类信号要求多周期（如 1m/5m/60m）同步出现以提高置信度。

3) 风险管理与回测
- 使用类似 Kelly 的仓位计算（并支持 fractional Kelly），限制最大单笔亏损（默认 2%）、最大持仓比例（默认 10%）。
- 回测引擎会输出胜率、Sharpe 比率、总 PnL 以及逐笔交易记录，便于策略评估和参数调优。

四、快速上手（命令）

- 快速验证（热模式，26 只，约 1 秒）：
```bash
python3 run_complete_system.py --mode all --collect-mode hot --no-backtest
```

- 完整采集（全量，5000+，约 6–9 分钟）：
```bash
python3 run_complete_system.py --mode all --collect-mode all
```

说明：日志与报告保存在 `logs/` 目录下：
- `logs/collector.log`（采集日志）
- `logs/analysis_report.txt`（信号分析报告）
- `logs/backtest_report.txt`（回测报告）

五、实测数据与性能

- 热模式（26 只）采集耗时 ~0.9s（平均约 28–37 股/秒，取决于网络与代理）
- 估算全量（5000+）耗时约 6–9 分钟（含写入与分析）
- 信号稳定性要求至少 10–15 根 K 线用于分型与中枢识别，数据少时信号会被自动忽略或标记为待确认。

六、常见问题与建议

- 采集到 0 条数据：检查网络与 API 源可用性，或检查 `HTTP_PROXY`/`HTTPS_PROXY` 设置。
- 无信号：确认每只股票至少有 10+ 条 minute K 线；若不足请运行更长时间的采集以累积历史数据。
- GitHub Actions 超时：默认 30 分钟；如需要可把 `timeout-minutes` 提高到 45 或 60。

七、下一步计划

- 在 GitHub Actions 中加入定期回测与参数自动调优任务。
- 集成实时推送（企业微信 / 钉钉）与可选的下单接口。
- 收集 2 周历史数据进行大样本回测，评估长期稳健性。

八、结语

这是一个工程化、可复现的缠论信号平台：从数据采集到信号识别再到回测与风险管理，具备上线到 GitHub Actions 的能力。欢迎试用并反馈你希望的功能（如自动下单、通知渠道、参数调优策略）。

---

附件：本文的实现细节与设计说明已写入仓库文档 `DEPLOYMENT_GUIDE.md` 与 `PROJECT_STATUS.md`，请替换顶部的 `<REPO_URL>` 为你的仓库地址并发布。
