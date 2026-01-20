# GitHub Secrets 配置指南

## 📋 需要配置的 Secrets

项目中使用的 GitHub Secrets 列表：

### 必需配置 (P1)

| Secret 名称 | 说明 | 获取方式 |
|-----------|------|--------|
| `DINGTALK_WEBHOOK` | 钉钉群机器人 Webhook URL | 见下方 |
| `WECHAT_WEBHOOK` | 企业微信机器人 Webhook URL | 见下方 |

### 可选配置 (P2)

| Secret 名称 | 说明 | 获取方式 |
|-----------|------|--------|
| `AWS_ACCESS_KEY_ID` | AWS 访问密钥 | AWS IAM 控制台 |
| `AWS_SECRET_ACCESS_KEY` | AWS 密钥 | AWS IAM 控制台 |
| `TUSHARE_TOKEN` | Tushare 数据源 Token | https://tushare.pro |

---

## 🔧 Step 1: 钉钉 Webhook 配置

### 获取钉钉 Webhook URL

1. **打开钉钉应用**
   - 进入需要的企业钉钉群或创建新群

2. **添加群机器人**
   - 群设置 → 群机器人 → 添加机器人
   - 选择 "自定义" 机器人类型

3. **配置机器人**
   - 机器人名称：`缠论交易系统告警`
   - 机器人描述：`自动推送采集/分析/告警信息`

4. **设置安全策略**
   - ✓ 勾选 "加签"（推荐）
   - 记录下生成的 **Secret** 值
   - 如果选择 IP 白名单，需要添加 GitHub Actions IP 范围：
     - https://api.github.com/meta → 查看 `actions_ipv4`

5. **复制 Webhook URL**
   - 形式：`https://oapi.dingtalk.com/robot/send?access_token=xxxxx`

### 钉钉 Webhook 测试命令

```bash
# 测试消息格式
curl -X POST 'https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "✓ 缠论系统连接正常\n时间：$(date)"
    }
  }'
```

---

## 🔧 Step 2: 企业微信 Webhook 配置

### 获取企业微信 Webhook URL

1. **进入企业微信工作台**
   - 使用企业微信账户登录

2. **创建或进入群聊**
   - 找到用于接收告警的群聊

3. **添加应用机器人**
   - 群设置 → 群机器人 → 添加机器人
   - 选择 "自定义机器人"

4. **配置机器人详情**
   - 机器人名称：`缠论交易系统Alert`
   - 机器人描述：`自动化交易信号推送`

5. **复制 Webhook URL**
   - 形式：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx`

### 企业微信 Webhook 测试命令

```bash
# 测试消息格式
curl -X POST 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "✓ 缠论系统连接正常\n时间：2026-01-20"
    }
  }'
```

---

## 📝 Step 3: 在 GitHub 中配置 Secrets

### 方法 1: Web 界面配置（推荐）

1. **进入仓库**
   - 访问：https://github.com/wuxibao53-cloud/stock-collection

2. **打开 Settings**
   - 仓库主页 → Settings → Secrets and variables → Actions

3. **添加 Secret**
   
   **第一个 Secret：DINGTALK_WEBHOOK**
   - 点击 "New repository secret"
   - 名称：`DINGTALK_WEBHOOK`
   - 值：粘贴完整的钉钉 Webhook URL
   - 点击 "Add secret"
   
   **第二个 Secret：WECHAT_WEBHOOK**
   - 点击 "New repository secret"
   - 名称：`WECHAT_WEBHOOK`
   - 值：粘贴完整的企业微信 Webhook URL
   - 点击 "Add secret"

### 方法 2: 命令行配置（使用 GitHub CLI）

```bash
# 安装 GitHub CLI（如果未安装）
brew install gh

# 登录 GitHub
gh auth login

# 添加 DINGTALK_WEBHOOK
gh secret set DINGTALK_WEBHOOK --body "https://oapi.dingtalk.com/robot/send?access_token=YOUR_DINGTALK_TOKEN" \
  --repo wuxibao53-cloud/stock-collection

# 添加 WECHAT_WEBHOOK
gh secret set WECHAT_WEBHOOK --body "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WECHAT_KEY" \
  --repo wuxibao53-cloud/stock-collection

