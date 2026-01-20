# 缠论交易系统 - 快速启动指南

## 系统架构

```
┌─────────────────────────────────────────┐
│     数据采集 (async_stock_collector)    │
│  • 异步20并发 (aiohttp)                 │
│  • 热门26股 或 全5000+A股              │
│  • Sina→Tencent 自动降级               │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  SQLite WAL模式数据存储 (logs/quotes.db)│
│  • 3-5x写入性能提升                    │
│  • minute_bars表 (OHLCV)               │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│   缠论三类买卖点识别系统                  │
│  (chan_theory_3point_signals.py)        │
│  • 第1类买点: 线段完成                 │
│  • 第2类买点: 盘整突破                 │
│  • 第3类买点: 多周期共振               │
│  • 对应卖点体系                        │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  回测与风险管理系统                      │
│  (backtest_system.py)                   │
│  • Position Sizing (Kelly标准)         │
│  • Stop-Loss / Take-Profit自动化       │
│  • Sharpe Ratio评估                    │
│  • 胜率/收益比统计                     │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│     GitHub Actions自动化部署             │
│  • 每日UTC 0:00启动 (北京时间8:00)     │
│  • 支持Manual Trigger选择模式           │
│  • 生成信号报告Artifacts               │
└─────────────────────────────────────────┘
```

## 快速启动

### 1️⃣ 本地快速测试 (推荐先试这个)

```bash
# 采集热门26只股票 + 分析 + 生成报告 (总耗时 ~1分钟)
python3 run_complete_system.py --mode all --collect-mode hot --no-backtest

# 输出应该包含:
# ✓ 采集完成
# ✓ 分析完成 (N只股票分析完毕)
# 📄 报告已保存: logs/analysis_report.txt
```

### 2️⃣ 完整全量采集 + 分析 + 回测 (适合跑过夜任务)

```bash
# 采集全部5000+A股 + 分析 + 回测 (总耗时 ~8-10分钟)
python3 run_complete_system.py --mode all --collect-mode all

# 输出报告:
# logs/analysis_report.txt - 买卖信号报告
# logs/backtest_report.txt - 回测绩效报告
```

### 3️⃣ 各个模块独立运行

```bash
# 仅采集数据
python3 run_complete_system.py --mode collect --collect-mode hot

# 仅执行信号分析
python3 run_complete_system.py --mode analyze

# 仅执行回测
python3 run_complete_system.py --mode backtest --capital 100000
```

## GitHub Actions部署

### ⚙️ 环境变量配置 (需要在GitHub设置Secrets)

Settings → Secrets and Variables → Actions

```
HTTP_PROXY     = [可选] socks5://proxy:port
HTTPS_PROXY    = [可选] socks5://proxy:port  
FORCE_UA       = [可选] Mozilla/5.0...
```

### 🚀 触发工作流

1. **定时触发**: 每天UTC 0:00 (北京时间8:00)
2. **手动触发**: 
   - GitHub → Actions → stock-collect
   - 点击 "Run workflow"
   - 选择采集模式:
     - `hot`: 26个热门股 (~1分钟)
     - `incremental`: 差量更新 (~2分钟)
     - `all`: 全部5000+A股 (~6分钟)

### 📊 查看运行结果

- **Artifacts**: 每次运行后生成报告
  - `collector.log` - 采集日志
  - `signals_report.txt` - 买卖信号汇总
  - 保留30天

## 关键文件说明

| 文件 | 功能 | 关键方法 |
|------|------|--------|
| `async_stock_collector.py` | 异步数据采集 | `collect_incremental_async()`, `collect_all_async()` |
| `chan_theory_3point_signals.py` | 缠论信号识别 | `_identify_first/second/third_buy_point()` |
| `chan_integrated_system.py` | 集成分析框架 | `analyze_multiple_symbols()`, `generate_report()` |
| `backtest_system.py` | 回测与风险管理 | `backtest_symbol()`, `get_statistics()` |
| `run_complete_system.py` | 完整管道编排 | `run_complete_pipeline()` |

