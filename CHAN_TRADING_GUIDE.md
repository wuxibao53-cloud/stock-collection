# 缠论综合交易系统 - 使用指南

## 功能概述

这是一个完整的A股实时缠论交易系统，包含：

### 1. **分型识别** (fractal_recognition.py)
- 识别顶分型（高点低于两侧）和底分型（低点高于两侧）
- 实时监测新增分型
- 支持多数据源（SQLite、CSV）

### 2. **线段识别** (stroke_recognition.py)
- 连接相邻分型形成线段
- 区分上升线段和下降线段
- 追踪线段方向和幅度

### 3. **中枢检测** (pivot_detection.py)
- 识别价格波动中枢
- 检测任意两条K线是否有重叠
- 支持中枢扩展

### 4. **买卖点算法** (trading_signals.py)
- 第一类买点：底分型形成后上升
- 第一类卖点：顶分型形成后下降
- 结合分型、线段、中枢判断

### 5. **区间套分析** (interval_analysis.py)
- 多周期分析（1分钟、5分钟、1小时）
- 快、中、慢三周期突破检测
- 三周期同步判断 (✓✓✓)

### 6. **实时提醒系统** (realtime_alerts.py)
- 生成分级提醒（弱、中、强）
- 开盘筛选和收盘筛选
- 支持钉钉/企业微信通知
- 数据库记录所有提醒

### 7. **综合系统** (chan_trading_system.py)
- 整合所有模块的协调器
- 一键生成完整分析报告
- 导出JSON格式的分析结果

## 快速开始

### 基础分析

```bash
# 分析单个股票
python chan_trading_system.py --symbol sh600519

# 分析所有股票
python chan_trading_system.py

# 分析并导出报告
python chan_trading_system.py --export
```

### 各模块单独使用

```bash
# 识别分型
python fractal_recognition.py --db logs/quotes.db --symbol sh600519

# 识别线段
python stroke_recognition.py --db logs/quotes.db

# 检测中枢
python pivot_detection.py --db logs/quotes.db --min-bars 5

# 生成买卖点
python trading_signals.py --db logs/quotes.db

# 区间套分析
python interval_analysis.py --db logs/quotes.db

# 交易提醒
python realtime_alerts.py --db logs/quotes.db --opening --closing --summary
```

## 交易信号解读

### 提醒等级

| 标记 | 等级 | 含义 |
|-----|-----|------|
| 🟢 | 弱买 | 单周期出现买信号 |
| 🟢🟢 | 中买 | 二周期同步买信号 |
| 🟢🟢🟢 | 强买 | 三周期同步买信号（最优） |
| 🔴 | 弱卖 | 单周期出现卖信号 |
| 🔴🔴 | 中卖 | 二周期同步卖信号 |
| 🔴🔴🔴 | 强卖 | 三周期同步卖信号（最优） |

### 关键指标

1. **分型** - 市场转折点
   - 顶分型 ▼：空头信号，关键阻力位
   - 底分型 ▲：多头信号，关键支撑位

2. **线段** - 价格运动方向
   - 上升线段：从底分型到下一个顶分型
   - 下降线段：从顶分型到下一个底分型

3. **中枢** - 价格密集区
   - 上升中枢：整体向上的价格汇聚
   - 下降中枢：整体向下的价格汇聚

4. **区间套** - 多周期同步
   - 快周期（1分钟）：快速反应
   - 中周期（5分钟）：趋势确认
   - 慢周期（1小时）：大趋势方向
   - 三周期同步 = 最强信号

## 配置说明

修改 `chan_config.py` 自定义参数：

```python
# 区间套参数
INTERVAL_ANALYSIS_SETTINGS = {
    'fast_cycle_minutes': 15,   # 快周期K线数
    'mid_cycle_minutes': 5,     # 中周期聚合分钟数
    'slow_cycle_minutes': 60,   # 慢周期聚合分钟数
}

# 通知设置
NOTIFICATION_SETTINGS = {
    'enable_dingtalk': True,
    'dingtalk_webhook': 'https://your-webhook-url',
    'enable_wechat': True,
    'wechat_webhook': 'https://your-wechat-webhook',
}
```

## 实盘应用

### 开盘策略
```bash
# 07:30 开盘前筛选前一日K线形态
python realtime_alerts.py --opening
```

### 交易监控
```bash
# 实时监测买卖信号
watch -n 2 "python chan_trading_system.py"
```

### 收盘统计
```bash
# 15:05 收盘后统计符合条件的信号
python realtime_alerts.py --closing --summary
```

## 钉钉/企业微信集成

### 钉钉配置

1. 创建钉钉机器人，获取webhook地址
2. 修改 `chan_config.py`:
```python
NOTIFICATION_SETTINGS = {
    'enable_dingtalk': True,
    'dingtalk_webhook': 'https://oapi.dingtalk.com/robot/send?access_token=xxx',
}
```

### 企业微信配置

1. 创建企业微信应用，获取webhook地址
2. 修改 `chan_config.py`:
```python
NOTIFICATION_SETTINGS = {
    'enable_wechat': True,
    'wechat_webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx',
}
```

## 数据库结构

### minute_bars 表
```sql
CREATE TABLE minute_bars (
    id INTEGER PRIMARY KEY,
    symbol TEXT,           -- 股票代码
    minute TEXT,           -- 时间戳 YYYY-MM-DD HH:MM
    open REAL,            -- 开盘价
    high REAL,            -- 最高价
    low REAL,             -- 最低价
    close REAL,           -- 收盘价
    volume INTEGER        -- 成交量
);
```

### trade_alerts 表
```sql
CREATE TABLE trade_alerts (
    alert_id TEXT PRIMARY KEY,
    symbol TEXT,           -- 股票代码
    signal_type TEXT,      -- 'buy' 或 'sell'
    alert_time TEXT,       -- 提醒时间
    price REAL,            -- 提醒价格
    target_price REAL,     -- 目标价格
    stop_loss REAL,        -- 止损价格
    level INTEGER,         -- 提醒等级 1-3
    reason TEXT,           -- 原因说明
    is_confirmed INTEGER,  -- 是否已确认
    created_at TEXT        -- 创建时间
);
```

## 常见问题

### Q: 如何判断是否应该操作？
**A:** 等待三周期同步信号（✓✓✓），这是最强的买卖信号

### Q: 一天内会有多少信号？
**A:** 根据市场波动程度，通常10-50个信号，其中2-5个为强信号

### Q: 如何避免亏损？
**A:** 严格遵循以下规则：
1. 只在三周期同步时操作
2. 在关键分型位置设置止损
3. 同一支股票同方向最多持仓3个信号周期

### Q: 如何进行回测？
**A:** 修改 `chan_config.py` 中的回测参数，然后运行回测脚本（待开发）

## 后续功能

- [ ] 历史数据回测
- [ ] 最优止损/止盈计算
- [ ] 资金管理模型
- [ ] 组合风险评估
- [ ] WebSocket 实时推送
- [ ] Web Dashboard

## 支持

遇到问题？请检查：
1. 数据库连接是否正常
2. K线数据是否完整
3. 参数配置是否合理
4. 日志文件是否有错误信息

---

**免责声明**: 本系统仅供学习研究使用，不构成投资建议。实际交易需自行承担风险。

**作者**: 仙儿仙儿碎碎念 (xianer_quant)
