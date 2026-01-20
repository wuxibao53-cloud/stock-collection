#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论交易系统回测框架

功能：
- 历史数据回测
- 信号准确率验证
- 风险收益分析
- 参数优化

使用：
    python3 backtest_system.py --db logs/quotes.db --symbol sh600000
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math
import logging

from chan_theory_3point_signals import ChanTheory3PointSignalGenerator, TradingSignal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Position:
    """交易头寸"""
    entry_price: float
    entry_time: str
    entry_signal: TradingSignal
    quantity: int = 100  # 默认100股
    stop_loss: float = 0
    take_profit: float = 0
    max_price: float = 0  # 最高价
    min_price: float = 0  # 最低价
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_signal: Optional[TradingSignal] = None
    status: str = "open"  # open/closed
    
    @property
    def pnl(self) -> float:
        """盈亏"""
        if not self.exit_price:
            return 0
        return (self.exit_price - self.entry_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """盈亏百分比"""
        if self.entry_price == 0:
            return 0
        if not self.exit_price:
            return 0
        return (self.exit_price - self.entry_price) / self.entry_price


class RiskManager:
    """风险管理系统"""
    
    def __init__(self, initial_capital: float = 100000, max_loss_per_trade: float = 0.02,
                 max_position_size: float = 0.1, stop_loss_pct: float = 0.03):
        """
        初始化风险管理器
        
        Args:
            initial_capital: 初始资金
            max_loss_per_trade: 单笔最大亏损比例
            max_position_size: 单笔最大仓位比例
            stop_loss_pct: 止损百分比
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_loss_per_trade = max_loss_per_trade
        self.max_position_size = max_position_size
        self.stop_loss_pct = stop_loss_pct
        
        self.positions: List[Position] = []
        self.trades_history = []
    
    def calculate_position_size(self, entry_price: float, stop_loss: float) -> int:
        """
        根据风险管理规则计算头寸大小
        
        Args:
            entry_price: 入场价
            stop_loss: 止损价
        
        Returns:
            头寸数量
        """
        # 单笔风险金额 = 初始资金 * 最大亏损比例
        risk_amount = self.initial_capital * self.max_loss_per_trade
        
        # 单位风险 = 入场价 - 止损价
        per_unit_risk = abs(entry_price - stop_loss)
        
        if per_unit_risk == 0:
            return 0
        
        # 头寸数 = 风险金额 / 单位风险
        position_size = int(risk_amount / per_unit_risk)
        
        # 检查最大仓位限制
        max_capital_per_trade = self.current_capital * self.max_position_size
        max_position = int(max_capital_per_trade / entry_price)
        
        return min(position_size, max_position)
    
    def open_position(self, signal: TradingSignal, current_price: float) -> Optional[Position]:
        """打开头寸"""
        if signal.signal_type != "buy":
            return None
        
        # 计算止损
        stop_loss = current_price * (1 - self.stop_loss_pct)
        take_profit = current_price * (1 + self.stop_loss_pct * 2)  # 盈亏比2:1
        
        # 计算头寸大小
        quantity = self.calculate_position_size(current_price, stop_loss)
        
        if quantity <= 0:
            logger.warning(f"头寸过小，跳过交易: {signal.symbol}")
            return None
        
        position = Position(
            entry_price=current_price,
            entry_time=signal.minute,
            entry_signal=signal,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_price=current_price,
            min_price=current_price,
        )
        
        self.positions.append(position)
        return position
    
    def close_position(self, position: Position, exit_price: float, 
                      exit_time: str, exit_signal: Optional[TradingSignal] = None):
        """平仓"""
        position.exit_price = exit_price
        position.exit_time = exit_time
        position.exit_signal = exit_signal
        position.status = "closed"
        
        # 更新资金
        self.current_capital += position.pnl
        
        # 记录交易
        self.trades_history.append({
            'entry_time': position.entry_time,
            'exit_time': exit_time,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'pnl': position.pnl,
            'pnl_pct': position.pnl_pct,
            'quantity': position.quantity,
        })
    
    def update_position(self, position: Position, current_price: float, current_time: str):
        """更新头寸状态"""
        position.max_price = max(position.max_price, current_price)
        position.min_price = min(position.min_price, current_price)
        
        # 检查止损
        if current_price <= position.stop_loss:
            return "stop_loss"
        
        # 检查止盈
        if current_price >= position.take_profit:
            return "take_profit"
        
        return None
    
    def get_statistics(self) -> Dict:
        """获取回测统计"""
        if not self.trades_history:
            return {'trades': 0, 'winning_rate': 0}
        
        wins = sum(1 for t in self.trades_history if t['pnl'] > 0)
        losses = sum(1 for t in self.trades_history if t['pnl'] < 0)
        total_trades = len(self.trades_history)
        
        total_pnl = sum(t['pnl'] for t in self.trades_history)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # 计算夏普比
        if total_trades > 1:
            pnl_list = [t['pnl_pct'] for t in self.trades_history]
            variance = sum((x - avg_pnl) ** 2 for x in pnl_list) / len(pnl_list)
            std_dev = math.sqrt(variance) if variance > 0 else 0.001
            sharpe_ratio = (sum(pnl_list) / len(pnl_list)) / std_dev if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': wins,
            'losing_trades': losses,
            'winning_rate': wins / total_trades if total_trades > 0 else 0,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl / self.initial_capital,
            'avg_pnl': avg_pnl,
            'avg_pnl_pct': avg_pnl / self.initial_capital if self.initial_capital > 0 else 0,
            'final_capital': self.current_capital,
            'sharpe_ratio': sharpe_ratio,
        }


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, db_path: str, initial_capital: float = 100000):
        self.db_path = db_path
        self.signal_generator = ChanTheory3PointSignalGenerator()
        self.risk_manager = RiskManager(initial_capital=initial_capital)
    
    def load_bars(self, symbol: str) -> List[Dict]:
        """加载历史K线"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM minute_bars WHERE symbol = ? ORDER BY minute ASC", (symbol,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"加载{symbol}数据失败: {e}")
            return []
    
    def backtest_symbol(self, symbol: str) -> Dict:
        """回测单个股票"""
        bars = self.load_bars(symbol)
        
        if len(bars) < 10:
            logger.warning(f"{symbol}: 数据不足")
            return {'symbol': symbol, 'status': 'insufficient_data'}
        
        logger.info(f"开始回测 {symbol} ({len(bars)} bars)")
        
        # 生成所有信号
        all_signals = self.signal_generator.analyze_bars(bars, symbol)
        
        buy_signals = [s for s in all_signals if s.signal_type == 'buy']
        sell_signals = [s for s in all_signals if s.signal_type == 'sell']
        
        # 简单的交易逻辑：买信号入场，卖信号出场
        for signal in all_signals:
            if signal.signal_type == 'buy':
                # 找到信号对应的K线价格
                signal_bar = None
                for bar in bars:
                    if bar['minute'] == signal.minute:
                        signal_bar = bar
                        break
                
                if signal_bar:
                    position = self.risk_manager.open_position(signal, signal_bar['close'])
                    if position:
                        logger.info(f"  买入: {signal.minute} @ {signal_bar['close']:.2f}")
            
            elif signal.signal_type == 'sell':
                # 平仓所有持仓
                open_positions = [p for p in self.risk_manager.positions if p.status == 'open']
                for position in open_positions:
                    signal_bar = None
                    for bar in bars:
                        if bar['minute'] == signal.minute:
                            signal_bar = bar
                            break
                    
                    if signal_bar:
                        self.risk_manager.close_position(position, signal_bar['close'], signal.minute, signal)
                        logger.info(f"  卖出: {signal.minute} @ {signal_bar['close']:.2f} 盈亏: {position.pnl:.0f}")
        
        # 平仓所有剩余头寸
        for position in self.risk_manager.positions:
            if position.status == 'open':
                last_bar = bars[-1]
                self.risk_manager.close_position(position, last_bar['close'], last_bar['minute'])
        
        # 获取统计
        stats = self.risk_manager.get_statistics()
        
        return {
            'symbol': symbol,
            'bars': len(bars),
            'signals_total': len(all_signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'trades': stats['total_trades'],
            'winning_rate': stats['winning_rate'],
            'total_pnl': stats['total_pnl'],
            'total_pnl_pct': stats['total_pnl_pct'],
            'sharpe_ratio': stats['sharpe_ratio'],
            'final_capital': stats['final_capital'],
        }
    
    def generate_report(self) -> str:
        """生成回测报告"""
        stats = self.risk_manager.get_statistics()
        
        report = f"""
{'='*80}
缠论交易系统回测报告
{'='*80}

📊 总体统计
{'─'*80}
总交易数: {stats['total_trades']}
胜交易数: {stats['winning_trades']}
败交易数: {stats['losing_trades']}
胜率: {stats['winning_rate']:.2%}

💰 盈亏统计
{'─'*80}
初始资金: ¥{self.risk_manager.initial_capital:,.0f}
最终资金: ¥{stats['final_capital']:,.0f}
总盈亏: ¥{stats['total_pnl']:,.0f}
总收益率: {stats['total_pnl_pct']:.2%}
平均单笔: ¥{stats['avg_pnl']:,.0f}

📈 风险指标
{'─'*80}
夏普比例: {stats['sharpe_ratio']:.2f}
最大单笔盈利: ¥{max([t['pnl'] for t in self.risk_manager.trades_history]) if self.risk_manager.trades_history else 0:,.0f}
最大单笔亏损: ¥{min([t['pnl'] for t in self.risk_manager.trades_history]) if self.risk_manager.trades_history else 0:,.0f}

📝 交易记录（最近10笔）
{'─'*80}
"""
        
        for i, trade in enumerate(self.risk_manager.trades_history[-10:], 1):
            side = "买→卖" if trade['pnl'] >= 0 else "买→卖"
            report += f"{i:2}. {trade['entry_time']} → {trade['exit_time']} | {trade['entry_price']:.2f} → {trade['exit_price']:.2f} | 盈亏: ¥{trade['pnl']:,.0f} ({trade['pnl_pct']:.2%})\n"
        
        report += f"\n{'='*80}\n"
        
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论交易系统回测框架')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--symbol', help='股票代码')
    parser.add_argument('--capital', type=float, default=100000, help='初始资金')
    
    args = parser.parse_args()
    
    engine = BacktestEngine(args.db, initial_capital=args.capital)
    
    if args.symbol:
        result = engine.backtest_symbol(args.symbol)
        print("\n" + "="*80)
        print(f"🎯 {args.symbol} 回测结果")
        print("="*80)
        for key, value in result.items():
            if isinstance(value, float):
                if 'pct' in key:
                    print(f"{key:20}: {value:.2%}")
                elif 'rate' in key:
                    print(f"{key:20}: {value:.2%}")
                else:
                    print(f"{key:20}: {value:.2f}")
            else:
                print(f"{key:20}: {value}")
    
    report = engine.generate_report()
    print(report)


if __name__ == '__main__':
    main()
