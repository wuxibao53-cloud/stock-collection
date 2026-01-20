# 缠论完整交易系统 - 功能手册

## 📚 系统概览

这是一个**完整的A股实时缠论交易系统**，从分型识别、线段连接、中枢检测，到买卖点生成、多周期分析、实时提醒的全套解决方案。

**核心特点:**
- ✅ 完全自动化的缠论分析流程
- ✅ 三周期多层级同步判断
- ✅ 实时交易信号生成
- ✅ 开盘/收盘筛选策略
- ✅ 钉钉/企业微信告警集成
- ✅ 数据库级别的信号记录

---

## 🔧 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│           缠论综合交易系统 (chan_trading_system.py)        │
└──────────────┬──────────────────────────────────────────────┘
               │
        ┌──────┴─────────┬──────────────────┬──────────────┐
        │                │                  │              │
    ┌───▼────┐   ┌──────▼─────┐   ┌────────▼─┐   ┌─────▼──────┐
    │ 分型   │   │ 线段       │   │ 中枢     │   │ 交易信号   │
    │ 识别   │   │ 识别       │   │ 检测     │   │ 生成       │
    └───┬────┘   └──────┬─────┘   └────────┬─┘   └─────┬──────┘
        │                │                  │            │
    (fractals)        (strokes)            (pivots)  (signals)
        │                │                  │            │
        └────────────────┴──────────────────┴────────────┘
               │
        ┌──────▼─────────────────────┐
        │ 区间套多周期分析           │
        │ (interval_analysis.py)     │
        │ 快/中/慢三周期同步判断    │
        └──────┬─────────────────────┘
               │
        ┌──────▼──────────────┐
        │ 实时提醒系统        │
        │ (realtime_alerts.py)│
        │ • 分级提醒          │
        │ • 钉钉通知          │
        │ • 数据库记录        │
        └─────────────────────┘
```

---

## 📦 模块清单

### 1️⃣ **分型识别** (`fractal_recognition.py`)
**功能**: 识别顶分型和底分型

```python
# 顶分型：高点低于两侧 (H[i] > H[i-1] AND H[i] > H[i+1])
# 底分型：低点高于两侧 (L[i] < L[i-1] AND L[i] < L[i+1])

python fractal_recognition.py --db logs/quotes.db --symbol sh600519
```

**输出**:
- 24个分型识别 (4个符号 × 6-7个分型)
- 顶分型标记为 ▼（空头）
- 底分型标记为 ▲（多头）

---

### 2️⃣ **线段识别** (`stroke_recognition.py`)
**功能**: 连接相邻分型形成线段

```python
# 上升线段: 底分型 → 顶分型
# 下降线段: 顶分型 → 底分型

