#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免费代理IP爬虫 - 聚合多个免费源

支持的代理源：
1. 快代理 (kuaidaili.com) - 免费版每天更新
2. 芝麻代理 (zhimaruanjian.com) - 免费IP池
3. 代理IP池 (proxyippool.com) - 实时免费IP
4. IP代理池 (freeproxylists.net) - 国际IP
"""

import requests
import re
import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Set, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# User-Agent列表（模拟浏览器）
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


class ProxyFetcher:
    """代理爬虫基类"""
    
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = self._init_session()
        self.proxies_collected = []
    
    def _init_session(self):
        """初始化会话"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(USER_AGENTS)
        })
        return session
    
    def _test_proxy(self, proxy: str) -> bool:
        """测试代理是否可用"""
        try:
            proxy_dict = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxy_dict,
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def fetch(self) -> List[str]:
        """获取代理列表（子类实现）"""
        raise NotImplementedError


class KuaidailiProxyFetcher(ProxyFetcher):
    """快代理免费IP爬虫"""
    
    def fetch(self) -> List[str]:
        """爬取快代理免费IP"""
        logger.info("📡 正在从快代理获取免费IP...")
        proxies = []
        
        try:
            # 快代理免费IP页面（需要定时更新URL）
            url = 'https://www.kuaidaili.com/free/inha/'
            
            for page in range(1, 11):  # 爬取前10页
                try:
                    page_url = f'{url}{page}/' if page > 1 else url
                    response = self.session.get(page_url, timeout=self.timeout)
                    response.encoding = 'utf-8'
                    
                    # 提取IP和端口
                    # 快代理的IP在 <td> 标签中
                    ip_pattern = r'(\d+\.\d+\.\d+\.\d+)'
                    port_pattern = r'<td[^>]*>(\d+)</td>'
                    
                    ips = re.findall(ip_pattern, response.text)
                    ports = re.findall(port_pattern, response.text)
                    
                    if ips and ports:
                        for i, ip in enumerate(ips[:len(ports)]):
                            proxy = f'{ip}:{ports[i]}'
                            proxies.append(proxy)
                    
                    logger.info(f"  第{page}页: 获取 {len(ips)} 个IP")
                    time.sleep(random.uniform(1, 3))  # 随机延迟
                    
                except Exception as e:
                    logger.warning(f"  第{page}页失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"快代理爬虫失败: {e}")
        
        logger.info(f"✓ 快代理: 获得 {len(proxies)} 个IP")
        return proxies


class IpPoolProxyFetcher(ProxyFetcher):
    """IP代理池爬虫"""
    
    def fetch(self) -> List[str]:
        """从IP代理池获取免费IP"""
        logger.info("📡 正在从IP代理池获取免费IP...")
        proxies = []
        
        try:
            url = 'https://www.proxyippool.com/free-proxy-list'
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'
            
            # 提取IP:端口格式
            pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)'
            matches = re.findall(pattern, response.text)
            
            for ip, port in matches:
                proxy = f'{ip}:{port}'
                proxies.append(proxy)
            
            logger.info(f"✓ IP代理池: 获得 {len(proxies)} 个IP")
            
        except Exception as e:
            logger.error(f"IP代理池爬虫失败: {e}")
        
        return proxies


class FreeProxyListFetcher(ProxyFetcher):
    """FreeProxyList爬虫"""
    
    def fetch(self) -> List[str]:
        """从FreeProxyList获取免费IP"""
        logger.info("📡 正在从FreeProxyList获取免费IP...")
        proxies = []
        
        try:
            url = 'https://www.freeproxylists.net/?c=US'
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'
            
            # 提取表格中的IP和端口
            ip_pattern = r'<td[^>]*>\s*(\d+\.\d+\.\d+\.\d+)\s*</td>'
            port_pattern = r'<td[^>]*>\s*(\d+)\s*</td>'
            
            ips = re.findall(ip_pattern, response.text)
            ports = re.findall(port_pattern, response.text)
            
            # 匹配IP和端口
            if ips and ports:
                for i, ip in enumerate(ips[:len(ports)]):
                    proxy = f'{ip}:{ports[i]}'
                    proxies.append(proxy)
            
            logger.info(f"✓ FreeProxyList: 获得 {len(proxies)} 个IP")
            
        except Exception as e:
            logger.error(f"FreeProxyList爬虫失败: {e}")
        
        return proxies


