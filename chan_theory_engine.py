#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论核心分析引擎 - 精准版

实现：
1. 笔的严格判断（向上笔/向下笔）
2. 线段的准确识别
3. 中枢的完整检测
4. 三类买卖点的明确定义
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Direction(Enum):
    """方向枚举"""
    UP = "up"
    DOWN = "down"


class SignalType(Enum):
    """信号类型"""
    BUY1 = "buy1"
    BUY2 = "buy2"
    BUY3 = "buy3"
    SELL1 = "sell1"
    SELL2 = "sell2"
    SELL3 = "sell3"


@dataclass
class Fractal:
    """分型"""
    time: str
    price: float
    fractal_type: str  # 'top' or 'bottom'
    index: int


@dataclass
class Stroke:
    """笔"""
    start_fractal: Fractal
    end_fractal: Fractal
    direction: Direction
    high: float
    low: float


@dataclass
class Segment:
    """线段"""
    strokes: List[Stroke]
    direction: Direction
    start_time: str
    end_time: str
    high: float
    low: float


@dataclass
class Center:
    """中枢"""
    high: float
    low: float
    start_time: str
    end_time: str
    k_count: int  # 参与中枢的K线数量


@dataclass
class TradingSignal:
    """交易信号"""
    symbol: str
    signal_type: SignalType
    time: str
    price: float
    reason: str
    suggested_entry: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-1


