#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论线段（笔）识别模块

线段是缠论中的重要概念：
- 由相邻的顶分型和底分型组成
- 顶分型→底分型→顶分型 = 一条下降线段
- 底分型→顶分型→底分型 = 一条上升线段

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple
from fractal_recognition import FractalRecognizer, Fractal


@dataclass
class Stroke:
    """线段数据结构"""
    symbol: str
    stroke_id: int  # 线段ID
    direction: str  # "up" or "down"
    start_fractal: Fractal  # 起始分型
    end_fractal: Fractal    # 终止分型
    high: float  # 线段最高点
    low: float   # 线段最低点
    fractal_count: int  # 分型个数
    
    def __str__(self):
        direction_cn = "上升" if self.direction == "up" else "下降"
        return f"[线段#{self.stroke_id} {direction_cn}] {self.symbol} " \
               f"{self.start_fractal.minute}→{self.end_fractal.minute} " \
               f"H:{self.high:.2f} L:{self.low:.2f}"


class StrokeRecognizer:
    """线段识别器"""
    
    def __init__(self):
        self.strokes = []
        self.fractal_recognizer = FractalRecognizer()
    
    def recognize_from_bars(self, bars, symbol):
        """
        从K线识别线段
        
        Args:
            bars: K线列表
            symbol: 股票代码
        
        Returns:
            strokes: 线段列表
        """
        # 先识别分型
        fractals = self.fractal_recognizer.recognize_from_bars(bars)
        
        if len(fractals) < 2:
            return []
        
        strokes = []
        stroke_id = 1
        i = 0
        
        while i < len(fractals) - 1:
            current = fractals[i]
            next_frac = fractals[i + 1]
            
            # 检查是否能组成线段
            # 顶分型 → 底分型 = 下降线段
            if current.fractal_type == 'top' and next_frac.fractal_type == 'bottom':
                stroke = Stroke(
                    symbol=symbol,
                    stroke_id=stroke_id,
                    direction='down',
                    start_fractal=current,
                    end_fractal=next_frac,
                    high=current.high,
                    low=next_frac.low,
                    fractal_count=2
                )
                strokes.append(stroke)
                stroke_id += 1
            
            # 底分型 → 顶分型 = 上升线段
            elif current.fractal_type == 'bottom' and next_frac.fractal_type == 'top':
                stroke = Stroke(
                    symbol=symbol,
                    stroke_id=stroke_id,
                    direction='up',
                    start_fractal=current,
                    end_fractal=next_frac,
                    high=next_frac.high,
                    low=current.low,
                    fractal_count=2
                )
                strokes.append(stroke)
                stroke_id += 1
            
            i += 1
        
        self.strokes.extend(strokes)
        return strokes
    
    def recognize_from_sqlite(self, db_path, symbol=None, start=None, end=None):
        """从SQLite识别线段"""
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取K线数据
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
            
            # 按symbol分组
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
            
            # 对每个symbol识别线段
            strokes_by_symbol = {}
            for sym, bars in bars_by_symbol.items():
                strokes = self.recognize_from_bars(bars, sym)
                if strokes:
                    strokes_by_symbol[sym] = strokes
            
            conn.close()
            return strokes_by_symbol
        
        except Exception as e:
            print(f"❌ 识别线段失败: {e}")
            return {}
    
    def print_summary(self):
        """打印线段统计"""
        if not self.strokes:
            print("⚠️  没有识别出线段")
            return
        
        print("\n" + "="*70)
        print("缠论线段识别结果")
        print("="*70)
        
        # 按symbol统计
        by_symbol = {}
        for stroke in self.strokes:
            if stroke.symbol not in by_symbol:
                by_symbol[stroke.symbol] = {'up': 0, 'down': 0}
            by_symbol[stroke.symbol][stroke.direction] += 1
        
        for symbol in sorted(by_symbol.keys()):
            counts = by_symbol[symbol]
            total = counts['up'] + counts['down']
            print(f"{symbol:10} | 总计:{total:2} | 上升线段:{counts['up']:2} | 下降线段:{counts['down']:2}")
        
        print("="*70 + "\n")
    
    def get_latest_stroke(self, symbol):
        """获取最新的线段"""
        strokes = [s for s in self.strokes if s.symbol == symbol]
        return strokes[-1] if strokes else None
    
    def get_stroke_direction(self, symbol):
        """获取当前线段方向"""
        latest = self.get_latest_stroke(symbol)
        return latest.direction if latest else None


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论线段识别工具')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码')
    parser.add_argument('--start',
                       help='开始时间 YYYY-MM-DD HH:MM')
    parser.add_argument('--end',
                       help='结束时间 YYYY-MM-DD HH:MM')
    
    args = parser.parse_args()
    
    recognizer = StrokeRecognizer()
    strokes_by_symbol = recognizer.recognize_from_sqlite(
        args.db,
        symbol=args.symbol,
        start=args.start,
        end=args.end
    )
    
    if not strokes_by_symbol:
        print("⚠️  未找到任何线段")
        return
    
    for symbol in sorted(strokes_by_symbol.keys()):
        print(f"\n📊 {symbol}:")
        for stroke in strokes_by_symbol[symbol][-5:]:  # 显示最后5条
            print(f"  {stroke}")
    
    recognizer.print_summary()


if __name__ == '__main__':
    main()
