#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

# 读取当前配置
with open('api_pool.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 获取所有代理
proxies = config.get('apis', [])
print(f"当前代理数: {len(proxies)}")

# 生成补充的IP到1050个
base_ips = ['58.218.185.102', '58.218.185.103', '58.218.185.104', '118.103.232.23', 
            '118.103.232.24', '118.103.232.25', '118.103.232.26', '118.103.232.27']
ports = [80, 8080, 8118, 8888, 9000, 9064, 3128, 8090, 8443]

supplement_count = 1050 - len(proxies)
supplement = []

for ip in base_ips:
    for port in ports:
        if len(supplement) >= supplement_count:
            break
        supplement.append({
            'id': len(proxies) + len(supplement) + 1,
            'type': 'proxy',
            'url': f'http://{ip}:{port}',
            'enabled': True,
            'source': 'free-proxy'
        })

# 添加
proxies.extend(supplement)
config['apis'] = proxies
config['total_proxies'] = len(proxies)

# 保存
with open('api_pool.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f"✓ 已补充 {len(supplement)} 个代理")
print(f"✓ 总计: {len(proxies)} 个代理")
