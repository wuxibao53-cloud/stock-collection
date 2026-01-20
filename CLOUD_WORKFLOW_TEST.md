# GitHub Actions 工作流测试和验证指南

## 🎯 概述

本指南将帮助你完成以下任务：
1. ✅ **配置 GitHub Secrets** - 钉钉/企业微信 webhooks
2. ✅ **测试云工作流执行** - 验证 GitHub Actions 正常运行
3. ✅ **验证 5000+ 股票采集** - 确保全 A 股采集正常工作

---

## 📋 前置准备

### 1.1 获取钉钉 Webhook URL

**步骤 1**: 打开钉钉应用
- 创建或进入一个群聊
- 点击群设置 (⚙️)

**步骤 2**: 添加群机器人
- 找到 "群机器人" 选项
- 选择 "自定义" 机器人
- 给机器人命名：`缠论交易系统告警`

**步骤 3**: 配置安全策略
- ✓ 勾选 "加签"（推荐）
- 记录下 Secret 值（需要保存）
- 生成 Webhook URL

**步骤 4**: 验证 Webhook
```bash
# 复制你的 Webhook URL，格式应该像这样：
# https://oapi.dingtalk.com/robot/send?access_token=xxxxx

# 快速测试
curl -X POST 'YOUR_DINGTALK_WEBHOOK_URL' \
  -H 'Content-Type: application/json' \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "✅ 测试消息"
    }
  }'
```

### 1.2 获取企业微信 Webhook URL

**步骤 1**: 打开企业微信
- 进入需要的群聊
- 点击群信息

**步骤 2**: 添加应用机器人
- 选择 "应用" 或 "机器人"
- 创建新的自定义机器人
- 命名：`缠论交易系统Alert`

**步骤 3**: 复制 Webhook URL
- 形式：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx`

**步骤 4**: 验证 Webhook
```bash
curl -X POST 'YOUR_WECHAT_WEBHOOK_URL' \
  -H 'Content-Type: application/json' \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "✅ 测试消息"
    }
  }'
```

---

## ⚙️ Step 1: 配置 GitHub Secrets

### 方法 A: 使用 Web 界面（推荐新手）

1. **进入 GitHub 仓库**
   - 打开：https://github.com/wuxibao53-cloud/stock-collection
   - 点击 "Settings" 标签页

2. **导航到 Secrets**
   - 左侧菜单 → "Secrets and variables" → "Actions"

3. **添加第一个 Secret**
   - 点击 "New repository secret"
   - 名称：`DINGTALK_WEBHOOK`
   - 值：粘贴你的钉钉 Webhook URL（完整 URL）
   - 点击 "Add secret"

4. **添加第二个 Secret**
   - 点击 "New repository secret"
   - 名称：`WECHAT_WEBHOOK`
   - 值：粘贴你的企业微信 Webhook URL（完整 URL）
   - 点击 "Add secret"

5. **验证配置**
   - 现在应该能看到两个 secrets：
     - `DINGTALK_WEBHOOK`
     - `WECHAT_WEBHOOK`

### 方法 B: 使用 GitHub CLI（推荐开发者）

```bash
# 1. 确保已安装 GitHub CLI
brew install gh

# 2. 登录 GitHub
gh auth login

# 3. 添加 DINGTALK_WEBHOOK
gh secret set DINGTALK_WEBHOOK \
  --body "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
  --repo wuxibao53-cloud/stock-collection

# 4. 添加 WECHAT_WEBHOOK
gh secret set WECHAT_WEBHOOK \
  --body "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY" \
  --repo wuxibao53-cloud/stock-collection

# 5. 验证 Secrets 已添加
gh secret list --repo wuxibao53-cloud/stock-collection
```

---

## 🚀 Step 2: 本地测试通知系统

在推送到 GitHub 之前，先在本地测试通知脚本：

```bash
# 1. 进入项目目录
cd /Users/lihaoran/Desktop/stock_collection

# 2. 设置环境变量（使用你实际的 webhooks）
export DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
export WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
export GITHUB_RUN_ID="test-local"
export GITHUB_REPOSITORY="wuxibao53-cloud/stock-collection"
export GITHUB_SERVER_URL="https://github.com"

