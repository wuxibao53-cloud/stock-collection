#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论交易系统集成脚本 - 支持完整三类买卖点分析

使用方式：
    python3 chan_integrated_system.py --db logs/quotes.db --mode analyze
    python3 chan_integrated_system.py --db logs/quotes.db --mode backtest
    python3 chan_integrated_system.py --db logs/quotes.db --mode report
"""

import argparse
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging

from chan_theory_3point_signals import ChanTheory3PointSignalGenerator, TradingSignal
from interval_analysis import IntervalAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChanTradingSystemIntegrated:
    """整合的缠论交易系统"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.signal_generator = ChanTheory3PointSignalGenerator()
        self.interval_analyzer = IntervalAnalyzer()
        self.all_signals: Dict[str, List[TradingSignal]] = {}
    
    def load_bars_from_db(self, symbol: str, limit: Optional[int] = None) -> List[Dict]:
        """从数据库加载K线"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM minute_bars WHERE symbol = ? ORDER BY minute ASC"
            if limit:
                query = f"SELECT * FROM (SELECT * FROM minute_bars WHERE symbol = ? ORDER BY minute DESC LIMIT ?) AS t ORDER BY minute ASC"
                cursor.execute(query, (symbol, limit))
            else:
                cursor.execute(query, (symbol,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"加载{symbol}数据失败: {e}")
            return []
    
    def analyze_symbol(self, symbol: str, limit: Optional[int] = None) -> Dict:
        """
        分析单个股票
        
        Args:
            symbol: 股票代码
            limit: 最多加载多少根K线（用于性能测试）
        
        Returns:
            分析结果字典
        """
        bars = self.load_bars_from_db(symbol, limit)
        
        if len(bars) < 5:
            logger.warning(f"{symbol}: 数据不足 ({len(bars)} bars)")
            return {'symbol': symbol, 'bars': len(bars), 'signals': []}
        
        # 执行信号识别
        signals = self.signal_generator.analyze_bars(bars, symbol)
        
        # 执行多周期分析
        try:
            interval_analysis = self.interval_analyzer.analyze_multilevel(bars, symbol)
        except:
            interval_analysis = {}
        
        result = {
            'symbol': symbol,
            'bars': len(bars),
            'latest_price': bars[-1]['close'],
            'signals': len(signals),
            'signal_details': [
                {
                    'type': s.signal_type,
                    'point': s.point_type,
                    'minute': s.minute,
                    'price': s.price,
                    'confidence': s.confidence,
                    'reason': s.reason,
                } for s in signals
            ],
            'interval_strength': interval_analysis.get('strength', 0),
        }
        
        self.all_signals[symbol] = signals
        return result
    
    def analyze_multiple_symbols(self, symbols: List[str], 
                                 limit: Optional[int] = None) -> Dict[str, Dict]:
        """分析多个股票"""
        results = {}
        
        for symbol in symbols:
            try:
                result = self.analyze_symbol(symbol, limit)
                results[symbol] = result
                
                signal_count = result['signals']
                if signal_count > 0:
                    logger.info(f"✓ {symbol}: {signal_count}个信号")
                
            except Exception as e:
                logger.error(f"✗ {symbol}: {e}")
                results[symbol] = {'symbol': symbol, 'error': str(e)}
        
        return results
    
    def get_all_symbols_from_db(self) -> List[str]:
        """获取数据库中的所有股票"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM minute_bars ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            return symbols
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def generate_report(self, results: Dict[str, Dict]) -> str:
        """生成分析报告"""
        total_symbols = len(results)
        total_signals = sum(r.get('signals', 0) for r in results.values())
        
        # 统计各类型信号
        buy_signals = 0
        sell_signals = 0
        first_type = 0
        second_type = 0
        third_type = 0
        
        for result in results.values():
            for sig_detail in result.get('signal_details', []):
                if sig_detail['type'] == 'buy':
                    buy_signals += 1
                else:
                    sell_signals += 1
                
                if sig_detail['point'] == '1st':
                    first_type += 1
                elif sig_detail['point'] == '2nd':
                    second_type += 1
                elif sig_detail['point'] == '3rd':
                    third_type += 1
        
        # Top信号
        top_signals = sorted(
            [(sym, r) for sym, r in results.items() if r.get('signals', 0) > 0],
            key=lambda x: x[1]['signals'],
            reverse=True
        )[:10]
        
        report = f"""
{'='*80}
缠论交易系统完整分析报告
{'='*80}

📊 总体统计
{'─'*80}
分析股票数: {total_symbols}
总信号数: {total_signals}
├─ 买入信号: {buy_signals}
└─ 卖出信号: {sell_signals}

三类买卖点分布
├─ 第一类: {first_type} (线段完成型)
├─ 第二类: {second_type} (中枢振荡型)
└─ 第三类: {third_type} (多周期共振型)

🎯 信号Top 10
{'─'*80}
"""
        
        for i, (symbol, result) in enumerate(top_signals, 1):
            signal_count = result.get('signals', 0)
            price = result.get('latest_price', 0)
            interval_str = result.get('interval_strength', 0)
            report += f"{i:2}. {symbol:8} 信号:{signal_count:2} 价格:{price:8.2f} 强度:{interval_str:.2%}\n"
        
        report += f"""
{'='*80}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
"""
        
        return report
    
    def print_symbol_signals(self, symbol: str):
        """打印单个股票的详细信号"""
        if symbol not in self.all_signals:
            logger.warning(f"{symbol} 未分析")
            return
        
        signals = self.all_signals[symbol]
        
        print(f"\n{'='*80}")
        print(f"🎯 {symbol} - 详细信号")
        print(f"{'='*80}")
        
        if not signals:
            print("⚠️  无信号")
            return
        
        # 分类输出
        for signal_type in ['buy', 'sell']:
            filtered = [s for s in signals if s.signal_type == signal_type]
            if not filtered:
                continue
            
            title = "🟢 买入信号" if signal_type == 'buy' else "🔴 卖出信号"
            print(f"\n{title}:")
            
            for signal in filtered:
                print(f"  {signal}")
        
        print(f"{'='*80}\n")


