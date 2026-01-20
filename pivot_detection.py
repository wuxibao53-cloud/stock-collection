#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论中枢检测模块

中枢定义：
- 至少包含5条K线的上升/下降区间
- 在该区间内，任意两条K线都有重叠

识别中枢的步骤：
1. 找到区间内所有K线的最高点H和最低点L
2. 如果任意两条K线都有重叠，则为中枢
3. 中枢方向由进入方向决定

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class Pivot:
    """中枢数据结构"""
    symbol: str
    pivot_id: int
    direction: str  # "up" or "down"
    start_minute: str
    end_minute: str
    high: float  # 中枢最高点
    low: float   # 中枢最低点
    bar_count: int  # K线数
    
    def get_center(self):
        """获取中枢中心（轴线）"""
        return (self.high + self.low) / 2
    
    def get_height(self):
        """获取中枢高度"""
        return self.high - self.low
    
    def __str__(self):
        direction_cn = "上升" if self.direction == "up" else "下降"
        center = self.get_center()
        height = self.get_height()
        return f"[中枢#{self.pivot_id} {direction_cn}] {self.symbol} " \
               f"{self.start_minute}→{self.end_minute} " \
               f"轴:{center:.2f} 高度:{height:.2f}"


class PivotDetector:
    """中枢检测器"""
    
    def __init__(self, min_bars=5):
        """
        Args:
            min_bars: 组成中枢的最少K线数
        """
        self.min_bars = min_bars
        self.pivots = []
    
    def check_overlap(self, bar1, bar2):
        """检查两条K线是否有重叠"""
        return not (bar1['high'] < bar2['low'] or bar2['high'] < bar1['low'])
    
    def check_all_overlap(self, bars):
        """检查所有K线是否两两重叠"""
        if len(bars) < 2:
            return False
        
        for i in range(len(bars)):
            for j in range(i + 1, len(bars)):
                if not self.check_overlap(bars[i], bars[j]):
                    return False
        return True
    
    def detect_from_bars(self, bars, symbol, direction='any'):
        """
        从K线中检测中枢
        
        Args:
            bars: K线列表
            symbol: 股票代码
            direction: 中枢方向 ('up', 'down', 'any')
        
        Returns:
            pivots: 中枢列表
        """
        if len(bars) < self.min_bars:
            return []
        
        pivots = []
        pivot_id = 1
        i = 0
        
        while i <= len(bars) - self.min_bars:
            # 尝试找到一个中枢
            for end in range(i + self.min_bars - 1, len(bars)):
                segment = bars[i:end + 1]
                
                # 检查是否所有K线两两重叠
                if self.check_all_overlap(segment):
                    # 计算中枢参数
                    highs = [b['high'] for b in segment]
                    lows = [b['low'] for b in segment]
                    high = max(highs)
                    low = min(lows)
                    
                    # 尝试继续扩展
                    last_end = end
                    for extend_end in range(end + 1, len(bars)):
                        extend_segment = bars[i:extend_end + 1]
                        if self.check_all_overlap(extend_segment):
                            last_end = extend_end
                            high = max(high, bars[extend_end]['high'])
                            low = min(low, bars[extend_end]['low'])
                        else:
                            break
                    
                    # 确定方向（简化：根据第一条和最后一条K线的收盘价）
                    if bars[i]['close'] < bars[last_end]['close']:
                        piv_direction = 'up'
                    elif bars[i]['close'] > bars[last_end]['close']:
                        piv_direction = 'down'
                    else:
                        piv_direction = 'none'
                    
                    if direction == 'any' or direction == piv_direction:
                        pivot = Pivot(
                            symbol=symbol,
                            pivot_id=pivot_id,
                            direction=piv_direction,
                            start_minute=bars[i]['minute'],
                            end_minute=bars[last_end]['minute'],
                            high=high,
                            low=low,
                            bar_count=last_end - i + 1
                        )
                        pivots.append(pivot)
                        pivot_id += 1
                    
                    i = last_end
                    break
            else:
                i += 1
        
        self.pivots.extend(pivots)
        return pivots
    
    def detect_from_sqlite(self, db_path, symbol=None, start=None, end=None):
        """从SQLite检测中枢"""
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM minute_bars WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if start:
                query += " AND minute >= ?"
                params.append(start)
            if end:
                query += " AND minute <= ?"
                params.append(end)
            
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
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                })
            
            pivots_by_symbol = {}
            for sym, bars in bars_by_symbol.items():
                pivots = self.detect_from_bars(bars, sym)
                if pivots:
                    pivots_by_symbol[sym] = pivots
            
            conn.close()
            return pivots_by_symbol
        
        except Exception as e:
            print(f"❌ 检测中枢失败: {e}")
            return {}
    
    def print_summary(self):
        """打印中枢统计"""
        if not self.pivots:
            print("⚠️  没有检测到中枢")
            return
        
        print("\n" + "="*70)
        print("缠论中枢检测结果")
        print("="*70)
        
        by_symbol = {}
        for pivot in self.pivots:
            if pivot.symbol not in by_symbol:
                by_symbol[pivot.symbol] = {'up': 0, 'down': 0}
            by_symbol[pivot.symbol][pivot.direction] += 1
        
        for symbol in sorted(by_symbol.keys()):
            counts = by_symbol[symbol]
            total = counts['up'] + counts['down']
            print(f"{symbol:10} | 总计:{total:2} | 上升中枢:{counts['up']:2} | 下降中枢:{counts['down']:2}")
        
        print("="*70 + "\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论中枢检测工具')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码')
    parser.add_argument('--min-bars', type=int, default=5,
                       help='中枢最少K线数')
    
    args = parser.parse_args()
    
    detector = PivotDetector(min_bars=args.min_bars)
    pivots_by_symbol = detector.detect_from_sqlite(args.db, symbol=args.symbol)
    
    if not pivots_by_symbol:
        print("⚠️  未找到任何中枢")
        return
    
    for symbol in sorted(pivots_by_symbol.keys()):
        print(f"\n📊 {symbol}:")
        for pivot in pivots_by_symbol[symbol][-3:]:  # 显示最后3个
            print(f"  {pivot}")
    
    detector.print_summary()


if __name__ == '__main__':
    main()
