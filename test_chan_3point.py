#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论三类买卖点系统测试和演示脚本

生成模拟K线数据，演示三类买卖点识别
"""

import sys
from datetime import datetime, timedelta
from chan_theory_3point_signals import ChanTheory3PointSignalGenerator, TradingSignal


def generate_sample_bars(pattern='uptrend'):
    """
    生成样本K线数据
    
    Args:
        pattern: 'uptrend' - 上升趋势, 'downtrend' - 下降趋势, 'consolidation' - 震荡
    
    Returns:
        K线列表
    """
    bars = []
    base_price = 100.0
    base_time = datetime(2026, 1, 1, 9, 30)
    
    if pattern == 'uptrend':
        # 上升趋势：会形成顶分型→底分型→顶分型，产生买卖点
        prices = [
            # 下降段（形成顶分型）
            (100, 102, 99, 101),   # 分型1：顶
            (101, 103, 100, 100),
            (100, 101, 98, 99),    # 分型2：底
            (99, 102, 99, 101),
            
            # 上升段（形成底→顶分型）
            (101, 105, 100, 104),
            (104, 106, 103, 105),
            (105, 107, 104, 106),  # 分型3：顶
            (106, 108, 105, 107),
            
            # 回调（形成底分型 = 第一类买点触发）
            (107, 108, 102, 103),
            (103, 104, 100, 101),  # 分型4：底 - 第一类买点！
            (101, 106, 100, 105),
            (105, 109, 104, 108),
        ]
    
    elif pattern == 'downtrend':
        # 下降趋势
        prices = [
            (100, 102, 99, 101),
            (101, 103, 100, 102),  # 顶分型
            (102, 104, 101, 103),
            (103, 104, 98, 99),    # 底分型
            (99, 100, 96, 97),
            (97, 98, 93, 94),      # 底分型 - 卖点
        ]
    
    else:  # consolidation
        # 震荡模式：会形成中枢
        prices = [
            (100, 102, 99, 101),
            (101, 103, 100, 102),  # 中枢区域
            (102, 103, 101, 102),
            (102, 103, 100, 101),  # 中枢区域
            (101, 102, 100, 101),
            (101, 103, 101, 102),  # 中枢区域
            (102, 105, 101, 104),  # 突破上沿 - 第二类买点
        ]
    
    for i, (open_p, high, low, close) in enumerate(prices):
        bar_time = base_time + timedelta(minutes=i)
        bars.append({
            'minute': bar_time.strftime('%Y-%m-%d %H:%M'),
            'symbol': 'TEST001',
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': 1000 + i * 100,
        })
    
    return bars


def test_three_point_signals():
    """测试三类买卖点识别"""
    
    print("\n" + "="*80)
    print("缠论三类买卖点识别系统 - 演示")
    print("="*80)
    
    generator = ChanTheory3PointSignalGenerator()
    
    # 测试1：上升趋势（产生第一类买点）
    print("\n【测试1】上升趋势 - 应该识别出第一类买点")
    print("-"*80)
    bars_up = generate_sample_bars('uptrend')
    
    print("K线数据:")
    for i, bar in enumerate(bars_up, 1):
        print(f"  {i:2}. {bar['minute']} O:{bar['open']:6.2f} H:{bar['high']:6.2f} "
              f"L:{bar['low']:6.2f} C:{bar['close']:6.2f} V:{bar['volume']}")
    
    signals_up = generator.analyze_bars(bars_up, 'TEST001')
    
    print(f"\n识别出 {len(signals_up)} 个信号:")
    if signals_up:
        for signal in signals_up:
            print(f"  {signal}")
    else:
        print("  （需要更多历史数据）")
    
    # 测试2：下降趋势（产生第一类卖点）
    print("\n【测试2】下降趋势 - 应该识别出第一类卖点")
    print("-"*80)
    bars_down = generate_sample_bars('downtrend')
    
    print("K线数据:")
    for i, bar in enumerate(bars_down, 1):
        print(f"  {i:2}. {bar['minute']} O:{bar['open']:6.2f} H:{bar['high']:6.2f} "
              f"L:{bar['low']:6.2f} C:{bar['close']:6.2f}")
    
    generator_down = ChanTheory3PointSignalGenerator()
    signals_down = generator_down.analyze_bars(bars_down, 'TEST002')
    
    print(f"\n识别出 {len(signals_down)} 个信号:")
    if signals_down:
        for signal in signals_down:
            print(f"  {signal}")
    else:
        print("  （需要更多历史数据）")
    
    # 测试3：震荡模式（产生第二类买点）
    print("\n【测试3】震荡模式 - 应该识别出第二类买点（中枢突破）")
    print("-"*80)
    bars_cons = generate_sample_bars('consolidation')
    
    print("K线数据:")
    for i, bar in enumerate(bars_cons, 1):
        print(f"  {i:2}. {bar['minute']} O:{bar['open']:6.2f} H:{bar['high']:6.2f} "
              f"L:{bar['low']:6.2f} C:{bar['close']:6.2f}")
    
    generator_cons = ChanTheory3PointSignalGenerator()
    signals_cons = generator_cons.analyze_bars(bars_cons, 'TEST003')
    
    print(f"\n识别出 {len(signals_cons)} 个信号:")
    if signals_cons:
        for signal in signals_cons:
            print(f"  {signal}")
    else:
        print("  （震荡模式需要更多数据点识别中枢）")
    
    # 总结
    print("\n" + "="*80)
    print("📊 系统演示总结")
    print("="*80)
    print("""
三类买卖点识别规则：

1️⃣ 第一类买点（线段完成型）
   - 条件：前面有顶分型→下降→出现底分型→向上
   - 含义：下降线段完成，向上突破形成买点
   - 实盘性质：最可靠的买点之一

2️⃣ 第二类买点（中枢震荡型）
   - 条件：在中枢下沿反弹→突破中枢上沿
   - 含义：中枢已完成，向上突破买入
   - 实盘性质：突破瞬间买入，需要及时反应

3️⃣ 第三类买点（多周期共振型）
   - 条件：第一类/二类买点 + 多周期同步信号
   - 含义：不同周期形成一致性信号（区间套）
   - 实盘性质：最强信号，成功率最高但频率低

系统特点：
✓ 自动识别所有分型（顶分型/底分型）
✓ 检测中枢形成与突破
✓ 支持多周期同步分析
✓ 置信度评分（0-1）
✓ 详细的信号原因说明
""")
    print("="*80 + "\n")


def print_usage():
    """打印使用说明"""
    print("""
使用方式：

1. 演示模式（推荐首先运行）：
   python3 test_chan_3point.py

2. 与实际数据库集成：
   python3 chan_integrated_system.py --db logs/quotes.db --mode analyze

3. 分析单个股票：
   python3 chan_integrated_system.py --db logs/quotes.db --mode symbol --symbol sh600000

下一步改进：
- 添加回测框架验证信号准确率
- 集成风险管理规则（止损、止盈）
- 添加成交量确认
- 实时监控模式
""")


if __name__ == '__main__':
    test_three_point_signals()
    print_usage()
