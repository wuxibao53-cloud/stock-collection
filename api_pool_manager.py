#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API池管理器 - 1000个备用API/代理轮转

当检测到API调用异常时：
1. 立刻标记当前API为"故障"
2. 自动切换到下一个备用API
3. 支持代理轮转、重试策略、错误恢复
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from collections import defaultdict
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIPool:
    """API池管理器 - 支持1000个备用API"""
    
    def __init__(self, config_file: str = 'api_pool.json'):
        self.config_file = config_file
        self.apis: List[Dict] = []
        self.current_index = 0
        self.api_lock = threading.Lock()
        
        # 统计信息
        self.stats = defaultdict(lambda: {
            'success': 0,
            'failed': 0,
            'last_error': None,
            'last_failed_time': None,
            'disabled_until': None,
            'error_count': 0,
        })
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从文件加载API池配置"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.apis = config.get('apis', [])
            
            if not self.apis:
                logger.warning(f"未找到API配置，创建模板文件: {self.config_file}")
                self._create_template()
                return
            
            logger.info(f"✓ 加载了 {len(self.apis)} 个API")
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_file}")
            self._create_template()
    
    def _create_template(self):
        """创建模板配置文件"""
        template = {
            "apis": [
                {
                    "id": 1,
                    "type": "proxy",
                    "url": "http://proxy1.example.com:8080",
                    "enabled": True
                },
                {
                    "id": 2,
                    "type": "proxy",
                    "url": "http://proxy2.example.com:8080",
                    "enabled": True
                },
                # ... 更多API/代理
                {
                    "id": 1000,
                    "type": "proxy",
                    "url": "http://proxy1000.example.com:8080",
                    "enabled": True
                }
            ],
            "strategy": "round_robin",  # 轮转策略
            "retry_count": 3,
            "retry_delay": 1,
            "fallback_to_direct": True,  # 所有API失败后回退到直连
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ 已创建模板文件: {self.config_file}")
        logger.info("📌 请填充1000个备用API/代理到 apis 数组中")
    
    def get_current_api(self) -> Optional[Dict]:
        """获取当前可用的API"""
        with self.api_lock:
            if not self.apis:
                return None
            
            # 轮转找到一个可用的API
            attempts = 0
            while attempts < len(self.apis):
                api = self.apis[self.current_index]
                
                # 检查API是否被禁用
                if not api.get('enabled', True):
                    self.current_index = (self.current_index + 1) % len(self.apis)
                    attempts += 1
                    continue
                
                # 检查API是否在冷却期
                api_id = api.get('id', self.current_index)
                disabled_until = self.stats[api_id]['disabled_until']
                
                if disabled_until and datetime.now() < disabled_until:
                    # 仍在冷却期，跳过
                    self.current_index = (self.current_index + 1) % len(self.apis)
                    attempts += 1
                    continue
                
                # 找到可用API
                logger.debug(f"使用 API #{api_id}")
                return api
            
            # 所有API都不可用
            logger.error("❌ 所有API都不可用（都在冷却期）")
            return None
    
    def rotate_api(self) -> Optional[Dict]:
        """切换到下一个API"""
        with self.api_lock:
            if not self.apis:
                return None
            
            self.current_index = (self.current_index + 1) % len(self.apis)
            logger.info(f"🔄 轮转到API #{self.current_index + 1}/{len(self.apis)}")
            return self.get_current_api()
    
    def mark_api_success(self, api_id: Optional[int] = None):
        """标记API调用成功"""
        if api_id is None:
            api = self.get_current_api()
            if api:
                api_id = api.get('id', self.current_index)
        
        with self.api_lock:
            self.stats[api_id]['success'] += 1
            self.stats[api_id]['error_count'] = 0  # 重置错误计数
            self.stats[api_id]['disabled_until'] = None  # 清除禁用状态
    
    def mark_api_failed(self, api_id: Optional[int] = None, error: str = None):
        """标记API调用失败"""
        if api_id is None:
            api = self.get_current_api()
            if api:
                api_id = api.get('id', self.current_index)
        
        with self.api_lock:
            self.stats[api_id]['failed'] += 1
            self.stats[api_id]['error_count'] += 1
            self.stats[api_id]['last_error'] = error
            self.stats[api_id]['last_failed_time'] = datetime.now()
            
            # 错误计数达到阈值时禁用API（冷却2-5分钟）
            error_count = self.stats[api_id]['error_count']
            if error_count >= 3:
                cooldown_minutes = min(5, error_count - 2)  # 最多冷却5分钟
                self.stats[api_id]['disabled_until'] = datetime.now() + timedelta(minutes=cooldown_minutes)
                logger.warning(f"⚠️  API #{api_id} 连续失败 {error_count} 次，冷却 {cooldown_minutes} 分钟")
    
    def get_stats(self, api_id: Optional[int] = None) -> Dict:
        """获取统计信息"""
        if api_id is not None:
            return self.stats.get(api_id, {})
        
        # 返回所有统计
        return dict(self.stats)
    
    def print_stats(self):
        """打印统计信息"""
        logger.info("\n" + "="*80)
        logger.info("【API池统计】")
        logger.info("="*80)
        
        stats = self.get_stats()
        
        # 按成功率排序
        sorted_apis = sorted(
            stats.items(),
            key=lambda x: x[1]['success'] / max(1, x[1]['success'] + x[1]['failed']),
            reverse=True
        )
        
        for api_id, stat in sorted_apis[:20]:  # 只显示前20个
            total = stat['success'] + stat['failed']
            if total == 0:
                continue
            
            success_rate = stat['success'] / total * 100
            status = "✓ 正常" if success_rate >= 80 else "⚠️  故障" if success_rate >= 50 else "❌ 禁用"
            
            disabled_until = stat['disabled_until']
            cooldown_info = ""
            if disabled_until and datetime.now() < disabled_until:
                remaining = (disabled_until - datetime.now()).total_seconds()
                cooldown_info = f" (冷却中, {remaining:.0f}秒)"
            
            logger.info(f"API #{api_id}: {stat['success']}成功 / {stat['failed']}失败 "
                       f"({success_rate:.0f}%) {status}{cooldown_info}")


class APIRetryStrategy:
    """API重试策略"""
    
    def __init__(self, pool: APIPool):
        self.pool = pool
        self.max_retries = 3
        self.base_delay = 0.5  # 基础延迟
    
    def call_with_retry(self, func, *args, **kwargs) -> Optional[any]:
        """
        使用重试策略调用API
        
        示例：
            pool = APIPool()
            strategy = APIRetryStrategy(pool)
            df = strategy.call_with_retry(ak.stock_zh_a_hist_min_em, symbol='000001', period='30')
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                api = self.pool.get_current_api()
                if not api:
                    logger.error("❌ 无可用API")
                    return None
                
                # 设置代理
                if api.get('type') == 'proxy' and api.get('url'):
                    proxies = {
                        'http': api['url'],
                        'https': api['url']
                    }
                    kwargs['proxies'] = proxies
                
                # 调用函数
                result = func(*args, **kwargs)
                
                # 成功
                self.pool.mark_api_success()
                logger.debug(f"✓ API调用成功 (尝试 {attempt + 1}/{self.max_retries})")
                return result
            
            except Exception as e:
                last_error = str(e)
                self.pool.mark_api_failed(error=last_error)
                
                logger.warning(f"❌ API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {type(e).__name__}")
                
                # 轮转到下一个API
                self.pool.rotate_api()
                
                # 等待后重试
                if attempt < self.max_retries - 1:
                    wait_time = self.base_delay * (2 ** attempt)  # 指数退避
                    logger.info(f"等待 {wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败
        logger.error(f"❌ API调用最终失败 (已尝试 {self.max_retries} 次)")
        logger.error(f"最后错误: {last_error}")
        
        return None


# 全局API池实例
_api_pool: Optional[APIPool] = None
_retry_strategy: Optional[APIRetryStrategy] = None


def get_api_pool() -> APIPool:
    """获取全局API池实例"""
    global _api_pool
    if _api_pool is None:
        _api_pool = APIPool()
    return _api_pool


def get_retry_strategy() -> APIRetryStrategy:
    """获取全局重试策略实例"""
    global _retry_strategy
    if _retry_strategy is None:
        _retry_strategy = APIRetryStrategy(get_api_pool())
    return _retry_strategy


if __name__ == '__main__':
    # 演示用法
    pool = APIPool()
    
    logger.info("🚀 API池管理器演示")
    logger.info(f"已加载 {len(pool.apis)} 个API")
    
    # 模拟API调用
    for i in range(10):
        api = pool.get_current_api()
        if api:
            logger.info(f"\n--- 模拟调用 {i+1} ---")
            logger.info(f"当前API: #{api.get('id', '?')}")
            
            # 随机模拟成功或失败
            if i % 3 == 0:
                pool.mark_api_failed(error="ConnectionError")
                logger.info("标记为失败，轮转API")
                pool.rotate_api()
            else:
                pool.mark_api_success()
                logger.info("标记为成功")
            
            time.sleep(0.5)
    
    # 打印统计
    pool.print_stats()