# 3. 测试成功通知
python notify_alert.py \
  --status success \
  --symbols 5000 \
  --records 50000 \
  --runtime 120 \
  --message "测试成功通知"

# 4. 测试失败通知
python notify_alert.py \
  --status failure \
  --error "测试失败通知"

# 5. 测试警告通知
python notify_alert.py \
  --status warning \
  --message "测试警告通知"
```

**预期结果**:
- ✅ 钉钉群收到消息
- ✅ 企业微信群收到消息
- 📊 显示详细的采集报告或错误信息

---

## 🔧 Step 3: 测试 GitHub Actions 工作流

### 3.1 手动触发工作流

1. **进入 GitHub 仓库**
   - 打开：https://github.com/wuxibao53-cloud/stock-collection

2. **进入 Actions 页面**
   - 点击 "Actions" 标签页

3. **找到工作流**
   - 左侧看到 "缠论交易系统 - 云端自动执行"
   - 点击进入

4. **手动触发**
   - 点击 "Run workflow" 按钮
   - 选择执行模式：`alert` （先测试告警功能）
   - 点击 "Run workflow"

### 3.2 监控工作流执行

工作流启动后，你可以实时查看执行进度：

```
运行队列：
├─ Jobs
│  ├─ ✅ market-collection (采集任务)
│  │  ├─ ✅ 检出代码
│  │  ├─ ✅ 设置 Python 环境
│  │  ├─ ✅ 安装依赖
│  │  ├─ ⏳ 采集热门股票数据
│  │  ├─ ⏳ 运行缠论分析
│  │  ├─ ⏳ 生成交易提醒
│  │  ├─ ⏳ 检查数据质量
│  │  ├─ ⏳ 上传数据和报告
│  │  └─ ⏳ 发送告警通知
│  │
│  ├─ ⏳ data-aggregation (数据去重)
│  └─ ⏳ monitoring-alerts (监控告警)
```

### 3.3 查看详细日志

1. **进入工作流运行**
   - 点击正在运行的工作流

2. **查看具体步骤的日志**
   - 点击每个步骤查看详细日志
   - 特别关注 "发送告警通知" 步骤

3. **检查错误**
   - 如果任何步骤失败，查看错误信息
   - 常见问题见下面的 FAQ

### 3.4 验证告警消息

在工作流运行时，检查以下内容：

```
✅ 检查清单：
- [ ] 工作流成功开始运行
- [ ] "采集热门股票数据" 步骤完成
- [ ] "运行缠论分析" 步骤完成
- [ ] "生成交易提醒" 步骤完成
- [ ] "采集成功通知" 步骤完成
- [ ] 钉钉群收到 ✅ 成功通知
- [ ] 企业微信群收到 ✅ 成功通知
- [ ] 通知中包含采集的股票数和记录数
- [ ] 通知中包含查看详情链接
```

---

## 📊 Step 4: 验证数据采集质量

### 4.1 检查采集的数据

1. **在 GitHub Actions 中查看数据质量步骤**
   - 进入工作流日志
   - 找到 "检查数据质量" 步骤
   - 应该看到类似输出：
   ```
   ✓ 采集5000只股票, 50000条数据
   ```

2. **下载采集结果**
   - 在工作流完成后
   - 找到 "Artifacts" 部分
   - 下载 `analysis-results` 或 `final-database`

3. **本地验证数据**
   ```bash
   # 1. 进入项目目录
   cd /Users/lihaoran/Desktop/stock_collection
   
   # 2. 检查数据库中的数据
   python -c "
   import sqlite3
   import os
   
   # 使用从 Actions 下载的数据库
   db_path = 'logs/quotes.db'
   
   conn = sqlite3.connect(db_path)
   cursor = conn.cursor()
   
   # 查询统计信息
   cursor.execute('SELECT COUNT(DISTINCT symbol) as symbols, COUNT(*) as records FROM minute_bars')
   symbols, records = cursor.fetchone()
   
   print(f'✓ 总股票数: {symbols:,}')
   print(f'✓ 总数据条数: {records:,}')
   print(f'✓ 平均每只股票的数据: {records // max(symbols, 1):,}')
   
   # 查看样本数据
   print('\n✓ 样本数据:')
   cursor.execute('SELECT symbol, minute, open, close, volume FROM minute_bars LIMIT 5')
   for row in cursor.fetchall():
       print(f'  {row}')
   
   conn.close()
   "
   ```

### 4.2 数据质量指标

| 指标 | 预期值 | 检查方式 |
|------|--------|--------|
| 股票总数 | 5000+ | `COUNT(DISTINCT symbol)` |
| 数据记录 | 50000+ | `COUNT(*)` |
| 去重后记录 | > 45000 | 数据聚合后检查 |
| 数据完整性 | > 98% | `COUNT(open) / COUNT(*)` |
| 采集耗时 | < 5min | GitHub Actions 日志 |

---

## 🐛 FAQ 和常见问题

### Q1: "发送告警通知" 步骤失败

**症状**：
```
Error: curl: (7) Failed to connect to oapi.dingtalk.com
```

**解决方案**：
1. 检查 Webhook URL 是否正确
   ```bash
   gh secret get DINGTALK_WEBHOOK --repo wuxibao53-cloud/stock-collection
   ```

2. 验证 URL 格式
   - 应该以 `https://` 开头
   - 包含 `access_token=` 或 `key=`

