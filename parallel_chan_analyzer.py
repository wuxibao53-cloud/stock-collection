#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行缠论分析系统 - 支持多股票高效并发分析

特点：
- 使用asyncio进行IO并发
- 使用ThreadPoolExecutor进行CPU密集计算（分型、线段、中枢识别）
- 支持批量分析5000+股票

Usage:
    analyzer = ParallelChanAnalyzer(db_path)
    results = asyncio.run(analyzer.analyze_multiple_async(symbols))
"""

import asyncio
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Dict, Optional
from functools import partial
import json

try:
    from fractal_recognition import FractalRecognizer
    from stroke_recognition import StrokeRecognizer
    from pivot_detection import PivotDetector
    from trading_signals import TradingSignalGenerator
    from interval_analysis import IntervalAnalyzer
    from realtime_alerts import RealTimeAlertSystem, AlertLevel
except ImportError as e:
    logging.warning(f"部分模块导入失败: {e}")
    FractalRecognizer = None

logger = logging.getLogger(__name__)


class ParallelChanAnalyzer:
    """并行缠论分析系统"""
    
    def __init__(self, db_path='logs/quotes.db', max_workers=4):
        """
        初始化并行分析器
        
        Args:
            db_path: 数据库路径
            max_workers: CPU线程池大小
        """
        self.db_path = db_path
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 初始化分析模块（如果可用）
        self.fractal_recognizer = FractalRecognizer() if FractalRecognizer else None
        self.stroke_recognizer = StrokeRecognizer() if FractalRecognizer else None
        self.pivot_detector = PivotDetector() if FractalRecognizer else None
        self.signal_generator = TradingSignalGenerator() if FractalRecognizer else None
        self.interval_analyzer = IntervalAnalyzer() if FractalRecognizer else None
        self.alert_system = RealTimeAlertSystem(db_path) if FractalRecognizer else None
        
        self.analysis_results = {}
    
    def _load_bars_sync(self, symbol: str, start: Optional[str] = None, 
                        end: Optional[str] = None) -> List[Dict]:
        """
        同步加载K线数据（在线程池中运行）
        
        Args:
            symbol: 股票代码
            start: 开始时间
            end: 结束时间
        
        Returns:
            K线数据列表
        """
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
            
            query += " ORDER BY minute ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            bars = [dict(row) for row in rows]
            return bars
        
        except Exception as e:
            logger.error(f"加载{symbol}数据失败: {e}")
            return []
    
    def _analyze_symbol_sync(self, symbol: str, start: Optional[str] = None,
                             end: Optional[str] = None) -> Optional[Dict]:
        """
        同步分析单个股票（在线程池中运行）
        
        Args:
            symbol: 股票代码
            start: 开始时间
            end: 结束时间
        
        Returns:
            分析结果字典
        """
        if not self.fractal_recognizer:
            logger.warning("分析模块不可用，跳过此股票")
            return None
        
        try:
            # 加载数据
            bars = self._load_bars_sync(symbol, start, end)
            if not bars or len(bars) < 5:
                return None
            
            # 执行分析（CPU密集）
            fractals = self.fractal_recognizer.recognize_from_bars(bars)
            strokes = self.stroke_recognizer.recognize_from_bars(bars, symbol)
            pivots = self.pivot_detector.detect_from_bars(bars, symbol)
            signals = self.signal_generator.analyze_bars(bars, symbol)
            interval_analysis = self.interval_analyzer.analyze_multilevel(bars, symbol)
            
            # 汇总结果
            result = {
                'symbol': symbol,
                'analyze_time': datetime.now().isoformat(),
                'bar_count': len(bars),
                'latest_price': bars[-1].get('close'),
                'fractals': {
                    'total': len(fractals),
                    'tops': len([f for f in fractals if hasattr(f, 'fractal_type') and f.fractal_type == 'top']),
                    'bottoms': len([f for f in fractals if hasattr(f, 'fractal_type') and f.fractal_type == 'bottom']),
                },
                'strokes': len(strokes) if strokes else 0,
                'pivots': len(pivots) if pivots else 0,
                'signals': len(signals) if signals else 0,
                'interval_strength': interval_analysis.get('strength', 0) if interval_analysis else 0,
            }
            
            return result
        
        except Exception as e:
            logger.error(f"分析{symbol}失败: {e}")
            return None
    
    async def analyze_symbol_async(self, symbol: str, start: Optional[str] = None,
                                    end: Optional[str] = None) -> Optional[Dict]:
        """
        异步分析单个股票 - 在线程池中执行CPU密集计算
        
        Args:
            symbol: 股票代码
            start: 开始时间
            end: 结束时间
        
        Returns:
            分析结果
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._analyze_symbol_sync,
            symbol,
            start,
            end
        )
        return result
    
    async def analyze_multiple_async(self, symbols: List[str], 
                                      concurrency: int = 10) -> Dict[str, Dict]:
        """
        并发分析多个股票
        
        Args:
            symbols: 股票代码列表
            concurrency: 最大并发数
        
        Returns:
            {symbol: analysis_result}
        """
        results = {}
        semaphore = asyncio.Semaphore(concurrency)
        
        async def analyze_with_semaphore(symbol):
            async with semaphore:
                result = await self.analyze_symbol_async(symbol)
                if result:
                    results[symbol] = result
                    logger.info(f"✓ {symbol} 分析完成 (分型:{result['fractals']['total']}, "
                               f"信号:{result['signals']})")
                return result
        
        # 并发执行
        tasks = [analyze_with_semaphore(symbol) for symbol in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    def get_summary_report(self, results: Dict[str, Dict]) -> str:
        """生成分析汇总报告"""
        total_symbols = len(results)
        if total_symbols == 0:
            return "无分析结果"
        
        # 统计信息
        total_fractals = sum(r.get('fractals', {}).get('total', 0) for r in results.values())
        total_signals = sum(r.get('signals', 0) for r in results.values())
        avg_strength = sum(r.get('interval_strength', 0) for r in results.values()) / total_symbols if total_symbols > 0 else 0
        
        # 按信号强度排序
        top_signals = sorted(
            [(s, r['signals']) for s, r in results.items() if r.get('signals', 0) > 0],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        report = f"""
{'='*70}
📊 缠论并行分析报告
{'='*70}
分析股票数: {total_symbols}
总分型数: {total_fractals}
总信号数: {total_signals}
平均强度: {avg_strength:.2f}

🎯 Top 5 强信号:
"""
        for symbol, signal_count in top_signals:
            report += f"  {symbol:10} {signal_count:3} 个信号\n"
        
        report += "="*70 + "\n"
        return report
    
    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)
        logger.info("✓ 线程池已关闭")
