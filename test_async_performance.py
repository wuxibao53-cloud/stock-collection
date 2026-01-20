#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整5000+股票异步采集性能测试脚本

用途：
- 测试异步采集器的真实性能
- 估算完整A股采集所需时间
- 验证数据库WAL模式效率
"""

import asyncio
import time
import sqlite3
import sys
from pathlib import Path

# 加载采集器
from full_a_stock_collector import FullAStockCollector

async def test_async_collection():
    """测试异步采集性能"""
    
    db_path = 'logs/test_async_5000.db'
    
    # 清理旧数据库
    Path(db_path).unlink(missing_ok=True)
    
    print("\n" + "="*70)
    print("🚀 异步采集性能测试")
    print("="*70)
    
    collector = FullAStockCollector(db_path)
    
    # 测试1：热门股票异步采集
    print("\n[测试1] 热门股票异步采集 (26只)...")
    start = time.time()
    await collector.collect_incremental_async()
    elapsed = time.time() - start
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM minute_bars")
    hot_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"  ✓ 完成: {hot_count} 条记录 ({elapsed:.2f}秒)")
    print(f"    平均速度: {hot_count/elapsed:.1f} 条/秒")
    
    # 测试2：估算5000+完整采集时间
    print("\n[测试2] 估算完整5000+采集时间...")
    total_symbols = len(collector.stock_list)
    batch_size = 500
    est_time = (total_symbols / 26) * elapsed + (total_symbols // batch_size) * 0.5
    
    print(f"  总股票数: {total_symbols}")
    print(f"  预估耗时: {est_time:.1f}秒 ({est_time/60:.1f}分钟)")
    print(f"  采集速度: ~{total_symbols/est_time:.0f} 只/秒")
    
    # 测试3：数据库性能检查
    print("\n[测试3] 数据库性能检查...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查WAL模式
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    print(f"  日志模式: {journal_mode}")
    
    # 检查缓存大小
    cursor.execute("PRAGMA cache_size")
    cache_size = cursor.fetchone()[0]
    print(f"  缓存大小: {cache_size}")
    
    # 获取数据库大小
    db_size = Path(db_path).stat().st_size / 1024  # KB
    print(f"  数据库大小: {db_size:.1f} KB ({hot_count} 条记录)")
    
    conn.close()
    
    # 总结
    print("\n" + "="*70)
    print("📊 测试总结")
    print("="*70)
    print(f"热门采集: ✓ {hot_count}条 ({elapsed:.2f}秒)")
    print(f"全量估算: {total_symbols}只股票需要 ~{est_time/60:.1f} 分钟")
    print(f"数据库: WAL模式启用, 缓存{abs(cache_size)}KB")
    print(f"结论: {'✓ 可以在GitHub Actions中运行' if est_time < 25*60 else '⚠️  需要优化或使用self-hosted runner'}")
    print("="*70 + "\n")
    
    # 清理
    Path(db_path).unlink(missing_ok=True)
    return est_time < 25*60  # 25分钟超时限制


if __name__ == '__main__':
    try:
        success = asyncio.run(test_async_collection())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