## 性能指标

| 场景 | 耗时 | 说明 |
|------|------|------|
| 采集热门26股 | 0.69秒 | 37.7股/秒 吞吐量 |
| 采集全5000股 | ~6.4分钟 | 13股/秒 平均吞吐量 |
| 分析26股信号 | 0.3秒 | 分形检测快速 |
| 分析5000股信号 | ~2分钟 | 40股/秒 分析速度 |
| 完整流程(热模式) | ~1分钟 | 采集+分析+报告 |
| 完整流程(全模式) | ~8分钟 | 采集+分析+回测 |

## 信号解读

### 买点类型

| 类型 | 触发条件 | 可靠性 | 示例 |
|------|---------|------|------|
| 第1类买点 | 线段完成(下跌段底→上升段) | 中等 | V字底部反弹 |
| 第2类买点 | 盘整区间突破 | 中等 | 突破盘整上沿 |
| 第3类买点 | 多周期共振(1m+5m+60m) | 高 | 所有周期同时形成第1类 |

### 卖点类型 (对称)

| 类型 | 触发条件 | 可靠性 |
|------|---------|------|
| 第1类卖点 | 线段完成(上升段顶→下跌段) | 中等 |
| 第2类卖点 | 盘整区间破位 | 中等 |
| 第3类卖点 | 多周期共振 | 高 |

### 置信度指标

```
confidence: 0.0-1.0
• 0.50-0.65: 弱信号 (低吞吐量，高概率)
• 0.65-0.80: 中等信号 (平衡)
• 0.80-1.00: 强信号 (高置信度，特别是第3类)
```

## 风险管理参数

| 参数 | 默认值 | 说明 |
|------|------|------|
| `max_loss_per_trade` | 2% | 单笔最大亏损 |
| `max_position_size` | 10% | 单笔最大持仓 |
| `stop_loss_pct` | 3% | 止损幅度 |
| `risk_reward_ratio` | 1:2 | 风险收益比例 |

## 故障排查

### 问题: 采集0条数据

```bash
# 检查数据源是否可用
curl -s 'https://hq.sinajs.cn/list=sh000001' | head -n 5

# 检查代理设置
echo $HTTP_PROXY $HTTPS_PROXY

# 查看数据库
python3 -c "import sqlite3; c = sqlite3.connect('logs/quotes.db'); print(c.cursor().execute('SELECT COUNT(*) FROM minute_bars').fetchone())"
```

### 问题: 信号识别失败

```bash
# 检查是否有足够K线数据 (需要最少10-15条)
python3 -c "
import sqlite3
c = sqlite3.connect('logs/quotes.db')
for row in c.cursor().execute('SELECT symbol, COUNT(*) FROM minute_bars GROUP BY symbol'):
    symbol, cnt = row
    if cnt < 10:
        print(f'{symbol}: {cnt} 条K线 (不足)')
    else:
        print(f'{symbol}: {cnt} 条K线 ✓')
"
```

### 问题: GitHub Actions超时

```bash
# 降低采集范围或增加超时时间
# 在 .github/workflows/full-a-stock-cloud.yml 中修改:
# timeout-minutes: 30  # 改为 45 或 60
```

## 下一步优化

- [ ] 添加实时行情推送 (WebSocket)
- [ ] 支持多账户交易执行
- [ ] 回测参数自动优化 (GridSearch)
- [ ] 绩效报告自动发送到钉钉/企业微信
- [ ] 支持A股期权交易信号
- [ ] Docker容器化部署

## 联系与支持

遇到问题? 检查:
1. 日志文件: `logs/collector.log`
2. 数据库: `logs/quotes.db` (sqlite3 viewer)
3. GitHub Actions: 查看最近的运行日志
4. 信号报告: `logs/analysis_report.txt`
