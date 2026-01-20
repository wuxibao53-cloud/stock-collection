#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论综合交易系统协调器

整合所有模块：
1. 分型识别 (fractal_recognition.py)
2. 线段识别 (stroke_recognition.py)
3. 中枢检测 (pivot_detection.py)
4. 买卖点算法 (trading_signals.py)
5. 区间套分析 (interval_analysis.py)
6. 实时提醒系统 (realtime_alerts.py)

运行流程：
1. 加载K线数据
2. 识别分型 → 线段 → 中枢
3. 生成买卖信号
4. 多周期分析
5. 生成交易提醒
6. 输出综合分析报告

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json

from fractal_recognition import FractalRecognizer
from stroke_recognition import StrokeRecognizer
from pivot_detection import PivotDetector
from trading_signals import TradingSignalGenerator
from interval_analysis import IntervalAnalyzer
from realtime_alerts import RealTimeAlertSystem, AlertLevel


class ChanTheoryTradingSystem:
    """缠论综合交易系统"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        
        # 初始化各个模块
        self.fractal_recognizer = FractalRecognizer()
        self.stroke_recognizer = StrokeRecognizer()
        self.pivot_detector = PivotDetector()
        self.signal_generator = TradingSignalGenerator()
        self.interval_analyzer = IntervalAnalyzer()
        self.alert_system = RealTimeAlertSystem(db_path)
        
        # 存储分析结果
        self.analysis_results = {}
    
    def analyze_symbol(self, symbol, start=None, end=None):
        """
        对单个股票进行完整缠论分析
        
        Args:
            symbol: 股票代码
            start: 开始时间
            end: 结束时间
        
        Returns:
            分析结果字典
        """
        # 1. 读取K线数据
        bars = self._load_bars(symbol, start, end)
        if not bars or len(bars) < 5:
            print(f"⚠️  {symbol} 数据不足")
            return None
        
        # 2. 识别分型
        fractals = self.fractal_recognizer.recognize_from_bars(bars)
        
        # 3. 识别线段
        strokes = self.stroke_recognizer.recognize_from_bars(bars, symbol)
        
        # 4. 检测中枢
        pivots = self.pivot_detector.detect_from_bars(bars, symbol)
        
        # 5. 生成买卖信号
        signals = self.signal_generator.analyze_bars(bars, symbol)
        
        # 6. 多周期分析
        interval_analysis = self.interval_analyzer.analyze_multilevel(bars, symbol)
        
        # 7. 生成交易提醒
        self._generate_alerts(symbol, fractals, signals, interval_analysis)
        
        # 8. 汇总结果
        result = {
            'symbol': symbol,
            'analyze_time': datetime.now().isoformat(),
            'bar_count': len(bars),
            'latest_price': bars[-1]['close'],
            'fractals': {
                'total': len(fractals),
                'tops': len([f for f in fractals if f.fractal_type == 'top']),
                'bottoms': len([f for f in fractals if f.fractal_type == 'bottom']),
            },
            'strokes': {
                'total': len(strokes),
                'ups': len([s for s in strokes if s.direction == 'up']),
                'downs': len([s for s in strokes if s.direction == 'down']),
                'latest': str(strokes[-1]) if strokes else None,
            },
            'pivots': {
                'total': len(pivots),
                'ups': len([p for p in pivots if p.direction == 'up']),
                'downs': len([p for p in pivots if p.direction == 'down']),
                'latest': str(pivots[-1]) if pivots else None,
            },
            'signals': {
                'buy': len([s for s in signals if s.signal_type == 'buy']),
                'sell': len([s for s in signals if s.signal_type == 'sell']),
                'latest': str(signals[-1]) if signals else None,
            },
            'interval_analysis': {
                'fast_signal': interval_analysis.fastcycle_signal if interval_analysis else None,
                'mid_signal': interval_analysis.midcycle_signal if interval_analysis else None,
                'slow_signal': interval_analysis.slowcycle_signal if interval_analysis else None,
                'is_synchronized': interval_analysis.is_synchronized() if interval_analysis else False,
                'strength': interval_analysis.strength if interval_analysis else 0,
            }
        }
        
        self.analysis_results[symbol] = result
        return result
    
    def _load_bars(self, symbol, start=None, end=None):
        """加载K线数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM minute_bars WHERE symbol = ?"
            params = [symbol]
            
            if start:
                query += " AND minute >= ?"
                params.append(start)
            if end:
                query += " AND minute <= ?"
                params.append(end)
            
            query += " ORDER BY minute"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            bars = []
            for row in rows:
                bars.append({
                    'minute': row['minute'],
                    'symbol': row['symbol'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                })
            
            conn.close()
            return bars
        
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return []
    
    def _generate_alerts(self, symbol, fractals, signals, interval_analysis):
        """生成交易提醒"""
        
        # 根据最新分型和信号生成提醒
        if fractals:
            latest_fractal = fractals[-1]
            
            # 底分型 → 买入信号
            if latest_fractal.fractal_type == 'bottom':
                level = 3 if interval_analysis and interval_analysis.is_synchronized() else 2
                reason = f"底分型出现 | {latest_fractal.minute}"
                
                self.alert_system.generate_alert(
                    symbol,
                    'buy',
                    latest_fractal.low,
                    level=level,
                    reason=reason
                )
            
            # 顶分型 → 卖出信号
            elif latest_fractal.fractal_type == 'top':
                level = 3 if interval_analysis and interval_analysis.is_synchronized() else 2
                reason = f"顶分型出现 | {latest_fractal.minute}"
                
                self.alert_system.generate_alert(
                    symbol,
                    'sell',
                    latest_fractal.high,
                    level=level,
                    reason=reason
                )
    
    def analyze_all_symbols(self):
        """分析所有股票"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT symbol FROM minute_bars ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            print(f"\n📊 开始分析 {len(symbols)} 个股票...")
            
            for symbol in symbols:
                result = self.analyze_symbol(symbol)
                if result:
                    self._print_result(result)
        
        except Exception as e:
            print(f"❌ 分析失败: {e}")
    
    def _print_result(self, result):
        """打印分析结果"""
        symbol = result['symbol']
        
        print(f"\n🔍 {symbol} | 价格:{result['latest_price']:.2f}")
        print(f"   分型: {result['fractals']['total']} " \
              f"(顶:{result['fractals']['tops']} 底:{result['fractals']['bottoms']})")
        print(f"   线段: {result['strokes']['total']} " \
              f"(上升:{result['strokes']['ups']} 下降:{result['strokes']['downs']})")
        print(f"   中枢: {result['pivots']['total']} " \
              f"(上升:{result['pivots']['ups']} 下降:{result['pivots']['downs']})")
        print(f"   信号: 买{result['signals']['buy']} 卖{result['signals']['sell']}")
        
        ia = result['interval_analysis']
        if ia['is_synchronized']:
            sync_mark = "✓✓✓"
            print(f"   区间: {sync_mark} 三周期同步 " \
                  f"({ia['fast_signal']}/{ia['mid_signal']}/{ia['slow_signal']}) " \
                  f"强度:{int(ia['strength']*100)}%")
        else:
            print(f"   区间: 快:{ia['fast_signal']} 中:{ia['mid_signal']} 慢:{ia['slow_signal']}")
    
    def print_summary_report(self):
        """打印综合总结报告"""
        if not self.analysis_results:
            print("⚠️  没有分析结果")
            return
        
        print("\n" + "="*90)
        print("缠论综合交易系统 - 分析报告")
        print("="*90)
        print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"分析股票数: {len(self.analysis_results)}")
        
        # 统计信号
        total_buy_alerts = len([a for a in self.alert_system.alerts if a.signal_type == 'buy'])
        total_sell_alerts = len([a for a in self.alert_system.alerts if a.signal_type == 'sell'])
        strong_alerts = len([a for a in self.alert_system.alerts if a.level == 3])
        
        print(f"生成提醒: 买{total_buy_alerts} 卖{total_sell_alerts} (强:{strong_alerts})")
        
        # 列出关键信号
        print("\n🟢 重点关注(三周期同步):")
        sync_symbols = [
            s for s, r in self.analysis_results.items()
            if r['interval_analysis']['is_synchronized']
        ]
        for sym in sync_symbols:
            result = self.analysis_results[sym]
            ia = result['interval_analysis']
            print(f"  {sym}: {ia['fast_signal'].upper()} " \
                  f"强度{int(ia['strength']*100)}%")
        
        print("="*90 + "\n")
    
    def export_report_json(self, output_path='logs/chan_analysis_report.json'):
        """导出JSON报告"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'analysis_results': self.analysis_results,
                'alerts_summary': self.alert_system.get_today_summary(),
                'total_alerts': len(self.alert_system.alerts),
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 报告已导出: {output_path}")
        
        except Exception as e:
            print(f"❌ 导出报告失败: {e}")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论综合交易系统')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码（不指定则分析所有）')
    parser.add_argument('--export', action='store_true',
                       help='导出JSON报告')
    
    args = parser.parse_args()
    
    system = ChanTheoryTradingSystem(args.db)
    
    if args.symbol:
        result = system.analyze_symbol(args.symbol)
        if result:
            system._print_result(result)
    else:
        system.analyze_all_symbols()
    
    system.print_summary_report()
    system.alert_system.print_alerts()
    
    if args.export:
        system.export_report_json()


if __name__ == '__main__':
    main()
