#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKShare API的返回值类型

用于诊断为什么某些股票会导致NoneType错误
"""

import sys
import traceback

try:
    import akshare as ak
except ImportError:
    print("❌ akshare未安装，请运行: pip install akshare")
    sys.exit(1)

from datetime import datetime, timedelta


def test_stock(symbol, clean_symbol):
    """测试单只股票的API返回值"""
    print(f"\n{'='*60}")
    print(f"测试 {symbol} (clean: {clean_symbol})")
    print('='*60)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    try:
        df = ak.stock_zh_a_hist_min_em(
            symbol=clean_symbol,
            period='30',
            adjust='',
            start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
            end_date=end_date.strftime('%Y-%m-%d 15:00:00')
        )
        
        print(f"✓ API调用成功")
        print(f"  类型: {type(df)}")
        print(f"  df is None: {df is None}")
        
        if df is not None:
            print(f"  hasattr(df, 'empty'): {hasattr(df, 'empty')}")
            print(f"  hasattr(df, 'columns'): {hasattr(df, 'columns')}")
            print(f"  hasattr(df, 'iterrows'): {hasattr(df, 'iterrows')}")
            
            if hasattr(df, 'empty'):
                print(f"  df.empty: {df.empty}")
            
            if hasattr(df, 'columns'):
                try:
                    print(f"  列: {list(df.columns)}")
                except Exception as e:
                    print(f"  ❌ 访问columns失败: {e}")
            
            if hasattr(df, 'shape'):
                print(f"  形状: {df.shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ API调用失败")
        print(f"  异常类型: {type(e).__name__}")
        print(f"  异常信息: {e}")
        print(f"  详细堆栈:")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # 测试已知有问题的股票
    problem_stocks = [
        ('sh600013', '600013'),
        ('sh600014', '600014'),
        ('sh600001', '600001'),  # 无数据
        ('sh600519', '600519'),  # 茅台，应该正常
    ]
    
    print("AKShare API 诊断工具")
    print(f"测试时间: {datetime.now()}")
    
    results = {}
    for symbol, clean in problem_stocks:
        success = test_stock(symbol, clean)
        results[symbol] = success
    
    print(f"\n\n{'='*60}")
    print("测试总结")
    print('='*60)
    for symbol, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        print(f"  {symbol:12} {status}")
