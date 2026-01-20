#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论买卖点识别模块

缠论第一类买点：
1. 下降线段完成后，向上突破前面中枢上沿
2. 出现顶分型，然后出现底分型，再向上

缠论第一类卖点：
1. 上升线段完成后，向下跌破前面中枢下沿
2. 出现底分型，然后出现顶分型，再向下

简化版本（适合实盘）：
- 买点：底分型 + 价格上升 + 成交量增加
- 卖点：顶分型 + 价格下降 + 成交量增加

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from fractal_recognition import FractalRecognizer, Fractal
from stroke_recognition import StrokeRecognizer
from pivot_detection import PivotDetector, Pivot


@dataclass
class TradingSignal:
    """交易信号"""
    symbol: str
    signal_type: str  # "buy" or "sell"
    minute: str
    price: float
    confidence: float  # 0-1, 信心指数
    reason: str  # 信号原因
    
    def __str__(self):
        signal_cn = "买入🟢" if self.signal_type == "buy" else "卖出🔴"
        confidence_pct = int(self.confidence * 100)
        return f"[{signal_cn}] {self.symbol} {self.minute} 价:{self.price:.2f} " \
               f"信心:{confidence_pct}% | {self.reason}"


class TradingSignalGenerator:
    """交易信号生成器"""
    
    def __init__(self):
        self.fractal_recognizer = FractalRecognizer()
        self.stroke_recognizer = StrokeRecognizer()
        self.pivot_detector = PivotDetector()
        self.signals = []
    
    def analyze_bars(self, bars, symbol):
        """
        完整分析：分型→线段→中枢→交易信号
        
        Returns:
            signals: 交易信号列表
        """
        if len(bars) < 5:
            return []
        
        # 1. 识别分型
        fractals = self.fractal_recognizer.recognize_from_bars(bars)
        if len(fractals) < 2:
            return []
        
        # 2. 识别线段
        strokes = self.stroke_recognizer.recognize_from_bars(bars, symbol)
        
        # 3. 识别中枢
        pivots = self.pivot_detector.detect_from_bars(bars, symbol)
        
        # 4. 生成交易信号
        signals = []
        
        # 简化版买卖点识别
        for i, fractal in enumerate(fractals):
            if i == 0:
                continue
            
            prev_fractal = fractals[i - 1]
            current_bar = bars[-1]  # 最新K线
            
            # 买点信号：底分型出现后，价格上升
            if fractal.fractal_type == 'bottom':
                # 检查是否是最近的底分型
                if i == len(fractals) - 1:  # 最新分型
                    # 计算与前面底分型的对比
                    prev_bottoms = [f for f in fractals[:-1] if f.fractal_type == 'bottom']
                    if prev_bottoms:
                        prev_bottom = prev_bottoms[-1]
                        # 如果当前底分型低于前面底分型，且价格在上升 = 强买点
                        if fractal.low < prev_bottom.low and current_bar['close'] > fractal.close:
                            signal = TradingSignal(
                                symbol=symbol,
                                signal_type='buy',
                                minute=fractal.minute,
                                price=fractal.low,
                                confidence=0.8,
                                reason=f"底分型#{fractal.idx}，价格上升"
                            )
                            signals.append(signal)
            
            # 卖点信号：顶分型出现后，价格下降
            elif fractal.fractal_type == 'top':
                if i == len(fractals) - 1:  # 最新分型
                    prev_tops = [f for f in fractals[:-1] if f.fractal_type == 'top']
                    if prev_tops:
                        prev_top = prev_tops[-1]
                        # 如果当前顶分型高于前面顶分型，且价格在下降 = 强卖点
                        if fractal.high > prev_top.high and current_bar['close'] < fractal.close:
                            signal = TradingSignal(
                                symbol=symbol,
                                signal_type='sell',
                                minute=fractal.minute,
                                price=fractal.high,
                                confidence=0.8,
                                reason=f"顶分型#{fractal.idx}，价格下降"
                            )
                            signals.append(signal)
        
        self.signals.extend(signals)
        return signals
    
    def analyze_from_sqlite(self, db_path, symbol=None):
        """从SQLite分析并生成交易信号"""
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
            
            signals_by_symbol = {}
            for sym, bars in bars_by_symbol.items():
                signals = self.analyze_bars(bars, sym)
                if signals:
                    signals_by_symbol[sym] = signals
            
            conn.close()
            return signals_by_symbol
        
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            return {}
    
    def get_latest_signals(self):
        """获取最新的交易信号"""
        if not self.signals:
            return []
        
        # 按时间排序，返回最新的
        return sorted(self.signals, key=lambda s: s.minute, reverse=True)[:5]
    
    def print_signals(self):
        """打印所有交易信号"""
        if not self.signals:
            print("⚠️  没有识别出交易信号")
            return
        
        print("\n" + "="*70)
        print("缠论交易信号")
        print("="*70)
        
        buy_signals = [s for s in self.signals if s.signal_type == 'buy']
        sell_signals = [s for s in self.signals if s.signal_type == 'sell']
        
        print(f"\n🟢 买入信号 ({len(buy_signals)}个):")
        for signal in buy_signals[-5:]:
            print(f"  {signal}")
        
        print(f"\n🔴 卖出信号 ({len(sell_signals)}个):")
        for signal in sell_signals[-5:]:
            print(f"  {signal}")
        
        print("="*70 + "\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论交易信号生成工具')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码')
    
    args = parser.parse_args()
    
    generator = TradingSignalGenerator()
    signals_by_symbol = generator.analyze_from_sqlite(args.db, symbol=args.symbol)
    
    generator.print_signals()


if __name__ == '__main__':
    main()
