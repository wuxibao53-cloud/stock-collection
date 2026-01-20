# 缠论交易系统 v2.0 — 文章（用于 Word 导出）

导读：

一个能在 GitHub Actions 上自动跑的 A 股缠论信号平台——从高并发数据采集、缠论三类买卖点识别，到回测与风险管理，我们把工程化做了一遍，并把“一键运行”交付给你。

## 1 背景与目标

（略，沿用已发布稿）

## 2 系统架构

异步采集 → SQLite (WAL) → 缠论信号引擎 → 回测 + 风控 → GitHub Actions

## 3 快速上手

本地快速验证（热模式）

```bash
python3 run_complete_system.py --mode all --collect-mode hot --no-backtest
```

完整采集（全量）

```bash
python3 run_complete_system.py --mode all --collect-mode all
```

## 4 实测数据与图示

（请在生成时替换图片：assets/wechat_fig_report.svg / assets/wechat_fig_log.svg）

## 5 FAQ 与下一步

（略）
