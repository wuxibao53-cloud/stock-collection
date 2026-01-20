# P1 优先级实施检查清单

## 🎯 今天任务总结

你已经完成了以下工作：

### ✅ 第一步：GitHub Secrets 配置文档
- [x] 创建 `GITHUB_SECRETS_SETUP.md` - 完整的配置指南
- [x] 包含钉钉/企业微信 Webhook 获取步骤
- [x] 提供 Web 界面和 CLI 两种配置方式
- [x] 包含故障排查和最佳实践

### ✅ 第二步：快速配置工具
- [x] 创建 `github_secrets_config.py` - 自动化配置工具
- [x] 支持本地测试 Webhook 连接
- [x] 生成 GitHub CLI 命令
- [x] 获取 GitHub Actions IP 范围

### ✅ 第三步：多渠道告警系统
- [x] 创建 `notify_alert.py` - 统一的通知系统
- [x] 支持钉钉富文本卡片消息
- [x] 支持企业微信 Markdown 消息
- [x] 自动生成采集报告和错误信息
- [x] 更新 GitHub Actions 工作流使用新的通知系统

### ✅ 第四步：采集验证工具
- [x] 创建 `verify_collection.py` - 详细的验证工具
- [x] 统计采集数据（股票数、记录数）
- [x] 市场分布分析（上证/深证/创业板/北交所）
- [x] 数据质量检查（异常值、重复、缺失）
- [x] 生成 HTML 和 Markdown 格式报告
- [x] 性能指标收集

### ✅ 第五步：云工作流测试指南
- [x] 创建 `CLOUD_WORKFLOW_TEST.md` - 完整测试指南
- [x] 手动触发工作流的步骤
- [x] 实时监控工作流进度
- [x] 验证告警消息传送
- [x] 下载和本地验证数据

---

## 📋 接下来的行动步骤

### 立即行动（今天）

1. **准备 Webhook URLs**
   ```bash
   # 步骤 1: 获取钉钉 Webhook
   # 打开钉钉 → 创建/进入群 → 群设置 → 群机器人 → 自定义 → 获取 URL
   
   # 步骤 2: 获取企业微信 Webhook  
   # 打开企业微信 → 进入群 → 群设置 → 机器人 → 自定义 → 获取 URL
   
   # 你应该得到两个类似这样的 URL：
   # DINGTALK: https://oapi.dingtalk.com/robot/send?access_token=xxxxx
   # WECHAT: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx
   ```

2. **本地测试通知（可选但推荐）**
   ```bash
   cd /Users/lihaoran/Desktop/stock_collection
   
   # 导入环境变量
   export DINGTALK_WEBHOOK="YOUR_DINGTALK_URL"
   export WECHAT_WEBHOOK="YOUR_WECHAT_URL"
   
   # 测试成功通知
   python notify_alert.py --status success --symbols 5000 --records 50000 --runtime 120
   
   # 你应该在钉钉和企业微信中看到详细的采集报告
   ```

3. **配置 GitHub Secrets**
   
   **选项 A: Web 界面（推荐新手）**
   ```
   1. 打开: https://github.com/wuxibao53-cloud/stock-collection
   2. Settings → Secrets and variables → Actions
   3. 点击 "New repository secret"
   4. 添加 DINGTALK_WEBHOOK（值为你的完整 URL）
   5. 添加 WECHAT_WEBHOOK（值为你的完整 URL）
   ```
   
   **选项 B: GitHub CLI（推荐开发者）**
   ```bash
   gh secret set DINGTALK_WEBHOOK --body "YOUR_DINGTALK_URL" \
     --repo wuxibao53-cloud/stock-collection
   
   gh secret set WECHAT_WEBHOOK --body "YOUR_WECHAT_URL" \
     --repo wuxibao53-cloud/stock-collection
   
   # 验证
   gh secret list --repo wuxibao53-cloud/stock-collection
   ```

4. **手动触发工作流测试**
   ```
   1. 打开: https://github.com/wuxibao53-cloud/stock-collection/actions
   2. 找到 "缠论交易系统 - 云端自动执行"
   3. 点击 "Run workflow"
   4. 选择模式: "alert"
   5. 点击 "Run workflow"
   6. 等待工作流完成（~5-10 分钟）
   7. 查看钉钉和企业微信是否收到通知
   ```

---

## 📊 预期结果

### ✅ 完成后你应该看到：

1. **GitHub Secrets 配置**
   - [ ] DINGTALK_WEBHOOK 显示为已配置
   - [ ] WECHAT_WEBHOOK 显示为已配置

2. **本地测试成功**
   - [ ] 钉钉群收到测试消息
   - [ ] 企业微信群收到测试消息
   - [ ] 消息包含采集统计信息

3. **GitHub Actions 工作流**
   - [ ] 工作流成功运行
   - [ ] 3 个 Jobs 都显示绿色 ✅
   - [ ] "采集成功通知" 步骤完成

4. **数据验证**
   - [ ] 钉钉/企业微信收到详细的采集报告
   - [ ] 报告显示采集的股票数 (5000+ 目标)
   - [ ] 报告显示采集的数据条数
   - [ ] 可以点击链接查看完整日志

---

## 🔗 关键文件和链接

| 文件 | 说明 | 用途 |
|------|------|------|
| `GITHUB_SECRETS_SETUP.md` | 配置完整指南 | 参考文档 |
| `CLOUD_WORKFLOW_TEST.md` | 工作流测试指南 | 测试步骤 |
| `github_secrets_config.py` | 配置工具 | 本地测试 |
| `notify_alert.py` | 通知系统 | 多渠道推送 |
| `verify_collection.py` | 验证工具 | 数据检查 |

**GitHub 仓库**: https://github.com/wuxibao53-cloud/stock-collection

**最新提交**: 046db84

---

## 💡 小贴士

1. **快速本地测试**
   ```bash
   python github_secrets_config.py --test-dingtalk "YOUR_URL"
   python github_secrets_config.py --test-wechat "YOUR_URL"
   ```

2. **查看工作流日志**
   - GitHub Actions 中每个步骤都可以展开查看详细日志
   - 查找 "发送告警通知" 步骤的输出

3. **生成验证报告**
   ```bash
   # 下载 final-database artifact 后
   python verify_collection.py --db logs/quotes.db --generate-report
   ```

4. **常见问题**
   - 如果 Webhook 测试失败，检查 URL 是否完整
   - 如果工作流超时，可能是采集数据量过大
   - 如果没有收到消息，检查群机器人权限

---

## 🎯 后续阶段

完成 P1 后，下一步是：

### P2 (本月)
- [ ] 运行完整回测验证策略
- [ ] 参数优化 (ATR 倍数遍历)
- [ ] 部署监控仪表板

### P3 (本季度)
- [ ] 迁移到 PostgreSQL/TimescaleDB
- [ ] WebSocket 实时推送
- [ ] Web Dashboard 可视化
- [ ] 自动化交易接口

---

## 📞 需要帮助？

1. **查看文档**
   - [GitHub Secrets 配置指南](./GITHUB_SECRETS_SETUP.md)
   - [云工作流测试指南](./CLOUD_WORKFLOW_TEST.md)

2. **常见问题**
   - 见本文件下方的 "常见问题" 部分
   - 见各个文档末尾的 FAQ

3. **调试工作流**
   - 查看 GitHub Actions 运行日志
   - 查找错误关键字
   - 参考故障排查指南

---

**版本**: 1.0  
**创建时间**: 2026-01-20  
**状态**: 🟢 已就绪
