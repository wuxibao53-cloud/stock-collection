#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论实时监控脚本 - 简化版

支持：
1. 完整分析 - 对所有股票进行分型/线段/中枢/信号分析
2. 快速查看 - 只看摘要信息
3. 导出报告 - 生成JSON和Markdown报告
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from chan_trading_system import ChanTheoryTradingSystem


def run_analysis(db_path):
    """运行完整分析"""
    
    system = ChanTheoryTradingSystem(db_path)
    
    print("\n" + "="*100)
    print("🔥 缠论综合交易系统 - 实时监控")
    print("="*100)
    print(f"⏱️  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 分析所有股票
    system.analyze_all_symbols()
    
    # 生成综合报告
    system.print_summary_report()
    system.alert_system.print_alerts()
    
    # 保存JSON报告
    try:
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'symbols': list(system.analysis_results.keys()),
            'analysis_count': len(system.analysis_results),
            'alerts': {
                'buy': len([a for a in system.alert_system.alerts if a.signal_type == 'buy']),
                'sell': len([a for a in system.alert_system.alerts if a.signal_type == 'sell']),
                'strong': len([a for a in system.alert_system.alerts if a.level == 3]),
            },
            'details': system.analysis_results,
        }
        
        report_path = Path(db_path).parent / 'chan_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 报告已保存: {report_path}")
    
    except Exception as e:
        print(f"⚠️  报告保存失败: {e}")
    
    return system


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论实时监控')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--symbol', help='只分析指定股票')
    
    args = parser.parse_args()
    
    # 检查数据库
    db_path = args.db
    if not Path(db_path).exists():
        print(f"❌ 数据库不存在: {db_path}")
        return
    
    system = ChanTheoryTradingSystem(db_path)
    
    if args.symbol:
        # 分析单个股票
        print(f"\n分析 {args.symbol}...")
        result = system.analyze_symbol(args.symbol)
        if result:
            system._print_result(result)
            system.alert_system.print_alerts()
    else:
        # 分析所有股票
        run_analysis(db_path)


if __name__ == '__main__':
    main()
