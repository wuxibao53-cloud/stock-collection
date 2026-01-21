#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时监控系统 - 5f/1f吃肉逻辑

功能：
1. 5f监控：每3-5分钟更新候选股
2. 1f监控：每1分钟更新入场股（高频）
3. 信号触发：检测到买卖点立即通知
4. 队列管理：候选股→入场股的状态转换
"""

import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Set
from threading import Thread, Event
import json

from chan_theory_engine import ChanTheoryEngine, SignalType
from email_notifier import EmailNotifier

logger = logging.getLogger(__name__)


class RealtimeMonitor:
    """实时监控器"""
    
    def __init__(self, 
                 db_path: str = 'logs/quotes.db',
                 email_notifier: EmailNotifier = None):
        self.db_path = db_path
        self.engine = ChanTheoryEngine(db_path)
        self.email_notifier = email_notifier
        
        # 状态管理
        self.watchlist_5f: Set[str] = set()  # 5f监控列表（候选股）
        self.watchlist_1f: Set[str] = set()  # 1f监控列表（入场股）
        self.sent_signals: Set[str] = set()  # 已发送的信号（去重）
        
        # 停止信号
        self.stop_event = Event()
    
    def load_watchlist_from_file(self, filepath: str = 'logs/watchlist.txt') -> List[str]:
        """从文件加载候选股清单"""
        try:
            with open(filepath, 'r') as f:
                stocks = [line.strip() for line in f if line.strip()]
            logger.info(f"✓ 从{filepath}加载{len(stocks)}只候选股")
            return stocks
        except FileNotFoundError:
            logger.warning(f"候选股文件不存在: {filepath}")
            return []
    
    def is_trading_time(self) -> bool:
        """判断是否在交易时间"""
        now = datetime.now()
        
        # 周末不交易
        if now.weekday() >= 5:
            return False
        
        # 交易时段：09:30-11:30, 13:00-15:00
        current_time = now.time()
        morning_start = datetime.strptime('09:30', '%H:%M').time()
        morning_end = datetime.strptime('11:30', '%H:%M').time()
        afternoon_start = datetime.strptime('13:00', '%H:%M').time()
        afternoon_end = datetime.strptime('15:00', '%H:%M').time()
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def fetch_latest_kline(self, symbol: str, timeframe: str) -> Dict:
        """获取最新一根K线（实际部署时调用API）"""
        # 这里应该调用实时API，暂时从数据库读取
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        table_name = f"minute_bars_{timeframe}f"
        cursor.execute(f"""
            SELECT minute, open, high, low, close, volume
            FROM {table_name}
            WHERE symbol = ?
            ORDER BY minute DESC
            LIMIT 1
        """, (symbol,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'time': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
            }
        return None
    
    def monitor_5f(self, interval: int = 300):
        """
        5f监控线程（每5分钟）
        
        Args:
            interval: 更新间隔（秒）
        """
        logger.info("🟢 启动5f监控线程")
        
        while not self.stop_event.is_set():
            # 非交易时间休眠
            if not self.is_trading_time():
                logger.debug("非交易时间，5f监控暂停")
                time.sleep(60)
                continue
            
            logger.info(f"━━━ 5f监控 ({datetime.now().strftime('%H:%M:%S')}) ━━━")
            
            for symbol in list(self.watchlist_5f):
                try:
                    # 分析5f
                    result = self.engine.analyze(symbol, timeframe='5')
                    
                    if result.get('signals'):
                        for sig in result['signals']:
                            sig_key = f"{symbol}_{sig.signal_type.value}_{sig.time}"
                            
                            # 去重
                            if sig_key in self.sent_signals:
                                continue
                            
                            logger.info(f"🔔 检测到信号: {symbol} {sig.signal_type.value} @ {sig.price:.2f}")
                            
                            # 买入信号 → 加入1f监控
                            if 'buy' in sig.signal_type.value:
                                self.watchlist_1f.add(symbol)
                                logger.info(f"  → 加入1f高频监控")
                            
                            # 发送邮件
                            if self.email_notifier:
                                signal_dict = {
                                    'signal_type': sig.signal_type.value,
                                    'price': sig.price,
                                    'reason': sig.reason,
                                    'suggested_entry': sig.suggested_entry,
                                    'stop_loss': sig.stop_loss,
                                    'take_profit': sig.take_profit,
                                    'confidence': sig.confidence
                                }
                                
                                # TODO: 生成K线图
                                # chart_path = self.email_notifier.generate_kline_chart(...)
                                
                                self.email_notifier.send_signal_email(symbol, signal_dict)
                            
                            self.sent_signals.add(sig_key)
                    
                except Exception as e:
                    logger.error(f"5f监控失败 {symbol}: {e}")
            
            # 等待下一个周期
            self.stop_event.wait(interval)
        
        logger.info("🔴 5f监控线程已停止")
    
    def monitor_1f(self, interval: int = 60):
        """
        1f监控线程（每1分钟）- 高频吃肉
        
        Args:
            interval: 更新间隔（秒）
        """
        logger.info("🟢 启动1f监控线程")
        
        while not self.stop_event.is_set():
            # 非交易时间休眠
            if not self.is_trading_time():
                logger.debug("非交易时间，1f监控暂停")
                time.sleep(60)
                continue
            
            if not self.watchlist_1f:
                logger.debug("1f监控列表为空，等待...")
                time.sleep(interval)
                continue
            
            logger.info(f"━━━ 1f监控 ({datetime.now().strftime('%H:%M:%S')}) | {len(self.watchlist_1f)}只 ━━━")
            
            for symbol in list(self.watchlist_1f):
                try:
                    # 分析1f
                    result = self.engine.analyze(symbol, timeframe='1')
                    
                    if result.get('signals'):
                        for sig in result['signals']:
                            sig_key = f"{symbol}_{sig.signal_type.value}_{sig.time}"
                            
                            if sig_key in self.sent_signals:
                                continue
                            
                            logger.info(f"🔥 【1f精准】{symbol} {sig.signal_type.value} @ {sig.price:.2f}")
                            logger.info(f"   理由: {sig.reason}")
                            logger.info(f"   入场: {sig.suggested_entry:.2f} 止损: {sig.stop_loss:.2f}")
                            
                            # 卖出信号 → 移出1f监控
                            if 'sell' in sig.signal_type.value:
                                self.watchlist_1f.discard(symbol)
                                logger.info(f"  → 移出1f监控（已卖出）")
                            
                            # 发送邮件
                            if self.email_notifier:
                                signal_dict = {
                                    'signal_type': sig.signal_type.value,
                                    'price': sig.price,
                                    'reason': sig.reason,
                                    'suggested_entry': sig.suggested_entry,
                                    'stop_loss': sig.stop_loss,
                                    'take_profit': sig.take_profit,
                                    'confidence': sig.confidence
                                }
                                self.email_notifier.send_signal_email(symbol, signal_dict)
                            
                            self.sent_signals.add(sig_key)
                    
                except Exception as e:
                    logger.error(f"1f监控失败 {symbol}: {e}")
            
            # 等待下一个周期
            self.stop_event.wait(interval)
        
        logger.info("🔴 1f监控线程已停止")
    
    def start(self, watchlist_file: str = 'logs/watchlist.txt'):
        """启动监控系统"""
        # 加载候选股
        stocks = self.load_watchlist_from_file(watchlist_file)
        self.watchlist_5f = set(stocks)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"实时监控系统启动")
        logger.info(f"  5f监控: {len(self.watchlist_5f)} 只候选股")
        logger.info(f"  1f监控: {len(self.watchlist_1f)} 只入场股")
        logger.info(f"{'='*70}\n")
        
        # 启动5f线程
        thread_5f = Thread(target=self.monitor_5f, args=(300,), daemon=True)
        thread_5f.start()
        
        # 启动1f线程
        thread_1f = Thread(target=self.monitor_1f, args=(60,), daemon=True)
        thread_1f.start()
        
        try:
            # 保持主线程运行
            while True:
                time.sleep(10)
                
                # 显示状态
                if datetime.now().second % 30 == 0:
                    logger.info(f"状态: 5f={len(self.watchlist_5f)}只 | 1f={len(self.watchlist_1f)}只 | 信号={len(self.sent_signals)}个")
        
        except KeyboardInterrupt:
            logger.info("\n接收到停止信号...")
            self.stop_event.set()
            thread_5f.join(timeout=5)
            thread_1f.join(timeout=5)
            logger.info("✓ 监控系统已停止")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s'
    )
    
    # 创建邮件通知器（需要配置）
    # notifier = EmailNotifier(
    #     smtp_server='smtp.163.com',
    #     from_email='your-email@163.com',
    #     password='your-password',
    #     to_emails=['receiver@example.com']
    # )
    
    # 创建监控器
    monitor = RealtimeMonitor(
        db_path='logs/quotes.db',
        email_notifier=None  # 配置后传入notifier
    )
    
    # 启动
    monitor.start()
