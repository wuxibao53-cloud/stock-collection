#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5000+ A 股采集验证工具
用于验证全 A 股采集是否正常工作

使用方式：
    python verify_collection.py --mode hot --db logs/quotes.db
    python verify_collection.py --mode full --db logs/quotes.db --check-quality
    python verify_collection.py --generate-report --db logs/quotes.db --output report.md
"""

import sqlite3
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from collections import defaultdict


class CollectionVerifier:
    """采集验证工具"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
    
    # ==================== 数据统计 ====================
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """获取采集摘要统计"""
        
        stats = {}
        
        # 总体统计
        self.cursor.execute('SELECT COUNT(DISTINCT symbol), COUNT(*), COUNT(DISTINCT minute) FROM minute_bars')
        symbols, records, dates = self.cursor.fetchone()
        
        stats['total_symbols'] = symbols
        stats['total_records'] = records
        stats['total_dates'] = dates
        stats['avg_records_per_symbol'] = records // max(symbols, 1)
        
        # 数据跨度
        self.cursor.execute('SELECT MIN(minute), MAX(minute) FROM minute_bars')
        min_date, max_date = self.cursor.fetchone()
        stats['date_range'] = f"{min_date} to {max_date}"
        
        # 数据质量
        self.cursor.execute('''
            SELECT 
                COUNT(CASE WHEN open IS NOT NULL THEN 1 END) as open_count,
                COUNT(CASE WHEN close IS NOT NULL THEN 1 END) as close_count,
                COUNT(CASE WHEN volume > 0 THEN 1 END) as volume_count
            FROM minute_bars
        ''')
        open_cnt, close_cnt, vol_cnt = self.cursor.fetchone()
        
        stats['data_quality'] = {
            'open_present_pct': (open_cnt / max(records, 1) * 100),
            'close_present_pct': (close_cnt / max(records, 1) * 100),
            'volume_present_pct': (vol_cnt / max(records, 1) * 100)
        }
        
        return stats
    
    def get_symbol_distribution(self) -> Dict[str, Any]:
        """获取股票分布统计"""
        
        self.cursor.execute('''
            SELECT 
                symbol,
                COUNT(*) as record_count,
                MIN(minute) as first_date,
                MAX(minute) as last_date,
                AVG(close) as avg_price,
                MAX(close) as max_price,
                MIN(close) as min_price
            FROM minute_bars
            GROUP BY symbol
            ORDER BY record_count DESC
        ''')
        
        distribution = []
        for row in self.cursor.fetchall():
            symbol, cnt, first, last, avg_price, max_p, min_p = row
            distribution.append({
                'symbol': symbol,
                'records': cnt,
                'first_date': first,
                'last_date': last,
                'avg_price': round(avg_price, 2) if avg_price else None,
                'price_range': (round(min_p, 2), round(max_p, 2)) if (min_p and max_p) else None
            })
        
        return {
            'top_10_symbols': distribution[:10],
            'total_symbols': len(distribution),
            'bottom_10_symbols': distribution[-10:] if len(distribution) > 10 else []
        }
    
    def get_market_segment_stats(self) -> Dict[str, Any]:
        """获取市场分段统计（上证/深证/创业板/北交所）"""
        
        segments = {}
        
        # 定义市场前缀
        market_prefixes = {
            '上证': 'sh',
            '深证': 'sz',
            '创业板': 'sz3',
            '科创板': 'sh6',
            '北交所': 'bj'
        }
        
        for market, prefix in market_prefixes.items():
            self.cursor.execute(f'''
                SELECT 
                    COUNT(DISTINCT symbol) as count,
                    COUNT(*) as records,
                    AVG(close) as avg_price
                FROM minute_bars
                WHERE symbol LIKE '{prefix}%'
            ''')
            
            count, records, avg_price = self.cursor.fetchone()
            if count > 0:
                segments[market] = {
                    'stock_count': count,
                    'record_count': records,
                    'avg_price': round(avg_price, 2) if avg_price else 0
                }
        
        return segments
    
    def check_data_quality(self) -> Dict[str, Any]:
        """检查数据质量问题"""
        
        issues = {
            'missing_prices': 0,
            'missing_volumes': 0,
            'invalid_prices': 0,
            'duplicate_records': 0,
            'data_gaps': []
        }
        
        # 1. 缺失的价格
        self.cursor.execute('SELECT COUNT(*) FROM minute_bars WHERE close IS NULL OR open IS NULL')
        issues['missing_prices'] = self.cursor.fetchone()[0]
        
        # 2. 缺失的成交量
        self.cursor.execute('SELECT COUNT(*) FROM minute_bars WHERE volume IS NULL OR volume = 0')
        issues['missing_volumes'] = self.cursor.fetchone()[0]
        
        # 3. 异常价格（极端高低）
        self.cursor.execute('''
            SELECT COUNT(*) FROM minute_bars 
            WHERE close > 10000 OR close < 0.01
        ''')
        issues['invalid_prices'] = self.cursor.fetchone()[0]
        
        # 4. 重复记录
        self.cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT symbol, minute, COUNT(*) as cnt
                FROM minute_bars
                GROUP BY symbol, minute
                HAVING cnt > 1
            )
        ''')
        issues['duplicate_records'] = self.cursor.fetchone()[0]
        
        # 5. 数据间隙检查
        self.cursor.execute('''
            SELECT DISTINCT symbol FROM minute_bars
            WHERE symbol LIKE 'sh%' OR symbol LIKE 'sz%'
            LIMIT 10
        ''')
        
        sample_symbols = [row[0] for row in self.cursor.fetchall()]
        for symbol in sample_symbols[:5]:
            self.cursor.execute(f'''
                SELECT COUNT(DISTINCT DATE(minute)) 
                FROM minute_bars 
                WHERE symbol = '{symbol}'
            ''')
            date_count = self.cursor.fetchone()[0]
            
            self.cursor.execute(f'''
                SELECT MIN(DATE(minute)), MAX(DATE(minute))
                FROM minute_bars
                WHERE symbol = '{symbol}'
            ''')
            min_date, max_date = self.cursor.fetchone()
            
            if min_date and max_date:
                delta = (datetime.fromisoformat(max_date) - datetime.fromisoformat(min_date)).days + 1
                gap = delta - date_count
                if gap > 5:
                    issues['data_gaps'].append({
                        'symbol': symbol,
                        'expected_days': delta,
                        'actual_days': date_count,
                        'gap_days': gap
                    })
        
        return issues
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        
        # 查询速度测试
        import time
        
        metrics = {}
        
        # 测试范围查询
        start = time.time()
        self.cursor.execute('SELECT COUNT(*) FROM minute_bars WHERE close > 10 AND close < 100')
        self.cursor.fetchone()
        metrics['range_query_time'] = (time.time() - start) * 1000  # 毫秒
        
        # 测试分组查询
        start = time.time()
        self.cursor.execute('SELECT symbol, COUNT(*) FROM minute_bars GROUP BY symbol')
        self.cursor.fetchall()
        metrics['groupby_query_time'] = (time.time() - start) * 1000
        
        # 测试排序查询
        start = time.time()
        self.cursor.execute('SELECT * FROM minute_bars ORDER BY close DESC LIMIT 100')
        self.cursor.fetchall()
        metrics['sort_query_time'] = (time.time() - start) * 1000
        
        # 数据库文件大小
        import os
        file_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
        metrics['db_file_size_mb'] = round(file_size, 2)
        
        return metrics
    
    # ==================== 报告生成 ====================
    
    def generate_html_report(self, output_path: str = None) -> str:
        """生成 HTML 格式的详细报告"""
        
        stats = self.get_summary_stats()
        dist = self.get_symbol_distribution()
        segments = self.get_market_segment_stats()
        quality = self.check_data_quality()
        perf = self.get_performance_metrics()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>缠论系统 - A股采集验证报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #07C160; padding-bottom: 10px; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .metric {{ 
            display: inline-block; 
            background: #f0f9ff; 
            padding: 15px; 
            margin: 10px; 
            border-radius: 5px; 
            border-left: 4px solid #07C160;
        }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #07C160; }}
        .metric-label {{ font-size: 12px; color: #999; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #07C160; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .status-ok {{ color: #07C160; font-weight: bold; }}
        .status-warning {{ color: #FFA500; font-weight: bold; }}
        .status-error {{ color: #FF3B30; font-weight: bold; }}
        .timestamp {{ color: #999; font-size: 12px; text-align: right; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ 缠论交易系统 - 全A股采集验证报告</h1>
        <p class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>📊 采集摘要</h2>
        <div>
            <div class="metric">
                <div class="metric-value">{stats['total_symbols']:,}</div>
                <div class="metric-label">采集股票数</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats['total_records']:,}</div>
                <div class="metric-label">数据记录数</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats['avg_records_per_symbol']:.0f}</div>
                <div class="metric-label">平均每股记录</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats['total_dates']}</div>
                <div class="metric-label">交易日期数</div>
            </div>
        </div>
        
        <h2>🏙️ 市场分布</h2>
        <table>
            <tr>
                <th>市场</th>
                <th>股票数</th>
                <th>数据条数</th>
                <th>平均价格</th>
            </tr>
            {"".join(f"<tr><td>{k}</td><td>{v['stock_count']}</td><td>{v['record_count']}</td><td>¥{v['avg_price']}</td></tr>" for k, v in segments.items())}
        </table>
        
        <h2>⭐ 热门股票 TOP 10</h2>
        <table>
            <tr>
                <th>代码</th>
                <th>数据条数</th>
                <th>最低价</th>
                <th>平均价</th>
                <th>最高价</th>
                <th>数据周期</th>
            </tr>
            {"".join(f'''<tr>
                <td>{s['symbol']}</td>
                <td>{s['records']}</td>
                <td>¥{s['price_range'][0]}</td>
                <td>¥{s['avg_price']}</td>
                <td>¥{s['price_range'][1]}</td>
                <td>{s['first_date']} ~ {s['last_date']}</td>
            </tr>''' for s in dist['top_10_symbols'])}
        </table>
        
        <h2>🔍 数据质量检查</h2>
        <table>
            <tr>
                <th>检查项</th>
                <th>结果</th>
                <th>状态</th>
            </tr>
            <tr>
                <td>缺失价格记录</td>
                <td>{quality['missing_prices']} 条</td>
                <td class="{'status-ok' if quality['missing_prices'] < 100 else 'status-warning'}">{'✓ OK' if quality['missing_prices'] < 100 else '⚠ 需要关注'}</td>
            </tr>
            <tr>
                <td>缺失成交量</td>
                <td>{quality['missing_volumes']} 条</td>
                <td class="{'status-ok' if quality['missing_volumes'] < 100 else 'status-warning'}">{'✓ OK' if quality['missing_volumes'] < 100 else '⚠ 需要关注'}</td>
            </tr>
            <tr>
                <td>异常价格</td>
                <td>{quality['invalid_prices']} 条</td>
                <td class="{'status-ok' if quality['invalid_prices'] == 0 else 'status-error'}">{'✓ OK' if quality['invalid_prices'] == 0 else '❌ 有问题'}</td>
            </tr>
            <tr>
                <td>重复记录</td>
                <td>{quality['duplicate_records']} 条</td>
                <td class="{'status-ok' if quality['duplicate_records'] == 0 else 'status-error'}">{'✓ OK' if quality['duplicate_records'] == 0 else '❌ 有问题'}</td>
            </tr>
        </table>
        
        <h2>⚡ 性能指标</h2>
        <table>
            <tr>
                <th>指标</th>
                <th>数值</th>
            </tr>
            <tr>
                <td>数据库文件大小</td>
                <td>{perf['db_file_size_mb']} MB</td>
            </tr>
            <tr>
                <td>范围查询耗时</td>
                <td>{perf['range_query_time']:.1f} ms</td>
            </tr>
            <tr>
                <td>分组查询耗时</td>
                <td>{perf['groupby_query_time']:.1f} ms</td>
            </tr>
            <tr>
                <td>排序查询耗时</td>
                <td>{perf['sort_query_time']:.1f} ms</td>
            </tr>
        </table>
        
        <h2>✅ 验证结果</h2>
        <table>
            <tr>
                <th>验证项</th>
                <th>结果</th>
            </tr>
            <tr>
                <td>股票覆盖 (5000+ 目标)</td>
                <td class="{'status-ok' if stats['total_symbols'] >= 5000 else 'status-warning'}">{stats['total_symbols']:,} {'✓ PASS' if stats['total_symbols'] >= 5000 else '⚠ 需要补充'}</td>
            </tr>
            <tr>
                <td>数据量充足 (50000+ 目标)</td>
                <td class="{'status-ok' if stats['total_records'] >= 50000 else 'status-warning'}">{stats['total_records']:,} {'✓ PASS' if stats['total_records'] >= 50000 else '⚠ 需要补充'}</td>
            </tr>
            <tr>
                <td>数据质量 (> 99%)</td>
                <td class="{'status-ok' if stats['data_quality']['close_present_pct'] > 99 else 'status-warning'}">{stats['data_quality']['close_present_pct']:.1f}% {'✓ PASS' if stats['data_quality']['close_present_pct'] > 99 else '⚠ 需要改进'}</td>
            </tr>
        </table>
        
        <p style="margin-top: 40px; color: #999; text-align: center;">
            本报告由缠论交易系统自动生成，仅供参考。
        </p>
    </div>
</body>
</html>
"""
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✓ HTML 报告已保存: {output_path}")
        
        return html
    
    def generate_markdown_report(self, output_path: str = None) -> str:
        """生成 Markdown 格式的报告"""
        
        stats = self.get_summary_stats()
        dist = self.get_symbol_distribution()
        segments = self.get_market_segment_stats()
        quality = self.check_data_quality()
        perf = self.get_performance_metrics()
        
        md = f"""# 缠论交易系统 - 全A股采集验证报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 采集摘要

| 指标 | 数值 |
|------|------|
| 采集股票数 | {stats['total_symbols']:,} 只 |
| 采集数据条数 | {stats['total_records']:,} 条 |
| 平均每股数据 | {stats['avg_records_per_symbol']:.0f} 条 |
| 交易日期数 | {stats['total_dates']} 天 |
| 数据时间范围 | {stats['date_range']} |

---

## 🏙️ 市场分布

### 各市场股票统计

| 市场 | 股票数 | 数据条数 | 平均价格 |
|------|--------|---------|----------|
{chr(10).join(f"| {k} | {v['stock_count']} | {v['record_count']} | ¥{v['avg_price']} |" for k, v in segments.items())}

---

## ⭐ 热门股票 TOP 10

| 代码 | 数据条数 | 最低价 | 平均价 | 最高价 | 数据周期 |
|------|---------|--------|--------|--------|---------|
{chr(10).join(f"| {s['symbol']} | {s['records']} | ¥{s['price_range'][0]} | ¥{s['avg_price']} | ¥{s['price_range'][1]} | {s['first_date']} ~ {s['last_date']} |" for s in dist['top_10_symbols'])}

---

## 🔍 数据质量检查

| 检查项 | 数值 | 状态 |
|--------|------|------|
| 缺失价格 | {quality['missing_prices']} 条 | {'✓ OK' if quality['missing_prices'] < 100 else '⚠ 需要关注'} |
| 缺失成交量 | {quality['missing_volumes']} 条 | {'✓ OK' if quality['missing_volumes'] < 100 else '⚠ 需要关注'} |
| 异常价格 | {quality['invalid_prices']} 条 | {'✓ OK' if quality['invalid_prices'] == 0 else '❌ 有问题'} |
| 重复记录 | {quality['duplicate_records']} 条 | {'✓ OK' if quality['duplicate_records'] == 0 else '❌ 有问题'} |

---

## ⚡ 性能指标

| 指标 | 数值 |
|------|------|
| 数据库文件大小 | {perf['db_file_size_mb']} MB |
| 范围查询 | {perf['range_query_time']:.1f} ms |
| 分组查询 | {perf['groupby_query_time']:.1f} ms |
| 排序查询 | {perf['sort_query_time']:.1f} ms |

---

## ✅ 验证结果

| 验证项 | 目标 | 实际 | 状态 |
|--------|------|------|------|
| 股票覆盖 | 5000+ | {stats['total_symbols']:,} | {'✓ PASS' if stats['total_symbols'] >= 5000 else '⚠ FAIL'} |
| 数据量 | 50000+ | {stats['total_records']:,} | {'✓ PASS' if stats['total_records'] >= 50000 else '⚠ FAIL'} |
| 数据质量 | >99% | {stats['data_quality']['close_present_pct']:.1f}% | {'✓ PASS' if stats['data_quality']['close_present_pct'] > 99 else '⚠ FAIL'} |

---

## 🎯 建议

"""
        
        recommendations = []
        if stats['total_symbols'] < 5000:
            recommendations.append("- ⚠️ 股票覆盖不足，建议继续采集")
        if stats['total_records'] < 50000:
            recommendations.append("- ⚠️ 数据量不足，建议采集更多历史数据")
        if quality['invalid_prices'] > 0:
            recommendations.append("- ❌ 发现异常价格数据，建议进行数据清洗")
        if quality['duplicate_records'] > 0:
            recommendations.append("- ❌ 发现重复记录，建议进行去重处理")
        if not recommendations:
            recommendations.append("- ✅ 所有检查都通过，系统运行正常")
        
        md += "\n".join(recommendations)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md)
            print(f"✓ Markdown 报告已保存: {output_path}")
        
        return md
    
    def print_summary(self):
        """打印摘要信息"""
        
        stats = self.get_summary_stats()
        segments = self.get_market_segment_stats()
        quality = self.check_data_quality()
        
        print("\n" + "="*60)
        print("📊 缠论交易系统 - 采集验证摘要")
        print("="*60 + "\n")
        
        # 基本统计
        print("📈 基本统计:")
        print(f"  • 采集股票数: {stats['total_symbols']:,} 只")
        print(f"  • 采集数据条数: {stats['total_records']:,} 条")
        print(f"  • 平均每股: {stats['avg_records_per_symbol']:.0f} 条")
        print(f"  • 数据跨度: {stats['date_range']}\n")
        
        # 市场分布
        print("🏙️ 市场分布:")
        for market, data in segments.items():
            print(f"  • {market}: {data['stock_count']} 只股票, {data['record_count']} 条数据")
        print()
        
        # 数据质量
        print("🔍 数据质量:")
        print(f"  • 缺失价格: {quality['missing_prices']} 条")
        print(f"  • 缺失成交量: {quality['missing_volumes']} 条")
        print(f"  • 异常价格: {quality['invalid_prices']} 条")
        print(f"  • 重复记录: {quality['duplicate_records']} 条\n")
        
        # 验证结果
        print("✅ 验证结果:")
        pass_fail_1 = "✓ PASS" if stats['total_symbols'] >= 5000 else "⚠ FAIL"
        pass_fail_2 = "✓ PASS" if stats['total_records'] >= 50000 else "⚠ FAIL"
        pass_fail_3 = "✓ PASS" if stats['data_quality']['close_present_pct'] > 99 else "⚠ FAIL"
        print(f"  • 股票覆盖 (5000+): {stats['total_symbols']:,} {pass_fail_1}")
        print(f"  • 数据量 (50000+): {stats['total_records']:,} {pass_fail_2}")
        print(f"  • 数据质量 (>99%): {stats['data_quality']['close_present_pct']:.1f}% {pass_fail_3}")
        print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="5000+ A股采集验证工具")
    parser.add_argument("--db", default="logs/quotes.db", help="数据库文件路径")
    parser.add_argument("--mode", choices=["hot", "full", "check"], default="check", 
                       help="验证模式")
    parser.add_argument("--check-quality", action="store_true", help="执行详细的数据质量检查")
    parser.add_argument("--generate-report", action="store_true", help="生成详细报告")
    parser.add_argument("--output", help="输出文件路径（可选）")
    parser.add_argument("--format", choices=["html", "markdown"], default="markdown",
                       help="报告格式")
    
    args = parser.parse_args()
    
    try:
        with CollectionVerifier(args.db) as verifier:
            if args.generate_report:
                if args.format == "html":
                    output_file = args.output or "collection_report.html"
                    verifier.generate_html_report(output_file)
                else:
                    output_file = args.output or "collection_report.md"
                    verifier.generate_markdown_report(output_file)
            else:
                verifier.print_summary()
                
                if args.check_quality:
                    print("\n🔍 详细质量检查:")
                    quality = verifier.check_data_quality()
                    for key, value in quality.items():
                        if isinstance(value, list):
                            print(f"  {key}: {len(value)} 项")
                        else:
                            print(f"  {key}: {value}")
    
    except FileNotFoundError:
        print(f"❌ 错误：数据库文件不存在: {args.db}")
        exit(1)
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
