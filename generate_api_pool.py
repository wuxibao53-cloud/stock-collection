#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成1000个备用API/代理配置脚本

支持多种来源：
1. 免费代理池（IP地址库）
2. 自定义代理地址
3. 代理服务商API
"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_api_pool_from_free_proxies():
    """从免费代理池生成（演示用）"""
    # 常见免费代理源示例（实际需要时爬取）
    free_proxy_sources = [
        # IP代理站点
        "http://11.22.33.44:8080",    # 示例代理
        "http://55.66.77.88:8080",
        "http://99.88.77.66:8080",
        # ... 需要实际爬取
    ]
    
    return free_proxy_sources


def generate_api_pool_from_commercial_service():
    """从商业代理服务商生成"""
    # 示例：使用芝麻代理、快代理等商业服务
    # 这些需要购买和获取真实的代理IP列表
    
    commercial_proxies = [
        # 格式: http://user:pass@proxy-host:port
        # 示例：
        # "http://user1:pass1@proxy.zhimadaili.com:808",
        # "http://user2:pass2@proxy.kuaidaili.com:8080",
    ]
    
    return commercial_proxies


def generate_default_api_pool(count: int = 1000):
    """生成默认API池配置（混合模式）"""
    apis = []
    
    # 1. 直连模式（主备）
    apis.append({
        "id": 1,
        "type": "direct",
        "name": "Direct AKShare (主直连)",
        "description": "无代理，直接连接AKShare",
        "enabled": True,
        "priority": 1
    })
    
    # 2. 备用直连
    apis.append({
        "id": 2,
        "type": "direct",
        "name": "Direct AKShare (备用直连)",
        "description": "无代理，直接连接AKShare",
        "enabled": True,
        "priority": 2
    })
    
    # 3. 添加代理（模板 - 需要用实际代理替换）
    # 免费代理来源示例
    free_proxy_pools = [
        # 快代理免费IP（需从他们网站获取）
        # "http://proxy-free-1.kuaidaili.com:8080",
        # "http://proxy-free-2.kuaidaili.com:8080",
        
        # 芝麻代理（需从官网获取）
        # "http://proxy-zm-1.zhimadaili.com:808",
        # "http://proxy-zm-2.zhimadaili.com:808",
        
        # 其他公共代理服务
        # ... 添加实际的代理地址
    ]
    
    # 添加VPN/SOCKS代理支持
    vpn_proxies = [
        # "socks5://user:pass@vpn-host-1:1080",
        # "socks5://user:pass@vpn-host-2:1080",
    ]
    
    # 自定义企业代理（可选）
    custom_proxies = [
        # "http://internal-proxy-1.company.com:8080",
        # "http://internal-proxy-2.company.com:8080",
    ]
    
    # 汇总所有代理
    all_proxies = free_proxy_pools + vpn_proxies + custom_proxies
    
    # 如果代理不足，填充占位符（用户需要手动替换）
    while len(apis) < count:
        proxy_id = len(apis) + 1
        
        if proxy_id - 2 < len(all_proxies):
            # 使用真实代理
            apis.append({
                "id": proxy_id,
                "type": "proxy",
                "url": all_proxies[proxy_id - 3],
                "name": f"代理 {proxy_id}",
                "enabled": True,
                "priority": 3
            })
        else:
            # 添加占位符（用户需要替换）
            apis.append({
                "id": proxy_id,
                "type": "proxy",
                "url": f"http://proxy-{proxy_id}.example.com:8080",  # 占位符
                "name": f"代理 {proxy_id} (待配置)",
                "description": f"请将此地址替换为实际代理地址",
                "enabled": False,  # 默认禁用直到配置
                "priority": 3
            })
    
    return apis


def save_api_pool_config(apis: list, output_file: str = 'api_pool.json'):
    """保存API池配置到文件"""
    config = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_apis": len(apis),
        "apis": apis[:1000],  # 最多1000个
        "strategy": {
            "type": "round_robin",  # 轮转策略
            "retry_count": 3,
            "retry_delay": 0.5,
            "fallback_to_direct": True,  # 所有代理失败后回退到直连
            "cooldown_period_minutes": 5  # API故障冷却期
        },
        "notes": [
            "这是一个API/代理池配置文件",
            "共支持1000个备用API/代理",
            "系统会自动轮转，避免单点故障",
            "每个API失败3次会冷却5分钟后重试",
            "如果所有API都失败，会回退到直连模式"
        ]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ 已生成 {len(apis)} 个API配置，保存到: {output_file}")


def add_custom_proxies(existing_config_file: str, proxy_list: list, output_file: str = None):
    """添加自定义代理到现有配置"""
    # 加载现有配置
    try:
        with open(existing_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {existing_config_file}")
        return
    
    apis = config.get('apis', [])
    max_id = max([api.get('id', 0) for api in apis]) if apis else 0
    
    # 添加代理
    for i, proxy_url in enumerate(proxy_list):
        max_id += 1
        if max_id > 1000:
            logger.warning(f"API数量已达上限(1000)，停止添加")
            break
        
        apis.append({
            "id": max_id,
            "type": "proxy",
            "url": proxy_url,
            "name": f"自定义代理 {i+1}",
            "enabled": True,
            "priority": 3
        })
    
    config['apis'] = apis
    config['total_apis'] = len(apis)
    
    output_file = output_file or existing_config_file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ 已添加 {len(proxy_list)} 个代理，共 {len(apis)} 个API")


if __name__ == '__main__':
    from datetime import datetime
    
    logger.info("🚀 生成API池配置文件")
    
    # 生成1000个API/代理配置
    apis = generate_default_api_pool(1000)
    
    # 保存配置
    save_api_pool_config(apis, 'api_pool.json')
    
    # 如果有自定义代理，可以添加
    # custom_proxies = [
    #     "http://your-proxy-1.com:8080",
    #     "http://your-proxy-2.com:8080",
    # ]
    # add_custom_proxies('api_pool.json', custom_proxies)
    
    logger.info("\n📌 使用说明:")
    logger.info("1. 根据上述代理源获取真实代理地址")
    logger.info("2. 替换 api_pool.json 中的占位符地址")
    logger.info("3. 或使用 add_custom_proxies() 函数批量添加")
    logger.info("4. 支持的代理类型: HTTP/HTTPS/SOCKS5")
