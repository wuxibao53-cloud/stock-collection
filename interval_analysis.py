#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论区间套分析模块

区间套的概念：
- 包含在中枢内的区间称为"区间套"
- 可以进行多层级分析（日线、1小时线、5分钟线）
- 更小级别突破中枢 = 交易机会

多周期分析：
- 周期1（快）：1分钟K线 → 快速响应
- 周期2（中）：5分钟K线 → 趋势确认
- 周期3（慢）：1小时K线 → 大趋势

买卖点判定规则：
- 小级别突破中枢上沿 + 中级别确认 + 大级别无阻力 = 买入
- 小级别跌破中枢下沿 + 中级别确认 + 大级别无阻力 = 卖出

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta
from enum import Enum


class SignalStrength(Enum):
    """信号强度"""
    WEAK = 0.3  # 弱信号
    MEDIUM = 0.6  # 中信号
    STRONG = 0.9  # 强信号


@dataclass
class IntervalAnalysis:
    """区间套分析结果"""
    symbol: str
    minute: str
    fastcycle_signal: str  # "buy", "sell", "none"
    midcycle_signal: str
    slowcycle_signal: str
    fast_price: float
    mid_price: float
    slow_price: float
    pivot_high: float  # 中枢上沿
    pivot_low: float   # 中枢下沿
    strength: float  # 信号强度 0-1
    analysis: str  # 分析说明
    
    def is_synchronized(self):
        """检查是否三周期同步"""
        signals = [self.fastcycle_signal, self.midcycle_signal, self.slowcycle_signal]
        # 过滤掉 'none'
        signals = [s for s in signals if s != 'none']
        if not signals:
            return False
        # 所有信号相同
        return all(s == signals[0] for s in signals)
    
    def __str__(self):
        sync_mark = "✓✓✓" if self.is_synchronized() else ""
        strength_pct = int(self.strength * 100)
        return f"{self.symbol} {self.minute} " \
               f"[快:{self.fastcycle_signal} 中:{self.midcycle_signal} 慢:{self.slowcycle_signal}] {sync_mark} " \
               f"强度:{strength_pct}% P:{self.pivot_high:.2f}/{self.pivot_low:.2f}"


