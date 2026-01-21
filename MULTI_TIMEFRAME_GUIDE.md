# 多时间框架K线系统使用指南

## 核心改进（针对你的需求）

### 1. **支持多时间框架** ✅
- **1分钟K线** (`1f`): 盘中细粒度监控
- **5分钟K线** (`5f`): 5分钟级别的区间套
- **30分钟K线** (`30f`): 主级别判断分型

#### 获取数据时无需分别拉取，一条命令获取三层框架：
```bash
python3 multi_timeframe_fetcher.py --symbol sh600519 --timeframes 1 5 30
```

---

### 2. **失败重试机制** ✅
- **问题**: 拉取失败后没有反馈和重试
- **解决**:
  - 最多3次自动重试
  - 延迟递增（2秒→4秒→6秒），避免频繁轰击API
  - 单个股票失败不影响整体进度
  - 详细日志记录每次重试

```python
# 在fetch_stock_multiframe_akshare()中自动处理
if retry_count < self.max_retries:
    wait_time = (retry_count + 1) * 2
    time.sleep(wait_time)
    # 递归重试
```

---

### 3. **交易时间策略** ✅
整个采集计划在交易日**只举行两次**：

#### **阶段1：开盘前 (09:15-09:30)**
```bash
python3 trading_scheduler.py --mode demo
# 第1步：获取最近5天的1f/5f/30f完整K线
# 第2步：全量扫描分型检测
# 第3步：生成今日监控清单（优先级排序）
```

**输出**:
- ✓ 5000+只A股的历史数据
- ✓ 检测出符合分型条件的股票清单
- ✓ 每只股票的买卖点建议

#### **阶段2：盘中 (09:30-15:00) - 只监控符合条件的股票**
```bash
# 实时监控代码已内置在trading_scheduler.py
# 每15分钟自动更新1f/5f数据
# 检测5f/1f的操作信号
```

**实时推送**:
- 5分钟走势确认 + 1分钟出现底分型 → **买入机会**
- 5分钟走势突破 + 1分钟出现顶分型 → **减仓/止盈**
- 5分钟出现顶分型 + 1分钟破位 → **止损逃顶**

#### **阶段3：闭盘后 (15:05-16:00)**
```bash
# 自动执行（在交易_scheduler.py post_market_task()中）
# 更新今日完整K线数据
# 生成日报（JSON格式）
```

---

### 4. **分型检测与信号生成** ✅

#### 缠论三类买卖点识别：

**顶分型** (高点 > 两侧高点)
- 信号类型：**卖出** 
- 建议价格：当前价 × 1.02
- 止损位：当前价 × 1.05
- 止盈位：当前价 × 0.95

**底分型** (低点 < 两侧低点)
- 信号类型：**买入**
- 建议价格：当前价 × 0.98
- 止损位：当前价 × 0.95
- 止盈位：当前价 × 1.05

```python
# 自动计算（在generate_trading_signal()中）
fractals = fetcher.detect_fractal_patterns(symbol, TimeFrame.THIRTY_MIN)
if fractals:
    signal = fetcher.generate_trading_signal(symbol, fractal_type, price)
    # 返回: {'action': 'BUY'/'SELL', 'suggested_price': ..., 'stop_loss': ..., ...}
```

---

### 5. **持仓实时监控 (5f/1f区间套)** ✅

#### **买入后的监控逻辑**:
```
买入信号(底分型) 确立后:

✓ 场景1：5f走势回踩支撑 + 1f出现底分型
  → 可加仓（确认支撑有效）

✓ 场景2：5f走势突破前期阻力 + 1f出现顶分型
  → 可减仓/止盈（目标达成）

✗ 场景3：5f出现顶分型 + 1f破位向下
  → 止损逃顶（危险信号）
```

#### **卖出后的监控逻辑**:
```
卖出信号(顶分型) 确立后:

✓ 场景1：5f走势突破阻力 + 1f出现顶分型
  → 可加仓（确认阻力突破）

✓ 场景2：5f走势回踩支撑 + 1f出现底分型
  → 可减仓/止盈（充分获利）

✗ 场景3：5f出现底分型 + 1f破位向上
  → 止损逃底（反向危险）
```

---

## 使用命令速查表

