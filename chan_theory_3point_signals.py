#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整缠论三类买卖点识别系统

缠论三类买点（精确版本）：
  1. 第一类买点：
     - 前面有顶分型→形成下降线段
     - 下降线段完成后，出现底分型
     - 向上离开底分型就是买点
  
  2. 第二类买点（中枢震荡买点）：
     - 在中枢内震荡
     - 触及中枢下沿后反弹突破中枢上沿
     - 突破瞬间就是买点
  
  3. 第三类买点（多周期共振买点）：
     - 第一类或第二类买点出现
     - 同时多个周期形成共振（1min+5min+60min都有买信号）
     - 区间套形成时是最强买点

缠论三类卖点：对称的逻辑

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BuyPointType(Enum):
    """买点类型"""
    FIRST_TYPE = "第一类买点"      # 线段完成后底分型
    SECOND_TYPE = "第二类买点"    # 中枢振荡后突破
    THIRD_TYPE = "第三类买点"     # 多周期共振
    UNKNOWN = "未知买点"


class SellPointType(Enum):
    """卖点类型"""
    FIRST_TYPE = "第一类卖点"
    SECOND_TYPE = "第二类卖点"
    THIRD_TYPE = "第三类卖点"
    UNKNOWN = "未知卖点"


@dataclass
class TradingSignal:
    """交易信号 - 扩展版"""
    symbol: str
    signal_type: str          # "buy" or "sell"
    point_type: str           # "1st", "2nd", "3rd"
    minute: str
    price: float
    confidence: float         # 0-1
    reason: str
    fractal_count: int = 0    # 分型数
    pivot_count: int = 0      # 中枢数
    cycles_sync: int = 1      # 周期共振数
    volume_confirm: bool = False  # 成交量确认
    
    def __str__(self):
        signal_cn = "🟢买" if self.signal_type == "buy" else "🔴卖"
        confidence_pct = int(self.confidence * 100)
        sync_info = f" {self.cycles_sync}周期共振" if self.cycles_sync > 1 else ""
        vol_info = " 量能确认" if self.volume_confirm else ""
        return (f"[{signal_cn}{self.point_type}] {self.symbol} {self.minute} "
                f"价{self.price:.2f} 信{confidence_pct}%{sync_info}{vol_info} | {self.reason}")


