#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时分型监测工具

在采集过程中实时监测分型的出现，并发出告警
- 新增顶分型 → 可能见顶，建议减仓或卖出
- 新增底分型 → 可能探底，建议抄底或买入

Author: 仙儿仙儿碎碎念
"""

import sqlite3
import json
from datetime import datetime
from collections import defaultdict
from fractal_recognition import FractalRecognizer


class FractalMonitor:
    """实时分型监测器"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.last_checked = {}  # {symbol: last_idx}
        self.recent_fractals = defaultdict(list)  # {symbol: [Fractal, ...]}
    
    def check_for_new_fractals(self, symbol):
        """
        检查该symbol是否出现了新的分型
        
        Returns:
            new_fractals: 新增分型列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取该symbol的所有K线
            cursor.execute("""
                SELECT minute, symbol, open, high, low, close, volume
                FROM minute_bars
                WHERE symbol = ?
                ORDER BY minute
            """, (symbol,))
            
            rows = cursor.fetchall()
            bars = [dict(row) for row in rows]
            conn.close()
            
            if len(bars) < 3:
                return []
            
            # 用识别器识别分型
            recognizer = FractalRecognizer()
            fractals = recognizer.recognize_from_bars(bars)
            
            # 找出新增的分型
            last_idx = self.last_checked.get(symbol, 0)
            new_fractals = [f for f in fractals if f.idx > last_idx]
            
            self.last_checked[symbol] = len(bars) - 1
            self.recent_fractals[symbol] = fractals
            
            return new_fractals
        
        except Exception as e:
            print(f"❌ 检查分型失败: {e}")
            return []
    
    def get_latest_fractal(self, symbol):
        """获取该symbol的最新分型"""
        fractals = self.recent_fractals.get(symbol, [])
        return fractals[-1] if fractals else None
    
    def print_alert(self, fractal):
        """打印分型告警"""
        cn_type = "顶分型🔴" if fractal.fractal_type == "top" else "底分型🟢"
        print(f"\n{'='*60}")
        print(f"🚨 新增分型告警！")
        print(f"{'='*60}")
        print(f"标的: {fractal.symbol}")
        print(f"时间: {fractal.minute}")
        print(f"类型: {cn_type}")
        print(f"价格: H:{fractal.high:.2f} L:{fractal.low:.2f} C:{fractal.close:.2f}")
        
        if fractal.fractal_type == "top":
            print(f"💡 建议: 可能见顶，考虑减仓或卖出")
        else:
            print(f"💡 建议: 可能探底，考虑抄底或买入")
        
        print(f"{'='*60}\n")
    
    def monitor_continuous(self, symbols, interval=2, duration=None):
        """
        持续监测分型（用于后台运行）
        
        Args:
            symbols: 股票代码列表
            interval: 检查间隔（秒）
            duration: 运行时长（秒，None表示无限）
        """
        import time
        
        print(f"开始监测 {len(symbols)} 只股票的分型变化...")
        print(f"检查间隔: {interval}秒，按Ctrl+C停止\n")
        
        start_time = time.time()
        check_count = 0
        
        try:
            while True:
                # 检查是否超时
                if duration and (time.time() - start_time) > duration:
                    print(f"\n监测时间已到，退出。")
                    break
                
                for symbol in symbols:
                    new_fractals = self.check_for_new_fractals(symbol)
                    
                    for fractal in new_fractals:
                        self.print_alert(fractal)
                
                check_count += 1
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print(f"\n\n监测已停止 (共进行{check_count}次检查)")


def print_fractal_stats(db_path, symbols=None):
    """打印分型统计"""
    recognizer = FractalRecognizer()
    fractals_by_symbol = recognizer.recognize_from_sqlite(db_path, symbol=None)
    
    print("\n" + "="*70)
    print("缠论分型统计")
    print("="*70)
    print(f"{'代码':<10} {'总数':>4} {'顶分型':>4} {'底分型':>4} {'最新分型':<20} {'信号':<10}")
    print("-"*70)
    
    for sym in sorted(fractals_by_symbol.keys()):
        fractals = fractals_by_symbol[sym]
        
        top_count = sum(1 for f in fractals if f.fractal_type == 'top')
        bottom_count = sum(1 for f in fractals if f.fractal_type == 'bottom')
        total = len(fractals)
        
        latest = fractals[-1]
        latest_type = "顶🔴" if latest.fractal_type == "top" else "底🟢"
        signal = "空头" if latest.fractal_type == "top" else "多头"
        
        print(f"{sym:<10} {total:>4} {top_count:>4} {bottom_count:>4} "
              f"{latest.minute} {latest_type} {signal:<5}")
    
    print("="*70 + "\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='实时分型监测工具')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbols', default='sh000001,sz399001,sh600519,sz300750',
                       help='监测的股票代码（逗号分隔）')
    parser.add_argument('--interval', type=int, default=2,
                       help='检查间隔（秒）')
    parser.add_argument('--duration', type=int,
                       help='运行时长（秒）')
    parser.add_argument('--stats', action='store_true',
                       help='仅打印统计信息，不持续监测')
    
    args = parser.parse_args()
    
    symbols = args.symbols.split(',')
    
    if args.stats:
        print_fractal_stats(args.db)
    else:
        monitor = FractalMonitor(args.db)
        monitor.monitor_continuous(symbols, args.interval, args.duration)


if __name__ == '__main__':
    main()
