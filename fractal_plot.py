#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论分型可视化模块

在蜡烛图上标注识别出的分型，用不同的标记显示：
- 顶分型：红色 ▼
- 底分型：绿色 ▲

Author: 仙儿仙儿碎碎念
"""

import sqlite3
import csv
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from collections import defaultdict
from fractal_recognition import FractalRecognizer


def plot_candles_with_fractals(bars, fractals, title, out_path, figsize=(14, 7)):
    """
    绘制带分型标注的蜡烛图
    
    Args:
        bars: K线列表
        fractals: 分型列表
        title: 图表标题
        out_path: 输出文件路径
        figsize: 图表大小
    """
    if not bars:
        print("❌ 没有K线数据")
        return
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # 绘制蜡烛图
    for i, bar in enumerate(bars):
        open_price = bar['open']
        close_price = bar['close']
        high_price = bar['high']
        low_price = bar['low']
        
        # 确定颜色
        color = 'red' if close_price >= open_price else 'green'
        
        # 绘制高低线（灯芯）
        ax.plot([i, i], [low_price, high_price], color=color, linewidth=1)
        
        # 绘制K线实体
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        rect = mpatches.Rectangle((i - 0.3, bottom), 0.6, height,
                                   linewidth=1, edgecolor=color, facecolor=color, alpha=0.8)
        ax.add_patch(rect)
    
    # 标注分型
    top_count = 0
    bottom_count = 0
    
    for frac in fractals:
        idx = frac.idx
        if 0 <= idx < len(bars):
            bar = bars[idx]
            
            if frac.fractal_type == 'top':
                # 顶分型：在最高点上方标注红色▼
                ax.scatter(idx, bar['high'], marker='v', color='red', s=200, 
                          zorder=5, edgecolors='darkred', linewidth=2)
                top_count += 1
            else:  # bottom
                # 底分型：在最低点下方标注绿色▲
                ax.scatter(idx, bar['low'], marker='^', color='green', s=200,
                          zorder=5, edgecolors='darkgreen', linewidth=2)
                bottom_count += 1
    
    # 设置X轴标签（每10根K线显示一个）
    step = max(1, len(bars) // 10)
    x_ticks = list(range(0, len(bars), step))
    x_labels = [bars[i]['minute'].split(' ')[1] if i < len(bars) else '' for i in x_ticks]
    
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=45, ha='right')
    
    ax.set_ylabel('Price (¥)')
    ax.set_title(f'{title}\n分型识别：顶分型{top_count}个 | 底分型{bottom_count}个', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # 添加图例
    red_marker = plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='red', 
                           markersize=10, label='顶分型', markeredgecolor='darkred')
    green_marker = plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='green',
                             markersize=10, label='底分型', markeredgecolor='darkgreen')
    ax.legend(handles=[red_marker, green_marker], loc='upper left')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches='tight')
    print(f"✓ 分型图已保存: {out_path}")
    plt.close()


def read_minute_bars_sqlite(db_path, symbol, start=None, end=None):
    """从SQLite读取分钟K线"""
    bars = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM minute_bars WHERE symbol = ?"
        params = [symbol]
        
        if start:
            query += " AND minute >= ?"
            params.append(start)
        if end:
            query += " AND minute <= ?"
            params.append(end)
        
        query += " ORDER BY minute"
        
        cursor.execute(query, params)
        
        for row in cursor.fetchall():
            bars.append({
                'minute': row['minute'],
                'symbol': row['symbol'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
            })
        
        conn.close()
    except Exception as e:
        print(f"❌ 读取数据库失败: {e}")
    
    return bars


def read_minute_bars_csv(csv_path, symbol):
    """从CSV读取分钟K线"""
    bars = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('symbol') == symbol:
                    bars.append({
                        'minute': row.get('minute'),
                        'symbol': row.get('symbol'),
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'volume': int(row.get('volume', 0)),
                    })
    except Exception as e:
        print(f"❌ 读取CSV失败: {e}")
    
    return bars


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论分型可视化工具')
    parser.add_argument('--source', choices=['sqlite', 'csv'], default='sqlite',
                       help='数据源类型')
    parser.add_argument('--db', default='logs/quotes.db',
                       help='SQLite数据库路径')
    parser.add_argument('--csv',
                       help='CSV文件路径')
    parser.add_argument('--symbol', required=True,
                       help='股票代码（如 sh600519）')
    parser.add_argument('--start',
                       help='开始时间 YYYY-MM-DD HH:MM')
    parser.add_argument('--end',
                       help='结束时间 YYYY-MM-DD HH:MM')
    parser.add_argument('--out', required=True,
                       help='输出PNG文件路径')
    
    args = parser.parse_args()
    
    # 读取K线数据
    print(f"📖 读取K线数据...")
    if args.source == 'sqlite':
        bars = read_minute_bars_sqlite(args.db, args.symbol, args.start, args.end)
    else:  # csv
        if not args.csv:
            print("❌ 使用CSV源时必须指定 --csv 参数")
            return
        bars = read_minute_bars_csv(args.csv, args.symbol)
    
    if not bars:
        print(f"❌ 未找到 {args.symbol} 的数据")
        return
    
    print(f"✓ 读取 {len(bars)} 根K线")
    
    # 识别分型
    print(f"🔍 识别分型...")
    recognizer = FractalRecognizer()
    fractals = recognizer.recognize_from_bars(bars)
    
    print(f"✓ 识别 {len(fractals)} 个分型")
    recognizer.print_summary()
    
    # 绘制图表
    print(f"📊 绘制图表...")
    date_str = bars[0]['minute'].split(' ')[0] if bars else 'unknown'
    title = f"{args.symbol} 分钟K线 - {date_str} (缠论分型识别)"
    plot_candles_with_fractals(bars, fractals, title, args.out)
    
    print(f"\n✅ 完成！")


if __name__ == '__main__':
    main()