python stroke_recognition.py --db logs/quotes.db
```

**输出**:
```
sh600519 | 总计:4 | 上升线段:2 | 下降线段:2
  [线段#1 上升] sh600519 2026-01-20 09:38→2026-01-20 10:10 H:1378.12 L:1360.01
```

---

### 3️⃣ **中枢检测** (`pivot_detection.py`)
**功能**: 识别价格波动中枢

```python
# 中枢: 任意两条K线都有重叠的连续区间（最少5条）
# 计算中枢中心轴线: (high + low) / 2
# 中枢高度: high - low

python pivot_detection.py --db logs/quotes.db --min-bars 5
```

**输出**:
```
[中枢#1 下降] sh600519 2026-01-20 10:05→2026-01-20 10:10
轴:1373.52 高度:4.62
```

---

### 4️⃣ **买卖点算法** (`trading_signals.py`)
**功能**: 生成交易信号

```python
# 第一类买点: 底分型后价格上升
# 第一类卖点: 顶分型后价格下降

python trading_signals.py --db logs/quotes.db
```

**输出**:
```
🟢 买入提醒 (0个):
🔴 卖出提醒 (4个):
  🔴🔴 sh600519 SELL 2026-01-20 10:10 1378.12 | 顶分型出现
```

---

### 5️⃣ **区间套分析** (`interval_analysis.py`)
**功能**: 多周期同步判断

```python
# 快周期: 15分钟K线（快速反应）
# 中周期: 5分钟聚合线（趋势确认）
# 慢周期: 60分钟聚合线（大趋势方向）

# 三周期同步 = 最强信号！

python interval_analysis.py --db logs/quotes.db
```

**分析过程**:
1. 检测快周期是否突破中枢上/下沿
2. 检测中周期是否同向突破
3. 检测慢周期是否同向突破
4. 计算信号强度 (0-1)

---

### 6️⃣ **实时提醒系统** (`realtime_alerts.py`)
**功能**: 生成分级提醒和告警

```python
# 提醒等级:
# 🟢 弱信号 (等级1)   - 单周期
# 🟢🟢 中信号 (等级2)  - 二周期同步  
# 🟢🟢🟢 强信号 (等级3) - 三周期同步 ← 最佳操作机会

python realtime_alerts.py --db logs/quotes.db --opening --closing --summary
```

**功能**:
- 开盘筛选: `--opening` 
- 收盘筛选: `--closing`
- 今日统计: `--summary`

---

### 7️⃣ **综合系统** (`chan_trading_system.py`)
**功能**: 整合所有模块的协调器

```python
# 完整流程: 分型 → 线段 → 中枢 → 信号 → 区间套 → 提醒

# 分析单个股票
python chan_trading_system.py --symbol sh600519

# 分析所有股票
python chan_trading_system.py

# 分析并导出报告
python chan_trading_system.py --export
```

**输出格式**:
```
🔍 sh600519 | 价格:1374.60
   分型: 5 (顶:3 底:2)
   线段: 4 (上升:2 下降:2)
   中枢: 0 (上升:0 下降:0)
   信号: 买0 卖1
   区间: 快:None 中:None 慢:None
```

---

### 8️⃣ **监控仪表板** (`monitor.py`)
**功能**: 简化的实时监控脚本

```python
# 快速分析
python monitor.py

# 分析指定股票
python monitor.py --symbol sh600519

# 指定数据库
python monitor.py --db ../logs/quotes.db
```

---

## 🎯 使用流程

### 场景1: 每日开盘前准备

```bash
# 1. 筛选前一交易日形态
python realtime_alerts.py --opening

# 输出: 符合条件的早间买卖点
# 🟢🟢🟢 sh600519 BUY 09:30 1360.00 (三周期同步)
```

### 场景2: 实时监控交易

```bash
# 1. 每5分钟运行一次
watch -n 300 "python monitor.py"

# 2. 关注三周期同步信号
# 🟢🟢🟢 sh300750 BUY (强度90%)
```

### 场景3: 每日收盘后总结

```bash
# 1. 筛选尾盘信号
python realtime_alerts.py --closing

# 2. 生成日报
python monitor.py --db logs/quotes.db

# 3. 查看日统计
python realtime_alerts.py --summary
```

---

## 📊 数据库结构

### minute_bars 表
```sql
CREATE TABLE minute_bars (
    symbol TEXT,        -- 股票代码
    minute TEXT,        -- 时间戳 YYYY-MM-DD HH:MM
    open REAL,          -- 开盘价
    high REAL,          -- 最高价
    low REAL,           -- 最低价
    close REAL,         -- 收盘价
    volume INTEGER      -- 成交量
);
```

### trade_alerts 表
```sql
CREATE TABLE trade_alerts (
    alert_id TEXT,      -- 提醒ID
    symbol TEXT,        -- 股票代码
    signal_type TEXT,   -- 'buy' or 'sell'
    alert_time TEXT,    -- 提醒时间
    price REAL,         -- 提醒价格
    level INTEGER,      -- 等级 1-3
    reason TEXT,        -- 原因说明
    is_confirmed INTEGER -- 是否已确认
);
```

---

## ⚙️ 配置参数

编辑 `chan_config.py` 自定义系统参数:

```python
# 区间套参数
INTERVAL_ANALYSIS_SETTINGS = {
    'fast_cycle_minutes': 15,   # 快周期K线数
    'mid_cycle_minutes': 5,     # 中周期聚合分钟数
    'slow_cycle_minutes': 60,   # 慢周期聚合分钟数
    'breakout_threshold': 0.01, # 突破阈值（百分比）
}

# 通知配置
NOTIFICATION_SETTINGS = {
    'enable_dingtalk': True,
    'dingtalk_webhook': 'https://oapi.dingtalk.com/robot/send?access_token=xxx',
    'enable_wechat': False,
    'wechat_webhook': '',
}
```

---

## 🚀 实盘应用示例

### 操作规则

1. **只在三周期同步时操作** ✓✓✓
   ```
   快周期: BUY
   中周期: BUY
   慢周期: BUY
   → 执行买入！
   ```

2. **在关键分型位置设置止损**
   - 买入信号: 底分型 - 2×(底分型高度) = 止损位
   - 卖出信号: 顶分型 + 2×(顶分型高度) = 止损位

3. **遵循资金管理规则**
   - 单笔头寸: 账户总资金的5%
   - 风险/收益比: 最低1:2

### 监控命令

```bash
# 方式1: 每2秒检查一次
while true; do
  clear
  python monitor.py --symbol sh600519
  sleep 2
done

# 方式2: 使用watch命令
watch -n 2 "python monitor.py"

# 方式3: 后台运行并记录日志
python monitor.py >> logs/monitor.log &
```

---

## 📈 输出指标解读

### 分型统计
```
分型: 5 (顶:3 底:2)
↑ 总共5个分型
  ├─ 3个顶分型 (可能的空头信号)
  └─ 2个底分型 (可能的多头信号)
```

### 线段统计
```
线段: 4 (上升:2 下降:2)
↑ 总共4条线段
  ├─ 2条上升线段 (多头趋势)
  └─ 2条下降线段 (空头趋势)
```

### 中枢统计
```
中枢: 1 (上升:0 下降:1)
↑ 总共1个中枢
  ├─ 0个上升中枢 (多头整理)
  └─ 1个下降中枢 (空头整理)
```

### 信号统计
```
信号: 买0 卖1
↑ 买入提醒: 0个
↑ 卖出提醒: 1个
```

### 区间套
```
区间: 快:None 中:None 慢:None
↑ 快周期: 无突破
↑ 中周期: 无突破
↑ 慢周期: 无突破
→ 暂无明确信号

或

区间: 快:BUY 中:BUY 慢:BUY
↑ 三周期同步 ✓✓✓
→ 强烈买入信号！
```

---

## 🔗 GitHub 提交历史

```
45d873d - 缠论完整交易系统: 线段识别/中枢检测/买卖点/区间套/实时提醒/多周期分析
b68a26b - Add real-time fractal monitoring tool
abc4a33 - Add Chan theory fractal recognition feature
143da05 - Initial commit with data collection and visualization
```

---

## 🎓 缠论理论基础

### 核心概念

**1. 分型 (缠中说禅的最小单位)**
- 顶分型: 形成波峰，表示可能反向下跌
- 底分型: 形成波谷，表示可能反向上升

**2. 线段 (连接分型)**
- 上升线段: 从底分型到下一个顶分型
- 下降线段: 从顶分型到下一个底分型

**3. 中枢 (关键支撑/阻力)**
- 价格在某个区间反复波动
- 突破中枢 = 趋势开始

**4. 买卖点 (交易机会)**
- 第一类: 笔完成后的逆向突破
- 第二类: 线段完成后的突破
- 第三类: 中枢突破

**5. 区间套 (多层级确认)**
- 小级别突破 + 中级别确认 + 大级别无阻力 = 高概率信号

---

## ⚠️ 风险提示

1. **历史数据回测有效，未来表现无保证**
2. **A股存在跳空风险，不利于精确止损**
3. **市场在极端行情下可能失效**
4. **操作前务必设置好止损**
5. **本系统仅供学习研究，不构成投资建议**

---

## 📞 支持

**遇到问题?**
- 检查数据库连接是否正常: `sqlite3 logs/quotes.db ".tables"`
- 查看Python环境: `python --version`
- 检查依赖包: `pip list | grep requests`

**日志文件位置:**
- `logs/chan_system.log` - 系统日志
- `logs/monitor.log` - 监控日志
- `logs/chan_report.json` - 最新报告

---

## 📚 更新日志

### v1.0 (2026-01-20)
- ✅ 完成分型识别
- ✅ 完成线段识别
- ✅ 完成中枢检测
- ✅ 完成买卖点生成
- ✅ 完成区间套分析
- ✅ 完成实时提醒系统
- ✅ 完成综合协调器

### 计划中
- [ ] 历史回测模块
- [ ] 最优止损计算
- [ ] 组合风险评估
- [ ] WebSocket 实时推送
- [ ] Web Dashboard

---

**作者**: 仙儿仙儿碎碎念 (xianer_quant)
**项目**: https://github.com/wuxibao53-cloud/stock-collection
**更新**: 2026-01-20