# 验证 Secrets 已添加
gh secret list --repo wuxibao53-cloud/stock-collection
```

---

## ✅ Step 4: 验证配置

### 检查 Secrets 是否正确配置

1. **在 GitHub 网页中确认**
   - Settings → Secrets → 应该看到 `DINGTALK_WEBHOOK` 和 `WECHAT_WEBHOOK`

2. **运行测试工作流**
   - 进入 Actions 标签页
   - 找到 "缠论交易系统 - 云端自动执行"
   - 点击 "Run workflow" → 选择 "alert" 模式
   - 查看日志确保通知成功发送

3. **检查工作流日志**
   - 工作流运行完成后，检查日志中的 "发送告警通知" 步骤
   - 如果看到 curl 命令成功执行，说明配置正确

---

## 🔐 安全最佳实践

### Do's ✓

- ✅ 定期轮换 Webhook URLs
- ✅ 使用 IP 白名单限制访问
- ✅ 启用钉钉/企业微信的 "加签" 功能
- ✅ 定期审查 Secrets 使用日志
- ✅ 对敏感信息使用 masked values

### Don'ts ✗

- ❌ 在代码中硬编码 Webhook URLs
- ❌ 将 Secrets 提交到 Git
- ❌ 在日志中打印完整的 Secrets
- ❌ 与未授权人员分享 Webhook URLs
- ❌ 使用过于宽泛的权限

---

## 🐛 常见问题排查

### 问题 1: "发送告警通知" 步骤失败

**症状**：工作流日志显示 curl 命令失败

**排查方法**：
```bash
# 检查 Webhook URL 是否正确
echo ${{ secrets.DINGTALK_WEBHOOK }}

# 测试连接
curl -X POST "${{ secrets.DINGTALK_WEBHOOK }}" \
  -H 'Content-Type: application/json' \
  -d '{"msgtype":"text","text":{"content":"测试"}}'
```

### 问题 2: 钉钉/企业微信没有收到消息

**可能原因**：
1. Webhook URL 已过期
2. 消息格式不符合要求
3. IP 白名单配置错误
4. 机器人权限不足

**解决方案**：
- 重新生成 Webhook URL
- 验证消息 JSON 格式
- 检查 IP 白名单设置
- 确认机器人有发送权限

### 问题 3: "加签" 验证失败

**症状**：即使 Webhook URL 正确，消息仍然被拒绝

**解决方案**：
```python
# 钉钉加签示例（需要在通知脚本中实现）
import hmac
import hashlib
import base64
import time

def sign_dingtalk(secret: str) -> tuple:
    timestamp = str(int(time.time() * 1000))
    sign = hmac.new(
        secret.encode(),
        f"{timestamp}\n{secret}".encode(),
        hashlib.sha256
    ).digest()
    sign = base64.b64encode(sign).decode()
    return timestamp, sign

# 使用方式：
timestamp, sign = sign_dingtalk(DINGTALK_SECRET)
webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={TOKEN}&timestamp={timestamp}&sign={sign}"
```

---

## 📊 预期配置完成后的测试清单

- [ ] DINGTALK_WEBHOOK Secret 已添加到 GitHub
- [ ] WECHAT_WEBHOOK Secret 已添加到 GitHub
- [ ] 手动测试：触发工作流 "alert" 模式
- [ ] 钉钉群收到成功通知
- [ ] 企业微信群收到成功通知
- [ ] 查看工作流日志无错误
- [ ] 记录 Webhook URLs（存放在安全位置）

---

## 下一步操作

配置完成后：

1. **测试云工作流执行** → [查看 CLOUD_WORKFLOW_TEST.md]
2. **验证 5000+ 只股票采集** → [查看 COLLECTION_VERIFICATION.md]
3. **设置监控告警** → 在工作流中启用完整的告警功能

---

## 参考资源

- 🔗 钉钉开发者文档：https://developers.dingtalk.com/document
- 🔗 企业微信开发者文档：https://work.weixin.qq.com/api/doc
- 🔗 GitHub Secrets 文档：https://docs.github.com/en/actions/security-guides/encrypted-secrets
- 🔗 GitHub Actions IP 范围：https://api.github.com/meta

---

**版本**: 1.0  
**最后更新**: 2026-01-20  
**状态**: 🟢 就绪配置
