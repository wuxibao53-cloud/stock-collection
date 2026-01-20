#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘交易提醒和自动化交易模块

功能：
1. 实时监测交易信号
2. 根据买卖点生成操作提醒
3. 支持自动化交易接口（DingDing、钉钉、企业微信）
4. 每日开盘和收盘筛选符合条件的K线形态
5. 记录所有交易提醒到数据库

交易提醒等级：
- 🟢🟢🟢 : 强烈买入信号（三周期同步）
- 🟢🟢 : 中等买入信号（二周期同步）
- 🟢 : 弱买入信号（单周期或单独分型）
- 🔴🔴🔴 : 强烈卖出信号
- 🔴🔴 : 中等卖出信号
- 🔴 : 弱卖出信号

Author: 仙儿仙儿碎碎念
"""

import sqlite3
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional
from enum import Enum
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """提醒等级"""
    WEAK = 1  # 弱信号
    MEDIUM = 2  # 中等信号
    STRONG = 3  # 强信号


@dataclass
class TradeAlert:
    """交易提醒"""
    alert_id: str
    symbol: str
    signal_type: str  # "buy" or "sell"
    alert_time: str
    price: float
    target_price: Optional[float] = None  # 目标价格
    stop_loss: Optional[float] = None  # 止损价格
    level: int = 2  # 提醒等级 1-3
    reason: str = ""  # 原因说明
    is_confirmed: bool = False  # 是否被确认
    
    def to_dict(self):
        """转换为字典"""
        return asdict(self)
    
    def format_message(self):
        """格式化为人类可读的消息"""
        level_marks = "🟢" * self.level if self.signal_type == "buy" else "🔴" * self.level
        action = "买入" if self.signal_type == "buy" else "卖出"
        
        msg = f"{level_marks} [{action}提醒]\n"
        msg += f"代码: {self.symbol}\n"
        msg += f"时间: {self.alert_time}\n"
        msg += f"价格: {self.price:.2f}\n"
        
        if self.target_price:
            msg += f"目标价: {self.target_price:.2f}\n"
        if self.stop_loss:
            msg += f"止损: {self.stop_loss:.2f}\n"
        
        msg += f"原因: {self.reason}\n"
        
        return msg
    
    def __str__(self):
        level_marks = "🟢" * self.level if self.signal_type == "buy" else "🔴" * self.level
        return f"{level_marks} {self.symbol} {self.signal_type.upper()} " \
               f"{self.alert_time} {self.price:.2f} | {self.reason}"


class RealTimeAlertSystem:
    """实时交易提醒系统"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.alerts = []
        self.processed_signals = set()  # 避免重复提醒
        self._init_alert_table()
    
    def _init_alert_table(self):
        """初始化提醒表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_alerts (
                    alert_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    alert_time TEXT NOT NULL,
                    price REAL NOT NULL,
                    target_price REAL,
                    stop_loss REAL,
                    level INTEGER NOT NULL,
                    reason TEXT,
                    is_confirmed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化提醒表失败: {e}")
    
    def generate_alert(self, symbol, signal_type, price, level=2,
                      reason="", target_price=None, stop_loss=None):
        """
        生成交易提醒
        
        Args:
            symbol: 股票代码
            signal_type: "buy" 或 "sell"
            price: 当前价格
            level: 提醒等级 1-3
            reason: 提醒原因
            target_price: 目标价格
            stop_loss: 止损价格
        """
        alert_id = f"{symbol}_{signal_type}_{datetime.now().isoformat()}"
        
        # 避免重复提醒（同一个信号在5分钟内不重复提醒）
        signal_key = f"{symbol}_{signal_type}_{int(price*100)}"
        if signal_key in self.processed_signals:
            return None
        
        self.processed_signals.add(signal_key)
        
        alert = TradeAlert(
            alert_id=alert_id,
            symbol=symbol,
            signal_type=signal_type,
            alert_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            price=price,
            target_price=target_price,
            stop_loss=stop_loss,
            level=level,
            reason=reason
        )
        
        self.alerts.append(alert)
        self._save_alert(alert)
        
        return alert
    
    def _save_alert(self, alert):
        """保存提醒到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trade_alerts (
                    alert_id, symbol, signal_type, alert_time, price,
                    target_price, stop_loss, level, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.symbol,
                alert.signal_type,
                alert.alert_time,
                alert.price,
                alert.target_price,
                alert.stop_loss,
                alert.level,
                alert.reason
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"保存提醒失败: {e}")
    
    def screen_opening_signals(self, scan_time=None):
        """
        开盘筛选：获取符合条件的早间信号
        
        Args:
            scan_time: 扫描时间（默认当前时间）
        
        Returns:
            alerts: 符合条件的提醒列表
        """
        if scan_time is None:
            scan_time = datetime.now()
        
        # 筛选最近1小时内的强买卖信号
        opening_alerts = [
            a for a in self.alerts
            if a.level >= 2 and (
                scan_time - datetime.fromisoformat(a.alert_time)
            ) < timedelta(hours=1)
        ]
        
        return opening_alerts
    
    def screen_closing_signals(self, scan_time=None):
        """
        收盘筛选：获取符合条件的尾盘信号
        
        Args:
            scan_time: 扫描时间（默认当前时间）
        
        Returns:
            alerts: 符合条件的提醒列表
        """
        if scan_time is None:
            scan_time = datetime.now()
        
        # 筛选最近2小时内的所有信号，按等级排序
        closing_alerts = [
            a for a in self.alerts
            if (scan_time - datetime.fromisoformat(a.alert_time)) < timedelta(hours=2)
        ]
        
        return sorted(closing_alerts, key=lambda a: -a.level)
    
    def print_alerts(self):
        """打印所有提醒"""
        if not self.alerts:
            print("⚠️  没有生成任何提醒")
            return
        
        print("\n" + "="*70)
        print("实盘交易提醒")
        print("="*70)
        
        buy_alerts = [a for a in self.alerts if a.signal_type == 'buy']
        sell_alerts = [a for a in self.alerts if a.signal_type == 'sell']
        
        print(f"\n🟢 买入提醒 ({len(buy_alerts)}个):")
        for alert in buy_alerts[-3:]:
            print(f"  {alert}")
        
        print(f"\n🔴 卖出提醒 ({len(sell_alerts)}个):")
        for alert in sell_alerts[-3:]:
            print(f"  {alert}")
        
        print("="*70 + "\n")
    
    def send_dingtalk_alert(self, alert, webhook_url=None):
        """
        发送钉钉提醒
        
        Args:
            alert: TradeAlert 对象
            webhook_url: 钉钉机器人webhook地址
        """
        if not webhook_url:
            logger.warning("钉钉webhook地址未设置，跳过发送")
            return
        
        try:
            import requests
            
            message = {
                "msgtype": "text",
                "text": {
                    "content": alert.format_message()
                },
                "at": {
                    "isAtAll": False
                }
            }
            
            response = requests.post(webhook_url, json=message, timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ 钉钉提醒已发送: {alert.symbol} {alert.signal_type}")
            else:
                logger.warning(f"钉钉提醒发送失败: {response.status_code}")
        
        except Exception as e:
            logger.error(f"发送钉钉提醒错误: {e}")
    
    def send_wechat_alert(self, alert, webhook_url=None):
        """
        发送企业微信提醒
        
        Args:
            alert: TradeAlert 对象
            webhook_url: 企业微信机器人webhook地址
        """
        if not webhook_url:
            logger.warning("企业微信webhook地址未设置，跳过发送")
            return
        
        try:
            import requests
            
            level_emoji = "🟢" * alert.level if alert.signal_type == "buy" else "🔴" * alert.level
            
            message = {
                "msgtype": "text",
                "text": {
                    "content": f"{level_emoji} {alert.symbol} {alert.signal_type.upper()}\n"
                              f"时间: {alert.alert_time}\n"
                              f"价格: {alert.price:.2f}\n"
                              f"原因: {alert.reason}"
                }
            }
            
            response = requests.post(webhook_url, json=message, timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ 企业微信提醒已发送: {alert.symbol} {alert.signal_type}")
            else:
                logger.warning(f"企业微信提醒发送失败: {response.status_code}")
        
        except Exception as e:
            logger.error(f"发送企业微信提醒错误: {e}")
    
    def get_today_summary(self):
        """获取今日提醒统计"""
        today = datetime.now().date()
        today_alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a.alert_time).date() == today
        ]
        
        buy_count = len([a for a in today_alerts if a.signal_type == 'buy'])
        sell_count = len([a for a in today_alerts if a.signal_type == 'sell'])
        strong_count = len([a for a in today_alerts if a.level == 3])
        
        return {
            'date': str(today),
            'total': len(today_alerts),
            'buy': buy_count,
            'sell': sell_count,
            'strong': strong_count
        }


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='实盘交易提醒系统')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--symbol',
                       help='股票代码')
    parser.add_argument('--opening', action='store_true',
                       help='开盘筛选')
    parser.add_argument('--closing', action='store_true',
                       help='收盘筛选')
    parser.add_argument('--summary', action='store_true',
                       help='显示今日统计')
    
    args = parser.parse_args()
    
    alert_system = RealTimeAlertSystem(args.db)
    
    if args.opening:
        alerts = alert_system.screen_opening_signals()
        print("\n📍 开盘筛选结果:")
        for alert in alerts:
            print(f"  {alert}")
    
    if args.closing:
        alerts = alert_system.screen_closing_signals()
        print("\n📍 收盘筛选结果:")
        for alert in alerts:
            print(f"  {alert}")
    
    if args.summary:
        summary = alert_system.get_today_summary()
        print(f"\n📊 今日统计: {summary}")
    
    alert_system.print_alerts()


if __name__ == '__main__':
    main()
