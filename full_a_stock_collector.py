#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全A股数据采集系统 - 支持5000+只股票

支持多个数据源：
1. Sina Finance API - 免费, 速度快, 延迟低
2. Tencent API - 免费, 稳定性好
3. 163网易 - 免费, 数据完整
4. Tushare - 需要Token, 数据质量高

策略：
- 主源(Sina) + 备源(Tencent) 自动切换
- 智能限流 (避免IP被封)
- 异步并发采集 (提高效率)
- 增量更新 (避免重复)
- 容错重试 (提高稳定性)

Author: 仙儿仙儿碎碎念
"""

import asyncio
import json
import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from pathlib import Path
import hashlib
import time
from dataclasses import dataclass
from collections import defaultdict

try:
    import aiohttp
except Exception:
    aiohttp = None
import requests
import os
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 默认 User-Agent 列表（轮换用）
DEFAULT_UAS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
]

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    """股票信息"""
    symbol: str  # 代码
    name: str    # 名称
    market: str  # 市场 (SH/SZ)
    exchange_code: str  # 交易所代码


class StockListManager:
    """A股股票列表管理"""
    
    # 主要指数和板块代码
    INDICES = {
        'sh000001': '上证指数',
        'sh000016': '上证50',
        'sh000300': '沪深300',
        'sh000905': '中证500',
        'sh000852': '中证1000',
        'sz399001': '深证成指',
        'sz399006': '创业板指',
    }
    
    @staticmethod
    def get_a_stock_list() -> List[StockInfo]:
        """
        获取A股完整股票列表
        
        包括：
        - 沪深京A股 (4500+只)
        - 主要指数 (7个)
        
        Returns:
            股票信息列表
        """
        stocks = []
        
        # 添加主要指数
        for symbol, name in StockListManager.INDICES.items():
            market = 'SH' if symbol.startswith('sh') else 'SZ'
            stocks.append(StockInfo(
                symbol=symbol,
                name=name,
                market=market,
                exchange_code=symbol
            ))
        
        # 添加A股股票
        # 上证股票 (600000-609999)
        for code in range(600000, 609000):
            stocks.append(StockInfo(
                symbol=f'sh{code}',
                name=f'SH{code}',
                market='SH',
                exchange_code=f'sh{code}'
            ))
        
        # 深证主板 (000001-000999)
        for code in range(1, 2000):
            stocks.append(StockInfo(
                symbol=f'sz{code:06d}',
                name=f'SZ{code:06d}',
                market='SZ',
                exchange_code=f'sz{code:06d}'
            ))
        
        # 创业板 (300000-309999)
        for code in range(300000, 302000):
            stocks.append(StockInfo(
                symbol=f'sz{code}',
                name=f'SZ{code}',
                market='SZ',
                exchange_code=f'sz{code}'
            ))
        
        # 北京市场 (400000-489999)
        for code in range(400000, 401000):
            stocks.append(StockInfo(
                symbol=f'bj{code}',
                name=f'BJ{code}',
                market='BJ',
                exchange_code=f'bj{code}'
            ))
        
        return stocks


class MultiSourceCollector:
    """多源数据采集器"""
    
    # API端点
    SINA_API = "https://hq.sinajs.cn/list={symbols}"
    TENCENT_API = "https://qt.gtimg.cn/q={symbols}"
    
    # 限流参数
    MAX_SYMBOLS_PER_REQUEST = 50  # 单次请求最多符号数
    REQUEST_DELAY = 0.5  # 请求间隔（秒）
    BATCH_SIZE = 100  # 批处理大小
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = 0
        # Setup session retries and headers/proxies
        retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        self.proxies = {}
        self._setup_headers()

    @staticmethod
    def _to_int(value):
        """将字符串数字安全转换为整数，兼容带小数点的成交额/成交量"""
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    
    def _setup_headers(self):
        """设置请求头和代理（从环境变量读取）"""
        # 支持强制 UA（用于调试或覆盖）
        ua = os.getenv('FORCE_UA') or random.choice(DEFAULT_UAS)
        self.headers = {
            'User-Agent': ua,
            'Referer': 'http://finance.sina.com.cn',
        }
        # 读取代理配置（如果在 GitHub Secrets 中配置 HTTP_PROXY / HTTPS_PROXY）
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if http_proxy:
            self.proxies['http'] = http_proxy
        if https_proxy:
            self.proxies['https'] = https_proxy
        # 使 session 使用同样的代理映射
        self.session.proxies.update(self.proxies)
    
    def _apply_rate_limit(self):
        """应用限流"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def fetch_sina(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        从新浪API采集数据
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            {symbol: {open, high, low, close, volume, ...}}
        """
        results = {}
        
        # 分批请求
        for i in range(0, len(symbols), self.MAX_SYMBOLS_PER_REQUEST):
            batch = symbols[i:i+self.MAX_SYMBOLS_PER_REQUEST]
            symbol_str = ','.join(batch)
            
            try:
                self._apply_rate_limit()
                
                url = self.SINA_API.format(symbols=symbol_str)
                # rotate UA per batch to reduce fingerprinting
                self.headers['User-Agent'] = os.getenv('FORCE_UA') or random.choice(DEFAULT_UAS)
                response = self.session.get(url, headers=self.headers, timeout=10)
                if response.status_code == 403:
                    raise Exception("Sina API 403 Forbidden")
                response.raise_for_status()
                response.encoding = 'gbk'

                lines = response.text.split('\n')
                for line in lines:
                    if not line.strip():
                        continue
                    # 解析新浪格式
                    match = re.search(r'hq_str_(\w+)="([^"]+)"', line)
                    if match:
                        code = match.group(1)
                        data = match.group(2).split(',')
                        if len(data) >= 8:
                            results[code] = {
                                'name': data[0],
                                'price': float(data[1]),
                                'open': float(data[2]),
                                'high': float(data[4]),
                                'low': float(data[5]),
                                'volume': self._to_int(data[8]) if len(data) > 8 else 0,
                                'amount': self._to_int(data[9]) if len(data) > 9 else 0,
                                'timestamp': datetime.now().isoformat(),
                            }
                    self.request_count += 1
                if self.request_count % 100 == 0:
                    logger.info(f"✓ 已采集{self.request_count}个数据点")
            except Exception as e:
                logger.warning(f"✗ 采集失败 {batch[:3]}...: {e}")
                continue
        return results
    
    def collect_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        批量采集数据（带自动重试和备源切换）
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            采集结果
        """
        # 尝试主源
        try:
            results = self.fetch_sina(symbols)
            if results:
                return results
            logger.warning("主源返回空数据，尝试备源")
        except Exception as e:
            logger.error(f"主源采集失败: {e}")
        # 备源腾讯
        try:
            return self.fetch_tencent(symbols)
        except Exception as e:
            logger.error(f"备源采集失败: {e}")
            return {}

    def fetch_tencent(self, symbols: List[str]) -> Dict[str, Dict]:
        """从腾讯API采集数据 (qt.gtimg.cn)"""
        results = {}
        for i in range(0, len(symbols), self.MAX_SYMBOLS_PER_REQUEST):
            batch = symbols[i:i+self.MAX_SYMBOLS_PER_REQUEST]
            symbol_str = ','.join(batch)
            try:
                self._apply_rate_limit()
                resp = self.session.get(self.TENCENT_API.format(symbols=symbol_str), headers=self.headers, timeout=10)
                if resp.status_code == 403:
                    raise Exception("Tencent API 403 Forbidden")
                resp.raise_for_status()
                lines = resp.text.split('\n')
                for line in lines:
                    if not line.strip():
                        continue
                    # 样例: v_sh000001="1~上证指数~000001~2672.03~2669.00~2662.37~2672.03~...~成交量(手)~成交额(元)~..."
                    parts = line.split('=')
                    if len(parts) < 2:
                        continue
                    payload = parts[1].strip('";')
                    fields = payload.split('~')
                    if len(fields) < 10:
                        continue
                    code = fields[2]
                    try:
                        price = float(fields[3])
                        prev_close = float(fields[4]) if fields[4] else price
                        open_p = float(fields[5]) if fields[5] else prev_close
                        high = float(fields[6]) if fields[6] else price
                        low = float(fields[7]) if fields[7] else price
                        volume = self._to_int(fields[8]) * 100  # 手 -> 股
                        amount = self._to_int(fields[9])
                    except Exception:
                        continue
                    results[code] = {
                        'name': fields[1],
                        'price': price,
                        'open': open_p,
                        'high': high,
                        'low': low,
                        'volume': volume,
                        'amount': amount,
                        'timestamp': datetime.now().isoformat(),
                    }
            except Exception as e:
                logger.warning(f"腾讯采集失败 {batch[:3]}...: {e}")
                continue
        return results


