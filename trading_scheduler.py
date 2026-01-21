#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易时间策略调度器

根据交易时间自动执行不同策略：
1. 开盘前 (9:15-9:30):     获取最近5天历史K线 → 分型检测 → 生成买卖点列表
2. 盘中 (9:30-15:00):       实时监控符合条件的股票 → 5f/1f区间套监控 → 推送提示
3. 闭盘后 (15:05-16:00):    更新今日完整K线 → 更新信号数据库 → 生成日报
"""

import logging
import time
import schedule
from datetime import datetime, time as datetime_time
from typing import List, Dict
import subprocess
import json

from multi_timeframe_fetcher import (
    MultiTimeframeDataFetcher,
    TradePhase,
    TimeFrame
)

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
        self.monitored_symbols: Dict[str, Dict] = {}  # {symbol: {signal_info}}
    
    def pre_market_task(self):
        """
        开盘前任务 (9:15-9:30)
        - 获取最近5天的1f/5f/30f完整K线
        - 检测分型和买卖点
        - 生成今日监控清单
        """
        logger.info("\n" + "="*70)
        logger.info("🌅 开始执行「开盘前」数据获取任务")
        logger.info("="*70)
        
        # 获取全量A股多时间框架数据
        self.fetcher.fetch_all_a_stocks_multiframe(
            days=5,
            batch_size=50,
            timeframes=[TimeFrame.ONE_MIN, TimeFrame.FIVE_MIN, TimeFrame.THIRTY_MIN]
        )
        
        logger.info("\n开始分型检测...")
        
        # 扫描所有股票，检测分型
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT symbol FROM minute_bars_30f")
        symbols = cursor.fetchall()
        conn.close()
        
        fractal_count = 0
        self.monitored_symbols = {}
        
        for (symbol,) in symbols[:500]:  # 限制为500只以加快处理
            fractals = self.fetcher.detect_fractal_patterns(symbol, TimeFrame.THIRTY_MIN)
            
            if fractals:
                latest_fractal = fractals[-1]  # 最新分型
                
                # 获取当前价格（取最后一条K线的收盘价）
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
                
                # 生成交易信号
                signal = self.fetcher.generate_trading_signal(
                    symbol,
                    latest_fractal['type'],
                    current_price,
                    TimeFrame.THIRTY_MIN
                )
                
                self.monitored_symbols[symbol] = {
                    'fractal_type': latest_fractal['type'],
                    'fractal_level': latest_fractal['level'],
                    'current_price': current_price,
                    'signal': signal,
                    'detected_at': latest_fractal['time']
                }
                
                fractal_count += 1
                
                logger.info(
                    f"  ✓ {symbol:12} | {latest_fractal['type']:6} | "
                    f"价格: ¥{current_price:.2f} | "
                    f"信号: {signal['action']:4} | "
                    f"信心: {signal['confidence']:.0%}"
                )
        
        logger.info(f"\n✓ 检测完成：发现 {fractal_count} 只符合分型条件的股票")
        logger.info(f"将在盘中实时监控这些股票的5f/1f走势\n")
        
        return self.monitored_symbols
    
    def intra_day_task(self):
        """
        盘中任务 (9:30-15:00)
        - 每15分钟更新一次符合条件的股票的1f/5f数据
        - 检测5f/1f的买卖点和破位信号
        - 推送实时提示
        """
        now = datetime.now()
        logger.info(f"\n[{now.strftime('%H:%M')}] 🔔 盘中实时监控更新")
        
        if not self.monitored_symbols:
            logger.info("  无监控股票")
            return
        
        logger.info(f"  正在更新 {len(self.monitored_symbols)} 只监控股票的1f/5f数据...")
        
        for symbol in list(self.monitored_symbols.keys())[:20]:  # 每次更新20只（避免频繁API调用）
            try:
                # 只获取今天的数据（1条最新K线）
                bars_1f = self.fetcher.fetch_stock_multiframe_akshare(
                    symbol, days=1, timeframes=[TimeFrame.ONE_MIN, TimeFrame.FIVE_MIN]
                )
                
                if bars_1f.get('1'):
                    self.fetcher.save_multiframe_bars(symbol, bars_1f)
                    
                    # 检测1f/5f的分型
                    fractals_1f = self.fetcher.detect_fractal_patterns(symbol, TimeFrame.ONE_MIN)
                    fractals_5f = self.fetcher.detect_fractal_patterns(symbol, TimeFrame.FIVE_MIN)
                    
                    signal = self.monitored_symbols[symbol]['signal']
                    
                    if fractals_1f and fractals_5f:
                        latest_1f = fractals_1f[-1]
                        latest_5f = fractals_5f[-1]
                        
                        # 判断是否出现操作机会
                        if signal['action'] == 'BUY' and latest_1f['type'] == '底分型':
                            logger.info(f"  📈 {symbol} - 1f出现底分型！建议买入")
                            self.fetcher.monitor_position_realtime(symbol, signal['suggested_price'], 'BUY')
                        
                        elif signal['action'] == 'SELL' and latest_1f['type'] == '顶分型':
                            logger.info(f"  📉 {symbol} - 1f出现顶分型！建议卖出")
                            self.fetcher.monitor_position_realtime(symbol, signal['suggested_price'], 'SELL')
                
                time.sleep(0.5)  # 限流
                
            except Exception as e:
                logger.debug(f"  {symbol} 更新失败: {e}")
    
    def post_market_task(self):
        """
        闭盘后任务 (15:05-16:00)
        - 获取今日完整数据（补全最后1小时的K线）
        - 生成日报
        - 保存信号数据库
        """
        logger.info("\n" + "="*70)
        logger.info("🌇 开始执行「闭盘后」数据汇总任务")
        logger.info("="*70)
        
        logger.info("获取今日完整数据...")
        
        # 更新所有股票的今日完整数据
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
                'confidence': info['signal']['confidence']
            })
        
        # 保存为JSON
        with open('logs/daily_trading_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 日报已保存到 logs/daily_trading_report.json")
        logger.info(f"  - 监控股票: {report['monitored_count']} 只")
        logger.info(f"  - 买入信号: {sum(1 for s in report['signals'] if s['action'] == 'BUY')} 个")
        logger.info(f"  - 卖出信号: {sum(1 for s in report['signals'] if s['action'] == 'SELL')} 个")
    
    def start_scheduler(self):
        """启动调度器"""
        logger.info("\n" + "="*70)
        logger.info("📅 启动交易时间调度器")
        logger.info("="*70)
        logger.info("工作日时间表:")
        logger.info("  🌅 09:15-09:30 → 开盘前数据获取 + 分型检测")
        logger.info("  🔔 09:30-15:00 → 每15分钟更新一次盘中实时监控")
        logger.info("  🌇 15:05-16:00 → 闭盘后数据汇总 + 日报生成")
        logger.info("="*70 + "\n")
        
        # 定时任务配置
        schedule.every().monday.at("09:15").do(self.pre_market_task)
        schedule.every().tuesday.at("09:15").do(self.pre_market_task)
        schedule.every().wednesday.at("09:15").do(self.pre_market_task)
        schedule.every().thursday.at("09:15").do(self.pre_market_task)
        schedule.every().friday.at("09:15").do(self.pre_market_task)
        
        schedule.every().monday.at("09:30").to(15, 0).minutes.do(self.intra_day_task)
        schedule.every().tuesday.at("09:30").to(15, 0).minutes.do(self.intra_day_task)
        schedule.every().wednesday.at("09:30").to(15, 0).minutes.do(self.intra_day_task)
        schedule.every().thursday.at("09:30").to(15, 0).minutes.do(self.intra_day_task)
        schedule.every().friday.at("09:30").to(15, 0).minutes.do(self.intra_day_task)
        
        schedule.every().monday.at("15:05").do(self.post_market_task)
        schedule.every().tuesday.at("15:05").do(self.post_market_task)
        schedule.every().wednesday.at("15:05").do(self.post_market_task)
        schedule.every().thursday.at("15:05").do(self.post_market_task)
        schedule.every().friday.at("15:05").do(self.post_market_task)
        
        # 持续运行
        logger.info("调度器已启动，等待执行时间...\n")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='交易时间调度器')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--mode', choices=['demo', 'run'], default='demo',
                       help='运行模式 (demo=测试一次, run=持续运行)')
    
    args = parser.parse_args()
    
    scheduler = TradingScheduler(args.db)
    
    if args.mode == 'demo':
        # 演示模式：立即执行各个任务
        logger.info("📋 演示模式：依次执行所有交易时间任务\n")
        
        logger.info("【第1步】执行开盘前任务...")
        scheduler.pre_market_task()
        
        time.sleep(2)
        
        logger.info("\n【第2步】执行盘中监控任务...")
        scheduler.intra_day_task()
        
        time.sleep(2)
        
        logger.info("\n【第3步】执行闭盘后任务...")
        scheduler.post_market_task()
        
        logger.info("\n✓ 演示完成！")
    
    else:
        # 持续运行模式
        scheduler.start_scheduler()


if __name__ == '__main__':
    main()