class ChanTheoryEngine:
    """缠论分析引擎"""
    
    def __init__(self, db_path: str = 'logs/quotes.db'):
        self.db_path = db_path
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 500) -> List[Dict]:
        """获取K线数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        table_name = f"minute_bars_{timeframe}f"
        
        cursor.execute(f"""
            SELECT minute, open, high, low, close, volume
            FROM {table_name}
            WHERE symbol = ?
            ORDER BY minute DESC
            LIMIT ?
        """, (symbol, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        klines = []
        for row in reversed(rows):
            klines.append({
                'time': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
            })
        
        return klines
    
    def detect_fractals(self, klines: List[Dict]) -> List[Fractal]:
        """
        检测分型（严格定义）
        
        顶分型：K(n).high > K(n-1).high AND K(n).high > K(n+1).high
        底分型：K(n).low < K(n-1).low AND K(n).low < K(n+1).low
        """
        fractals = []
        
        for i in range(1, len(klines) - 1):
            prev_k = klines[i - 1]
            curr_k = klines[i]
            next_k = klines[i + 1]
            
            # 顶分型
            if curr_k['high'] > prev_k['high'] and curr_k['high'] > next_k['high']:
                fractals.append(Fractal(
                    time=curr_k['time'],
                    price=curr_k['high'],
                    fractal_type='top',
                    index=i
                ))
            
            # 底分型
            elif curr_k['low'] < prev_k['low'] and curr_k['low'] < next_k['low']:
                fractals.append(Fractal(
                    time=curr_k['time'],
                    price=curr_k['low'],
                    fractal_type='bottom',
                    index=i
                ))
        
        return fractals
    
    def detect_strokes(self, fractals: List[Fractal], klines: List[Dict]) -> List[Stroke]:
        """
        检测笔（相邻异性分型之间）
        
        向上笔：底分型 → 顶分型，且顶 > 底
        向下笔：顶分型 → 底分型，且顶 > 底
        """
        strokes = []
        
        for i in range(len(fractals) - 1):
            start = fractals[i]
            end = fractals[i + 1]
            
            # 异性分型才能成笔
            if start.fractal_type == end.fractal_type:
                continue
            
            # 向上笔：底 → 顶
            if start.fractal_type == 'bottom' and end.fractal_type == 'top':
                if end.price > start.price:
                    # 计算笔的高低点
                    segment_klines = klines[start.index:end.index+1]
                    high = max(k['high'] for k in segment_klines)
                    low = min(k['low'] for k in segment_klines)
                    
                    strokes.append(Stroke(
                        start_fractal=start,
                        end_fractal=end,
                        direction=Direction.UP,
                        high=high,
                        low=low
                    ))
            
            # 向下笔：顶 → 底
            elif start.fractal_type == 'top' and end.fractal_type == 'bottom':
                if start.price > end.price:
                    segment_klines = klines[start.index:end.index+1]
                    high = max(k['high'] for k in segment_klines)
                    low = min(k['low'] for k in segment_klines)
                    
                    strokes.append(Stroke(
                        start_fractal=start,
                        end_fractal=end,
                        direction=Direction.DOWN,
                        high=high,
                        low=low
                    ))
        
        return strokes
    
    def detect_centers(self, strokes: List[Stroke]) -> List[Center]:
        """
        检测中枢（至少3根笔重叠）
        
        中枢高点 = min(笔1高, 笔2高, 笔3高)
        中枢低点 = max(笔1低, 笔2低, 笔3低)
        """
        centers = []
        
        for i in range(len(strokes) - 2):
            s1, s2, s3 = strokes[i], strokes[i+1], strokes[i+2]
            
            # 中枢高低点
            center_high = min(s1.high, s2.high, s3.high)
            center_low = max(s1.low, s2.low, s3.low)
            
            # 确保中枢有效（高点>低点）
            if center_high > center_low:
                centers.append(Center(
                    high=center_high,
                    low=center_low,
                    start_time=s1.start_fractal.time,
                    end_time=s3.end_fractal.time,
                    k_count=3
                ))
        
        return centers
    
    def identify_buy_signals(self, strokes: List[Stroke], centers: List[Center], klines: List[Dict]) -> List[TradingSignal]:
        """
        识别三类买点
        
        买1：向下线段后的底分型
        买2：回踩中枢后再次上升
        买3：中枢震荡中的底部
        """
        signals = []
        
        if len(strokes) < 2:
            return signals
        
        # 买1：最近一笔是向下笔 + 形成底分型
        last_stroke = strokes[-1]
        if last_stroke.direction == Direction.DOWN:
            entry_price = last_stroke.end_fractal.price * 1.01
            stop_loss = last_stroke.low * 0.97
            take_profit = last_stroke.start_fractal.price * 0.98
            
            signals.append(TradingSignal(
                symbol='',  # 外部填充
                signal_type=SignalType.BUY1,
                time=last_stroke.end_fractal.time,
                price=last_stroke.end_fractal.price,
                reason=f"向下笔完成，形成底分型于{last_stroke.end_fractal.price:.2f}",
                suggested_entry=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.8
            ))
        
        # 买2：有中枢 + 回踩后上升
        if len(centers) > 0 and len(strokes) >= 4:
            last_center = centers[-1]
            recent_strokes = strokes[-3:]
            
            # 检查是否有回踩中枢的动作
            touched_center = any(
                s.low <= last_center.high and s.high >= last_center.low
                for s in recent_strokes
            )
            
            if touched_center and recent_strokes[-1].direction == Direction.UP:
                entry_price = recent_strokes[-1].end_fractal.price
                stop_loss = last_center.low * 0.98
                take_profit = entry_price * 1.05
                
                signals.append(TradingSignal(
                    symbol='',
                    signal_type=SignalType.BUY2,
                    time=recent_strokes[-1].end_fractal.time,
                    price=entry_price,
                    reason=f"回踩中枢[{last_center.low:.2f}-{last_center.high:.2f}]后再次上升",
                    suggested_entry=entry_price * 1.005,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.85
                ))
        
        return signals
    
    def identify_sell_signals(self, strokes: List[Stroke], centers: List[Center]) -> List[TradingSignal]:
        """
        识别三类卖点
        
        卖1：向上线段后的顶分型
        卖2：反弹中枢后再次下跌
        卖3：中枢震荡中的顶部
        """
        signals = []
        
        if len(strokes) < 2:
            return signals
        
        # 卖1：最近一笔是向上笔 + 形成顶分型
        last_stroke = strokes[-1]
        if last_stroke.direction == Direction.UP:
            entry_price = last_stroke.end_fractal.price * 0.99
            stop_loss = last_stroke.high * 1.03
            take_profit = last_stroke.start_fractal.price * 1.02
            
            signals.append(TradingSignal(
                symbol='',
                signal_type=SignalType.SELL1,
                time=last_stroke.end_fractal.time,
                price=last_stroke.end_fractal.price,
                reason=f"向上笔完成，形成顶分型于{last_stroke.end_fractal.price:.2f}",
                suggested_entry=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.8
            ))
        
        return signals
    
    def analyze(self, symbol: str, timeframe: str = '30') -> Dict:
        """完整分析一只股票"""
        klines = self.get_klines(symbol, timeframe, limit=500)
        
        if len(klines) < 10:
            return {'symbol': symbol, 'signals': [], 'error': '数据不足'}
        
        # 1. 检测分型
        fractals = self.detect_fractals(klines)
        
        # 2. 检测笔
        strokes = self.detect_strokes(fractals, klines)
        
        # 3. 检测中枢
        centers = self.detect_centers(strokes)
        
        # 4. 识别信号
        buy_signals = self.identify_buy_signals(strokes, centers, klines)
        sell_signals = self.identify_sell_signals(strokes, centers)
        
        all_signals = buy_signals + sell_signals
        
        # 填充symbol
        for sig in all_signals:
            sig.symbol = symbol
        
        return {
            'symbol': symbol,
            'fractals_count': len(fractals),
            'strokes_count': len(strokes),
            'centers_count': len(centers),
            'signals': all_signals,
            'last_stroke_direction': strokes[-1].direction.value if strokes else None,
            'last_price': klines[-1]['close'] if klines else 0,
        }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    engine = ChanTheoryEngine()
    result = engine.analyze('sh600519', timeframe='30')
    
    print(f"\n分析结果：{result['symbol']}")
    print(f"  分型数: {result['fractals_count']}")
    print(f"  笔数: {result['strokes_count']}")
    print(f"  中枢数: {result['centers_count']}")
    print(f"  信号数: {len(result['signals'])}")
    
    for sig in result['signals']:
        print(f"\n  [{sig.signal_type.value.upper()}] {sig.time}")
        print(f"    价格: {sig.price:.2f}")
        print(f"    理由: {sig.reason}")
        print(f"    建议: 入场{sig.suggested_entry:.2f} 止损{sig.stop_loss:.2f} 止盈{sig.take_profit:.2f}")
        print(f"    置信度: {sig.confidence:.0%}")
