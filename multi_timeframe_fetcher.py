#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多时间框架K线数据获取器 + 交易时间策略 + 实时监控系统

核心功能：
1. 支持1f、5f、30f多时间框架数据获取
2. 智能重试机制（最多3次重试，间隔递增）
3. 交易时间段策略：
   - 开盘前：9:15-9:30（获取前5天的全量K线作为基础）
   - 闭盘后：15:05-16:00（更新今日数据）
   - 盘中：实时监控符合分型条件的股票
4. 分型检测与信号识别
5. 买卖点建议与风险提示
6. 持仓监控：买入后进行5f/1f区间套监控

Author: 仙儿仙儿碎碎念
Date: 2026-01-21
"""

import sqlite3
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
import time as time_module
from enum import Enum

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare未安装，运行 pip install akshare")

import requests
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


class TradePhase(Enum):
    """交易阶段"""
    PRE_MARKET = '开盘前'       # 9:15-9:30
    INTRA_DAY = '盘中'          # 9:30-15:00
    POST_MARKET = '闭盘后'      # 15:05-16:00
    OFF_MARKET = '休市'         # 其他时间


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
        
        # 创建多个表，分别存储不同时间框架的K线
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
        
        # 创建买卖点信号表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                signal_time TEXT NOT NULL,
                signal_type TEXT,  -- '买卖点', '分型', '实时提示'
                signal_detail TEXT,
                confidence REAL,
                action TEXT,  -- 'BUY', 'SELL', 'HOLD'
                suggested_price REAL,
                stop_loss REAL,
                take_profit REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建持仓监控表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                entry_price REAL,
                entry_time TEXT,
                entry_timeframe TEXT,  -- '1f', '5f', '30f'
                shares INTEGER,
                status TEXT,  -- 'OPEN', 'CLOSED'
                exit_price REAL,
                exit_time TEXT,
                pnl REAL,
                monitoring_active BOOLEAN DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✓ 数据库初始化完成（支持1f/5f/30f）")
    
    def get_current_trade_phase(self) -> TradePhase:
        """获取当前交易阶段"""
        now = datetime.now()
        current_time = now.time()
        
        # 仅工作日有交易
        if now.weekday() >= 5:  # 周末
            return TradePhase.OFF_MARKET
        
        if time(9, 15) <= current_time < time(9, 30):
            return TradePhase.PRE_MARKET
        elif time(9, 30) <= current_time < time(15, 0):
            return TradePhase.INTRA_DAY
        elif time(15, 5) <= current_time <= time(16, 0):
            return TradePhase.POST_MARKET
        else:
            return TradePhase.OFF_MARKET
    
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
                
                logger.info(f"获取 {symbol} {tf.value}分钟K线（尝试 {retry_count+1}/{self.max_retries+1}）...")
                
                # 根据时间框架调用不同的AKShare接口
                if tf == TimeFrame.ONE_MIN:
                    period = '1'
                elif tf == TimeFrame.FIVE_MIN:
                    period = '5'
                elif tf == TimeFrame.THIRTY_MIN:
                    period = '30'
                else:
                    continue
                
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
                
                # 限流
                time_module.sleep(0.2)
                
            except Exception as e:
                logger.error(f"✗ {symbol} {tf.value}f 获取失败: {e}")
                
                # 重试逻辑
                if retry_count < self.max_retries:
                    wait_time = (retry_count + 1) * 2  # 2s, 4s, 6s递增延迟
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
                    logger.error(f"{symbol} {tf.value}f 已达到最大重试次数，放弃")
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
        
        # 获取最近50条数据
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
        
        rows = list(reversed(rows))  # 时间从早到晚
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
                    'strength': (curr_high - max(prev_high, next_high)) / curr_high
                })
            
            # 底分型
            elif curr_low < prev_low and curr_low < next_low:
                fractals.append({
                    'type': '底分型',
                    'time': rows[i][0],
                    'level': curr_low,
                    'strength': (min(prev_low, next_low) - curr_low) / min(prev_low, next_low)
                })
        
        return fractals
    
    def generate_trading_signal(
        self,
        symbol: str,
        fractal_type: str,
        current_price: float,
        timeframe: TimeFrame = TimeFrame.THIRTY_MIN
    ) -> Dict:
        """
        根据分型生成交易信号
        
        Args:
            symbol: 股票代码
            fractal_type: 分型类型（'顶分型' 或 '底分型'）
            current_price: 当前价格
            timeframe: 时间框架
        """
        if fractal_type == '底分型':
            return {
                'action': 'BUY',
                'confidence': 0.75,
                'suggested_price': current_price * 0.98,  # 建议价格（略低于当前）
                'stop_loss': current_price * 0.95,        # 止损位
                'take_profit': current_price * 1.05,      # 止盈位
                'monitoring_timeframe': ['5', '1'],        # 需要用5f/1f监控
                'detail': f'底分型形成，{timeframe.value}分钟级别买卖点，建议关注'
            }
        else:  # 顶分型
            return {
                'action': 'SELL',
                'confidence': 0.75,
                'suggested_price': current_price * 1.02,  # 建议价格（略高于当前）
                'stop_loss': current_price * 1.05,        # 止损位
                'take_profit': current_price * 0.95,      # 止盈位
                'monitoring_timeframe': ['5', '1'],
                'detail': f'顶分型形成，{timeframe.value}分钟级别卖卖点，建议关注'
            }
    
    def monitor_position_realtime(self, symbol: str, entry_price: float, action: str):
        """
        实时监控持仓（5f/1f区间套）
        
        Args:
            symbol: 股票代码
            entry_price: 买入价格
            action: 操作类型 ('BUY' 或 'SELL')
        """
        logger.info(f"\n🔔 开始监控 {symbol} 的实时走势（5f/1f区间套）...")
        logger.info(f"   入场价格: {entry_price}")
        logger.info(f"   操作类型: {'买入' if action == 'BUY' else '卖出'}")
        logger.info(f"   监控信息:")
        
        if action == 'BUY':
            logger.info(f"   - 5分钟走势确认回踩支撑 → 1分钟出现底分型 → 可加仓")
            logger.info(f"   - 5分钟走势突破前期阻力 → 1分钟出现顶分型 → 可减仓/止盈")
            logger.info(f"   - 5分钟出现顶分型，1分钟破位 → 止损逃顶")
        else:
            logger.info(f"   - 5分钟走势确认突破阻力 → 1分钟出现顶分型 → 可加仓")
            logger.info(f"   - 5分钟走势回踩支撑 → 1分钟出现底分型 → 可减仓/止盈")
            logger.info(f"   - 5分钟出现底分型，1分钟破位 → 止损逃底")
    
    def fetch_all_a_stocks_multiframe(
        self,
        days: int = 5,
        batch_size: int = 50,
        timeframes: List[TimeFrame] = None
    ):
        """
        获取全部A股多时间框架历史数据（带重试）
        
        Args:
            days: 天数
            batch_size: 每批数量
            timeframes: 时间框架列表
        """
        from full_a_stock_collector import StockListManager
        
        if timeframes is None:
            timeframes = self.timeframes
        
        stock_list = StockListManager.get_a_stock_list()
        total_success = 0
        total_failed = 0
        total_bars = {tf.value: 0 for tf in timeframes}
        
        logger.info(f"开始获取 {len(stock_list)} 只A股多时间框架数据...")
        logger.info(f"时间框架: {', '.join([f'{tf.value}f' for tf in timeframes])}")
        logger.info(f"批处理: 每批 {batch_size} 只，最多重试 {self.max_retries} 次\n")
        
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"{'='*70}")
            logger.info(f"处理第 {batch_num} 批（{len(batch)}只 / {len(stock_list)}只）")
            logger.info(f"{'='*70}")
            
            batch_success = 0
            batch_failed = 0
            
            for idx, stock in enumerate(batch, 1):
                symbol = stock.symbol
                
                try:
                    bars_dict = self.fetch_stock_multiframe_akshare(
                        symbol, days, timeframes
                    )
                    
                    # 检查是否有任何数据获取成功
                    has_data = any(bars_dict.values())
                    
                    if has_data:
                        self.save_multiframe_bars(symbol, bars_dict)
                        
                        # 统计
                        for tf_str, bars in bars_dict.items():
                            total_bars[tf_str] += len(bars)
                        
                        # 检测分型
                        fractals = self.detect_fractal_patterns(symbol, TimeFrame.THIRTY_MIN)
                        if fractals:
                            logger.info(f"  [{idx}/{len(batch)}] {symbol} ✓ （发现 {len(fractals)} 个分型）")
                        else:
                            logger.info(f"  [{idx}/{len(batch)}] {symbol} ✓")
                        
                        batch_success += 1
                        total_success += 1
                    else:
                        logger.debug(f"  [{idx}/{len(batch)}] {symbol} ✗ （无数据）")
                        batch_failed += 1
                        total_failed += 1
                    
                    # 限流：每5只休息0.5秒
                    if (idx % 5 == 0):
                        time_module.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"  [{idx}/{len(batch)}] {symbol} ✗ ({e})")
                    batch_failed += 1
                    total_failed += 1
            
            # 批次摘要
            logger.info(f"本批结果: 成功 {batch_success}, 失败 {batch_failed}")
            logger.info(f"累计进度: 成功 {total_success}, 失败 {total_failed}\n")
        
        # 总结
        logger.info(f"\n{'='*70}")
        logger.info(f"✓ 全量多时间框架数据获取完成")
        logger.info(f"{'='*70}")
        logger.info(f"总股票数: {len(stock_list)}")
        logger.info(f"成功获取: {total_success}")
        logger.info(f"失败/无数据: {total_failed}")
        logger.info(f"K线总数:")
        for tf_str, count in total_bars.items():
            logger.info(f"  - {tf_str}分钟: {count}")
        logger.info(f"{'='*70}\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='多时间框架K线数据获取器')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--days', type=int, default=5, help='天数（开盘前用）')
    parser.add_argument('--symbol', type=str, help='指定股票代码')
    parser.add_argument('--mode', choices=['hot', 'all'], default='all',
                       help='采集模式')
    parser.add_argument('--timeframes', nargs='+', default=['1', '5', '30'],
                       help='时间框架列表 (1/5/30)')
    
    args = parser.parse_args()
    
    timeframes = [TimeFrame(tf) for tf in args.timeframes]
    fetcher = MultiTimeframeDataFetcher(args.db)
    
    # 打印当前交易阶段
    phase = fetcher.get_current_trade_phase()
    logger.info(f"当前交易阶段: {phase.value}")
    logger.info(f"更新策略: 开盘前获取历史数据 → 闭盘后更新 → 盘中实时监控\n")
    
    if args.symbol:
        # 单个股票
        logger.info(f"获取单只股票 {args.symbol}...")
        bars_dict = fetcher.fetch_stock_multiframe_akshare(
            args.symbol, args.days, timeframes
        )
        
        if any(bars_dict.values()):
            fetcher.save_multiframe_bars(args.symbol, bars_dict)
            
            # 检测分型
            fractals = fetcher.detect_fractal_patterns(args.symbol)
            if fractals:
                logger.info(f"检测到分型: {fractals}")
    
    elif args.mode == 'all':
        # 全量A股
        fetcher.fetch_all_a_stocks_multiframe(args.days, timeframes=timeframes)
    
    else:
        # 热门股（测试）
        hot_stocks = ['sh600519', 'sz000001', 'sz300750']
        for symbol in hot_stocks:
            logger.info(f"\n获取 {symbol}...")
            bars_dict = fetcher.fetch_stock_multiframe_akshare(
                symbol, args.days, timeframes
            )
            
            if any(bars_dict.values()):
                fetcher.save_multiframe_bars(symbol, bars_dict)
                
                # 检测分型
                fractals = fetcher.detect_fractal_patterns(symbol)
                if fractals:
                    logger.info(f"分型检测: {len(fractals)} 个")


if __name__ == '__main__':
    main()
