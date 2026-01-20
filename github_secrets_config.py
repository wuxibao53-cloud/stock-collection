#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Secrets 快速配置工具
用于测试和验证钉钉、企业微信 Webhook 配置

使用方式：
    python github_secrets_config.py --test-dingtalk <webhook_url>
    python github_secrets_config.py --test-wechat <webhook_url>
    python github_secrets_config.py --show-github-ips
"""

import requests
import json
import hmac
import hashlib
import base64
import time
import argparse
from datetime import datetime
from typing import Tuple, Dict, Any


class GitHubSecretsConfig:
    """GitHub Secrets 配置和测试工具"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10
    
    # ==================== 钉钉相关 ====================
    
    @staticmethod
    def sign_dingtalk(secret: str) -> Tuple[str, str]:
        """生成钉钉加签（如果启用了加签功能）
        
        Args:
            secret: 钉钉机器人的 Secret
            
        Returns:
            (timestamp, sign) 元组
        """
        timestamp = str(int(time.time() * 1000))
        sign_data = f"{timestamp}\n{secret}"
        sign = hmac.new(
            secret.encode(),
            sign_data.encode(),
            hashlib.sha256
        ).digest()
        sign = base64.b64encode(sign).decode()
        return timestamp, sign
    
    def test_dingtalk_webhook(self, webhook_url: str, secret: str = None) -> Dict[str, Any]:
        """测试钉钉 Webhook 连接
        
        Args:
            webhook_url: 钉钉 Webhook 完整 URL
            secret: 钉钉机器人 Secret（如果启用了加签）
            
        Returns:
            测试结果字典
        """
        print("\n" + "="*60)
        print("🔔 测试钉钉 Webhook")
        print("="*60)
        
        result = {
            "service": "dingtalk",
            "timestamp": datetime.now().isoformat(),
            "status": "UNKNOWN",
            "details": {}
        }
        
        # 1. URL 验证
        print("\n[1/3] 验证 Webhook URL...")
        if not webhook_url or not webhook_url.startswith("https://"):
            print("❌ URL 无效")
            result["status"] = "INVALID_URL"
            result["details"]["url_check"] = "URL 必须以 https:// 开头"
            return result
        print(f"✓ URL 格式正确: {webhook_url[:50]}...")
        
        # 2. 准备消息
        print("\n[2/3] 准备测试消息...")
        test_message = {
            "msgtype": "text",
            "text": {
                "content": f"✅ 缠论交易系统告警测试成功\n"
                          f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"源: GitHub Actions\n"
                          f"状态: 连接正常 🎉"
            }
        }
        print(f"✓ 消息已准备: {json.dumps(test_message, ensure_ascii=False, indent=2)}")
        
        # 3. 发送请求
        print("\n[3/3] 发送 Webhook 请求...")
        try:
            # 如果提供了 Secret，添加加签参数
            url = webhook_url
            if secret:
                timestamp, sign = self.sign_dingtalk(secret)
                url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
                print(f"  使用加签: timestamp={timestamp[:10]}..., sign={sign[:20]}...")
            
            response = self.session.post(
                url,
                json=test_message,
                headers={"Content-Type": "application/json"}
            )
            
            result["details"]["http_status"] = response.status_code
            result["details"]["response_body"] = response.text
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("errcode") == 0:
                    print(f"✓ 请求成功 (HTTP {response.status_code})")
                    print(f"✓ 响应: {response_data.get('errmsg', 'OK')}")
                    result["status"] = "SUCCESS"
                    return result
                else:
                    print(f"❌ 钉钉返回错误: {response_data.get('errmsg', '未知错误')}")
                    result["status"] = "DINGTALK_ERROR"
                    result["details"]["error_message"] = response_data.get("errmsg")
                    return result
            else:
                print(f"❌ HTTP 错误 {response.status_code}")
                result["status"] = "HTTP_ERROR"
                return result
                
        except requests.Timeout:
            print(f"❌ 请求超时 (>10秒)")
            result["status"] = "TIMEOUT"
            result["details"]["error"] = "Connection timeout"
        except requests.ConnectionError as e:
            print(f"❌ 连接错误: {str(e)}")
            result["status"] = "CONNECTION_ERROR"
            result["details"]["error"] = str(e)
        except Exception as e:
            print(f"❌ 未预期的错误: {str(e)}")
            result["status"] = "UNKNOWN_ERROR"
            result["details"]["error"] = str(e)
        
        return result
    
    # ==================== 企业微信相关 ====================
    
    def test_wechat_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """测试企业微信 Webhook 连接
        
        Args:
            webhook_url: 企业微信 Webhook 完整 URL
            
        Returns:
            测试结果字典
        """
        print("\n" + "="*60)
        print("💬 测试企业微信 Webhook")
        print("="*60)
        
        result = {
            "service": "wechat",
            "timestamp": datetime.now().isoformat(),
            "status": "UNKNOWN",
            "details": {}
        }
        
        # 1. URL 验证
        print("\n[1/3] 验证 Webhook URL...")
        if not webhook_url or not webhook_url.startswith("https://"):
            print("❌ URL 无效")
            result["status"] = "INVALID_URL"
            result["details"]["url_check"] = "URL 必须以 https:// 开头"
            return result
        print(f"✓ URL 格式正确: {webhook_url[:50]}...")
        
        # 2. 准备消息
        print("\n[2/3] 准备测试消息...")
        test_message = {
            "msgtype": "text",
            "text": {
                "content": f"✅ 缠论交易系统告警测试成功\n"
                          f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"源: GitHub Actions\n"
                          f"状态: 连接正常 🎉"
            }
        }
        print(f"✓ 消息已准备: {json.dumps(test_message, ensure_ascii=False, indent=2)}")
        
        # 3. 发送请求
        print("\n[3/3] 发送 Webhook 请求...")
        try:
            response = self.session.post(
                webhook_url,
                json=test_message,
                headers={"Content-Type": "application/json"}
            )
            
            result["details"]["http_status"] = response.status_code
            result["details"]["response_body"] = response.text
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("errcode") == 0:
                    print(f"✓ 请求成功 (HTTP {response.status_code})")
                    print(f"✓ 响应: {response_data.get('errmsg', 'OK')}")
                    result["status"] = "SUCCESS"
                    return result
                else:
                    print(f"❌ 企业微信返回错误: {response_data.get('errmsg', '未知错误')}")
                    result["status"] = "WECHAT_ERROR"
                    result["details"]["error_message"] = response_data.get("errmsg")
                    return result
            else:
                print(f"❌ HTTP 错误 {response.status_code}")
                result["status"] = "HTTP_ERROR"
                return result
                
        except requests.Timeout:
            print(f"❌ 请求超时 (>10秒)")
            result["status"] = "TIMEOUT"
            result["details"]["error"] = "Connection timeout"
        except requests.ConnectionError as e:
            print(f"❌ 连接错误: {str(e)}")
            result["status"] = "CONNECTION_ERROR"
            result["details"]["error"] = str(e)
        except Exception as e:
            print(f"❌ 未预期的错误: {str(e)}")
            result["status"] = "UNKNOWN_ERROR"
            result["details"]["error"] = str(e)
        
        return result
    
    # ==================== GitHub 相关 ====================
    
    def get_github_actions_ips(self) -> Dict[str, Any]:
        """获取 GitHub Actions 的 IP 范围
        
        用于在钉钉/企业微信中配置 IP 白名单
        
        Returns:
            GitHub IP 范围信息
        """
        print("\n" + "="*60)
        print("🌐 获取 GitHub Actions IP 范围")
        print("="*60)
        
        try:
            response = requests.get("https://api.github.com/meta")
            if response.status_code == 200:
                data = response.json()
                actions_ips = data.get("actions", [])
                
                print(f"\n✓ GitHub Actions IPv4 范围 ({len(actions_ips)} 个):")
                for ip_range in actions_ips[:5]:  # 只显示前5个
                    print(f"  • {ip_range}")
                if len(actions_ips) > 5:
                    print(f"  ... 以及其他 {len(actions_ips) - 5} 个范围")
                
                print(f"\n✓ 完整 IP 列表可用于 Webhook IP 白名单配置")
                return {
                    "status": "SUCCESS",
                    "total_ranges": len(actions_ips),
                    "sample_ranges": actions_ips[:5]
                }
            else:
                print(f"❌ 获取失败 (HTTP {response.status_code})")
                return {"status": "FAILED", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return {"status": "ERROR", "error": str(e)}
    
    # ==================== 配置生成 ====================
    
    @staticmethod
    def generate_github_cli_commands(dingtalk_url: str, wechat_url: str) -> str:
        """生成 GitHub CLI 命令用于快速配置 Secrets
        
        Args:
            dingtalk_url: 钉钉 Webhook URL
            wechat_url: 企业微信 Webhook URL
            
        Returns:
            可直接执行的命令字符串
        """
        commands = f"""
# GitHub CLI 快速配置命令
# 复制并在终端执行：

# 1. 添加钉钉 Webhook
gh secret set DINGTALK_WEBHOOK --body "{dingtalk_url}" --repo wuxibao53-cloud/stock-collection

# 2. 添加企业微信 Webhook
gh secret set WECHAT_WEBHOOK --body "{wechat_url}" --repo wuxibao53-cloud/stock-collection

# 3. 验证 Secrets
gh secret list --repo wuxibao53-cloud/stock-collection
"""
        return commands


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Secrets 快速配置和测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：

  # 测试钉钉 Webhook
  python github_secrets_config.py --test-dingtalk "https://oapi.dingtalk.com/robot/send?access_token=XXX"

  # 测试钉钉 Webhook (带加签)
  python github_secrets_config.py --test-dingtalk "https://oapi.dingtalk.com/robot/send?access_token=XXX" --dingtalk-secret "YOUR_SECRET"

  # 测试企业微信 Webhook
  python github_secrets_config.py --test-wechat "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX"

  # 获取 GitHub Actions IP 范围
  python github_secrets_config.py --show-github-ips

  # 生成配置命令
  python github_secrets_config.py --generate-commands \\
    --dingtalk-url "https://oapi.dingtalk.com/..." \\
    --wechat-url "https://qyapi.weixin.qq.com/..."
        """
    )
    
    parser.add_argument("--test-dingtalk", help="测试钉钉 Webhook URL")
    parser.add_argument("--test-wechat", help="测试企业微信 Webhook URL")
    parser.add_argument("--dingtalk-secret", help="钉钉机器人 Secret（可选，用于加签）")
    parser.add_argument("--show-github-ips", action="store_true", help="显示 GitHub Actions IP 范围")
    parser.add_argument("--generate-commands", action="store_true", help="生成 GitHub CLI 命令")
    parser.add_argument("--dingtalk-url", help="钉钉 Webhook URL（用于生成命令）")
    parser.add_argument("--wechat-url", help="企业微信 Webhook URL（用于生成命令）")
    
    args = parser.parse_args()
    
    config = GitHubSecretsConfig()
    
    if args.test_dingtalk:
        result = config.test_dingtalk_webhook(args.test_dingtalk, args.dingtalk_secret)
        print(f"\n📊 测试结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    elif args.test_wechat:
        result = config.test_wechat_webhook(args.test_wechat)
        print(f"\n📊 测试结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    elif args.show_github_ips:
        result = config.get_github_actions_ips()
        print(f"\n📊 结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    elif args.generate_commands:
        if not args.dingtalk_url or not args.wechat_url:
            print("❌ 错误: 需要提供 --dingtalk-url 和 --wechat-url")
            return
        commands = config.generate_github_cli_commands(args.dingtalk_url, args.wechat_url)
        print(commands)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