class IntervalAnalyzer:
    """区间套分析器"""
    
    def __init__(self):
        self.analysis_results = []
    
    def get_pivot_bounds(self, bars, min_overlap=0.8):
        """
        获取价格区间的上下界限
        
        Args:
            bars: K线列表
            min_overlap: 重叠度要求
        
        Returns:
            (high, low): 区间上下界
        """
        if not bars:
            return None, None
        
        highs = [b['high'] for b in bars]
        lows = [b['low'] for b in bars]
        
        # 简化：使用最高点和最低点
        return max(highs), min(lows)
    
    def detect_breakout(self, bars, pivot_high, pivot_low, threshold=0.0):
        """
        检测突破信号
        
        Args:
            bars: K线列表
            pivot_high: 中枢上界
            pivot_low: 中枢下界
            threshold: 突破阈值（百分比）
        
        Returns:
            ("buy", price), ("sell", price) 或 ("none", None)
        """
        if not bars:
            return "none", None
        
        latest = bars[-1]
        current_price = latest['close']
        
        # 计算突破阈值
        pivot_height = pivot_high - pivot_low
        breakout_threshold_up = pivot_high + pivot_height * threshold
        breakout_threshold_down = pivot_low - pivot_height * threshold
        
        # 检查突破
        if current_price > breakout_threshold_up:
            return "buy", current_price
        elif current_price < breakout_threshold_down:
            return "sell", current_price
        else:
            return "none", None
    
    def aggregate_bars(self, bars, timeframe_minutes):
        """
        从1分钟K线聚合到更大的时间周期
        
        Args:
            bars: K线列表
            timeframe_minutes: 目标时间周期（分钟数）
        
        Returns:
            聚合后的K线列表
        """
        if not bars or timeframe_minutes <= 1:
            return bars
        
        aggregated = []
        i = 0
        
        while i < len(bars):
            # 收集timeframe_minutes内的所有K线
            segment = [bars[i]]
            j = i + 1
            
            while j < len(bars) and j < i + timeframe_minutes:
                segment.append(bars[j])
                j += 1
            
            # 合并成一条K线
            opens = [b['open'] for b in segment]
            highs = [b['high'] for b in segment]
            lows = [b['low'] for b in segment]
            closes = [b['close'] for b in segment]
            volumes = [b.get('volume', 0) for b in segment]
            
            aggregated_bar = {
                'minute': segment[0]['minute'],  # 使用第一条的时间戳
                'open': opens[0],
                'high': max(highs),
                'low': min(lows),
                'close': closes[-1],
                'volume': sum(volumes),
            }
            aggregated.append(aggregated_bar)
            
            i = j
        
        return aggregated
    
    def analyze_multilevel(self, bars, symbol):
        """
        多周期分析
        
        Args:
            bars: 1分钟K线列表
            symbol: 股票代码
        
        Returns:
            IntervalAnalysis 对象
        """
        if len(bars) < 30:  # 至少需要30分钟数据
            return None
        
        # 准备三个周期的K线
        fast_bars = bars[-15:]  # 最近15分钟
        mid_bars = self.aggregate_bars(bars[-60:], 5)[-12:]  # 最近12条5分钟线
        slow_bars = self.aggregate_bars(bars[-240:], 60)[-4:]  # 最近4条小时线
        
        if not all([fast_bars, mid_bars, slow_bars]):
            return None
        
        # 获取各周期的中枢界限
        fast_high, fast_low = self.get_pivot_bounds(fast_bars)
        mid_high, mid_low = self.get_pivot_bounds(mid_bars)
        slow_high, slow_low = self.get_pivot_bounds(slow_bars)
        
        if any(x is None for x in [fast_high, fast_low, mid_high, mid_low, slow_high, slow_low]):
            return None
        
        # 检测各周期的突破
        fast_signal, fast_price = self.detect_breakout(fast_bars, fast_high, fast_low, threshold=0.01)
        mid_signal, mid_price = self.detect_breakout(mid_bars, mid_high, mid_low, threshold=0.005)
        slow_signal, slow_price = self.detect_breakout(slow_bars, slow_high, slow_low, threshold=0.002)
        
        # 计算信号强度
        strength = 0.3  # 基础强度
        
        if fast_signal != "none":
            strength += 0.2  # 快周期有信号
        if mid_signal != "none":
            strength += 0.25  # 中周期有信号
        if slow_signal != "none":
            strength += 0.25  # 慢周期有信号
        
        # 如果三周期同步，加分
        if fast_signal == mid_signal == slow_signal and fast_signal != "none":
            strength = min(1.0, strength + 0.2)
        
        analysis = IntervalAnalysis(
            symbol=symbol,
            minute=bars[-1]['minute'],
            fastcycle_signal=fast_signal,
            midcycle_signal=mid_signal,
            slowcycle_signal=slow_signal,
            fast_price=fast_price or bars[-1]['close'],
            mid_price=mid_price or mid_bars[-1]['close'],
            slow_price=slow_price or slow_bars[-1]['close'],
            pivot_high=(fast_high + mid_high + slow_high) / 3,  # 平均中枢上界
            pivot_low=(fast_low + mid_low + slow_low) / 3,  # 平均中枢下界
            strength=strength,
            analysis=self._generate_analysis_text(
                fast_signal, mid_signal, slow_signal,
                fast_high, fast_low, mid_high, mid_low, slow_high, slow_low
            )
        )
        
        self.analysis_results.append(analysis)
        return analysis
    
    def _generate_analysis_text(self, fast_sig, mid_sig, slow_sig,
                               fast_h, fast_l, mid_h, mid_l, slow_h, slow_l):
        """生成分析说明文本"""
        text = ""
        
        if fast_sig == mid_sig == slow_sig == "buy":
            text = "✓✓✓三周期同步买入信号，强度最大"
        elif fast_sig == mid_sig == slow_sig == "sell":
            text = "✓✓✓三周期同步卖出信号，强度最大"
        elif fast_sig == mid_sig == slow_sig:
            text = "二周期以上同步中立"
        else:
            signals = [fast_sig, mid_sig, slow_sig]
            buy_count = signals.count("buy")
            sell_count = signals.count("sell")
            if buy_count > sell_count:
                text = f"偏多信号（{buy_count}个买，{sell_count}个卖）"
            elif sell_count > buy_count:
                text = f"偏空信号（{sell_count}个卖，{buy_count}个买）"
            else:
                text = "信号混乱，不建议操作"
        
        return text
    
    def analyze_from_sqlite(self, db_path, symbol=None):
        """从SQLite进行多周期分析"""
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM minute_bars WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY symbol, minute"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            bars_by_symbol = {}
            for row in rows:
                sym = row['symbol']
                if sym not in bars_by_symbol:
                    bars_by_symbol[sym] = []
                
                bars_by_symbol[sym].append({
                    'minute': row['minute'],
                    'symbol': row['symbol'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                })
            
            analysis_by_symbol = {}
            for sym, bars in bars_by_symbol.items():
                analysis = self.analyze_multilevel(bars, sym)
                if analysis:
                    analysis_by_symbol[sym] = analysis
            
            conn.close()
            return analysis_by_symbol
        
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            return {}
    
    def print_results(self):
        """打印分析结果"""
        if not self.analysis_results:
            print("⚠️  没有分析结果")
            return
        
        print("\n" + "="*90)
        print("缠论区间套多周期分析")
        print("="*90)
        
        for analysis in self.analysis_results[-5:]:  # 显示最后5条
            print(f"\n{analysis}")
            if analysis.is_synchronized():
                print(f"  💡 {analysis.analysis}")
        
        print("\n" + "="*90 + "\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论区间套多周期分析工具')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码')
    
    args = parser.parse_args()
    
    analyzer = IntervalAnalyzer()
    analysis_by_symbol = analyzer.analyze_from_sqlite(args.db, symbol=args.symbol)
    
    analyzer.print_results()


if __name__ == '__main__':
    main()