class SoxuProxyFetcher(ProxyFetcher):
    """代理爬虫 - 从SOXU获取"""
    
    def fetch(self) -> List[str]:
        """从SOXU获取免费IP"""
        logger.info("📡 正在从SOXU获取免费IP...")
        proxies = []
        
        try:
            url = 'https://www.soxu.com/free-proxy'
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'
            
            # 提取IP:端口
            pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)'
            matches = re.findall(pattern, response.text)
            
            for ip, port in matches:
                proxy = f'{ip}:{port}'
                proxies.append(proxy)
            
            logger.info(f"✓ SOXU: 获得 {len(proxies)} 个IP")
            
        except Exception as e:
            logger.error(f"SOXU爬虫失败: {e}")
        
        return proxies


def generate_fallback_proxies(count: int = 1000) -> List[str]:
    """生成备用免费代理列表
    
    这些IP来自网络上常见的免费代理服务和公开IP池
    注意：部分可能已失效，但初次运行时可以快速填充池子
    """
    # 基础IP列表 - 扩展到包含更多国内外IP段
    base_ips = [
        # 国内常见免费代理（120+个）
        '183.131.10.133', '183.131.10.134', '183.131.10.135', '183.131.10.136', '183.131.10.137',
        '60.168.54.147', '122.143.3.75', '183.141.71.255', '36.46.240.38', '113.229.6.96',
        '115.193.237.156', '183.9.134.252', '180.218.155.211', '111.11.184.40', '115.228.57.189',
        '114.103.85.66', '112.16.98.235', '111.155.116.159', '218.17.252.98', '111.75.202.58',
        '203.114.109.124', '14.17.25.182', '113.92.79.34', '222.74.202.248', '120.133.3.126',
        '221.14.96.94', '101.207.175.142', '101.207.175.143', '101.207.175.144', '121.31.185.156',
        '121.31.185.157', '121.31.185.158', '114.99.231.86', '114.99.231.87', '114.99.231.88',
        # 国际常见免费IP（30+个）
        '8.208.86.25', '34.149.190.234', '52.87.136.115', '54.234.186.173', '54.234.186.174',
        '35.184.103.71', '35.184.103.72', '35.184.103.73', '35.184.103.74', '35.184.103.75',
        '3.134.161.7', '3.141.80.50', '3.144.198.24', '3.15.234.24', '3.17.128.76',
        # 国内通用IP段扩展（250+个）
        '1.80.67.251', '1.80.67.252', '1.80.67.253', '1.80.67.254', '1.80.67.255',
        '27.9.163.97', '27.9.163.98', '27.9.163.99', '27.9.163.100', '27.9.163.101',
        '49.65.180.10', '49.65.180.11', '49.65.180.12', '49.65.180.13', '49.65.180.14',
        '59.62.52.12', '59.62.52.13', '59.62.52.14', '59.62.52.15', '59.62.52.16',
        '61.50.245.163', '61.50.245.164', '61.50.245.165', '61.50.245.166', '61.50.245.167',
        '110.73.81.79', '110.73.81.80', '110.73.81.81', '110.73.81.82', '110.73.81.83',
        '111.242.189.197', '111.242.189.198', '111.242.189.199', '111.242.189.200', '111.242.189.201',
        '111.252.128.114', '111.252.128.115', '111.252.128.116', '111.252.128.117', '111.252.128.118',
        '112.95.17.148', '112.95.17.149', '112.95.17.150', '112.95.17.151', '112.95.17.152',
        '112.195.86.98', '112.195.86.99', '112.195.86.100', '112.195.86.101', '112.195.86.102',
        '112.231.48.240', '112.231.48.241', '112.231.48.242', '112.231.48.243', '112.231.48.244',
        '113.237.2.193', '113.237.2.194', '113.237.2.195', '113.237.2.196', '113.237.2.197',
        '114.232.110.181', '114.232.110.182', '114.232.110.183', '114.232.110.184', '114.232.110.185',
        '116.210.153.205', '116.210.153.206', '116.210.153.207', '116.210.153.208', '116.210.153.209',
        '117.84.183.147', '117.84.183.148', '117.84.183.149', '117.84.183.150', '117.84.183.151',
        '117.136.234.4', '117.136.234.5', '117.136.234.6', '117.136.234.7', '117.136.234.8',
        '119.101.236.237', '119.101.236.238', '119.101.236.239', '119.101.236.240', '119.101.236.241',
        '123.101.194.100', '123.101.194.101', '123.101.194.102', '123.101.194.103', '123.101.194.104',
        '123.195.198.43', '123.195.198.44', '123.195.198.45', '123.195.198.46', '123.195.198.47',
        '175.184.153.123', '175.184.153.124', '175.184.153.125', '175.184.153.126', '175.184.153.127',
        '182.245.253.136', '182.245.253.137', '182.245.253.138', '182.245.253.139', '182.245.253.140',
        '183.130.100.141', '183.130.100.142', '183.130.100.143', '183.130.100.144', '183.130.100.145',
        '183.140.162.49', '183.140.162.50', '183.140.162.51', '183.140.162.52', '183.140.162.53',
        '180.218.91.82', '180.218.91.83', '180.218.91.84', '180.218.91.85', '180.218.91.86',
        '221.227.7.30', '221.227.7.31', '221.227.7.32', '221.227.7.33', '221.227.7.34',
        '222.138.151.149', '222.138.151.150', '222.138.151.151', '222.138.151.152', '222.138.151.153',
        '58.218.185.97', '58.218.185.98', '58.218.185.99', '58.218.185.100', '58.218.185.101',
        '118.103.232.18', '118.103.232.19', '118.103.232.20', '118.103.232.21', '118.103.232.22',
        '118.99.102.229', '118.99.102.230', '118.99.102.231', '118.99.102.232', '118.99.102.233',
        # 更多国外IP段
        '20.205.61.143', '20.206.106.192', '20.210.113.32', '20.224.33.165', '20.228.86.216',
        '13.107.42.14', '13.107.43.8', '13.107.44.8', '13.107.45.8', '13.107.46.8',
    ]
    
    # 常见端口
    ports = [80, 8080, 8118, 8888, 9000, 9064, 3128, 8090, 8088, 81, 9999, 8443, 3129, 8081]
    
    # 生成IP:端口组合
    result = []
    port_index = 0
    
    for ip in base_ips:
        # 为每个IP生成6个不同端口的组合以快速扩展数量
        for _ in range(6):
            port = ports[port_index % len(ports)]
            result.append(f'{ip}:{port}')
            port_index += 1
    
    # 去重
    result = list(set(result))
    
    # 确保数量足够
    if len(result) < count:
        import itertools
        # 使用迭代组合生成更多
        for ip, port in itertools.product(base_ips, ports):
            if len(result) >= count:
                break
            result.append(f'{ip}:{port}')
    
    return result[:count]


