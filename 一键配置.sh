#!/bin/bash
# 缠论系统 - 快速配置脚本
# 使用方法：bash 一键配置.sh

echo "════════════════════════════════════════════════════════"
echo "      缠论交易系统 - 快速配置助手"
echo "════════════════════════════════════════════════════════"
echo ""

# 检查是否在正确的目录
if [ ! -f "notify_alert.py" ]; then
    echo "❌ 错误：请在 stock_collection 目录下运行此脚本"
    echo "   cd /Users/lihaoran/Desktop/stock_collection"
    exit 1
fi

echo "✅ 目录检查通过"
echo ""

# 步骤 1: 测试钉钉 Webhook
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第一步：测试钉钉 Webhook 连接"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -z "$DINGTALK_WEBHOOK" ]; then
    echo "⚠️  环境变量 DINGTALK_WEBHOOK 未设置"
    echo ""
    echo "请按以下步骤操作："
    echo "1. 打开钉钉，创建群机器人"
    echo "2. 复制 Webhook URL"
    echo "3. 运行命令："
    echo ""
    echo "   export DINGTALK_WEBHOOK=\"你的URL\""
    echo "   bash 一键配置.sh"
    echo ""
    exit 1
else
    echo "✓ 检测到 DINGTALK_WEBHOOK"
    echo "  URL: ${DINGTALK_WEBHOOK:0:50}..."
    echo ""
    
    echo "正在测试连接..."
    python github_secrets_config.py --test-dingtalk "$DINGTALK_WEBHOOK"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ 钉钉连接测试成功！"
        echo "   请检查钉钉群是否收到消息"
        echo ""
    else
        echo ""
        echo "❌ 钉钉连接测试失败"
        echo "   请检查 Webhook URL 是否正确"
        exit 1
    fi
fi

# 步骤 2: 测试通知系统
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第二步：测试通知系统"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "正在发送测试通知..."
export GITHUB_RUN_ID="test-local"
export GITHUB_REPOSITORY="wuxibao53-cloud/stock-collection"
export GITHUB_SERVER_URL="https://github.com"

python notify_alert.py \
    --status success \
    --symbols 100 \
    --records 5000 \
    --runtime 120 \
    --message "本地测试 - 系统配置中"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 通知系统测试成功！"
    echo "   请检查钉钉群是否收到详细报告"
    echo ""
else
    echo ""
    echo "⚠️  通知系统测试失败，但可以继续"
    echo ""
fi

# 步骤 3: GitHub CLI 检查
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第三步：配置 GitHub Secrets"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v gh &> /dev/null; then
    echo "✓ 检测到 GitHub CLI (gh)"
    echo ""
    
    read -p "是否使用 GitHub CLI 配置 Secret？(y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "正在配置 GitHub Secret..."
        gh secret set DINGTALK_WEBHOOK \
            --body "$DINGTALK_WEBHOOK" \
            --repo wuxibao53-cloud/stock-collection
        
        if [ $? -eq 0 ]; then
            echo "✅ GitHub Secret 配置成功！"
            echo ""
            echo "验证配置："
            gh secret list --repo wuxibao53-cloud/stock-collection
        else
            echo "❌ GitHub Secret 配置失败"
            echo "   请使用 Web 界面手动配置"
        fi
    else
        echo ""
        echo "请手动在 GitHub 网页配置 Secret："
        echo "1. 访问：https://github.com/wuxibao53-cloud/stock-collection/settings/secrets/actions"
        echo "2. 点击：New repository secret"
        echo "3. Name: DINGTALK_WEBHOOK"
        echo "4. Secret: $DINGTALK_WEBHOOK"
        echo "5. 点击：Add secret"
    fi
else
    echo "⚠️  未检测到 GitHub CLI"
    echo ""
    echo "请使用以下两种方式之一配置："
    echo ""
    echo "方式 A: 安装 GitHub CLI"
    echo "  brew install gh"
    echo "  gh auth login"
    echo "  gh secret set DINGTALK_WEBHOOK --body \"$DINGTALK_WEBHOOK\""
    echo ""
    echo "方式 B: 使用 Web 界面"
    echo "  访问：https://github.com/wuxibao53-cloud/stock_collection/settings/secrets/actions"
    echo "  添加 Secret: DINGTALK_WEBHOOK"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "配置完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ 已完成："
echo "  • 钉钉 Webhook 连接测试"
echo "  • 通知系统功能测试"
echo "  • GitHub Secret 配置指引"
echo ""
echo "📋 下一步："
echo "  1. 确认 GitHub Secret 已配置"
echo "  2. 访问：https://github.com/wuxibao53-cloud/stock-collection/actions"
echo "  3. 点击：Run workflow"
echo "  4. 选择模式：alert"
echo "  5. 等待完成，查看钉钉通知"
echo ""
echo "📚 查看完整指南："
echo "  cat 快速上手指南.md"
echo ""
echo "════════════════════════════════════════════════════════"
