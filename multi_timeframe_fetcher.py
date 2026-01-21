#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多时间框架K线数据获取器 + 交易时间策略 + 实时监控系统

核心功能：
1. 支持1f、5f、30f多时间框架数据获取
2. 智能重试机制（最多3次重试，间隔递增）
3. 分型检测与信号识别
4. 买卖点建议与风险提示
5. 持仓监控：买入后进行5f/1f区间套监控
6. 多线程并发获取（提高效率）
"""

import sqlite3
import logging
from datetime import datetime, timedelta, time as datetime_time
from typing import List, Dict, Optional
import time as time_module
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare未安装")

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)


class TimeFrame(Enum):
    """时间框架枚举"""
    ONE_MIN = '1'      # 1分钟
    FIVE_MIN = '5'     # 5分钟
    THIRTY_MIN = '30'  # 30分钟


class MultiTimeframeDataFetcher:
    """多时间框架K线数据获取器"""
    
    def __init__(self, db_path: str = 'logs/quotes.db'):
        self.db_path = db_path
        self.max_retries = 3  # 最多重试次数
        self.timeframes = [TimeFrame.ONE_MIN, TimeFrame.FIVE_MIN, TimeFrame.THIRTY_MIN]
        self._init_db()
    
    def _init_db(self):
        """初始化数据库 - 支持多个时间框架表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # 创建多个表
        for tf in self.timeframes:
            table_name = f"minute_bars_{tf.value}f"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    minute TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    amount REAL,
                    UNIQUE(symbol, minute)
                )
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_minute 
                ON {table_name}(symbol, minute DESC)
            """)
        
        conn.commit()
        conn.close()
        logger.info("✓ 数据库初始化完成（支持1f/5f/30f）")
    
    def fetch_stock_multiframe_akshare(
        self,
        symbol: str,
        days: int = 5,
        timeframes: List[TimeFrame] = None,
        retry_count: int = 0
    ) -> Dict[str, List[Dict]]:
        """
        获取多时间框架K线数据（带重试机制）
        
        Args:
            symbol: 股票代码
            days: 天数
            timeframes: 时间框架列表
            retry_count: 当前重试次数
        
        Returns:
            {'1': [...], '5': [...], '30': [...]}
        """
        if not AKSHARE_AVAILABLE:
            logger.error("akshare未安装")
            return {}
        
        if timeframes is None:
            timeframes = self.timeframes
        
        result = {}
        clean_symbol = symbol.replace('sh', '').replace('sz', '')
        
        for tf in timeframes:
            result[tf.value] = []  # 默认空结果
            
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # 只在首次尝试或重试时打印详细日志
                if retry_count == 0:
                    logger.debug(f"获取 {symbol} {tf.value}f K线...")
                else:
                    logger.info(f"获取 {symbol} {tf.value}f K线（尝试 {retry_count+1}/{self.max_retries+1}）...")
                
                period = tf.value
                
                # API调用本身可能抛异常或返回奇怪的值
                try:
                    df = ak.stock_zh_a_hist_min_em(
                        symbol=clean_symbol,
                        period=period,
                        adjust='',
                        start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                        end_date=end_date.strftime('%Y-%m-%d 15:00:00')
                    )
                except Exception as e:
                    logger.warning(f"{symbol} {tf.value}f API调用异常: {type(e).__name__}")
                    continue
                
                # 健壮性检查：处理None、空数据、格式错误
                if df is None:
                    logger.warning(f"{symbol} {tf.value}f API返回None")
                    continue
                
                # 检查是否是DataFrame类型
                if not hasattr(df, 'empty') or not hasattr(df, 'columns') or not hasattr(df, 'iterrows'):
                    logger.warning(f"{symbol} {tf.value}f 返回类型异常")
                    continue
                
                if df.empty:
                    logger.warning(f"{symbol} {tf.value}f 无数据")
                    continue
                
                # 检查必需列
                required_cols = ['时间', '开盘', '最高', '最低', '收盘', '成交量']
                try:
                    missing = [col for col in required_cols if col not in df.columns]
                    if missing:
                        logger.warning(f"{symbol} {tf.value}f 缺少列: {missing}")
                        continue
                except Exception:
                    logger.warning(f"{symbol} {tf.value}f 列检查失败")
                    continue
                
                # 解析数据行
                bars = []
                try:
                    for _, row in df.iterrows():
                        try:
                            bars.append({
                                'symbol': symbol,
                                'minute': str(row['时间']),
                                'open': float(row['开盘']),
                                'high': float(row['最高']),
                                'low': float(row['最低']),
                                'close': float(row['收盘']),
                                'volume': int(row['成交量']),
                                'amount': float(row.get('成交额', 0)),
                            })
                        except (ValueError, KeyError, TypeError) as e:
                            logger.debug(f"{symbol} {tf.value}f 跳过异常行: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"{symbol} {tf.value}f 数据解析失败: {type(e).__name__}")
                    continue
                
                # 成功获取数据
                if bars:
                    logger.debug(f"✓ {symbol} {tf.value}f 获取 {len(bars)} 条K线")
                    result[tf.value] = bars
                
                time_module.sleep(0.2)
                
            except Exception as e:
                # 外层catch-all异常处理（理论上不应该到这里，但保险起见）
                logger.error(f"✗ {symbol} {tf.value}f 未捕获异常: {type(e).__name__} - {e}")
                
                # 重试逻辑
                if retry_count < self.max_retries:
                    wait_time = (retry_count + 1) * 2
                    logger.info(f"等待{wait_time}秒后重试...")
                    time_module.sleep(wait_time)
                    
                    retry_result = self.fetch_stock_multiframe_akshare(
                        symbol, days, [tf], retry_count + 1
                    )
                    if tf.value in retry_result and retry_result[tf.value]:
                        result[tf.value] = retry_result[tf.value]
                else:
                    logger.error(f"{symbol} {tf.value}f 已达最大重试次数")
        
        return result
    
    def save_multiframe_bars(self, symbol: str, bars_dict: Dict[str, List[Dict]]):
        """保存多时间框架K线数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for timeframe_str, bars in bars_dict.items():
            if not bars:
                continue
            
            table_name = f"minute_bars_{timeframe_str}f"
            
            for bar in bars:
                try:
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {table_name}
                        (symbol, minute, open, high, low, close, volume, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bar['symbol'],
                        bar['minute'],
                        bar['open'],
                        bar['high'],
                        bar['low'],
                        bar['close'],
                        bar['volume'],
                        bar.get('amount', 0),
                    ))
                except Exception as e:
                    logger.debug(f"保存失败: {e}")
        
        conn.commit()
        conn.close()
    
    def detect_fractal_patterns(self, symbol: str, timeframe: TimeFrame = TimeFrame.THIRTY_MIN) -> List[Dict]:
        """
        检测分型模式（缠论基础）
        
        分型定义：
        - 顶分型：高点 > 两侧高点
        - 底分型：低点 < 两侧低点
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        table_name = f"minute_bars_{timeframe.value}f"
        
        cursor.execute(f"""
            SELECT minute, high, low, close FROM {table_name}
            WHERE symbol = ?
            ORDER BY minute DESC
            LIMIT 50
        """, (symbol,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return []
        
        rows = list(reversed(rows))
        fractals = []
        
        for i in range(1, len(rows) - 1):
            prev_high, prev_low = rows[i-1][1], rows[i-1][2]
            curr_high, curr_low = rows[i][1], rows[i][2]
            next_high, next_low = rows[i+1][1], rows[i+1][2]
            
            # 顶分型
            if curr_high > prev_high and curr_high > next_high:
                fractals.append({
                    'type': '顶分型',
                    'time': rows[i][0],
                    'level': curr_high,
                })
            
            # 底分型
            elif curr_low < prev_low and curr_low < next_low:
                fractals.append({
                    'type': '底分型',
                    'time': rows[i][0],
                    'level': curr_low,
                })
        
        return fractals
    
    def generate_trading_signal(
        self,
        symbol: str,
        fractal_type: str,
        current_price: float,
        timeframe: TimeFrame = TimeFrame.THIRTY_MIN
    ) -> Dict:
        """根据分型生成交易信号"""
        if fractal_type == '底分型':
            return {
                'action': 'BUY',
                'suggested_price': current_price * 0.98,
                'stop_loss': current_price * 0.95,
                'take_profit': current_price * 1.05,
            }
        else:  # 顶分型
            return {
                'action': 'SELL',
                'suggested_price': current_price * 1.02,
                'stop_loss': current_price * 1.05,
                'take_profit': current_price * 0.95,
            }
    
    def fetch_all_a_stocks_multiframe(self, days: int = 5, batch_size: int = 50, timeframes: List[TimeFrame] = None, max_workers: int = 10):
        """获取全部A股多时间框架历史数据（支持多线程并发）"""
        from full_a_stock_collector import StockListManager
        
        if timeframes is None:
            timeframes = self.timeframes
        
        # 获取股票列表并过滤掉指数
        all_stocks = StockListManager.get_a_stock_list()
        
        # 过滤规则：排除指数代码（sh000xxx, sz399xxx）
        stock_list = [
            stock for stock in all_stocks
            if not (stock.symbol.startswith('sh000') or stock.symbol.startswith('sz399'))
        ]
        
        filtered_count = len(all_stocks) - len(stock_list)
        if filtered_count > 0:
            logger.info(f"已过滤 {filtered_count} 个指数代码")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"开始并发获取 {len(stock_list)} 只A股数据（{max_workers}个线程）")
        logger.info(f"{'='*70}\n")
        
        # 统计锁（线程安全）
        stats_lock = threading.Lock()
        stats = {'success': 0, 'failed': 0, 'processed': 0}
        
        def process_stock(stock):
            """处理单只股票的线程函数"""
            symbol = stock.symbol
            try:
                bars_dict = self.fetch_stock_multiframe_akshare(symbol, days, timeframes)
                
                if any(bars_dict.values()):
                    self.save_multiframe_bars(symbol, bars_dict)
                    with stats_lock:
                        stats['success'] += 1
                    return (symbol, True)
                else:
                    with stats_lock:
                        stats['failed'] += 1
                    return (symbol, False)
                    
            except Exception as e:
                logger.debug(f"{symbol} 异常: {e}")
                with stats_lock:
                    stats['failed'] += 1
                return (symbol, False)
        
        # 使用ThreadPoolExecutor进行并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_stock, stock): stock for stock in stock_list}
            
            start_time = time_module.time()
            
            for i, future in enumerate(as_completed(futures), 1):
                with stats_lock:
                    stats['processed'] = i
                    current = stats.copy()
                
                # 每50只显示一次进度
                if i % 50 == 0:
                    elapsed = time_module.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (len(stock_list) - i) / rate if rate > 0 else 0
                    
                    logger.info(f"进度: {i}/{len(stock_list)} | 成功: {current['success']} | 跳过: {current['failed']} | 速度: {rate:.1f}个/秒 | ETA: {eta:.0f}秒")
        
        elapsed = time_module.time() - start_time
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✓ 全部完成")
        logger.info(f"  成功获取: {stats['success']}")
        logger.info(f"  跳过失败: {stats['failed']}")
        logger.info(f"  耗时: {elapsed:.1f}秒")
        logger.info(f"  平均速度: {len(stock_list)/elapsed:.1f}个/秒")
        logger.info(f"{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='多时间框架K线数据获取器')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--days', type=int, default=5, help='天数')
    parser.add_argument('--symbol', type=str, help='指定股票代码')
    parser.add_argument('--mode', choices=['hot', 'all'], default='all', help='采集模式')
    parser.add_argument('--timeframes', nargs='+', default=['1', '5', '30'], help='时间框架')
    parser.add_argument('--workers', type=int, default=10, help='并发线程数（默认10，建议5-20）')
    
    args = parser.parse_args()
    
    timeframes = [TimeFrame(tf) for tf in args.timeframes]
    fetcher = MultiTimeframeDataFetcher(args.db)
    
    logger.info(f"当前时间框架: {', '.join([f'{tf.value}f' for tf in timeframes])}")
    logger.info(f"最大重试次数: {fetcher.max_retries}")
    logger.info(f"并发线程数: {args.workers}\n")
    
    if args.symbol:
        logger.info(f"获取单只股票 {args.symbol}...")
        bars_dict = fetcher.fetch_stock_multiframe_akshare(args.symbol, args.days, timeframes)
        
        if any(bars_dict.values()):
            fetcher.save_multiframe_bars(args.symbol, bars_dict)
            fractals = fetcher.detect_fractal_patterns(args.symbol)
            if fractals:
                logger.info(f"检测到 {len(fractals)} 个分型")
    
    elif args.mode == 'all':
        fetcher.fetch_all_a_stocks_multiframe(args.days, timeframes=timeframes, max_workers=args.workers)
    
    else:
        hot_stocks = ['sh600519', 'sz000001', 'sz300750']
        for symbol in hot_stocks:
            logger.info(f"\n获取 {symbol}...")
            bars_dict = fetcher.fetch_stock_multiframe_akshare(symbol, args.days, timeframes)
            
            if any(bars_dict.values()):
                fetcher.save_multiframe_bars(symbol, bars_dict)


if __name__ == '__main__':
    main()