### 测试单只股票（获取1f/5f/30f三层数据）
```bash
python3 multi_timeframe_fetcher.py \
  --symbol sh600519 \
  --days 5 \
  --timeframes 1 5 30
```

### 全量获取5000+A股（仅1分钟K线）
```bash
python3 multi_timeframe_fetcher.py \
  --mode all \
  --days 5 \
  --timeframes 1
```

### 完整获取5000+A股（1f/5f/30f三层）
```bash
python3 multi_timeframe_fetcher.py \
  --mode all \
  --days 5 \
  --timeframes 1 5 30
```

### 执行交易调度演示（一次完整流程）
```bash
python3 trading_scheduler.py --mode demo
```

### 获取热门股票快速测试
```bash
python3 multi_timeframe_fetcher.py --mode hot --timeframes 1 5
```

---

## 数据结构

### 数据库表
```
minute_bars_1f     → 1分钟K线数据
minute_bars_5f     → 5分钟K线数据
minute_bars_30f    → 30分钟K线数据
trading_signals    → 交易信号表
positions          → 持仓监控表
```

### 每条K线字段
```python
{
    'symbol': 'sh600519',      # 股票代码
    'minute': '2026-01-21 10:30',  # 时间
    'open': 1234.56,           # 开盘价
    'high': 1245.00,           # 最高价
    'low': 1230.00,            # 最低价
    'close': 1240.00,          # 收盘价
    'volume': 1000000,         # 成交量
    'amount': 1234567890.00    # 成交额
}
```

---

## 日报输出

### 文件: `logs/daily_trading_report.json`
```json
{
  "date": "2026-01-21",
  "monitored_count": 245,
  "signals": [
    {
      "symbol": "sh600519",
      "fractal_type": "底分型",
      "action": "BUY",
      "current_price": 1240.50,
      "suggested_price": 1215.69,
      "stop_loss": 1178.48,
      "take_profit": 1302.53
    },
    ...
  ]
}
```

---

## 重试机制详解

```
第1次尝试: 立即执行
  ↓ 失败
等待2秒 → 第2次重试
  ↓ 失败
等待4秒 → 第3次重试
  ↓ 失败
放弃并记录，继续下一只股票
```

**优势**:
- ✓ 避免单点失败导致整体中断
- ✓ 网络抖动时自动恢复
- ✓ 延迟递增保护API不被频繁轰击
- ✓ 详细日志便于分析问题

---

## 部署建议

### 本地开发测试
```bash
# 第1步：测试单只股票
python3 multi_timeframe_fetcher.py --symbol sh600519 --timeframes 1 5 30

# 第2步：执行完整演示
python3 trading_scheduler.py --mode demo

# 第3步：查看日报
cat logs/daily_trading_report.json
```

### 云端自动化（GitHub Actions）
编辑`.github/workflows/cloud-analysis.yml`，配置：
```yaml
- name: 多时间框架数据获取
  run: python3 multi_timeframe_fetcher.py --mode all --days 5 --timeframes 1 5 30

- name: 交易调度演示
  run: python3 trading_scheduler.py --mode demo
```

---

## 常见问题

### Q: 为什么有些股票拉取失败？
A: 这是正常的。某些股票可能：
   - 今天没有交易（停牌）
   - API返回无数据
   - 网络超时
   
   系统会**自动重试3次**。如果仍失败，会跳过该股票继续。详见日志。

### Q: 1f/5f/30f怎么选？
A: 建议组合：
   - **短线交易**: 1f + 5f（快速反应）
   - **中线交易**: 5f + 30f（平衡）
   - **长线判断**: 30f（趋势）
   - **完整分析**: 1f + 5f + 30f（全面）

### Q: 重试延迟能改吗？
A: 可以，修改代码：
```python
wait_time = (retry_count + 1) * 2  # 改成你要的延迟
```

### Q: 数据量太大怎么办？
A: 可以：
   - 减少天数：`--days 3` (default 5)
   - 减少符号：`--symbol sh600519` (只获取一个)
   - 分批处理：修改`batch_size=50`

---

## 下一步优化方向

- [ ] 实时推送提示（企业微信/钉钉）
- [ ] 历史胜率统计
- [ ] 风险回撤分析
- [ ] 自适应止损位
- [ ] 多因子组合验证

