#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步高并发数据采集模块 - 支持5000+股票的快速采集

特点：
- 基于aiohttp实现异步并发请求
- 支持代理和UA轮换
- 自动主源/备源切换
- WAL数据库优化并发写入

Usage:
    async with AsyncMultiSourceCollector(db_path) as collector:
        results = await collector.collect_batch_async(symbols)
"""

import asyncio
import aiohttp
import re
import os
import random
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认 User-Agent 列表
DEFAULT_UAS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
]


class AsyncMultiSourceCollector:
    """异步多源数据采集器 - 支持高并发"""
    
    # API端点
    SINA_API = "https://hq.sinajs.cn/list={symbols}"
    TENCENT_API = "https://qt.gtimg.cn/q={symbols}"
    
    # 并发参数
    MAX_SYMBOLS_PER_REQUEST = 50  # 单次请求最多符号数
    MAX_CONCURRENT_REQUESTS = 20  # 最多同时请求数
    REQUEST_TIMEOUT = 10  # 请求超时(秒)
    
    def __init__(self, db_path='logs/quotes.db'):
        self.db_path = db_path
        self.request_count = 0
        self.proxies = {}
        self.headers = {}
        self._setup_headers()
        self.session = None
        self.connector = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.connector = aiohttp.TCPConnector(
            limit_per_host=self.MAX_CONCURRENT_REQUESTS, 
            limit=200
        )
        self.session = aiohttp.ClientSession(connector=self.connector)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
    
    @staticmethod
    def _to_int(value):
        """安全的整数转换"""
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    
    def _setup_headers(self):
        """设置请求头和代理配置"""
        ua = os.getenv('FORCE_UA') or random.choice(DEFAULT_UAS)
        self.headers = {
            'User-Agent': ua,
            'Referer': 'http://finance.sina.com.cn',
        }
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if http_proxy:
            self.proxies['http'] = http_proxy
        if https_proxy:
            self.proxies['https'] = https_proxy
    
    async def _fetch_batch_async(self, batch: List[str], api_url: str, 
                                  parser_func) -> Dict[str, Dict]:
        """
        异步获取单个批次数据
        
        Args:
            batch: 股票代码列表
            api_url: API模板URL
            parser_func: 解析函数
        
        Returns:
            {symbol: {quote_data}}
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager")
        
        results = {}
        symbol_str = ','.join(batch)
        url = api_url.format(symbols=symbol_str)
        
        try:
            headers = self.headers.copy()
            headers['User-Agent'] = random.choice(DEFAULT_UAS)
            proxy = self.proxies.get('https') or self.proxies.get('http')
            
            async with self.session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT),
                proxy=proxy
            ) as response:
                if response.status == 403:
                    raise Exception(f"API 403 Forbidden")
                response.raise_for_status()
                text = await response.text(errors='ignore')
                results = parser_func(text)
                self.request_count += len(results)
                
        except Exception as e:
            logger.warning(f"异步请求失败 {batch[:3]}...: {e}")
        
        return results
    
    def _parse_sina_response(self, text: str) -> Dict[str, Dict]:
        """解析新浪API响应"""
        results = {}
        lines = text.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            match = re.search(r'hq_str_(\w+)="([^"]+)"', line)
            if match:
                code = match.group(1)
                data = match.group(2).split(',')
                if len(data) >= 8:
                    try:
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
                    except (ValueError, IndexError):
                        continue
        
        return results
    
    def _parse_tencent_response(self, text: str) -> Dict[str, Dict]:
        """解析腾讯API响应"""
        results = {}
        lines = text.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            payload = parts[1].strip('";')
            fields = payload.split('~')
            if len(fields) < 10:
                continue
            
            try:
                code = fields[2]
                price = float(fields[3])
                prev_close = float(fields[4]) if fields[4] else price
                open_p = float(fields[5]) if fields[5] else prev_close
                high = float(fields[6]) if fields[6] else price
                low = float(fields[7]) if fields[7] else price
                volume = self._to_int(fields[8]) * 100
                amount = self._to_int(fields[9])
                
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
            except (ValueError, IndexError):
                continue
        
        return results
    
    async def fetch_sina_async(self, symbols: List[str]) -> Dict[str, Dict]:
        """异步从新浪API采集"""
        results = {}
        
        tasks = []
        for i in range(0, len(symbols), self.MAX_SYMBOLS_PER_REQUEST):
            batch = symbols[i:i+self.MAX_SYMBOLS_PER_REQUEST]
            task = self._fetch_batch_async(
                batch, 
                self.SINA_API, 
                self._parse_sina_response
            )
            tasks.append(task)
        
        # 并发执行
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch_result in batch_results:
                if isinstance(batch_result, dict):
                    results.update(batch_result)
        
        return results
    
    async def fetch_tencent_async(self, symbols: List[str]) -> Dict[str, Dict]:
        """异步从腾讯API采集"""
        results = {}
        
        tasks = []
        for i in range(0, len(symbols), self.MAX_SYMBOLS_PER_REQUEST):
            batch = symbols[i:i+self.MAX_SYMBOLS_PER_REQUEST]
            task = self._fetch_batch_async(
                batch,
                self.TENCENT_API,
                self._parse_tencent_response
            )
            tasks.append(task)
        
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch_result in batch_results:
                if isinstance(batch_result, dict):
                    results.update(batch_result)
        
        return results
    
    async def collect_batch_async(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        异步批量采集 - 主源+备源自动切换
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            采集结果字典
        """
        try:
            logger.info(f"尝试从新浪API异步采集 {len(symbols)} 只股票...")
            results = await self.fetch_sina_async(symbols)
            if results:
                logger.info(f"✓ 新浪API采集成功: {len(results)} 只")
                return results
            logger.warning("新浪API返回空数据，尝试备源...")
        except Exception as e:
            logger.error(f"新浪API采集失败: {e}")
        
        try:
            logger.info(f"尝试从腾讯API异步采集 {len(symbols)} 只股票...")
            results = await self.fetch_tencent_async(symbols)
            if results:
                logger.info(f"✓ 腾讯API采集成功: {len(results)} 只")
                return results
        except Exception as e:
            logger.error(f"腾讯API采集失败: {e}")
        
        return {}
