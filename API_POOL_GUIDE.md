# API池配置指南 - 1000个备用API

## 快速开始

### 1. 生成基础配置
```bash
python3 generate_api_pool.py
```

这会生成 `api_pool.json`，包含1000个API槽位（目前是占位符）。

### 2. 填充真实代理

#### 选项A：免费代理源（推荐）

**快代理** (https://www.kuaidaili.com/)
```python
# 在快代理网站获取免费IP列表
# 格式通常为: IP:PORT
# 转换为 http://IP:PORT

proxies = [
    "http://1.2.3.4:8080",
    "http://5.6.7.8:8080",
    # ... 添加更多
]
```

**芝麻代理** (https://www.zhimadaili.com/)
```python
# 获取芝麻代理的免费IP
proxies = [
    "http://proxy.zhimadaili.com:808",
    # ... 添加更多
]
```

**万IP代理** (https://www.wanip.com/)
```python
proxies = [
    "http://t.wanip.com:808",
    # ... 获取实际IP列表
]
```

**其他来源**：
- 云代理 (https://www.yunproxy.com/)
- 极光代理 (https://www.jiguangdaili.com/)
- 66代理 (http://www.66ip.cn/)

#### 选项B：商业代理服务（稳定性高）

**Bright Data** (https://www.brightdata.com/)
```json
{
  "id": 1,
  "type": "proxy",
  "url": "http://user:pass@geo.brightdata.com:22225",
  "name": "Bright Data代理",
  "enabled": true
}
```

**Oxylabs** (https://oxylabs.io/)
```json
{
  "id": 2,
  "type": "proxy",
  "url": "http://user-country-china:pass@pr.oxylabs.io:7777",
  "name": "Oxylabs代理",
  "enabled": true
}
```

**Smartproxy** (https://smartproxy.com/)
```json
{
  "id": 3,
  "type": "proxy",
  "url": "http://user:pass@gate.smartproxy.com:7000",
  "name": "Smartproxy代理",
  "enabled": true
}
```

#### 选项C：自建代理（企业级）

使用开源代理软件：
- **Shadowsocks** - 轻量级代理
- **V2Ray** - 高性能代理
- **Clash** - 多协议支持

配置格式：
```json
{
  "id": 500,
  "type": "proxy",
  "url": "socks5://user:pass@your-vps-ip:1080",
  "name": "自建代理服务器",
  "enabled": true
}
```

### 3. 更新配置

#### 方法1：手动编辑 `api_pool.json`
```json
{
  "apis": [
    {
      "id": 1,
      "type": "direct",
      "name": "Direct AKShare",
      "enabled": true
    },
    {
      "id": 2,
      "type": "proxy",
      "url": "http://proxy1.example.com:8080",
      "name": "Proxy 1",
      "enabled": true
    },
    {
      "id": 3,
      "type": "proxy",
      "url": "http://proxy2.example.com:8080",
      "name": "Proxy 2",
      "enabled": true
    }
    // ... 添加最多1000个API
  ]
}
```

#### 方法2：使用Python脚本
```python
from generate_api_pool import add_custom_proxies

proxies = [
    "http://proxy1.example.com:8080",
    "http://proxy2.example.com:8080",
    "http://proxy3.example.com:8080",
    # ... 添加1000个
]

add_custom_proxies('api_pool.json', proxies)
```

#### 方法3：从文件批量导入
```python
# proxies.txt (每行一个代理)
# http://proxy1.example.com:8080
# http://proxy2.example.com:8080

with open('proxies.txt', 'r') as f:
    proxies = [line.strip() for line in f if line.strip()]

add_custom_proxies('api_pool.json', proxies)
```

## API池工作流程

```
┌─────────────────┐
│  获取当前API    │
│  (轮转策略)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ✓ 成功
│  调用API获取数据 ├──────────→ 记录成功 → 继续
└────────┬────────┘
         │
         × 失败
         │
         ▼
┌──────────────────┐
│ 标记API为"故障" │
│ 冷却5分钟        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 轮转到下一个API  │
│ (第一个可用的)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 重试(最多3次)   │
└────────┬─────────┘
         │
    还有API?
    ↙     ↘
   是      否
   │       │
   ▼       ▼
重试    回退直连
```

## 使用示例

### 启用API池（推荐）
```python
from multi_timeframe_fetcher import MultiTimeframeDataFetcher

# 启用API池（默认启用）
fetcher = MultiTimeframeDataFetcher(use_api_pool=True)

# 采集数据 - 自动使用API池轮转
fetcher.fetch_all_a_stocks_multiframe(
    days=30,
    max_workers=20,
    timeframes=[TimeFrame.THIRTY_MIN]
)
```

### 查看API统计
```python
from api_pool_manager import get_api_pool

pool = get_api_pool()
pool.print_stats()  # 查看每个API的成功率、失败次数等
```

### 禁用API池（直连模式）
```python
fetcher = MultiTimeframeDataFetcher(use_api_pool=False)
# 使用直接连接，不经过代理
```

## 监控和诊断

### 查看API池状态
```bash
# 查看日志中的API统计信息
grep "API池统计" logs/system.log

# 查看故障API
grep "冷却中" logs/system.log
```

### 重置故障API
```python
from api_pool_manager import get_api_pool

pool = get_api_pool()

# 立即重试某个API（清除冷却状态）
stats = pool.stats[api_id]
stats['disabled_until'] = None
stats['error_count'] = 0
```

## 性能优化建议

### 1. 代理选择
- **免费代理**：速度快但不稳定，适合测试
- **商业代理**：稳定可靠，适合生产环境
- **自建代理**：完全控制，适合企业级应用

### 2. 线程配置
```python
# 不同代理质量下的推荐线程数
# 免费代理：15-20线程 (稳定性一般)
# 商业代理：20-30线程 (稳定性好)
# 自建代理：30-50线程 (完全可控)

fetcher.fetch_all_a_stocks_multiframe(max_workers=25)
```

### 3. 冷却策略
```json
{
  "strategy": {
    "cooldown_period_minutes": 5,  // 故障后冷却5分钟
    "max_error_count": 3,           // 3次失败后冷却
    "retry_count": 3,               // 每个API最多重试3次
    "retry_delay": 0.5              // 重试间隔0.5秒
  }
}
```

## 故障排查

### 问题1：所有代理都失败
```
原因: 代理地址错误或过期
解决: 
1. 测试代理是否可用: curl -x http://proxy:port http://www.google.com
2. 更新过期的代理地址
3. 增加回退直连模式（fallback_to_direct: true）
```

### 问题2：速度慢
```
原因: 代理质量差或线程数不足
解决:
1. 增加线程数: max_workers=30
2. 切换到更好的代理服务
3. 检查网络延迟
```

### 问题3：内存占用高
```
原因: 线程过多导致内存溢出
解决:
1. 降低max_workers到15-20
2. 增加批处理间隔
3. 监控线程数: ps aux | grep python
```

## 生产环境部署

### GitHub Actions云端配置
```yaml
- name: 获取30f历史K线（使用API池）
  run: |
    python3 multi_timeframe_fetcher.py \
      --db logs/quotes.db \
      --days 30 \
      --mode all \
      --timeframes 30 \
      --workers 20 \
      --use-api-pool true  # 启用API池
```

### 定期监控
```bash
# 每天检查API统计
0 22 * * * cd ~/stock_collection && python3 -c "from api_pool_manager import get_api_pool; get_api_pool().print_stats()" >> logs/api_stats.log
```

## 常见问题

**Q: 需要多少个代理？**
A: 1000个是上限。建议从100-200个开始，逐步增加到1000。

**Q: 免费代理和付费代理哪个好？**
A: 免费代理速度快但稳定性差(50-70%)，付费代理稳定性好(95%+)。混合使用效果最佳。

**Q: API失败后多久会重试？**
A: 默认冷却5分钟。之后系统会自动尝试重新使用。

**Q: 可以自定义轮转策略吗？**
A: 可以。修改 `api_pool.json` 的 `strategy` 字段，或编辑 `api_pool_manager.py`。

---

**更新**: 2026-01-21  
**版本**: 1.0  
**支持**: 最多1000个备用API/代理  
**自动故障转移**: ✓  
**成功率目标**: 95%+
