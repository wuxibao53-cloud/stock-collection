# GitHub 仓库推送与验证指南

## 第一步：配置Git用户信息

```bash
cd /Users/lihaoran/Desktop/stock_collection

# 配置用户名和邮箱（用你的GitHub账号信息）
git config user.name "仙儿仙儿碎碎念"
git config user.email "your-email@example.com"  # 替换为你的GitHub邮箱

# 验证配置
git config user.name
git config user.email

# 如果刚才已经提交，更新作者信息
git commit --amend --reset-author --no-edit
```

---

## 第二步：创建GitHub仓库

### 方法一：使用GitHub网页

1. 打开 https://github.com/new
2. Repository name: `stock-collection` 或 `a-share-realtime`
3. Description: `A股实时行情采集与分析系统 | A-share realtime stock data collection and analysis`
4. **Public** 或 **Private**（推荐Private，避免API滥用）
5. **不要勾选**任何初始化选项（README、.gitignore、License）
6. 点击 **Create repository**

### 方法二：使用GitHub CLI（如已安装gh命令）

```bash
# 安装gh（如果没有）
brew install gh

# 登录
gh auth login

# 创建私有仓库
gh repo create stock-collection --private --source=. --push
```

---

## 第三步：关联远程仓库并推送

### 使用HTTPS（简单）

```bash
# 替换 YOUR_USERNAME 为你的GitHub用户名
git remote add origin https://github.com/YOUR_USERNAME/stock-collection.git

# 推送到main分支
git branch -M main
git push -u origin main
```

### 使用SSH（推荐，免密）

```bash
# 检查SSH密钥（如果没有需要先生成）
ls ~/.ssh/id_*.pub

# 如果没有，生成SSH密钥
ssh-keygen -t ed25519 -C "your-email@example.com"

# 添加SSH公钥到GitHub
# 1. 复制公钥
cat ~/.ssh/id_ed25519.pub | pbcopy

# 2. 打开 https://github.com/settings/keys
# 3. 点击 "New SSH key"
# 4. 粘贴公钥并保存

# 添加远程仓库（SSH方式）
git remote add origin git@github.com:YOUR_USERNAME/stock-collection.git

# 推送
git branch -M main
git push -u origin main
```

---

## 第四步：启用GitHub Actions

1. 推送成功后，打开仓库页面
2. 点击 **Actions** 标签
3. 如果提示需要启用，点击 **I understand my workflows, go ahead and enable them**
4. 查看 **A股行情云端采集** 工作流

---

## 第五步：手动触发测试

1. 在Actions页面，点击 **A股行情云端采集** 工作流
2. 点击右上角 **Run workflow** 下拉菜单
3. 选择 `main` 分支
4. 点击 **Run workflow** 绿色按钮
5. 等待30秒，刷新页面查看运行状态

---

## 第六步：查看Artifacts

1. 等待工作流完成（约5-10分钟）
2. 点击完成的workflow run
3. 滚动到底部，查看 **Artifacts** 部分
4. 下载 `stock-data-*` zip文件
5. 解压后可看到：
   - `logs/quotes.db` - SQLite数据库
   - `logs/minute_bars_*.csv` - 分钟K线CSV
   - `logs/candle_*.png` - 蜡烛图
   - `logs/hourly_summary.csv` - 小时汇总
   - `logs/daily_report.md` - 日终报告

---

## 第七步：验证定时任务

### 检查Cron设置

```yaml
# 上午场: 09:25 (UTC+8) = 01:25 (UTC)
- cron: '25 1 * * 1-5'

# 下午场: 12:55 (UTC+8) = 04:55 (UTC)
- cron: '55 4 * * 1-5'
```

### 注意事项

1. **首次运行**：GitHub Actions可能需要几分钟启用
2. **时区**：GitHub使用UTC时间，已自动转换
3. **工作日**：`1-5` 表示周一到周五
4. **超时**：每次运行最多130分钟（7800秒timeout）
5. **费用**：Public仓库免费；Private仓库每月2000分钟免费额度

---

## 第八步：数据同步（可选）

如果想把云端数据自动提交回仓库：

1. 编辑 `.github/workflows/collect.yml`
2. 找到最后一步 `提交数据到仓库`
3. 将 `if: false` 改为 `if: true`
4. 推送更新：

```bash
git add .github/workflows/collect.yml
git commit -m "Enable data commit to repo"
git push
```

**警告**：启用后会频繁提交，仓库体积会快速增长！建议只提交PNG图片和markdown报告。

---

## 故障排查

### 问题：推送被拒绝 `! [rejected]`

```bash
# 强制推送（仅首次，确认远程无重要内容）
git push -u origin main --force
```

### 问题：Actions运行失败

1. 查看错误日志：点击失败的workflow → 点击红色的job → 查看具体步骤错误
2. 常见原因：
   - Python依赖安装失败 → 检查 `requirements.txt`
   - 网络请求超时 → 正常，Sina API可能不稳定
   - SQLite文件锁 → 不影响，数据已保存

### 问题：无法访问私有仓库

```bash
# 使用Personal Access Token（Settings → Developer settings → PAT）
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/stock-collection.git
```

---

## 配置代理（用于在 GitHub Actions 中绕过网站限制）

如果你想在 GitHub Hosted runner 上使用代理，请在仓库 Settings → Secrets → Actions 中添加以下 Secret（可选）：

- `HTTP_PROXY`：例如 `http://user:pass@proxy.example.com:3128`
- `HTTPS_PROXY`：例如 `https://user:pass@proxy.example.com:3129`
- `FORCE_UA`：可选，自定义 User-Agent（用于调试）

工作流会自动将这些 Secrets 注入运行环境，脚本会读取 `HTTP_PROXY` / `HTTPS_PROXY` / `FORCE_UA` 环境变量并应用。

---

## 通过仓库自动触发（推荐，用于测试）

为方便运行和调试，我增加了一个额外的调度工作流（`dispatch-stock-collect.yml`）。你可以创建并推送名为 `trigger/stock-collect` 的分支来触发一次云端采集：

```bash
# 在本地创建并推送触发分支（只用来触发一次）
git checkout -b trigger/stock-collect
git commit --allow-empty -m "trigger stock-collect"
git push origin trigger/stock-collect
```

该操作会触发一个短暂的 workflow，它会使用仓库的 `GITHUB_TOKEN` 调用 `stock-collect` 工作流的 `workflow_dispatch`，从而远程触发一次完整的采集并上传 `logs` 工件。

---

## 后续维护

### 定期拉取云端数据

```bash
cd /Users/lihaoran/Desktop/stock_collection

# 拉取最新提交（如果启用了数据自动提交）
git pull
```

### 更新代码

```bash
# 修改代码后
git add .
git commit -m "描述你的更改"
git push
```

### 暂停定时采集

1. 进入仓库 Settings → Actions → General
2. 选择 **Disable actions** 或删除 `.github/workflows/collect.yml`

---

## 下一步建议

✅ 本地停止采集脚本（Ctrl+C），让云端接管  
✅ 设置每日邮件提醒（GitHub可发送workflow失败通知）  
✅ 定期下载Artifacts，本地分析历史数据  
✅ 等待3-5天积累数据后，开始缠论分型识别开发  

---

**你的代码已经准备好上云了！** ☁️🚀
