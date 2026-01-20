#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库性能优化模块

优化方案:
1. 分表存储 - 按日期/市场分表
2. 索引优化 - 多级索引加速查询
3. 分区存储 - 冷热数据分离
4. 批量操作 - 减少事务次数
5. 连接池 - 复用连接

目标：
- 50000+只股票 × 1000条数据 = 5000万条记录
- 查询响应时间 < 100ms
- 写入吞吐量 > 10000条/秒

Author: 仙儿仙儿碎碎念
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """数据库优化器"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
    
    def create_optimized_schema(self):
        """创建优化的数据库结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 主表 - 分表存储
        # 按日期分表: minute_bars_20260120, minute_bars_20260121, ...
        
        # 创建基础表（最新数据）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minute_bars (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                minute TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                amount INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, minute)
            )
        """)
        
        # 2. 优化的索引
        cursor.executescript("""
            CREATE INDEX IF NOT EXISTS idx_symbol_time 
            ON minute_bars(symbol, minute DESC);
            
            CREATE INDEX IF NOT EXISTS idx_time 
            ON minute_bars(minute DESC);
            
            CREATE INDEX IF NOT EXISTS idx_symbol 
            ON minute_bars(symbol);
            
            CREATE INDEX IF NOT EXISTS idx_close 
            ON minute_bars(close);
        """)
        
        # 3. 分型表（存储已识别的分型）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fractals (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                minute TEXT NOT NULL,
                fractal_type TEXT NOT NULL,  -- 'top' or 'bottom'
                high REAL,
                low REAL,
                close REAL,
                strength REAL,  -- 分型强度 0-1
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fractals_symbol_time 
            ON fractals(symbol, minute DESC)
        """)
        
        # 4. 信号表（存储交易信号）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                signal_time TEXT NOT NULL,
                signal_type TEXT NOT NULL,  -- 'buy' or 'sell'
                price REAL NOT NULL,
                confidence REAL,  -- 信心度 0-1
                reason TEXT,
                status TEXT DEFAULT 'pending',  -- pending/active/closed
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_symbol_status 
            ON signals(symbol, status)
        """)
        
        # 5. 统计表（缓存统计数据）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                fractal_count INTEGER,
                signal_count INTEGER,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        
        # 6. 健康检查表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_check (
                id INTEGER PRIMARY KEY,
                check_time TEXT NOT NULL,
                total_symbols INTEGER,
                total_records INTEGER,
                last_update TEXT,
                status TEXT,
                notes TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✓ 优化的数据库结构已创建")
    
    def enable_optimizations(self):
        """启用数据库优化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 启用事务支持
        cursor.execute("PRAGMA journal_mode = WAL")  # 预写日志模式
        
        # 增加缓存
        cursor.execute("PRAGMA cache_size = -64000")  # 64MB
        
        # 关键路径模式
        cursor.execute("PRAGMA query_only = OFF")
        cursor.execute("PRAGMA synchronous = NORMAL")  # 牺牲一点安全性换性能
        
        # 临时表使用内存
        cursor.execute("PRAGMA temp_store = MEMORY")
        
        conn.commit()
        conn.close()
        
        logger.info("✓ 数据库优化参数已应用")
    
    def analyze_tables(self):
        """分析表统计（提升查询优化）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("ANALYZE")
        
        conn.commit()
        conn.close()
        
        logger.info("✓ 表统计分析完成")
    
    def batch_insert(self, table: str, records: list, batch_size=1000):
        """
        批量插入数据
        
        Args:
            table: 表名
            records: 记录列表 [{col: value, ...}, ...]
            batch_size: 批量大小
        """
        if not records:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取列名
        columns = list(records[0].keys())
        placeholders = ','.join(['?' for _ in columns])
        
        insert_sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        # 分批插入
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            values = [tuple(r.get(col) for col in columns) for r in batch]
            
            cursor.executemany(insert_sql, values)
            conn.commit()
            
            if i % 5000 == 0:
                logger.info(f"✓ 已插入{i+len(batch)}/{len(records)}条记录")
        
        conn.close()
    
    def vacuum_database(self):
        """清理和优化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("VACUUM")  # 重新整理数据库
        
        conn.commit()
        conn.close()
        
        logger.info("✓ 数据库清理完成")
    
    def get_health_status(self):
        """获取数据库健康状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 统计数据
        cursor.execute("SELECT COUNT(DISTINCT symbol), COUNT(*) FROM minute_bars")
        symbols, records = cursor.fetchone()
        
        cursor.execute("SELECT MAX(minute) FROM minute_bars")
        last_update = cursor.fetchone()[0]
        
        cursor.execute("SELECT SIZE FROM (SELECT SUM(pgsize) AS SIZE FROM dbstat)")
        try:
            db_size = cursor.fetchone()[0]
        except:
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        conn.close()
        
        health = {
            'timestamp': datetime.now().isoformat(),
            'symbols_count': symbols,
            'total_records': records,
            'avg_records_per_symbol': records // max(symbols, 1) if symbols > 0 else 0,
            'last_update': last_update,
            'db_size_mb': db_size / (1024 * 1024) if db_size else 0,
            'status': 'HEALTHY' if symbols > 0 and records > 0 else 'UNHEALTHY',
        }
        
        return health
    
    def optimize_all(self):
        """执行完整优化"""
        logger.info("开始数据库优化...")
        
        self.create_optimized_schema()
        self.enable_optimizations()
        self.analyze_tables()
        self.vacuum_database()
        
        health = self.get_health_status()
        
        print("\n" + "="*70)
        print("📊 数据库健康状态")
        print("="*70)
        for key, value in health.items():
            if isinstance(value, float):
                print(f"  {key:.<40} {value:.2f}")
            else:
                print(f"  {key:.<40} {value}")
        print("="*70 + "\n")
        
        return health


class ConnectionPool:
    """数据库连接池"""
    
    def __init__(self, db_path='logs/quotes.db', pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = []
        self._init_pool()
    
    def _init_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connections.append(conn)
    
    def get_connection(self):
        """获取连接"""
        if self.connections:
            return self.connections.pop()
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def return_connection(self, conn):
        """归还连接"""
        if len(self.connections) < self.pool_size:
            self.connections.append(conn)
        else:
            conn.close()
    
    def close_all(self):
        """关闭所有连接"""
        for conn in self.connections:
            conn.close()
        self.connections.clear()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库优化工具')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--optimize', action='store_true', help='执行优化')
    parser.add_argument('--health', action='store_true', help='检查健康状态')
    parser.add_argument('--vacuum', action='store_true', help='数据库清理')
    
    args = parser.parse_args()
    
    optimizer = DatabaseOptimizer(args.db)
    
    if args.optimize:
        optimizer.optimize_all()
    elif args.health:
        health = optimizer.get_health_status()
        print("\n数据库健康报告:")
        print(json.dumps(health, indent=2, ensure_ascii=False))
    elif args.vacuum:
        optimizer.vacuum_database()
    else:
        optimizer.create_optimized_schema()
        optimizer.enable_optimizations()


if __name__ == '__main__':
    import json
    main()
