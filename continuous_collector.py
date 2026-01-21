#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持续分钟级采集脚本 - 用于积累历史K线数据

每分钟采集一次，持续运行N小时，积累足够的历史深度供缠论分析使用。

使用方法:
    python3 continuous_collector.py --duration 60  # 运行60分钟
    python3 continuous_collector.py --mode hot --duration 30  # 热门股运行30分钟
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
import time
import signal
import sys

from full_a_stock_collector import FullAStockCollector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContinuousCollector:
    """持续采集器 - 每分钟采集一次"""
    
    def __init__(self, db_path='logs/quotes.db', mode='hot'):
        self.db_path = db_path
        self.mode = mode  # hot or all
        self.collector = FullAStockCollector(db_path)
        self.running = True
        self.collections_count = 0
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        logger.info("\n收到停止信号，正在优雅退出...")
        self.running = False
    
    async def run_continuous(self, duration_minutes=60):
        """
        持续采集
        
        Args:
            duration_minutes: 运行时长（分钟）
        """
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        logger.info("="*80)
        logger.info(f"开始持续采集")
        logger.info(f"采集模式: {self.mode}")
        logger.info(f"运行时长: {duration_minutes} 分钟")
        logger.info(f"预计结束: {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        while self.running and time.time() < end_time:
            collection_start = time.time()
            current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            logger.info(f"\n[第 {self.collections_count + 1} 次采集] {current_minute}")
            
            try:
                # 执行采集
                if self.mode == 'hot':
                    await self.collector.collect_incremental_async()
                else:
                    await self.collector.collect_all_async()
                
                self.collections_count += 1
                elapsed = time.time() - collection_start
                
                logger.info(f"✓ 本次采集完成，耗时 {elapsed:.1f}秒")
                
                # 打印统计
                if self.collections_count % 5 == 0:
                    self.collector.print_stats()
                
                # 等待到下一分钟
                next_minute = (datetime.now().replace(second=0, microsecond=0) 
                              + timedelta(minutes=1))
                wait_seconds = (next_minute - datetime.now()).total_seconds()
                
                if wait_seconds > 0 and self.running:
                    logger.info(f"等待 {wait_seconds:.0f}秒 到下一分钟...")
                    await asyncio.sleep(wait_seconds)
                
            except Exception as e:
                logger.error(f"✗ 采集失败: {e}")
                await asyncio.sleep(60)  # 失败后等待1分钟再试
        
        # 最终统计
        total_elapsed = time.time() - start_time
        logger.info("\n" + "="*80)
        logger.info("持续采集完成")
        logger.info(f"总运行时间: {total_elapsed/60:.1f} 分钟")
        logger.info(f"总采集次数: {self.collections_count}")
        logger.info("="*80)
        
        self.collector.print_stats()


async def main():
    parser = argparse.ArgumentParser(description='持续分钟级采集 - 积累历史K线')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--mode', choices=['hot', 'all'], default='hot',
                       help='采集模式 (hot=热门100只, all=全部5000+)')
    parser.add_argument('--duration', type=int, default=60,
                       help='运行时长（分钟），默认60分钟')
    
    args = parser.parse_args()
    
    collector = ContinuousCollector(args.db, args.mode)
    
    try:
        await collector.run_continuous(args.duration)
    except KeyboardInterrupt:
        logger.info("\n用户中断，正在退出...")
    except Exception as e:
        logger.error(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
