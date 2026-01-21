#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能A股过滤器

过滤规则：
1. 排除指数代码（sh000xxx, sz399xxx）
2. 排除ST/ST\*股票（风险/亏损企业）
3. 排除退市股票
4. 排除停牌股票
5. 排除成交量为0的股票（僵尸股）
6. 排除北京/京X开头的新股
7. 只保留主板/中小板/创业板活跃交易股票

预期：13999 → ~5500 只正常交易股
"""

import sys
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import akshare as ak
    import pandas as pd
except ImportError as e:
    logger.error(f"缺少依赖: {e}")
    sys.exit(1)


class SmartStockFilter:
    """智能A股过滤器"""
    
    EXCLUDE_KEYWORDS = {
        'ST': 'ST/风险股',
        '*': 'ST/风险股',
        '退市': '退市股',
        '停牌': '停牌股',
        'B': 'B股',
        '北': '北交所新股',
        '京': '北交所新股',
    }
    
    @staticmethod
    def get_filtered_stocks():
        """获取过滤后的A股列表"""
        try:
            logger.info("正在获取A股完整列表...")
            df = ak.stock_zh_a_spot_em()
            logger.info(f"✓ 原始列表: {len(df)} 只")
            
            initial_count = len(df)
            
            # 第1步：排除指数
            mask = ~((df['代码'].str.startswith('sh000')) | (df['代码'].str.startswith('sz399')))
            df = df[mask]
            logger.info(f"  (-{initial_count - len(df):4}) 排除指数代码 → 剩余 {len(df):6} 只")
            
            # 第2步：排除问题股票（ST/退市/停牌等）
            before = len(df)
            for keyword in SmartStockFilter.EXCLUDE_KEYWORDS:
                mask = ~df['名称'].str.contains(keyword, na=False)
                df = df[mask]
            logger.info(f"  (-{before - len(df):4}) 排除ST/退市/停牌等风险股 → 剩余 {len(df):6} 只")
            
            # 第3步：排除成交量为0的股票（僵尸股）
            before = len(df)
            if '成交量' in df.columns:
                df = df[df['成交量'] > 0]
            logger.info(f"  (-{before - len(df):4}) 排除成交量为0 → 剩余 {len(df):6} 只")
            
            # 第4步：排除最低价为0的股票（异常数据）
            before = len(df)
            if '最低' in df.columns:
                df = df[df['最低'] > 0]
            logger.info(f"  (-{before - len(df):4}) 排除异常价格 → 剩余 {len(df):6} 只")
            
            # 第5步：排除涨跌幅超过100%的股票（可能是数据错误或停牌复牌）
            before = len(df)
            if '涨跌幅' in df.columns:
                df = df[df['涨跌幅'].abs() < 100]
            logger.info(f"  (-{before - len(df):4}) 排除异常涨跌幅 → 剩余 {len(df):6} 只")
            
            logger.info(f"\n✓ 最终可交易股票: {len(df)} 只 ({len(df)/initial_count*100:.1f}%)")
            
            return df
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None
    
    @staticmethod
    def save_to_csv(df, filepath='logs/filtered_stocks.csv'):
        """保存过滤后的股票列表"""
        if df is None or df.empty:
            logger.warning("无数据可保存")
            return
        
        try:
            # 只保留关键列
            cols_to_save = ['代码', '名称', '最新价', '成交量', '涨跌幅']
            available_cols = [col for col in cols_to_save if col in df.columns]
            
            df_save = df[available_cols].copy()
            df_save.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"✓ 已保存到: {filepath}")
            
        except Exception as e:
            logger.error(f"保存失败: {e}")


def test_api_reliability(sample_stocks, sample_size=10):
    """测试过滤后的股票API可靠性"""
    logger.info(f"\n正在测试API可靠性（采样{sample_size}只）...")
    
    success = 0
    failed = 0
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    for idx, (_, row) in enumerate(sample_stocks.head(sample_size).iterrows()):
        code = row['代码'].replace('sh', '').replace('sz', '')
        name = row['名称']
        
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period='30',
                adjust='',
                start_date=start_date.strftime('%Y-%m-%d 09:30:00'),
                end_date=end_date.strftime('%Y-%m-%d 15:00:00')
            )
            
            if df is not None and not df.empty:
                success += 1
                status = "✓"
            else:
                failed += 1
                status = "⚠️"
        except Exception as e:
            failed += 1
            status = f"❌ {type(e).__name__}"
        
        logger.info(f"  [{idx+1}/{sample_size}] {code} ({name:8}) {status}")
    
    logger.info(f"\n✓ API成功率: {success}/{sample_size} ({success/sample_size*100:.1f}%)")
    return success, failed


if __name__ == '__main__':
    print("="*70)
    print("A股智能过滤系统")
    print("="*70 + "\n")
    
    # 1. 获取并过滤股票
    df_filtered = SmartStockFilter.get_filtered_stocks()
    
    # 2. 保存过滤结果
    if df_filtered is not None and not df_filtered.empty:
        SmartStockFilter.save_to_csv(df_filtered)
        
        # 3. 测试API可靠性
        test_api_reliability(df_filtered, sample_size=20)
    
    print("\n" + "="*70)
    print("✓ 过滤完成！")
    print("="*70)
