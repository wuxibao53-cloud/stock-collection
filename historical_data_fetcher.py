#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史K线获取器 - 直接从公开数据源获取历史分钟K线

支持数据源：
1. AKShare (免费，无需token，推荐)
2. 东方财富 (免费API)
3. 新浪财经历史数据

Author: 仙儿仙儿碎碎念
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare未安装，运行 pip install akshare")

import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """历史K线数据获取器"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minute_bars (
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
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_minute 
            ON minute_bars(symbol, minute DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.info("✓ 数据库初始化完成")
    
    def fetch_stock_1min_akshare(self, symbol: str, days: int = 5) -> List[Dict]:
        """
        使用AKShare获取分钟K线（免费）
        
        Args:
            symbol: 股票代码，如 '000001'（不带前缀）
            days: 获取最近N天数据
        
        Returns:
            K线列表
        """
        if not AKSHARE_AVAILABLE:
            logger.error("akshare未安装")
            return []
        
        try:
            # AKShare股票分钟数据
            # 格式: stock_zh_a_hist_min_em(symbol='000001', period='1', adjust='', start_date='2024-01-01 09:30:00', end_date='2024-01-01 15:00:00')
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 转换代码格式（去掉sh/sz前缀）
            clean_symbol = symbol.replace('sh', '').replace('sz', '')
            
            logger.info(f"获取 {symbol} 最近{days}天的1分钟K线...")
            
            df = ak.stock_zh_a_hist_min_em(
                symbol=clean_symbol,
                period='1',
                adjust='',
                start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                end_date=end_date.strftime('%Y-%m-%d 15:00:00')
            )
            
            if df is None or df.empty:
                logger.warning(f"{symbol} 无数据")
                return []
            
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
            
            logger.info(f"✓ {symbol} 获取 {len(bars)} 条K线")
            return bars
            
        except Exception as e:
            logger.error(f"✗ {symbol} AKShare获取失败: {e}")
            return []
    
    def fetch_index_1min_akshare(self, symbol: str, days: int = 5) -> List[Dict]:
        """
        获取指数分钟K线
        
        Args:
            symbol: 指数代码 sh000001, sz399001等
            days: 天数
        """
        if not AKSHARE_AVAILABLE:
            return []
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 指数代码映射
            index_map = {
                'sh000001': '000001',  # 上证指数
                'sh000016': '000016',  # 上证50
                'sh000300': '000300',  # 沪深300
                'sz399001': '399001',  # 深证成指
                'sz399006': '399006',  # 创业板指
            }
            
            clean_symbol = index_map.get(symbol, symbol.replace('sh', '').replace('sz', ''))
            
            logger.info(f"获取指数 {symbol} 分钟K线...")
            
            df = ak.stock_zh_index_hist_min_em(
                symbol=clean_symbol,
                period='1',
                start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                end_date=end_date.strftime('%Y-%m-%d 15:00:00')
            )
            
            if df is None or df.empty:
                return []
            
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
            
            logger.info(f"✓ {symbol} 获取 {len(bars)} 条K线")
            return bars
            
        except Exception as e:
            logger.error(f"✗ {symbol} 指数获取失败: {e}")
            return []
    
    def save_bars(self, bars: List[Dict]):
        """保存K线到数据库"""
        if not bars:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for bar in bars:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO minute_bars
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
                logger.error(f"保存失败: {e}")
        
        conn.commit()
        conn.close()
    
    def fetch_all_a_stocks_history(self, days: int = 5, batch_size: int = 50):
        """
        获取全部A股历史数据（5000+）
        
        Args:
            days: 天数
            batch_size: 每批处理数量
        """
        from full_a_stock_collector import StockListManager
        
        stock_list = StockListManager.get_a_stock_list()
        total_bars = 0
        success_count = 0
        failed_count = 0
        
        logger.info(f"开始获取 {len(stock_list)} 只A股历史数据（批处理 {batch_size}只/批）...")
        
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i+batch_size]
            logger.info(f"处理第 {i//batch_size + 1} 批（{len(batch)}只）...")
            
            for stock in batch:
                symbol = stock.symbol
                
                try:
                    # 判断是否为指数
                    is_index = symbol.startswith('sh000') or symbol.startswith('sz399')
                    
                    if is_index:
                        bars = self.fetch_index_1min_akshare(symbol, days)
                    else:
                        bars = self.fetch_stock_1min_akshare(symbol, days)
                    
                    if bars:
                        self.save_bars(bars)
                        total_bars += len(bars)
                        success_count += 1
                    else:
                        failed_count += 1
                    
                    # 限流：每5只股票休息0.5秒
                    if (success_count + failed_count) % 5 == 0:
                        time.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"{symbol} 失败: {e}")
                    failed_count += 1
            
            # 批次间报告
            logger.info(f"  已处理 {i+len(batch)}/{len(stock_list)}，成功 {success_count}，失败 {failed_count}")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✓ 全量历史数据获取完成")
        logger.info(f"总股票数: {len(stock_list)}")
        logger.info(f"成功获取: {success_count}")
        logger.info(f"失败/无数据: {failed_count}")
        logger.info(f"总K线数: {total_bars}")
        logger.info(f"{'='*70}\n")
    
    def fetch_hot_stocks_history(self, days: int = 5):
        """获取热门股票历史数据（快速测试用）"""
        hot_stocks = [
            ('sh000001', True),   # 上证指数
            ('sh000300', True),   # 沪深300
            ('sz399001', True),   # 深证成指
            ('sh600519', False),  # 茅台
            ('sz000001', False),  # 平安银行
            ('sz300750', False),  # 宁德时代
        ]
        
        total_bars = 0
        
        for symbol, is_index in hot_stocks:
            try:
                if is_index:
                    bars = self.fetch_index_1min_akshare(symbol, days)
                else:
                    bars = self.fetch_stock_1min_akshare(symbol, days)
                
                if bars:
                    self.save_bars(bars)
                    total_bars += len(bars)
                
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"{symbol} 处理失败: {e}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✓ 热门股历史数据获取完成")
        logger.info(f"总K线数: {total_bars}")
        logger.info(f"{'='*60}\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='获取历史分钟K线数据')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--days', type=int, default=5, help='获取最近N天数据')
    parser.add_argument('--symbol', type=str, help='指定股票代码')
    parser.add_argument('--mode', choices=['hot', 'all'], default='all',
                       help='采集模式 (hot=热门股快速测试, all=全部A股)')
    
    args = parser.parse_args()
    
    fetcher = HistoricalDataFetcher(args.db)
    
    if args.symbol:
        # 单个股票
        is_index = args.symbol.startswith('sh000') or args.symbol.startswith('sz399')
        if is_index:
            bars = fetcher.fetch_index_1min_akshare(args.symbol, args.days)
        else:
            bars = fetcher.fetch_stock_1min_akshare(args.symbol, args.days)
        
        if bars:
            fetcher.save_bars(bars)
    elif args.mode == 'all':
        # 全量A股
        fetcher.fetch_all_a_stocks_history(args.days)
    else:
        # 热门股（快速测试）
        fetcher.fetch_hot_stocks_history(args.days)


if __name__ == '__main__':
    main()
