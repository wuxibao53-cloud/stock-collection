#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论交易系统 - 一键启动主控脚本

完整流程：
1. 智能过滤股票（13999 → 5500）
2. 采集30f基线（多线程，5-10分钟）
3. 分析30f生成候选（缠论三类买卖点）
4. 采集候选股5f（快速）
5. 启动实时监控（5f每3-5分钟，1f每分钟）
6. 邮件通知（带K线图和信号）
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smart_stock_filter import SmartStockFilter
from multi_timeframe_fetcher import MultiTimeframeDataFetcher, TimeFrame
from chan_theory_engine import ChanTheoryEngine
from email_notifier import EmailNotifier
from realtime_monitor import RealtimeMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler('logs/system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChanTradingSystem:
    """缠论交易系统主控"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.db_path = self.config.get('db_path', 'logs/quotes.db')
        
        # 初始化模块
        self.fetcher = MultiTimeframeDataFetcher(self.db_path)
        self.engine = ChanTheoryEngine(self.db_path)
        
        # 邮件通知器（可选）
        email_config = self.config.get('email', {})
        if email_config.get('enabled'):
            self.email_notifier = EmailNotifier(
                smtp_server=email_config.get('smtp_server', 'smtp.163.com'),
                smtp_port=email_config.get('smtp_port', 465),
                from_email=email_config.get('from_email', ''),
                password=email_config.get('password', ''),
                to_emails=email_config.get('to_emails', [])
            )
        else:
            self.email_notifier = None
            logger.warning("邮件通知未配置，将跳过邮件发送")
    
    def step1_filter_stocks(self) -> int:
        """步骤1：智能过滤股票"""
        logger.info("\n" + "="*70)
        logger.info("【步骤1】智能过滤股票")
        logger.info("="*70)
        
        df = SmartStockFilter.get_filtered_stocks()
        
        if df is not None and not df.empty:
            SmartStockFilter.save_to_csv(df, 'logs/filtered_stocks.csv')
            logger.info(f"✓ 过滤完成: {len(df)} 只正常交易股")
            return len(df)
        else:
            logger.error("股票过滤失败")
            return 0
    
    def step2_fetch_30f_baseline(self, days: int = 30, workers: int = 15):
        """步骤2：采集30f基线"""
        logger.info("\n" + "="*70)
        logger.info("【步骤2】采集30f基线（全量）")
        logger.info("="*70)
        
        start_time = time.time()
        
        self.fetcher.fetch_all_a_stocks_multiframe(
            days=days,
            timeframes=[TimeFrame.THIRTY_MIN],
            max_workers=workers
        )
        
        elapsed = time.time() - start_time
        logger.info(f"✓ 30f基线采集完成，耗时: {elapsed/60:.1f}分钟")
    
    def step3_analyze_30f_generate_watchlist(self) -> List[str]:
        """步骤3：分析30f生成候选股"""
        logger.info("\n" + "="*70)
        logger.info("【步骤3】分析30f，生成候选股清单")
        logger.info("="*70)
        
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有有30f数据的股票
        cursor.execute("SELECT DISTINCT symbol FROM minute_bars_30f")
        all_symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"开始分析 {len(all_symbols)} 只股票的30f数据...")
        
        watchlist = []
        signal_count = 0
        
        for i, symbol in enumerate(all_symbols, 1):
            try:
                result = self.engine.analyze(symbol, timeframe='30')
                
                if result.get('signals'):
                    watchlist.append(symbol)
                    signal_count += len(result['signals'])
                    
                    logger.info(f"  [{i}/{len(all_symbols)}] {symbol} 检测到 {len(result['signals'])} 个信号")
                
                # 进度显示
                if i % 100 == 0:
                    logger.info(f"  进度: {i}/{len(all_symbols)} | 候选: {len(watchlist)} 只")
            
            except Exception as e:
                logger.debug(f"  {symbol} 分析失败: {e}")
        
        # 保存候选清单
        with open('logs/watchlist.txt', 'w') as f:
            for symbol in watchlist:
                f.write(f"{symbol}\n")
        
        logger.info(f"\n✓ 30f分析完成")
        logger.info(f"  候选股票: {len(watchlist)} 只")
        logger.info(f"  信号总数: {signal_count} 个")
        logger.info(f"  已保存到: logs/watchlist.txt")
        
        return watchlist
    
    def step4_fetch_5f_watchlist(self, watchlist: List[str], days: int = 3, workers: int = 5):
        """步骤4：采集候选股5f"""
        logger.info("\n" + "="*70)
        logger.info("【步骤4】采集候选股5f数据")
        logger.info("="*70)
        
        if not watchlist:
            logger.warning("候选股清单为空，跳过5f采集")
            return
        
        logger.info(f"开始采集 {len(watchlist)} 只候选股的5f数据...")
        
        # 这里需要修改fetcher来支持指定股票列表
        # 临时方案：逐个采集
        success = 0
        for symbol in watchlist:
            try:
                bars_dict = self.fetcher.fetch_stock_multiframe_akshare(
                    symbol, days, timeframes=[TimeFrame.FIVE_MIN]
                )
                if bars_dict.get('5'):
                    self.fetcher.save_multiframe_bars(symbol, bars_dict)
                    success += 1
            except Exception as e:
                logger.debug(f"{symbol} 5f采集失败: {e}")
        
        logger.info(f"✓ 5f采集完成: {success}/{len(watchlist)} 只")
    
    def step5_start_realtime_monitoring(self):
        """步骤5：启动实时监控"""
        logger.info("\n" + "="*70)
        logger.info("【步骤5】启动实时监控系统")
        logger.info("="*70)
        
        monitor = RealtimeMonitor(
            db_path=self.db_path,
            email_notifier=self.email_notifier
        )
        
        # 启动监控（阻塞）
        monitor.start(watchlist_file='logs/watchlist.txt')
    
    def run_full_pipeline(self):
        """运行完整流程"""
        logger.info("\n" + "="*80)
        logger.info("🚀 缠论交易系统启动")
        logger.info("="*80)
        logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # 步骤1: 过滤股票
            stock_count = self.step1_filter_stocks()
            if stock_count == 0:
                logger.error("无可交易股票，退出")
                return
            
            # 步骤2: 采集30f
            self.step2_fetch_30f_baseline(days=30, workers=15)
            
            # 步骤3: 分析30f
            watchlist = self.step3_analyze_30f_generate_watchlist()
            
            # 步骤4: 采集5f
            self.step4_fetch_5f_watchlist(watchlist, days=3, workers=5)
            
            # 步骤5: 实时监控
            self.step5_start_realtime_monitoring()
        
        except KeyboardInterrupt:
            logger.info("\n用户中断")
        except Exception as e:
            logger.error(f"系统异常: {e}", exc_info=True)
        finally:
            logger.info("\n" + "="*80)
            logger.info("系统已停止")
            logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(description='缠论交易系统 - 一键启动')
    parser.add_argument('--mode', choices=['full', 'monitor-only', 'collect-only'], 
                       default='full', help='运行模式')
    parser.add_argument('--config', type=str, help='配置文件路径（JSON）')
    parser.add_argument('--days', type=int, default=30, help='历史数据天数')
    parser.add_argument('--workers', type=int, default=15, help='并发线程数')
    
    args = parser.parse_args()
    
    # 加载配置
    config = {}
    if args.config:
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # 创建系统
    system = ChanTradingSystem(config)
    
    # 根据模式运行
    if args.mode == 'full':
        system.run_full_pipeline()
    elif args.mode == 'collect-only':
        system.step1_filter_stocks()
        system.step2_fetch_30f_baseline(days=args.days, workers=args.workers)
        system.step3_analyze_30f_generate_watchlist()
    elif args.mode == 'monitor-only':
        system.step5_start_realtime_monitoring()


if __name__ == '__main__':
    main()
