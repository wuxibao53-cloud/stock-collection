#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易时间策略调度器

根据交易时间自动执行不同策略：
1. 开盘前 (9:15-9:30):     获取历史K线 → 分型检测
2. 盘中 (9:30-15:00):       实时监控符合条件的股票
3. 闭盘后 (15:05-16:00):    更新数据 → 生成日报
"""

import logging
import time
from datetime import datetime
import json

from multi_timeframe_fetcher import MultiTimeframeDataFetcher, TimeFrame

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingScheduler:
    """交易时间调度器"""
    
    def __init__(self, db_path: str = 'logs/quotes.db'):
        self.db_path = db_path
        self.fetcher = MultiTimeframeDataFetcher(db_path)
        self.monitored_symbols = {}
    
    def pre_market_task(self):
        """开盘前任务：获取并分析历史数据"""
        logger.info("\n" + "="*70)
        logger.info("🌅 开盘前任务：获取历史数据 + 分型检测")
        logger.info("="*70)
        
        # 获取全量A股多时间框架数据
        self.fetcher.fetch_all_a_stocks_multiframe(
            days=5,
            batch_size=50,
            timeframes=[TimeFrame.ONE_MIN, TimeFrame.FIVE_MIN, TimeFrame.THIRTY_MIN]
        )
        
        logger.info("\n开始分型检测...")
        
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM minute_bars_30f LIMIT 500")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        fractal_count = 0
        self.monitored_symbols = {}
        
        for symbol in symbols:
            fractals = self.fetcher.detect_fractal_patterns(symbol, TimeFrame.THIRTY_MIN)
            
            if fractals:
                latest_fractal = fractals[-1]
                
                # 获取当前价格
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT close FROM minute_bars_1f 
                    WHERE symbol = ? 
                    ORDER BY minute DESC 
                    LIMIT 1
                """, (symbol,))
                
                result = cursor.fetchone()
                current_price = result[0] if result else None
                conn.close()
                
                if current_price is None:
                    continue
                
                signal = self.fetcher.generate_trading_signal(
                    symbol, latest_fractal['type'], current_price, TimeFrame.THIRTY_MIN
                )
                
                self.monitored_symbols[symbol] = {
                    'fractal_type': latest_fractal['type'],
                    'current_price': current_price,
                    'signal': signal,
                    'detected_at': latest_fractal['time']
                }
                
                fractal_count += 1
                logger.info(f"  ✓ {symbol:12} | {latest_fractal['type']:6} | 价格: ¥{current_price:.2f}")
        
        logger.info(f"\n✓ 检测完成：发现 {fractal_count} 只符合分型条件的股票")
        return self.monitored_symbols
    
    def intra_day_task(self):
        """盘中任务：更新实时监控"""
        now = datetime.now()
        logger.info(f"\n[{now.strftime('%H:%M')}] 🔔 盘中实时监控（监控{len(self.monitored_symbols)}只股票）")
        
        if not self.monitored_symbols:
            logger.info("  无监控股票")
            return
        
        logger.info("  正在更新1f/5f最新数据...")
        
        for symbol in list(self.monitored_symbols.keys())[:20]:
            try:
                bars_1f = self.fetcher.fetch_stock_multiframe_akshare(
                    symbol, days=1, timeframes=[TimeFrame.ONE_MIN, TimeFrame.FIVE_MIN]
                )
                
                if bars_1f.get('1'):
                    self.fetcher.save_multiframe_bars(symbol, bars_1f)
                    logger.debug(f"    {symbol} 已更新")
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.debug(f"    {symbol} 更新失败: {e}")
    
    def post_market_task(self):
        """闭盘后任务：汇总数据并生成日报"""
        logger.info("\n" + "="*70)
        logger.info("🌇 闭盘后任务：数据汇总 + 日报生成")
        logger.info("="*70)
        
        logger.info("更新今日完整数据...")
        
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM minute_bars_1f LIMIT 100")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        for symbol in symbols:
            try:
                bars_dict = self.fetcher.fetch_stock_multiframe_akshare(
                    symbol, days=1, timeframes=[TimeFrame.ONE_MIN]
                )
                
                if bars_dict.get('1'):
                    self.fetcher.save_multiframe_bars(symbol, bars_dict)
                
                time.sleep(0.3)
            except:
                pass
        
        # 生成日报
        self._generate_daily_report()
        logger.info("\n✓ 闭盘后任务完成\n")
    
    def _generate_daily_report(self):
        """生成交易日报"""
        report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'monitored_count': len(self.monitored_symbols),
            'signals': []
        }
        
        for symbol, info in self.monitored_symbols.items():
            report['signals'].append({
                'symbol': symbol,
                'fractal_type': info['fractal_type'],
                'action': info['signal']['action'],
                'current_price': info['current_price'],
                'suggested_price': info['signal']['suggested_price'],
                'stop_loss': info['signal']['stop_loss'],
                'take_profit': info['signal']['take_profit'],
            })
        
        with open('logs/daily_trading_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 日报已保存：logs/daily_trading_report.json")
        logger.info(f"  - 监控股票: {report['monitored_count']} 只")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='交易时间调度器')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--mode', choices=['demo', 'run'], default='demo', help='运行模式')
    
    args = parser.parse_args()
    
    scheduler = TradingScheduler(args.db)
    
    if args.mode == 'demo':
        logger.info("📋 演示模式：依次执行所有交易时间任务\n")
        
        logger.info("【第1步】执行开盘前任务...")
        scheduler.pre_market_task()
        
        time.sleep(2)
        
        logger.info("\n【第2步】执行盘中监控任务...")
        scheduler.intra_day_task()
        
        time.sleep(2)
        
        logger.info("\n【第3步】执行闭盘后任务...")
        scheduler.post_market_task()
        
        logger.info("✓ 演示完成！")
    
    else:
        logger.info("持续运行模式（建议配合系统cron）")
        logger.info("工作日时间表:")
        logger.info("  09:15 → 开盘前数据获取")
        logger.info("  09:30-15:00 (每15分钟) → 盘中实时监控")
        logger.info("  15:05 → 闭盘后数据汇总")


if __name__ == '__main__':
    main()
