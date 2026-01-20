# A股实时行情采集与分析系统

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于新浪财经API的轻量级A股实时行情监听与分析工具，支持分钟级K线聚合、多格式日志、可视化图表生成，为量化交易与缠论分析打基础。

## ✨ 核心功能

### 📡 实时行情监听
- ✅ 批量请求 + Session复用 + 指数退避重试
- ✅ UA/Referer轮换 + 代理支持，抗403封锁
- ✅ 盘前昨收回退 + 交易时段自动识别
- ✅ 涨跌幅/成交量实时告警
- ✅ 仅交易时段运行、去重输出

### 💾 数据持久化
- **SQLite**: 分钟OHLC聚合（`logs/quotes.db`）
- **CSV**: 明细日志 + 分钟汇总
- **JSON Lines**: 结构化明细，含扩展字段
- **Parquet**: 可选，按日期分区（需PyArrow）

### 📊 可视化与分析
- **蜡烛图**: 红涨绿跌K线图（`plot_candles.py`）
- **统计报告**: 小时汇总 + 日终排行榜（`summaries.py`）
- **日志归档**: 按天归档旧数据（`archive_logs.py`）

### ☁️ 云端采集（GitHub Actions）
- 定时任务：工作日交易时段自动采集
- 数据存储：Artifacts自动归档
- 无需本地运行：全自动云端执行

---

## 🚀 快速开始

### 环境要求
- Python 3.13+
- macOS / Linux / Windows

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基础使用

#### 1. 实时监听（本地）
```bash
# 仅交易时段、去重、聚合、显示涨跌幅
python realtime_cn_stock.py --only-trading --dedup --agg --json-log --show-pct

# 启用分钟摘要与CSV
python realtime_cn_stock.py --only-trading --dedup --agg --minute-summary --minute-csv

# 添加告警（涨跌幅2%、成交量50万）
python realtime_cn_stock.py --only-trading --agg --alert-pct 2.0 --alert-volume 500000
```

#### 2. 生成蜡烛图
```bash
# 从SQLite生成茅台K线图
python plot_candles.py --source sqlite --db logs/quotes.db --symbol sh600519 \
  --start "2026-01-20 09:30" --out logs/candle_sh600519.png

# 从CSV生成
python plot_candles.py --source csv --csv logs/minute_bars_20260120.csv \
  --symbol sz300750 --out logs/candle_sz300750.png
```

#### 3. 统计报告
```bash
# 生成小时汇总与日终报告
python summaries.py --source sqlite --db logs/quotes.db \
  --out-hourly logs/hourly_summary.csv \
  --out-daily logs/daily_report.md
```

#### 4. 日志归档
```bash
# 归档7天前的日志并压缩
python archive_logs.py --logs logs --days 7 --compress
```

---

## 📋 命令行参数

### realtime_cn_stock.py 主要参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--symbols` | 标的列表（逗号分隔） | sh000001,sz399001,sh600519,sz300750 |
| `--interval` | 轮询间隔（秒） | 2 |
| `--snapshot` | 单次快照并退出 | - |
| `--only-trading` | 仅交易时段输出 | - |
| `--dedup` | 去重（价格未变不输出） | - |
| `--agg` | 启用分钟聚合 | - |
| `--db-path` | SQLite路径 | logs/quotes.db |
| `--json-log` | 写JSONL日志 | - |
| `--minute-summary` | 打印分钟摘要 | - |
| `--minute-csv` | 写分钟CSV | - |
| `--show-pct` | 显示涨跌幅 | - |
| `--alert-pct` | 涨跌幅告警阈值 | - |
| `--alert-volume` | 成交量告警阈值 | - |
| `--https` | 使用HTTPS | - |
| `--proxy` | 代理地址 | - |
| `--parquet` | Parquet导出 | - |

---

## 📁 项目结构

```
.
├── realtime_cn_stock.py    # 主采集脚本
├── plot_candles.py          # 蜡烛图生成
├── plot_minutes.py          # 收盘线图生成
├── summaries.py             # 统计报告生成
├── archive_logs.py          # 日志归档
├── requirements.txt         # Python依赖
├── README.md                # 本文档
├── .github/
│   └── workflows/
│       └── collect.yml      # 云端采集Actions
└── logs/                    # 数据目录（.gitignore）
    ├── quotes.db            # SQLite数据库
    ├── realtime_quotes_*.csv
    ├── realtime_quotes_*.jsonl
    ├── minute_bars_*.csv
    ├── hourly_summary.csv
    ├── daily_report.md
    └── *.png                # 图表
```

---

## 🎯 使用场景

### 场景一：日内监控
```bash
# 上午监听（09:30-11:30）
python realtime_cn_stock.py --only-trading --dedup --agg --show-pct --alert-pct 1.5

# 下午继续（13:00-15:00）
# 同一命令，自动追加到同一DB与日志
```

### 场景二：盘后复盘
```bash
# 生成所有标的蜡烛图
for symbol in sh000001 sz399001 sh600519 sz300750; do
  python plot_candles.py --db logs/quotes.db --symbol $symbol \
    --start "2026-01-20 09:30" --out logs/candle_${symbol}.png
done

# 生成统计报告
python summaries.py --db logs/quotes.db
```

### 场景三：云端自动采集（推荐）
1. Fork本仓库到你的GitHub账号
2. 启用Actions（Settings → Actions → Allow all actions）
3. 工作日交易时段自动运行，数据存于Artifacts
4. 下载最新数据：Actions → 最新workflow → Artifacts

---

## 📊 数据示例

### 分钟K线（SQLite）
```sql
SELECT minute, symbol, open, high, low, close, volume, amount
FROM minute_bars
WHERE symbol='sh600519'
ORDER BY minute DESC
LIMIT 10;
```

### 日终报告（Markdown）
| symbol | open | close | pct% | maxVol | sumAmt |
|--------|------|-------|------|--------|--------|
| sh600519 | 1376.96 | 1377.36 | +0.03 | 20998 | 124274193 |

---

## 🔧 进阶配置

### 使用代理
```bash
python realtime_cn_stock.py --https --proxy http://127.0.0.1:7890
```

### 自定义标的
```bash
python realtime_cn_stock.py --symbols sh688981,sz000001,sh601318 --interval 3
```

### Parquet导出（需安装PyArrow）
```bash
pip install pyarrow
python realtime_cn_stock.py --agg --parquet --parquet-path logs/parquet
```

---

## 🛣️ 路线图

- [x] 实时行情采集
- [x] 分钟K线聚合
- [x] 多格式日志
- [x] 蜡烛图可视化
- [x] 统计报告
- [x] GitHub Actions云端采集
- [ ] 缠论分型识别
- [ ] 笔/线段/中枢算法
- [ ] WebSocket实时推送
- [ ] 简单回测框架
- [ ] Streamlit可视化仪表盘

---

## 📝 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 🤝 贡献

欢迎提Issue和PR！

---

## ⚠️ 免责声明

本项目仅供学习与研究使用，不构成任何投资建议。使用本工具进行实盘交易的一切后果由使用者自行承担。

---

**开始你的量化之旅！** 🚀
