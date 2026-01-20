#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论实时监控仪表板

提供实时监控、报告导出、告警管理的一站式脚本
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

from chan_trading_system import ChanTheoryTradingSystem


def generate_daily_report():
    """生成每日分析报告"""
    
    system = ChanTheoryTradingSystem('../logs/quotes.db')
    
    # 分析所有股票
    try:
        conn = sqlite3.connect(system.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM minute_bars ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
    except:
        symbols = []
    
    print("\n" + "="*100)
    print("缠论实时监控 - 每日报告")
    print("="*100)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 分析每个股票
    for symbol in symbols:
        result = system.analyze_symbol(symbol)
        if result:
            system._print_result(result)
    
    # 生成总结报告
    system.print_summary_report()
    system.alert_system.print_alerts()
    
    # 导出JSON报告
    system.export_report_json('logs/chan_daily_report.json')
    
    # 生成markdown报告
    generate_markdown_report(system)


def generate_markdown_report(system):
    """生成Markdown格式的日报"""
    
    report_lines = []
    report_lines.append("# 缠论交易系统日报\n")
    report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 市场概览
    report_lines.append("## 📊 市场概览\n")
    
    buy_alerts = len([a for a in system.alert_system.alerts if a.signal_type == 'buy'])
    sell_alerts = len([a for a in system.alert_system.alerts if a.signal_type == 'sell'])
    strong_alerts = len([a for a in system.alert_system.alerts if a.level == 3])
    
    report_lines.append(f"- 交易提醒总数: **{buy_alerts + sell_alerts}**\n")
    report_lines.append(f"  - 买入提醒: 🟢 {buy_alerts}\n")
    report_lines.append(f"  - 卖出提醒: 🔴 {sell_alerts}\n")
    report_lines.append(f"  - 强信号: ⭐ {strong_alerts}\n\n")
    
    # 各股票分析
    report_lines.append("## 📈 股票分析\n")
    
    for symbol in sorted(system.analysis_results.keys()):
        result = system.analysis_results[symbol]
        
        report_lines.append(f"### {symbol}\n")
        report_lines.append(f"- **价格**: {result['latest_price']:.2f}\n")
        
        # 分型统计
        frac = result['fractals']
        report_lines.append(f"- **分型**: {frac['total']} 个 (顶:{frac['tops']} 底:{frac['bottoms']})\n")
        
        # 线段统计
        stroke = result['strokes']
        report_lines.append(f"- **线段**: {stroke['total']} 条 (上升:{stroke['ups']} 下降:{stroke['downs']})\n")
        if stroke['latest']:
            report_lines.append(f"  - 最新: {stroke['latest']}\n")
        
        # 中枢统计
        pivot = result['pivots']
        report_lines.append(f"- **中枢**: {pivot['total']} 个 (上升:{pivot['ups']} 下降:{pivot['downs']})\n")
        
        # 信号统计
        signal = result['signals']
        report_lines.append(f"- **信号**: 买{signal['buy']} 卖{signal['sell']}\n\n")
    
    # 建议
    report_lines.append("## 💡 操作建议\n")
    
    sync_symbols = [
        s for s, r in system.analysis_results.items()
        if r['interval_analysis']['is_synchronized']
    ]
    
    if sync_symbols:
        report_lines.append("### 三周期同步股票（优先考虑）\n")
        for sym in sync_symbols:
            result = system.analysis_results[sym]
            ia = result['interval_analysis']
            report_lines.append(f"- **{sym}**: {ia['fast_signal'].upper()} " \
                              f"(强度 {int(ia['strength']*100)}%)\n")
    else:
        report_lines.append("### 暂无三周期同步信号\n")
    
    # 风险提示
    report_lines.append("\n## ⚠️ 风险提示\n")
    report_lines.append("- 只在三周期同步时进行操作\n")
    report_lines.append("- 在关键分型位置设置止损\n")
    report_lines.append("- 严格遵循资金管理规则\n")
    report_lines.append("- 本报告仅供参考，不构成投资建议\n")
    
    # 保存报告
    report_path = Path('logs/chan_daily_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.writelines(report_lines)
    
    print(f"✓ Markdown报告已生成: {report_path}")


def print_quick_summary():
    """打印快速摘要"""
    
    try:
        with open('logs/chan_daily_report.json', 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        print("\n" + "="*80)
        print("📊 缠论交易系统 - 快速摘要")
        print("="*80)
        
        if 'alerts_summary' in report:
            summary = report['alerts_summary']
            print(f"日期: {summary['date']}")
            print(f"提醒总数: {summary['total']}")
            print(f"买入: 🟢 {summary['buy']}")
            print(f"卖出: 🔴 {summary['sell']}")
            print(f"强信号: ⭐ {summary['strong']}")
        
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"❌ 无法读取报告: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论实时监控仪表板')
    parser.add_argument('--mode', choices=['daily', 'quick', 'all'], default='all',
                       help='运行模式')
    
    args = parser.parse_args()
    
    if args.mode in ['daily', 'all']:
        generate_daily_report()
    
    if args.mode in ['quick', 'all']:
        print_quick_summary()


if __name__ == '__main__':
    main()
