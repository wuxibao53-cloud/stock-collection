#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全A股缠论交易系统 - 完整端到端测试和部署脚本

功能流程：
1. 异步采集5000+热门股票或全部A股
2. 执行缠论三类买卖点分析
3. 生成交易信号和报告
4. 可选回测验证
5. GitHub Actions工作流触发

使用：
    python3 run_complete_system.py --mode collect
    python3 run_complete_system.py --mode analyze
    python3 run_complete_system.py --mode backtest
    python3 run_complete_system.py --mode all
"""

import asyncio
import argparse
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompleteSystemOrchestrator:
    """完整系统协调器"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.start_time = None
        self.results = {}
    
    async def step_1_collect_data(self, mode='hot'):
        """第1步：数据采集"""
        logger.info("="*80)
        logger.info("🔄 第1步：异步采集数据")
        logger.info("="*80)
        
        step_start = time.time()
        
        try:
            from full_a_stock_collector import FullAStockCollector
            
            collector = FullAStockCollector(self.db_path)
            
            if mode == 'hot':
                logger.info("采集热门26只股票...")
                await collector.collect_incremental_async()
            elif mode == 'all':
                logger.info("采集全部5000+A股...")
                await collector.collect_all_async()
            else:
                collector.collect_incremental()
            
            collector.print_stats()
            
            step_elapsed = time.time() - step_start
            self.results['collect'] = {
                'status': 'success',
                'elapsed': step_elapsed,
                'mode': mode,
            }
            
            logger.info(f"✓ 采集完成 (耗时 {step_elapsed:.1f}秒)")
            return True
        
        except Exception as e:
            logger.error(f"✗ 采集失败: {e}")
            self.results['collect'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def step_2_analyze_signals(self):
        """第2步：缠论分析"""
        logger.info("="*80)
        logger.info("🔄 第2步：缠论三类买卖点分析")
        logger.info("="*80)
        
        step_start = time.time()
        
        try:
            from chan_integrated_system import ChanTradingSystemIntegrated
            
            system = ChanTradingSystemIntegrated(self.db_path)
            
            # 获取所有股票
            symbols = system.get_all_symbols_from_db()
            
            if not symbols:
                logger.warning("⚠️  数据库中无数据")
                return False
            
            logger.info(f"分析 {len(symbols)} 只股票...")
            results = system.analyze_multiple_symbols(symbols)
            
            # 生成报告
            report = system.generate_report(results)
            print(report)
            
            # 保存报告
            report_path = Path('logs/analysis_report.txt')
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            step_elapsed = time.time() - step_start
            self.results['analyze'] = {
                'status': 'success',
                'elapsed': step_elapsed,
                'symbols_analyzed': len(results),
                'report_saved': str(report_path),
            }
            
            logger.info(f"✓ 分析完成 (耗时 {step_elapsed:.1f}秒)")
            logger.info(f"📄 报告已保存: {report_path}")
            return True
        
        except Exception as e:
            logger.error(f"✗ 分析失败: {e}")
            self.results['analyze'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def step_3_backtest_signals(self, capital=100000):
        """第3步：回测验证"""
        logger.info("="*80)
        logger.info("🔄 第3步：回测验证信号准确率")
        logger.info("="*80)
        
        step_start = time.time()
        
        try:
            from backtest_system import BacktestEngine
            import sqlite3
            
            engine = BacktestEngine(self.db_path, initial_capital=capital)
            
            # 获取所有股票
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM minute_bars")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not symbols:
                logger.warning("⚠️  数据库中无数据")
                return False
            
            logger.info(f"回测 {len(symbols)} 只股票...")
            
            for symbol in symbols[:5]:  # 仅回测前5只以节省时间
                result = engine.backtest_symbol(symbol)
                if result.get('trades', 0) > 0:
                    logger.info(f"  {symbol}: {result['trades']}笔交易, 胜率{result['winning_rate']:.2%}")
            
            # 生成回测报告
            report = engine.generate_report()
            print(report)
            
            # 保存报告
            backtest_report_path = Path('logs/backtest_report.txt')
            with open(backtest_report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            step_elapsed = time.time() - step_start
            self.results['backtest'] = {
                'status': 'success',
                'elapsed': step_elapsed,
                'report_saved': str(backtest_report_path),
            }
            
            logger.info(f"✓ 回测完成 (耗时 {step_elapsed:.1f}秒)")
            logger.info(f"📄 回测报告已保存: {backtest_report_path}")
            return True
        
        except Exception as e:
            logger.error(f"✗ 回测失败: {e}")
            self.results['backtest'] = {'status': 'failed', 'error': str(e)}
            return False
    
    async def run_complete_pipeline(self, mode='hot', skip_backtest=False):
        """运行完整管道"""
        self.start_time = time.time()
        
        logger.info("\n")
        logger.info("╔" + "═"*78 + "╗")
        logger.info("║" + " "*78 + "║")
        logger.info("║" + "缠论交易系统 - 完整端到端测试".center(78) + "║")
        logger.info("║" + f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(78) + "║")
        logger.info("║" + " "*78 + "║")
        logger.info("╚" + "═"*78 + "╝")
        logger.info("\n")
        
        success = True
        
        # Step 1: 采集数据
        if not await self.step_1_collect_data(mode=mode):
            success = False
        
        # Step 2: 分析信号
        if success and not self.step_2_analyze_signals():
            success = False
        
        # Step 3: 回测（可选）
        if success and not skip_backtest:
            if not self.step_3_backtest_signals():
                logger.warning("⚠️  回测失败，但不影响主流程")
        
        # 总结
        total_elapsed = time.time() - self.start_time
        
        logger.info("\n")
        logger.info("╔" + "═"*78 + "╗")
        logger.info("║" + " "*78 + "║")
        logger.info("║" + "完整管道总结".center(78) + "║")
        logger.info("║" + " "*78 + "║")
        
        for step, result in self.results.items():
            status_icon = "✓" if result['status'] == 'success' else "✗"
            elapsed = f" ({result.get('elapsed', 0):.1f}s)" if 'elapsed' in result else ""
            logger.info("║ " + f"{status_icon} {step:15}: {result['status']}{elapsed}".ljust(77) + "║")
        
        logger.info("║" + " "*78 + "║")
        logger.info("║" + f"总耗时: {total_elapsed:.1f}秒".ljust(78) + "║")
        logger.info("║" + " "*78 + "║")
        logger.info("╚" + "═"*78 + "╝")
        logger.info("\n")
        
        return success


async def main():
    parser = argparse.ArgumentParser(description='缠论交易系统完整端到端测试')
    parser.add_argument('--mode', choices=['collect', 'analyze', 'backtest', 'all'],
                       default='all', help='运行模式')
    parser.add_argument('--collect-mode', choices=['hot', 'all'],
                       default='hot', help='采集模式')
    parser.add_argument('--no-backtest', action='store_true', help='跳过回测')
    parser.add_argument('--capital', type=float, default=100000, help='回测初始资金')
    
    args = parser.parse_args()
    
    orchestrator = CompleteSystemOrchestrator()
    
    if args.mode == 'all':
        success = await orchestrator.run_complete_pipeline(
            mode=args.collect_mode,
            skip_backtest=args.no_backtest
        )
    elif args.mode == 'collect':
        success = await orchestrator.step_1_collect_data(mode=args.collect_mode)
    elif args.mode == 'analyze':
        success = orchestrator.step_2_analyze_signals()
    elif args.mode == 'backtest':
        success = orchestrator.step_3_backtest_signals(capital=args.capital)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
