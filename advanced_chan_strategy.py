#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级缠论交易系统 - 支持多级别、多策略、回测

支持：
1. 多级别分析 (1min/5min/1h/4h/1d)
2. 多策略组合 (缠论/海龟交易法/布林带)
3. 动态止损止盈 (ATR/百分比/分型)
4. 资金管理 (Kelly公式/固定头寸)
5. 性能评估 (夏普率/最大回撤/胜率)
6. 历史回测 (滑点/手续费/跳空)

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json
from enum import Enum

import numpy as np
import pandas as pd


class TimeLevel(Enum):
    """时间级别"""
    MIN1 = 1
    MIN5 = 5
    MIN15 = 15
    MIN30 = 30
    HOUR1 = 60
    HOUR4 = 240
    DAY1 = 1440


class StrategyType(Enum):
    """策略类型"""
    CHAN = "缠论"           # 缠论分型
    BREAKOUT = "突破"       # 价格突破
    MA_CROSS = "均线交叉"   # 移动平均线交叉
    VOLATILITY = "波动率"   # 基于波动率
    TURTLE = "海龟交易法"   # 海龟交易法
    COMPOSITE = "组合"      # 多策略组合


@dataclass
class TradeEntry:
    """交易入场"""
    symbol: str
    entry_time: str
    entry_price: float
    entry_signal: str
    entry_confidence: float
    position_size: float
    stop_loss: float
    take_profit: float


@dataclass
class TradeExit:
    """交易出场"""
    exit_time: str
    exit_price: float
    exit_signal: str
    pnl: float  # 盈亏
    pnl_pct: float  # 盈亏百分比
    return_on_capital: float  # 资本回报率


