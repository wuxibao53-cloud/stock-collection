# 缠论交易系统 - 使用指南

## 🎯 系统架构

```
30f基线分析（全量） → 5f精准监控（候选股） → 1f执行交易（高频）
         ↓                    ↓                  ↓
     生成候选清单          信号触发            邮件通知
```

## 📦 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| **智能过滤** | `smart_stock_filter.py` | 13999股 → 5500正常股 |
| **数据采集** | `multi_timeframe_fetcher.py` | 多线程采集1f/5f/30f |
| **缠论引擎** | `chan_theory_engine.py` | 笔/线段/中枢/三类买卖点 |
| **实时监控** | `realtime_monitor.py` | 5f线程+1f线程，双线程监控 |
| **邮件通知** | `email_notifier.py` | K线图+信号，图文并茂 |
| **主控脚本** | `main.py` | 一键启动，流程编排 |

## 🚀 快速启动

### 1. 完整流程（推荐）

```bash
# 完整流程：过滤→采集→分析→监控→通知
python3 main.py --mode full --days 30 --workers 20
```

### 2. 仅数据采集

```bash
# 只采集数据，不启动监控
python3 main.py --mode collect-only --days 30 --workers 15
```

### 3. 仅实时监控

```bash
# 假设已有数据，直接启动监控
python3 main.py --mode monitor-only
```

## ⚙️ 配置文件

编辑 `config.json`：

```json
{
  "email": {
    "enabled": true,  // 开启邮件通知
    "smtp_server": "smtp.163.com",
    "smtp_port": 465,
    "from_email": "your-email@163.com",
    "password": "your-auth-code",  // 163邮箱授权码
    "to_emails": ["receiver@example.com"]
  }
}
```

使用配置文件启动：

```bash
python3 main.py --config config.json --mode full
```

## 📊 数据流程

### 阶段1: 智能过滤（5秒）

```
获取A股列表 → 移除指数 → 移除ST/退市 → 移除成交量=0 → 移除异常涨跌幅
13999股 → 12000股 → 8000股 → 6500股 → 5500股
```

### 阶段2: 30f基线（8-10分钟，15线程）

```
5500股 × 30天 × 30分钟K线 = 全量采集
↓
缠论分析：笔、线段、中枢、三类买卖点
↓
生成候选清单（约100-300股）
```

### 阶段3: 5f补充（1-2分钟）

```
候选股 × 3天 × 5分钟K线 = 快速补充
```

### 阶段4: 实时监控（持续）

```
5f线程（每3-5分钟）:
  - 扫描候选股
  - 检测买入信号 → 加入1f监控
  
1f线程（每1分钟）:
  - 高频扫描入场股
  - 检测卖出信号 → 移出监控 + 发邮件
```

## 📧 邮件通知示例

**主题**: 🔔 缠论信号提醒 - sh600519 - Buy1第一类买点

**内容**:
- K线图（带分型、中枢、信号标记）
- 信号类型、价格、置信度
- 分型数量、笔数量、中枢数量
- 触发时间

## 📁 文件结构

```
stock_collection/
├── main.py                         # 主控脚本（一键启动）
├── config.json                     # 配置文件
├── smart_stock_filter.py           # 智能过滤器
├── multi_timeframe_fetcher.py      # 多周期数据采集
├── chan_theory_engine.py           # 缠论分析引擎
├── realtime_monitor.py             # 实时监控系统
├── email_notifier.py               # 邮件通知器
├── logs/
│   ├── quotes.db                   # SQLite数据库
│   ├── filtered_stocks.csv         # 过滤后股票
│   ├── watchlist.txt               # 候选股清单
│   ├── system.log                  # 系统日志
│   └── charts/                     # K线图缓存
└── .github/workflows/
    └── cloud-analysis.yml          # GitHub Actions定时任务
```

## 🔧 GitHub Actions云端部署

### 手动触发

1. 进入仓库 → Actions → "Cloud Stock Analysis"
2. 点击 "Run workflow"
3. 填写参数：
   - `days`: 历史天数（默认30）
   - `workers`: 线程数（默认15）

### 定时任务

- **09:15** 早盘前采集
- **15:10** 收盘后采集

## 💡 使用建议

### 本地开发环境

```bash
# 使用20线程，加速采集
python3 main.py --mode full --workers 20 --days 30
```

### 云端环境（GitHub Actions）

```bash
# 使用15线程，稳定可靠
python3 main.py --mode collect-only --workers 15 --days 30
```

### 测试邮件通知

```python
from email_notifier import EmailNotifier
from chan_theory_engine import TradingSignal

# 初始化
notifier = EmailNotifier(
    smtp_server='smtp.163.com',
    smtp_port=465,
    from_email='your@163.com',
    password='your-auth-code',
    to_emails=['receiver@example.com']
)

# 测试信号
signal = TradingSignal(
    signal_type='Buy1',
    timestamp='2025-01-15 14:30:00',
    price=100.5,
    confidence=0.85,
    description='第一类买点'
)

# 发送测试邮件
notifier.send_signal_email('sh600519', '30', signal)
```

## 📊 性能指标

| 任务 | 股票数 | 耗时 | 线程数 |
|------|--------|------|--------|
| 30f全量采集 | 5500 | 8-10分钟 | 15 |
| 5f候选补充 | 300 | 1-2分钟 | 5 |
| 1f实时更新 | 50 | 每分钟 | 2 |

## 🐛 常见问题

### Q1: 邮件发送失败

**A**: 检查以下配置：
1. 163邮箱需要开启SMTP服务
2. 密码使用**授权码**，不是登录密码
3. 防火墙放行465端口

### Q2: TypeError: NoneType

**A**: AKShare API对某些股票返回None，已通过5层异常处理解决，不影响系统运行。

### Q3: 监控线程不工作

**A**: 检查交易时间：
- 工作日 09:30-11:30, 13:00-15:00
- 非交易时间线程休眠

### Q4: 候选股数量过少

**A**: 调整参数：
- 增加 `history_days` 到60天
- 降低 `confidence_threshold` 到0.6

## 📈 后续优化方向

- [ ] 回测系统（验证信号准确率）
- [ ] 风控模块（止损、止盈）
- [ ] 可视化看板（Web界面）
- [ ] 微信/钉钉通知
- [ ] 机器学习优化置信度

---

**版本**: v1.0.0  
**最后更新**: 2025-01-15
