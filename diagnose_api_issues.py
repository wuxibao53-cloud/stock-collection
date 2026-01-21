#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断API异常的根本原因

分析：
1. 为什么会有TypeError
2. 哪些股票无法获取数据（停牌/退市/ST等）
3. AKShare API的限制
"""

import sys
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:
    logger.error("akshare未安装")
    sys.exit(1)


def get_all_a_stocks():
    """获取所有A股信息（包括停牌/ST等标记）"""
    try:
        logger.info("正在获取A股完整列表...")
        df = ak.stock_zh_a_spot_em()
        logger.info(f"✓ 获取 {len(df)} 只股票的基本信息")
        return df
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return None


def analyze_stock_status(df):
    """分析股票状态分布"""
    if df is None or df.empty:
        return
    
    print("\n" + "="*70)
    print("A股状态分布分析")
    print("="*70)
    
    # 分析名称中的特殊标记
    status_counts = {
        'ST': 0,
        '退市': 0,
        '停牌': 0,
        '其他': 0
    }
    
    for name in df['名称'].fillna(''):
        if 'ST' in name or '*' in name:
            status_counts['ST'] += 1
        elif '退市' in name:
            status_counts['退市'] += 1
        elif '停牌' in name:
            status_counts['停牌'] += 1
        else:
            status_counts['其他'] += 1
    
    print(f"\n📊 股票类型分布:")
    for status, count in status_counts.items():
        pct = count / len(df) * 100
        print(f"  {status:6} {count:6} 只 ({pct:5.2f}%)")
    
    print(f"\n可交易股票（剔除问题股）: {status_counts['其他']} 只 ({status_counts['其他']/len(df)*100:.2f}%)")
    
    # 显示问题股票示例
    print(f"\n问题股票示例:")
    print(f"  ST股: {df[df['名称'].str.contains('ST|\\*', na=False)]['名称'].head(3).tolist()}")
    print(f"  退市: {df[df['名称'].str.contains('退市', na=False)]['名称'].head(3).tolist()}")
    
    return status_counts['其他']


def test_akshare_api_limits():
    """测试AKShare API的已知问题"""
    print("\n" + "="*70)
    print("AKShare API 限制测试")
    print("="*70)
    
    test_cases = [
        ('600000', '浦发银行', True),
        ('600001', '邯郸钢铁', True),  # 曾有问题
        ('688981', '中芯国际', True),  # 科创板
        ('000001', '平安银行', True),   # 深市
        ('399001', '深证成指', False),  # 指数，应该失败
        ('000300', '沪深300', False),   # 指数，应该失败
    ]
    
    print("\n测试各种股票代码...")
    for code, name, should_work in test_cases:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)
            
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period='30',
                adjust='',
                start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                end_date=end_date.strftime('%Y-%m-%d 15:00:00')
            )
            
            if df is not None and not df.empty:
                status = "✓ 成功"
            else:
                status = "⚠️  无数据"
                
        except TypeError as e:
            status = f"❌ TypeError: {str(e)[:50]}"
        except Exception as e:
            status = f"❌ {type(e).__name__}: {str(e)[:50]}"
        
        expected = "✓" if should_work else "❌"
        print(f"  {code} ({name:8}) {status:50} [期望: {expected}]")


def find_problematic_stocks(df, sample_size=50):
    """采样测试找出有问题的股票"""
    if df is None or df.empty:
        return
    
    print("\n" + "="*70)
    print(f"采样测试前{sample_size}个交易所热门股...")
    print("="*70)
    
    # 按成交量排序，获取活跃股票
    if '成交量' in df.columns:
        active_stocks = df.nlargest(sample_size, '成交量')
    else:
        active_stocks = df.head(sample_size)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    success = 0
    failed = 0
    errors = {}
    
    for idx, row in active_stocks.iterrows():
        code = row['代码']
        name = row['名称']
        
        # 提取纯数字代码
        clean_code = code.replace('sh', '').replace('sz', '')
        
        try:
            df_result = ak.stock_zh_a_hist_min_em(
                symbol=clean_code,
                period='30',
                adjust='',
                start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                end_date=end_date.strftime('%Y-%m-%d 15:00:00')
            )
            
            if df_result is not None and not df_result.empty:
                success += 1
                status = "✓"
            else:
                failed += 1
                status = "⚠️"
                
        except Exception as e:
            failed += 1
            error_type = type(e).__name__
            status = "❌"
            errors[error_type] = errors.get(error_type, 0) + 1
            if failed <= 5:  # 显示前5个错误
                print(f"  {code} ({name:8}) {error_type}: {str(e)[:40]}")
        
        if (idx + 1) % 10 == 0:
            print(f"  进度: {idx+1}/{len(active_stocks)} 成功:{success} 失败:{failed}")
    
    print(f"\n📊 采样结果:")
    print(f"  成功率: {success}/{sample_size} ({success/sample_size*100:.1f}%)")
    if errors:
        print(f"  错误类型: {errors}")


if __name__ == '__main__':
    print("="*70)
    print("A股API诊断工具 - 找出真正的问题原因")
    print("="*70)
    
    # 1. 获取股票列表
    df = get_all_a_stocks()
    
    # 2. 分析股票状态
    if df is not None:
        normal_count = analyze_stock_status(df)
    
    # 3. 测试API限制
    test_akshare_api_limits()
    
    # 4. 采样测试
    if df is not None:
        find_problematic_stocks(df, sample_size=50)
    
    print("\n" + "="*70)
    print("诊断完成！")
    print("="*70)