class ChanTheory3PointSignalGenerator:
    """完整缠论三类买卖点生成器"""
    
    def __init__(self):
        self.signals = []
        # 中枢参数
        self.pivot_threshold = 0.02  # 2%价格变化作为中枢范围
        self.pivot_min_bars = 5      # 最少5根K线形成中枢
    
    @staticmethod
    def _is_fractal(bars: List[Dict], idx: int) -> Tuple[bool, str]:
        """
        判断是否形成分型
        
        Args:
            bars: K线列表
            idx: 当前K线索引
        
        Returns:
            (是否分型, 类型)
        """
        if idx < 1 or idx >= len(bars) - 1:
            return False, ""
        
        try:
            prev_bar = bars[idx - 1]
            curr_bar = bars[idx]
            next_bar = bars[idx + 1]
            
            # 数据验证和类型转换
            def safe_value(bar, key):
                val = bar.get(key, 0)
                # 如果是列表，取第一个元素
                if isinstance(val, (list, tuple)):
                    val = val[0] if val else 0
                return float(val) if val is not None else 0.0
            
            prev_high = safe_value(prev_bar, 'high')
            prev_low = safe_value(prev_bar, 'low')
            curr_high = safe_value(curr_bar, 'high')
            curr_low = safe_value(curr_bar, 'low')
            next_high = safe_value(next_bar, 'high')
            next_low = safe_value(next_bar, 'low')
            
            # 顶分型：前低，中高，后低
            if (prev_low < curr_high and 
                curr_high > next_high and
                curr_low > next_low):
                return True, "top"
            
            # 底分型：前高，中低，后高
            if (prev_high > curr_low and 
                curr_low < next_low and
                curr_high < next_high):
                return True, "bottom"
            
            return False, ""
        
        except (TypeError, ValueError) as e:
            logger.debug(f"分型检测异常 at idx {idx}: {e}")
            return False, ""
        if (prev_bar['high'] > curr_bar['low'] and 
            curr_bar['low'] < next_bar['low'] and
            curr_bar['high'] < next_bar['high']):
            return True, "bottom"
        
        return False, ""
    
    def _find_fractals(self, bars: List[Dict]) -> List[Tuple[int, str, Dict]]:
        """
        找出所有分型
        
        Returns:
            [(索引, 类型, K线)]列表
        """
        fractals = []
        for i in range(1, len(bars) - 1):
            is_frac, frac_type = self._is_fractal(bars, i)
            if is_frac:
                fractals.append((i, frac_type, bars[i]))
        return fractals
    
    def _find_pivot(self, bars: List[Dict], start_idx: int, 
                    end_idx: int) -> Optional[Dict]:
        """
        识别区间内的中枢
        
        中枢 = 至少3根K线的高低交集
        
        Returns:
            {"high": 中枢上沿, "low": 中枢下沿, "bars": 包含K线数}
        """
        if end_idx - start_idx < self.pivot_min_bars:
            return None
        
        try:
            segment = bars[start_idx:end_idx + 1]
            
            # 找出最高高点和最低低点
            def safe_value(bar, key):
                val = bar.get(key, 0)
                if isinstance(val, (list, tuple)):
                    val = val[0] if val else 0
                return float(val) if val is not None else 0.0
            
            highs = [safe_value(b, 'high') for b in segment]
            lows = [safe_value(b, 'low') for b in segment]
            
            if not highs or not lows:
                return None
            
            max_high = max(highs)
            min_low = min(lows)
            
            # 判断是否形成中枢（有重叠区间）
            pivot_range = max_high - min_low
            if pivot_range < min(highs) * self.pivot_threshold:
                return {
                    'high': max_high,
                    'low': min_low,
                    'bars': len(segment),
                    'range': pivot_range
                }
            
            return None
        
        except Exception as e:
            logger.debug(f"中枢识别异常: {e}")
            return None
    
    def _identify_first_buy_point(self, bars: List[Dict], 
                                   fractals: List[Tuple]) -> List[TradingSignal]:
        """
        识别第一类买点
        
        逻辑：
        1. 下降线段后出现底分型
        2. 底分型向上离开
        """
        signals = []
        
        if len(fractals) < 2:
            return signals
        
        # 扫描从倒数第三个分型开始
        for i in range(len(fractals) - 2, 0, -1):
            idx1, type1, bar1 = fractals[i - 1]
            idx2, type2, bar2 = fractals[i]
            idx3, type3, bar3 = fractals[i + 1] if i + 1 < len(fractals) else (None, None, None)
            
            # 顶→底：下降线段完成
            if type1 == "top" and type2 == "bottom":
                # 检查底分型后是否向上
                if idx3 and type3 == "top":
                    # 有向上的顶分型 = 形成第一类买点
                    signal = TradingSignal(
                        symbol=bar2.get('symbol', 'UNKNOWN'),
                        signal_type='buy',
                        point_type='1st',
                        minute=bar2['minute'],
                        price=bar2['low'],
                        confidence=0.75,
                        reason=f"下降线段完成，底分型#{i}向上",
                        fractal_count=len(fractals),
                        pivot_count=0,
                    )
                    signals.append(signal)
                else:
                    # 仅有底分型（可能性更小但也标记）
                    if i == len(fractals) - 1:  # 最新底分型
                        signal = TradingSignal(
                            symbol=bar2.get('symbol', 'UNKNOWN'),
                            signal_type='buy',
                            point_type='1st',
                            minute=bar2['minute'],
                            price=bar2['low'],
                            confidence=0.6,
                            reason=f"最新底分型#{i}（等待确认向上）",
                            fractal_count=len(fractals),
                        )
                        signals.append(signal)
        
        return signals
    
    def _identify_second_buy_point(self, bars: List[Dict],
                                    fractals: List[Tuple]) -> List[TradingSignal]:
        """
        识别第二类买点
        
        逻辑：
        1. 在中枢区间震荡
        2. 触及下沿后反弹
        3. 突破上沿时确认
        """
        signals = []
        
        if len(bars) < 20:  # 需要足够的数据
            return signals
        
        try:
            # 查找最近的中枢
            pivot = None
            for i in range(len(bars) - self.pivot_min_bars, max(0, len(bars) - 50), -1):
                pivot = self._find_pivot(bars, i, len(bars) - 1)
                if pivot:
                    break
            
            if not pivot:
                return signals
            
            current = bars[-1]
            
            # 数据类型转换
            def safe_value(bar, key):
                val = bar.get(key, 0)
                if isinstance(val, (list, tuple)):
                    val = val[0] if val else 0
                return float(val) if val is not None else 0.0
            
            curr_low = safe_value(current, 'low')
            curr_close = safe_value(current, 'close')
            curr_high = safe_value(current, 'high')
            
            # 判断是否在中枢下沿附近反弹
            if (curr_low <= pivot['low'] * (1 + self.pivot_threshold) and
                curr_close > pivot['low'] * (1 + self.pivot_threshold)):
                
                # 检查是否突破上沿
                if curr_high > pivot['high']:
                    signal = TradingSignal(
                        symbol=current.get('symbol', 'UNKNOWN'),
                        signal_type='buy',
                        point_type='2nd',
                        minute=current['minute'],
                        price=pivot['high'],
                        confidence=0.7,
                        reason=f"中枢震荡后突破 (中枢范围{pivot['range']:.2%})",
                        pivot_count=1,
                        volume_confirm=current.get('volume', 0) > 0
                    )
                    signals.append(signal)
            
            return signals
        
        except Exception as e:
            logger.debug(f"第二类买点识别异常: {e}")
            return signals
    
    def _identify_third_buy_point(self, bars_1m: List[Dict],
                                   bars_5m: List[Dict],
                                   bars_60m: List[Dict]) -> List[TradingSignal]:
        """
        识别第三类买点
        
        逻辑：
        1. 在1分钟、5分钟、60分钟上
        2. 同时出现第一类或第二类买点
        3. 形成区间套（多周期共振）
        """
        signals = []
        
        if not (bars_1m and bars_5m and bars_60m):
            return signals
        
        # 获取各周期的第一类买点
        first_buys_1m = self._identify_first_buy_point(bars_1m, self._find_fractals(bars_1m))
        first_buys_5m = self._identify_first_buy_point(bars_5m, self._find_fractals(bars_5m))
        first_buys_60m = self._identify_first_buy_point(bars_60m, self._find_fractals(bars_60m))
        
        # 统计共振数
        sync_count = sum([
            len(first_buys_1m) > 0,
            len(first_buys_5m) > 0,
            len(first_buys_60m) > 0
        ])
        
        # 至少2个周期共振
        if sync_count >= 2:
            avg_price = (bars_1m[-1]['close'] + bars_5m[-1]['close'] + bars_60m[-1]['close']) / 3
            signal = TradingSignal(
                symbol=bars_1m[-1].get('symbol', 'UNKNOWN'),
                signal_type='buy',
                point_type='3rd',
                minute=bars_1m[-1]['minute'],
                price=avg_price,
                confidence=min(0.95, 0.7 + sync_count * 0.1),
                reason=f"{sync_count}个周期共振区间套",
                cycles_sync=sync_count,
            )
            signals.append(signal)
        
        return signals
    
    def analyze_bars(self, bars: List[Dict], symbol: str) -> List[TradingSignal]:
        """
        完整分析 - 识别所有三类买卖点
        
        Args:
            bars: K线数据列表
            symbol: 股票代码
        
        Returns:
            交易信号列表
        """
        if len(bars) < 5:
            return []
        
        # 添加symbol字段
        for bar in bars:
            bar['symbol'] = symbol
        
        # 找出所有分型
        fractals = self._find_fractals(bars)
        
        signals = []
        
        # 识别三类买点
        signals.extend(self._identify_first_buy_point(bars, fractals))
        signals.extend(self._identify_second_buy_point(bars, fractals))
        
        # 第一类卖点（对称逻辑）
        for i in range(1, len(fractals) - 1):
            idx1, type1, bar1 = fractals[i - 1]
            idx2, type2, bar2 = fractals[i]
            idx3, type3, bar3 = fractals[i + 1] if i + 1 < len(fractals) else (None, None, None)
            
            # 底→顶：上升线段完成
            if type1 == "bottom" and type2 == "top":
                if idx3 and type3 == "bottom":
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type='sell',
                        point_type='1st',
                        minute=bar2['minute'],
                        price=bar2['high'],
                        confidence=0.75,
                        reason=f"上升线段完成，顶分型#{i}向下",
                        fractal_count=len(fractals),
                    )
                    signals.append(signal)
        
        self.signals.extend(signals)
        return signals
    
    def print_signals(self):
        """打印所有交易信号"""
        if not self.signals:
            logger.info("⚠️  没有识别出交易信号")
            return
        
        print("\n" + "="*80)
        print("缠论完整三类买卖点识别")
        print("="*80)
        
        for signal_type in ["buy", "sell"]:
            signals_filtered = [s for s in self.signals if s.signal_type == signal_type]
            if not signals_filtered:
                continue
            
            title = "🟢 买入信号" if signal_type == "buy" else "🔴 卖出信号"
            print(f"\n{title} ({len(signals_filtered)}个):")
            
            # 按点型分组
            for point_type in ["1st", "2nd", "3rd"]:
                point_signals = [s for s in signals_filtered if s.point_type == point_type]
                if point_signals:
                    print(f"\n  {point_type.upper()}")
                    for signal in point_signals[-3:]:
                        print(f"    {signal}")
        
        print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    # 测试例子
    import argparse
    
    parser = argparse.ArgumentParser(description='完整缠论三类买卖点识别')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--symbol', help='股票代码')
    
    args = parser.parse_args()
    
    generator = ChanTheory3PointSignalGenerator()
    print("✓ 完整三类买卖点识别系统就绪")