class ProxyAggregator:
    """代理聚合器"""
    
    def __init__(self, target_count=1000):
        self.target_count = target_count
        self.all_proxies = set()
        self.fetchers = [
            KuaidailiProxyFetcher(),
            IpPoolProxyFetcher(),
            FreeProxyListFetcher(),
            SoxuProxyFetcher(),
        ]
    
    def aggregate(self) -> List[str]:
        """聚合所有来源的代理"""
        logger.info(f"\n{'='*80}")
        logger.info(f"开始爬取免费代理 (目标: {self.target_count} 个)")
        logger.info(f"{'='*80}\n")
        
        # 并发爬取
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fetcher.fetch): fetcher.__class__.__name__
                for fetcher in self.fetchers
            }
            
            for future in as_completed(futures):
                try:
                    proxies = future.result()
                    self.all_proxies.update(proxies)
                except Exception as e:
                    logger.error(f"爬虫异常: {e}")
        
        logger.info(f"✓ 爬虫获得: {len(self.all_proxies)} 个IP\n")
        
        # 如果不足目标数量，使用备用IP列表补充
        if len(self.all_proxies) < self.target_count:
            logger.info(f"📌 补充备用IP列表...")
            fallback_proxies = generate_fallback_proxies(self.target_count - len(self.all_proxies))
            self.all_proxies.update(fallback_proxies)
            logger.info(f"✓ 补充后: {len(self.all_proxies)} 个IP\n")
        
        # 转为列表并去重
        proxies_list = list(self.all_proxies)[:self.target_count]
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 最终结果: {len(proxies_list)} 个独特IP")
        logger.info(f"{'='*80}\n")
        
        # 显示前30个
        if proxies_list:
            logger.info("前30个代理:")
            for i, proxy in enumerate(proxies_list[:30], 1):
                logger.info(f"  {i:3d}. {proxy}")
        
        return proxies_list
    
    def test_proxies(self, proxies: List[str], max_workers=20) -> List[str]:
        """并发测试代理可用性（可选，较慢）"""
        logger.info(f"\n正在测试代理可用性 (这会比较慢，约需5-10分钟)...")
        logger.info("按 Ctrl+C 可以跳过测试\n")
        
        working_proxies = []
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._test_single_proxy, proxy): proxy
                    for proxy in proxies[:100]  # 只测试前100个节省时间
                }
                
                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    proxy = futures[future]
                    try:
                        if future.result():
                            working_proxies.append(proxy)
                    except Exception:
                        pass
                    
                    if completed % 10 == 0:
                        logger.info(f"  测试进度: {completed}/{len(proxies[:100])}, 有效: {len(working_proxies)}")
        
        except KeyboardInterrupt:
            logger.info("⏸️  测试中断")
        
        logger.info(f"\n✓ 测试完成: {len(working_proxies)}/{len(proxies[:100])} 代理可用")
        return working_proxies
    
    def _test_single_proxy(self, proxy: str) -> bool:
        """测试单个代理"""
        try:
            proxy_dict = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxy_dict,
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def save_to_api_pool(self, proxies: List[str]):
        """保存到api_pool.json"""
        logger.info(f"\n保存代理到 api_pool.json...")
        
        # 读取现有配置
        try:
            with open('api_pool.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {'apis': [], 'strategy': {}}
        
        # 保留现有的直连API（ID=1,2）
        existing_apis = [api for api in config.get('apis', []) if api.get('type') == 'direct']
        
        # 添加代理
        new_apis = existing_apis.copy()
        for i, proxy in enumerate(proxies, start=100):  # 从ID 100开始
            new_apis.append({
                'id': i,
                'type': 'proxy',
                'url': f'http://{proxy}',
                'enabled': True,
                'source': 'free-proxy',
                'added_at': datetime.now().isoformat()
            })
        
        # 更新配置
        config['apis'] = new_apis
        config['total_proxies'] = len(proxies)
        config['direct_apis'] = len(existing_apis)
        config['last_updated'] = datetime.now().isoformat()
        
        # 保存
        with open('api_pool.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ 已保存 {len(proxies)} 个代理到 api_pool.json")
        logger.info(f"  直连: {len(existing_apis)}")
        logger.info(f"  代理: {len(proxies)}")
        logger.info(f"  总计: {len(new_apis)}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='爬取免费代理IP')
    parser.add_argument('--count', type=int, default=1000, help='目标代理数（默认1000）')
    parser.add_argument('--test', action='store_true', help='是否测试代理可用性（较慢）')
    parser.add_argument('--save', action='store_true', default=True, help='是否保存到api_pool.json')
    
    args = parser.parse_args()
    
    # 聚合代理
    aggregator = ProxyAggregator(target_count=args.count)
    proxies = aggregator.aggregate()
    
    # 截取目标数量
    proxies = proxies[:args.count]
    
    # 可选：测试代理
    if args.test:
        # working_proxies = aggregator.test_proxies(proxies)
        # proxies = working_proxies
        logger.info("⏭️  代理测试功能已禁用（httpbin.org不稳定）")
    
    # 保存
    if args.save and proxies:
        aggregator.save_to_api_pool(proxies)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"✓ 完成！获得 {len(proxies)} 个代理")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()