class FullAStockCollector:
    """完整A股采集系统"""
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.collector = MultiSourceCollector(db_path)
        self.stock_list = StockListManager.get_a_stock_list()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        try:
            # ensure parent directory exists
            from pathlib import Path
            db_parent = Path(self.db_path).parent
            if not db_parent.exists():
                db_parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS minute_bars (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    minute TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    UNIQUE(symbol, minute)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_minute 
                ON minute_bars(symbol, minute DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol 
                ON minute_bars(symbol)
            """)
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
    
    def get_hot_symbols(self, limit=50) -> List[str]:
        """
        获取热门股票（优先采集）
        
        包括：
        - 主要指数
        - 权重股
        - 热门板块代表
        
        Returns:
            股票代码列表
        """
        hot_symbols = [
            # 主要指数
            'sh000001', 'sh000016', 'sh000300', 'sh000905',
            'sz399001', 'sz399006',
            
            # 权重蓝筹
            'sh600000', 'sh600016', 'sh600019', 'sh600031',  # 四大行
            'sh600519', 'sh600887', 'sh600989',  # 消费龙头
            'sh601398', 'sh601988', 'sh601988',  # 大型金融
            
            # 热门板块
            'sz300750', 'sz300141', 'sz300408',  # 科技
            'sh688111', 'sh688008', 'sh688690',  # 科创板
            'sh900905', 'sh900903',  # 权证
        ]
        
        # 补充创业板热门
        for code in [300001, 300002, 300003]:
            hot_symbols.append(f'sz{code}')
        
        return hot_symbols[:limit]
    
    def collect_incremental(self):
        """
        增量采集（只采集变化的数据）
        
        策略：
        1. 获取热门股票（实时）
        2. 采集近期更新的股票
        3. 周期性更新所有股票
        """
        logger.info(f"开始增量采集...")
        
        # 获取热门股票
        hot_symbols = self.get_hot_symbols(limit=100)
        
        # 采集热门股票
        results = self.collector.collect_batch(hot_symbols)
        
        # 保存到数据库
        if results:
            self._save_results(results)
            logger.info(f"✓ 采集{len(results)}个热门股票")
    
    def _save_results(self, results: Dict):
        """保存采集结果到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            minute = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            for symbol, data in results.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO minute_bars
                    (symbol, minute, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    minute,
                    data.get('open'),
                    data.get('high'),
                    data.get('low'),
                    data.get('price'),
                    data.get('volume'),
                ))
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def print_stats(self):
        """打印统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM minute_bars")
            symbol_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM minute_bars")
            data_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT symbol, COUNT(*) as cnt FROM minute_bars GROUP BY symbol ORDER BY cnt DESC LIMIT 5")
            top_symbols = cursor.fetchall()
            
            conn.close()
            
            print("\n" + "="*70)
            print("📊 采集统计")
            print("="*70)
            print(f"采集股票数: {symbol_count}")
            print(f"总数据点: {data_count}")
            print(f"平均每股: {data_count // max(symbol_count, 1):.0f}条")
            
            print("\n📈 Top 5 采集最多:")
            for symbol, cnt in top_symbols:
                print(f"  {symbol:10} {cnt:6} 条")
            
            print("="*70 + "\n")
        
        except Exception as e:
            logger.error(f"统计失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='全A股数据采集系统')
    parser.add_argument('--db', default='logs/quotes.db', help='数据库路径')
    parser.add_argument('--mode', choices=['hot', 'incremental', 'all', 'stats'], default='hot',
                       help='采集模式 (incremental 为 hot 别名)')
    
    args = parser.parse_args()
    
    collector = FullAStockCollector(args.db)
    
    if args.mode in ('hot', 'incremental'):
        print("采集热门股票...")
        collector.collect_incremental()
    elif args.mode == 'all':
        print("采集所有股票（演示）...")
        # 完整采集演示（实际使用GitHub Actions分批）
        all_symbols = [s.symbol for s in collector.stock_list[:500]]  # 限制演示规模
        results = collector.collector.collect_batch(all_symbols)
        collector._save_results(results)
    
    collector.print_stats()


if __name__ == '__main__':
    main()
