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
"""

import sqlite3
import logging
from datetime import datetime, timedelta, time as datetime_time
from typing import List, Dict, Optional
import time as time_module
from enum import Enum

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
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                logger.info(f"获取 {symbol} {tf.value}f K线（尝试 {retry_count+1}/{self.max_retries+1}）...")
                
                period = tf.value
                
                df = ak.stock_zh_a_hist_min_em(
                    symbol=clean_symbol,
                    period=period,
                    adjust='',
                    start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                    end_date=end_date.strftime('%Y-%m-%d 15:00:00')
                )
                
                if df is None or df.empty:
                    logger.warning(f"{symbol} {tf.value}f 无数据")
                    result[tf.value] = []
                    continue
                
                bars = []
                for _, row in df.iterrows():
                    bars.append({
                        'symbol': symbol,
                        'minute': row['时间'],
                        'open': float(row['开盘']),
                        'high': float(row['最高']),
                        'low': float(row['最低']),
                        'close': float(row['收盘']),
                        'volume': int(row['成交量']),
                        'amount': float(row['成交额']) if '成交额' in row else 0,
                    })
                
                logger.info(f"✓ {symbol} {tf.value}f 获取 {len(bars)} 条K线")
                result[tf.value] = bars
                time_module.sleep(0.2)
                
            except Exception as e:
                logger.error(f"✗ {symbol} {tf.value}f 获取失败: {e}")
                
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
                        result[tf.value] = []
                else:
                    logger.error(f"{symbol} {tf.value}f 已达最大重试次数")
                    result[tf.value] = []
        
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
    
    def fetch_all_a_stocks_multiframe(self, days: int = 5, batch_size: int = 50, timeframes: List[TimeFrame] = None):
        """获取全部A股多时间框架历史数据"""
        from full_a_stock_collector import StockListManager
        
        if timeframes is None:
            timeframes = self.timeframes
        
        stock_list = StockListManager.get_a_stock_list()
        total_success = 0
        total_failed = 0
        
        logger.info(f"开始获取 {len(stock_list)} 只A股数据（支持1f/5f/30f）...\n")
        
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"第 {batch_num} 批（{len(batch)}只 / {len(stock_list)}只）")
            
            for idx, stock in enumerate(batch, 1):
                symbol = stock.symbol
                
                try:
                    bars_dict = self.fetch_stock_multiframe_akshare(symbol, days, timeframes)
                    
                    if any(bars_dict.values()):
                        self.save_multiframe_bars(symbol, bars_dict)
                        total_success += 1
                        logger.info(f"  [{idx}/{len(batch)}] {symbol} ✓")
                    else:
                        total_failed += 1
                    
                    if idx % 5 == 0:
                        time_module.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"  [{idx}/{len(batch)}] {symbol} ✗")
                    total_failed += 1
        
        logger.info(f"\n✓ 完成：成功 {total_success}, 失败 {total_failed}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='多时间框架K线数据获取器')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--days', type=int, default=5, help='天数')
    parser.add_argument('--symbol', type=str, help='指定股票代码')
    parser.add_argument('--mode', choices=['hot', 'all'], default='all', help='采集模式')
    parser.add_argument('--timeframes', nargs='+', default=['1', '5', '30'], help='时间框架')
    
    args = parser.parse_args()
    
    timeframes = [TimeFrame(tf) for tf in args.timeframes]
    fetcher = MultiTimeframeDataFetcher(args.db)
    
    logger.info(f"当前时间框架: {', '.join([f'{tf.value}f' for tf in timeframes])}")
    logger.info(f"最大重试次数: {fetcher.max_retries}\n")
    
    if args.symbol:
        logger.info(f"获取单只股票 {args.symbol}...")
        bars_dict = fetcher.fetch_stock_multiframe_akshare(args.symbol, args.days, timeframes)
        
        if any(bars_dict.values()):
            fetcher.save_multiframe_bars(args.symbol, bars_dict)
            fractals = fetcher.detect_fractal_patterns(args.symbol)
            if fractals:
                logger.info(f"检测到 {len(fractals)} 个分型")
    
    elif args.mode == 'all':
        fetcher.fetch_all_a_stocks_multiframe(args.days, timeframes=timeframes)
    
    else:
        hot_stocks = ['sh600519', 'sz000001', 'sz300750']
        for symbol in hot_stocks:
            logger.info(f"\n获取 {symbol}...")
            bars_dict = fetcher.fetch_stock_multiframe_akshare(symbol, args.days, timeframes)
            
            if any(bars_dict.values()):
                fetcher.save_multiframe_bars(symbol, bars_dict)


if __name__ == '__main__':
    main()