3. 重新生成 Webhook
   - 在钉钉/企业微信中删除旧机器人
   - 创建新机器人并复制新 URL
   - 更新 GitHub Secrets

### Q2: 工作流超时

**症状**：
```
The job exceeded the maximum execution time of 30 minutes
```

**解决方案**：
1. 减少采集的股票数
   - 修改 `full_a_stock_collector.py` 中的 `--mode hot`
   - 只采集热门股票

2. 增加超时时间
   - 编辑工作流文件
   - 增加 `timeout-minutes` 的值

### Q3: 钉钉/企业微信收不到消息

**排查步骤**：
1. 在本地测试通知脚本
   ```bash
   export DINGTALK_WEBHOOK="YOUR_URL"
   python notify_alert.py --status success
   ```

2. 检查机器人权限
   - 确保机器人有发送消息权限
   - 检查群聊是否禁用了机器人

3. 查看钉钉/企业微信设置
   - 检查 IP 白名单
   - 检查加签是否正确配置

### Q4: 工作流报错 "AttributeError"

**症状**：
```
AttributeError: module 'os' has no attribute 'environ'
```

**解决方案**：
1. 确保 Python 环境正确
2. 检查通知脚本语法
3. 查看完整错误堆栈

---

## ✅ 完成清单

- [ ] 获取钉钉 Webhook URL
- [ ] 获取企业微信 Webhook URL
- [ ] 在 GitHub 中配置 DINGTALK_WEBHOOK
- [ ] 在 GitHub 中配置 WECHAT_WEBHOOK
- [ ] 本地测试通知脚本成功
- [ ] 手动触发 GitHub Actions 工作流
- [ ] 工作流运行完成（3 个 Jobs）
- [ ] 钉钉群收到成功通知
- [ ] 企业微信群收到成功通知
- [ ] 验证采集数据 5000+ 只股票
- [ ] 验证采集数据 50000+ 条记录

---

## 🎯 下一步

完成以上所有步骤后：

1. **定时执行设置**
   - 工作流每天自动执行 4 次
   - 使用 GitHub Actions 日志查看定时执行结果

2. **性能优化**
   - 监控工作流执行时间
   - 根据需要调整并发数

3. **监控仪表板**
   - 创建 Grafana 仪表板
   - 实时显示采集统计信息
   - 自动告警异常情况

---

## 📞 获取帮助

如遇到问题：
1. 查看 GitHub Actions 运行日志
2. 检查通知脚本输出
3. 参考 [GitHub Secrets 配置指南](./GITHUB_SECRETS_SETUP.md)
4. 查看 [GitHub Actions 文档](https://docs.github.com/en/actions)

---

**版本**: 1.0  
**最后更新**: 2026-01-20  
**状态**: 🟢 已就绪