def main():
    """命令行主程序"""
    parser = argparse.ArgumentParser(description='缠论交易系统 - 完整三类买卖点分析')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--mode', choices=['analyze', 'backtest', 'report', 'symbol'],
                       default='analyze', help='运行模式')
    parser.add_argument('--symbol', help='股票代码（用于symbol模式）')
    parser.add_argument('--limit', type=int, help='最多分析多少根K线')
    parser.add_argument('--output', help='输出文件（保存报告）')
    
    args = parser.parse_args()
    
    system = ChanTradingSystemIntegrated(args.db)
    
    if args.mode == 'analyze':
        # 分析所有股票
        logger.info("开始分析所有股票...")
        symbols = system.get_all_symbols_from_db()
        
        if not symbols:
            logger.error("数据库中无股票数据")
            return
        
        logger.info(f"找到 {len(symbols)} 只股票")
        results = system.analyze_multiple_symbols(symbols, limit=args.limit)
        
        # 生成报告
        report = system.generate_report(results)
        print(report)
        
        # 可选保存
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"✓ 报告已保存到 {args.output}")
    
    elif args.mode == 'symbol' and args.symbol:
        # 分析单个股票
        system.analyze_symbol(args.symbol, limit=args.limit)
        system.print_symbol_signals(args.symbol)
    
    elif args.mode == 'report':
        # 生成完整报告
        logger.info("生成完整报告...")
        symbols = system.get_all_symbols_from_db()
        results = system.analyze_multiple_symbols(symbols, limit=args.limit)
        report = system.generate_report(results)
        print(report)


if __name__ == '__main__':
    main()