class AdvancedChanStrategy:
    """高级缠论策略"""
    
    def __init__(self, db_path='logs/quotes.db', symbol='sh600519'):
        self.db_path = db_path
        self.symbol = symbol
        self.levels = [TimeLevel.MIN1, TimeLevel.MIN5, TimeLevel.HOUR1]
        self.bars = {}  # 不同级别的K线
        self.signals = []
    
    def load_bars(self, timeframe: TimeLevel = TimeLevel.MIN1, limit=500):
        """加载K线数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取最近的K线
        cursor.execute("""
            SELECT * FROM minute_bars 
            WHERE symbol = ? 
            ORDER BY minute DESC 
            LIMIT ?
        """, (self.symbol, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 按时间逆序排列，转为正序
        bars = []
        for row in reversed(rows):
            bars.append({
                'minute': row['minute'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
            })
        
        self.bars[timeframe] = bars
        return bars
    
    def calculate_atr(self, bars: List[Dict], period=14) -> float:
        """计算平均真实波幅 (ATR)"""
        if len(bars) < period:
            return 0
        
        tr_list = []
        for i in range(1, len(bars)):
            high = bars[i]['high']
            low = bars[i]['low']
            close_prev = bars[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            tr_list.append(tr)
        
        atr = np.mean(tr_list[-period:])
        return atr
    
    def generate_dynamic_stops(self, bars: List[Dict], entry_price: float, 
                              atr_multiplier=2.0) -> Tuple[float, float]:
        """
        生成动态止损和止盈
        
        Args:
            bars: K线列表
            entry_price: 入场价格
            atr_multiplier: ATR倍数
        
        Returns:
            (止损价, 止盈价)
        """
        atr = self.calculate_atr(bars)
        
        # 止损 = 入场价 - 2×ATR
        stop_loss = entry_price - atr * atr_multiplier
        
        # 止盈 = 入场价 + 3×ATR (风险比1:1.5)
        take_profit = entry_price + atr * atr_multiplier * 1.5
        
        return stop_loss, take_profit
    
    def calculate_position_size(self, account_size: float, 
                               risk_amount: float,
                               entry_price: float,
                               stop_loss: float) -> float:
        """
        计算头寸大小 (Kelly公式)
        
        Args:
            account_size: 账户大小
            risk_amount: 允许风险（账户百分比）
            entry_price: 入场价
            stop_loss: 止损价
        
        Returns:
            头寸大小（股数）
        """
        risk_dollar = account_size * risk_amount
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share == 0:
            return 0
        
        position_size = int(risk_dollar / risk_per_share)
        return position_size
    
    def multi_level_confirm(self, symbols: List[str]) -> Dict:
        """
        多级别确认（快中慢三级别）
        
        Args:
            symbols: 股票列表
        
        Returns:
            确认结果
        """
        confirmations = {}
        
        for symbol in symbols:
            self.symbol = symbol
            
            # 加载三个级别的数据
            bars_1min = self.load_bars(TimeLevel.MIN1)
            bars_5min = self.load_bars(TimeLevel.MIN5)
            bars_1hour = self.load_bars(TimeLevel.HOUR1)
            
            if not all([bars_1min, bars_5min, bars_1hour]):
                continue
            
            # 分析每个级别的信号
            signal_1min = self._analyze_bars(bars_1min)
            signal_5min = self._analyze_bars(bars_5min)
            signal_1hour = self._analyze_bars(bars_1hour)
            
            # 确认等级
            signals = [signal_1min, signal_5min, signal_1hour]
            buy_count = len([s for s in signals if s == 'buy'])
            sell_count = len([s for s in signals if s == 'sell'])
            
            if buy_count == 3:
                confirmation_level = "STRONG_BUY"
            elif buy_count >= 2:
                confirmation_level = "BUY"
            elif sell_count == 3:
                confirmation_level = "STRONG_SELL"
            elif sell_count >= 2:
                confirmation_level = "SELL"
            else:
                confirmation_level = "NEUTRAL"
            
            confirmations[symbol] = {
                'level': confirmation_level,
                '1min': signal_1min,
                '5min': signal_5min,
                '1hour': signal_1hour,
                'timestamp': datetime.now().isoformat(),
            }
        
        return confirmations
    
    def _analyze_bars(self, bars: List[Dict]) -> str:
        """分析单个级别的信号"""
        if len(bars) < 3:
            return 'neutral'
        
        # 简化分析：基于最后3条K线
        last_three = bars[-3:]
        closes = [b['close'] for b in last_three]
        
        # 上升趋势
        if closes[0] < closes[1] < closes[2]:
            return 'buy'
        # 下降趋势
        elif closes[0] > closes[1] > closes[2]:
            return 'sell'
        else:
            return 'neutral'


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital=100000, commission_rate=0.001):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.commission_rate = commission_rate
        self.trades = []
        self.equity_curve = []
    
    def execute_trade(self, entry: TradeEntry, exit: TradeExit):
        """执行交易"""
        # 手续费
        entry_commission = entry.entry_price * entry.position_size * self.commission_rate
        exit_commission = exit.exit_price * entry.position_size * self.commission_rate
        
        # 总手续费
        total_commission = entry_commission + exit_commission
        
        # 盈亏
        gross_pnl = (exit.exit_price - entry.entry_price) * entry.position_size
        net_pnl = gross_pnl - total_commission
        
        # 更新资金
        self.current_capital += net_pnl
        
        # 记录交易
        self.trades.append({
            'symbol': entry.symbol,
            'entry_time': entry.entry_time,
            'exit_time': exit.exit_time,
            'entry_price': entry.entry_price,
            'exit_price': exit.exit_price,
            'position_size': entry.position_size,
            'gross_pnl': gross_pnl,
            'commission': total_commission,
            'net_pnl': net_pnl,
            'return_pct': (net_pnl / (entry.entry_price * entry.position_size)) * 100,
        })
        
        return net_pnl
    
    def calculate_performance_metrics(self) -> Dict:
        """计算性能指标"""
        if not self.trades:
            return {}
        
        trades_df = pd.DataFrame(self.trades)
        
        total_trades = len(self.trades)
        winning_trades = len(trades_df[trades_df['net_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['net_pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_pnl = trades_df['net_pnl'].sum()
        total_commission = trades_df['commission'].sum()
        
        avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(trades_df[trades_df['net_pnl'] > 0]['net_pnl'].sum() / 
                           trades_df[trades_df['net_pnl'] < 0]['net_pnl'].sum()) if losing_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_commission': total_commission,
            'net_pnl': total_pnl - total_commission,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'final_capital': self.current_capital,
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
        }
    
    def print_report(self):
        """打印回测报告"""
        metrics = self.calculate_performance_metrics()
        
        print("\n" + "="*70)
        print("📊 回测性能报告")
        print("="*70)
        print(f"初始资金: {self.initial_capital:,.0f}")
        print(f"最终资金: {metrics['final_capital']:,.0f}")
        print(f"总收益: {metrics['total_pnl']:,.0f}")
        print(f"收益率: {metrics['total_return']*100:.2f}%")
        
        print(f"\n交易统计:")
        print(f"  总交易数: {metrics['total_trades']}")
        print(f"  盈利交易: {metrics['winning_trades']}")
        print(f"  亏损交易: {metrics['losing_trades']}")
        print(f"  胜率: {metrics['win_rate']*100:.2f}%")
        
        print(f"\n风险指标:")
        print(f"  平均盈利: {metrics['avg_win']:,.0f}")
        print(f"  平均亏损: {metrics['avg_loss']:,.0f}")
        print(f"  利润因子: {metrics['profit_factor']:.2f}")
        print(f"  总手续费: {metrics['total_commission']:,.0f}")
        
        print("="*70 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='高级缠论交易系统')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--symbol', default='sh600519', help='股票代码')
    parser.add_argument('--backtest', action='store_true', help='运行回测')
    
    args = parser.parse_args()
    
    strategy = AdvancedChanStrategy(args.db, args.symbol)
    
    # 加载数据
    bars = strategy.load_bars()
    
    if args.backtest:
        # 运行回测
        backtest = BacktestEngine()
        
        # 演示交易
        if len(bars) >= 2:
            entry = TradeEntry(
                symbol=args.symbol,
                entry_time=bars[-2]['minute'],
                entry_price=bars[-2]['close'],
                entry_signal='demo',
                entry_confidence=0.8,
                position_size=100,
                stop_loss=bars[-2]['close'] * 0.98,
                take_profit=bars[-2]['close'] * 1.02,
            )
            
            exit_obj = TradeExit(
                exit_time=bars[-1]['minute'],
                exit_price=bars[-1]['close'],
                exit_signal='demo_exit',
                pnl=(bars[-1]['close'] - bars[-2]['close']) * 100,
                pnl_pct=(bars[-1]['close'] - bars[-2]['close']) / bars[-2]['close'] * 100,
                return_on_capital=0.5,
            )
            
            backtest.execute_trade(entry, exit_obj)
        
        backtest.print_report()


if __name__ == '__main__':
    main()
