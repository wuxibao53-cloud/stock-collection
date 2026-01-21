# 教学讲义与云端使用指南

欢迎使用本仓库的云端采集与分析环境（教育优惠版）。

## 快速开始
- 触发云端工作流：仓库 Actions → 选择“云端分析” → Run workflow（mode=all, history_days=3）。
- 下载产物：运行完成后在 Artifacts 下载日志、数据库与报告。
- Codespaces：点击仓库 Code → Codespaces → Create codespace on main，打开后直接运行脚本与Notebook。

## 主要脚本
- multi_timeframe_fetcher.py：获取 1f/5f/30f 历史K线（全量/单股）。
- trading_scheduler.py：开盘前/盘中/闭盘后调度演示。

## 教学建议
- Classroom 模板：使用 tests/ 与 CI 自动评分。
- 预算控制：主任务两次/工作日，盘中仅少量更新。
