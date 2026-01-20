#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论分型识别模块

识别A股分钟K线上的缠论分型：
- 顶分型（Top Fractal）：中间高点 > 两边高点
- 底分型（Bottom Fractal）：中间低点 < 两边低点

Author: 仙儿仙儿碎碎念
"""

import sqlite3
import csv
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass
import json


@dataclass
class Fractal:
    """分型数据结构"""
    symbol: str
    minute: str  # "2026-01-20 10:30"
    fractal_type: str  # "top" or "bottom"
    high: float  # 中间K线的最高价
    low: float  # 中间K线的最低价
    close: float  # 中间K线的收盘价
    idx: int  # 在K线序列中的索引（中间的那根）
    
    def __str__(self):
        cn_type = "顶分型" if self.fractal_type == "top" else "底分型"
        return f"[{cn_type}] {self.symbol} {self.minute} H:{self.high:.2f} L:{self.low:.2f} C:{self.close:.2f}"


class FractalRecognizer:
    """缠论分型识别器"""
    
    def __init__(self):
        self.fractals = []  # 存储识别出的分型
    
    def recognize_from_bars(self, bars):
        """
        从K线列表中识别分型
        
        Args:
            bars: K线列表，每个元素为 {
                'minute': '2026-01-20 10:30',
                'symbol': 'sh600519',
                'high': 1376.5,
                'low': 1375.0,
                'close': 1376.0,
                ...
            }
        
        Returns:
            fractals: 分型列表 [Fractal, ...]
        """
        if len(bars) < 3:
            return []
        
        fractals = []
        
        # 从第二根K线开始（需要前后各一根K线）
        for i in range(1, len(bars) - 1):
            prev_bar = bars[i - 1]
            curr_bar = bars[i]
            next_bar = bars[i + 1]
            
            # 检查顶分型：中间高点 > 两边高点
            if (curr_bar['high'] > prev_bar['high'] and 
                curr_bar['high'] > next_bar['high']):
                
                fractal = Fractal(
                    symbol=curr_bar['symbol'],
                    minute=curr_bar['minute'],
                    fractal_type='top',
                    high=curr_bar['high'],
                    low=curr_bar['low'],
                    close=curr_bar['close'],
                    idx=i
                )
                fractals.append(fractal)
            
            # 检查底分型：中间低点 < 两边低点
            elif (curr_bar['low'] < prev_bar['low'] and 
                  curr_bar['low'] < next_bar['low']):
                
                fractal = Fractal(
                    symbol=curr_bar['symbol'],
                    minute=curr_bar['minute'],
                    fractal_type='bottom',
                    high=curr_bar['high'],
                    low=curr_bar['low'],
                    close=curr_bar['close'],
                    idx=i
                )
                fractals.append(fractal)
        
        self.fractals.extend(fractals)
        return fractals
    
    def recognize_from_sqlite(self, db_path, symbol=None, start=None, end=None):
        """
        从SQLite数据库读取K线并识别分型
        
        Args:
            db_path: SQLite数据库路径
            symbol: 股票代码（不指定则处理所有）
            start: 开始时间 "2026-01-20 09:30"
            end: 结束时间 "2026-01-20 15:00"
        
        Returns:
            fractals_by_symbol: {symbol: [Fractal, ...]}
        """
        fractals_by_symbol = {}
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 构建查询
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
            bars_by_symbol = defaultdict(list)
            for row in rows:
                bar = {
                    'symbol': row['symbol'],
                    'minute': row['minute'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'open': row['open'],
                    'volume': row['volume'],
                }
                bars_by_symbol[row['symbol']].append(bar)
            
            # 对每个symbol识别分型
            for sym, bars in bars_by_symbol.items():
                if len(bars) >= 3:
                    fractals = self.recognize_from_bars(bars)
                    if fractals:
                        fractals_by_symbol[sym] = fractals
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 读取数据库失败: {e}")
            return {}
        
        return fractals_by_symbol
    
    def recognize_from_csv(self, csv_path, symbol=None):
        """
        从CSV文件读取K线并识别分型
        
        Args:
            csv_path: CSV文件路径（分钟K线文件）
            symbol: 股票代码（不指定则处理所有）
        
        Returns:
            fractals_by_symbol: {symbol: [Fractal, ...]}
        """
        fractals_by_symbol = {}
        
        try:
            bars_by_symbol = defaultdict(list)
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sym = row.get('symbol')
                    if symbol and sym != symbol:
                        continue
                    
                    bar = {
                        'symbol': sym,
                        'minute': row.get('minute'),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'open': float(row.get('open', 0)),
                        'volume': int(row.get('volume', 0)),
                    }
                    bars_by_symbol[sym].append(bar)
            
            # 对每个symbol识别分型
            for sym, bars in bars_by_symbol.items():
                if len(bars) >= 3:
                    fractals = self.recognize_from_bars(bars)
                    if fractals:
                        fractals_by_symbol[sym] = fractals
            
        except Exception as e:
            print(f"❌ 读取CSV失败: {e}")
            return {}
        
        return fractals_by_symbol
    
    def save_to_csv(self, output_path):
        """保存分型到CSV文件"""
        if not self.fractals:
            print("⚠️  没有分型数据可保存")
            return
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['symbol', 'minute', 'fractal_type', 'high', 'low', 'close', 'idx'])
                
                for frac in self.fractals:
                    writer.writerow([
                        frac.symbol,
                        frac.minute,
                        frac.fractal_type,
                        f"{frac.high:.2f}",
                        f"{frac.low:.2f}",
                        f"{frac.close:.2f}",
                        frac.idx
                    ])
            
            print(f"✓ 分型已保存: {output_path} ({len(self.fractals)}个)")
        except Exception as e:
            print(f"❌ 保存失败: {e}")
    
    def save_to_jsonl(self, output_path):
        """保存分型到JSON Lines文件"""
        if not self.fractals:
            print("⚠️  没有分型数据可保存")
            return
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for frac in self.fractals:
                    line = json.dumps({
                        'symbol': frac.symbol,
                        'minute': frac.minute,
                        'fractal_type': frac.fractal_type,
                        'high': frac.high,
                        'low': frac.low,
                        'close': frac.close,
                        'idx': frac.idx,
                    }, ensure_ascii=False)
                    f.write(line + '\n')
            
            print(f"✓ 分型已保存: {output_path} ({len(self.fractals)}个)")
        except Exception as e:
            print(f"❌ 保存失败: {e}")
    
    def print_summary(self):
        """打印分型统计摘要"""
        if not self.fractals:
            print("⚠️  没有识别出分型")
            return
        
        print("\n" + "="*60)
        print("缠论分型识别结果")
        print("="*60)
        
        # 按symbol统计
        by_symbol = defaultdict(lambda: {'top': 0, 'bottom': 0})
        for frac in self.fractals:
            by_symbol[frac.symbol][frac.fractal_type] += 1
        
        for symbol in sorted(by_symbol.keys()):
            counts = by_symbol[symbol]
            total = counts['top'] + counts['bottom']
            print(f"{symbol:10} | 总计:{total:3} | 顶分型:{counts['top']:2} | 底分型:{counts['bottom']:2}")
        
        print("="*60 + "\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论分型识别工具')
    parser.add_argument('--source', choices=['sqlite', 'csv'], default='sqlite',
                       help='数据源类型')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--csv', 
                       help='CSV文件路径')
    parser.add_argument('--symbol',
                       help='股票代码（如 sh600519）')
    parser.add_argument('--start',
                       help='开始时间 YYYY-MM-DD HH:MM')
    parser.add_argument('--end',
                       help='结束时间 YYYY-MM-DD HH:MM')
    parser.add_argument('--out-csv',
                       help='输出CSV文件路径')
    parser.add_argument('--out-jsonl',
                       help='输出JSONL文件路径')
    
    args = parser.parse_args()
    
    recognizer = FractalRecognizer()
    
    if args.source == 'sqlite':
        print(f"📖 从SQLite读取数据: {args.db}")
        fractals_by_symbol = recognizer.recognize_from_sqlite(
            args.db, 
            symbol=args.symbol,
            start=args.start,
            end=args.end
        )
    else:  # csv
        if not args.csv:
            print("❌ 使用CSV源时必须指定 --csv 参数")
            return
        print(f"📖 从CSV读取数据: {args.csv}")
        fractals_by_symbol = recognizer.recognize_from_sqlite(args.csv, symbol=args.symbol)
    
    if not fractals_by_symbol:
        print("⚠️  未找到任何分型")
        return
    
    # 打印结果
    for symbol in sorted(fractals_by_symbol.keys()):
        print(f"\n📊 {symbol}:")
        for frac in fractals_by_symbol[symbol][-10:]:  # 显示最后10个
            print(f"  {frac}")
    
    recognizer.print_summary()
    
    # 保存结果
    if args.out_csv:
        recognizer.save_to_csv(args.out_csv)
    if args.out_jsonl:
        recognizer.save_to_jsonl(args.out_jsonl)


if __name__ == '__main__':
    main()
