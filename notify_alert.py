#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级告警通知系统
支持钉钉、企业微信、Email 多渠道推送

使用方式：
    python notify_alert.py \
        --status success \
        --message "采集成功" \
        --symbols 5000 \
        --records 50000 \
        --runtime 120
"""

import requests
import json
import os
import sys
import argparse
import hmac
import hashlib
import base64
import time
from datetime import datetime
from typing import Dict, Any, Optional


class AlertNotifier:
    """多渠道告警通知器"""
    
    def __init__(self):
        self.dingtalk_webhook = os.getenv("DINGTALK_WEBHOOK")
        self.wechat_webhook = os.getenv("WECHAT_WEBHOOK")
        self.run_id = os.getenv("GITHUB_RUN_ID", "unknown")
        self.repo = os.getenv("GITHUB_REPOSITORY", "stock-collection")
        self.server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    
    def _build_dingtalk_message(self, title: str, content: str, status: str) -> Dict[str, Any]:
        """构建钉钉消息格式"""
        color_map = {
            "success": "#07C160",  # 绿色
            "failure": "#FF3B30",  # 红色
            "warning": "#FFA500"   # 橙色
        }
        
        status_emoji = {
            "success": "✅",
            "failure": "❌",
            "warning": "⚠️"
        }
        
        return {
            "msgtype": "actionCard",
            "actionCard": {
                "title": f"{status_emoji.get(status, '📢')} {title}",
                "text": content,
                "btnOrientation": "0",
                "buttons": [
                    {
                        "title": "查看详情",
                        "actionURL": f"{self.server_url}/{self.repo}/actions/runs/{self.run_id}"
                    }
                ]
            }
        }
    
    def _build_wechat_message(self, title: str, content: str, status: str) -> Dict[str, Any]:
        """构建企业微信消息格式"""
        color_map = {
            "success": "#07C160",
            "failure": "#FF3B30",
            "warning": "#FFA500"
        }
        
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n{content}\n\n"
                          f"[查看详情]({self.server_url}/{self.repo}/actions/runs/{self.run_id})"
            }
        }
    
    def send_dingtalk(self, title: str, content: str, status: str = "info") -> bool:
        """发送钉钉通知"""
        if not self.dingtalk_webhook:
            print("⚠️  DINGTALK_WEBHOOK 未配置")
            return False
        
        try:
            message = self._build_dingtalk_message(title, content, status)
            response = requests.post(
                self.dingtalk_webhook,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"✅ 钉钉通知已发送")
                    return True
                else:
                    print(f"❌ 钉钉返回错误: {result.get('errmsg')}")
                    return False
            else:
                print(f"❌ 钉钉请求失败 (HTTP {response.status_code})")
                return False
        except Exception as e:
            print(f"❌ 钉钉发送异常: {str(e)}")
            return False
    
    def send_wechat(self, title: str, content: str, status: str = "info") -> bool:
        """发送企业微信通知"""
        if not self.wechat_webhook:
            print("⚠️  WECHAT_WEBHOOK 未配置")
            return False
        
        try:
            message = self._build_wechat_message(title, content, status)
            response = requests.post(
                self.wechat_webhook,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"✅ 企业微信通知已发送")
                    return True
                else:
                    print(f"❌ 企业微信返回错误: {result.get('errmsg')}")
                    return False
            else:
                print(f"❌ 企业微信请求失败 (HTTP {response.status_code})")
                return False
        except Exception as e:
            print(f"❌ 企业微信发送异常: {str(e)}")
            return False
    
    def send_all(self, title: str, content: str, status: str = "info"):
        """同时发送到所有渠道"""
        print(f"\n{'='*60}")
        print(f"📢 发送告警通知 [{status.upper()}]")
        print(f"{'='*60}")
        
        results = {
            "dingtalk": self.send_dingtalk(title, content, status),
            "wechat": self.send_wechat(title, content, status)
        }
        
        print(f"\n📊 通知结果:")
        for channel, success in results.items():
            status_icon = "✅" if success else "❌"
            print(f"  {status_icon} {channel}: {'成功' if success else '失败'}")
        
        return results


def format_collection_report(
    status: str,
    symbols: int,
    records: int,
    runtime: float,
    message: str = ""
) -> str:
    """格式化采集报告"""
    
    status_emoji = {
        "success": "✅",
        "failure": "❌",
        "warning": "⚠️"
    }
    
    report = f"""
### 缠论交易系统 - 采集报告

**状态**: {status_emoji.get(status, '❓')} {status.upper()}

**基本信息**:
- 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 采集股票数: {symbols:,} 只
- 采集数据条数: {records:,} 条
- 平均记录数/股票: {records // max(symbols, 1):,.0f}
- 执行耗时: {runtime:.1f} 秒

**性能指标**:
- 吞吐量: {records / max(runtime, 0.1):.0f} 条/秒
- 平均处理速度: {runtime / max(symbols, 1) * 1000:.1f} ms/只

**备注**: {message or '采集完成'}
"""
    
    return report


def format_error_report(error_message: str, traceback: str = "") -> str:
    """格式化错误报告"""
    report = f"""
### 缠论交易系统 - 错误报告

**错误描述**: {error_message}

{"**错误追踪**:" + f"\n```\n{traceback}\n```" if traceback else ""}

**可能原因**:
1. 网络连接问题（Sina API 无法访问）
2. API 限流（频率过高）
3. 数据库连接问题
4. 磁盘空间不足

**推荐操作**:
- 检查网络连接
- 查看 GitHub Actions 日志
- 重试或手动触发工作流
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="缠论系统多渠道告警通知")
    parser.add_argument("--status", choices=["success", "failure", "warning"], 
                       default="info", help="通知状态")
    parser.add_argument("--message", default="", help="自定义消息")
    parser.add_argument("--symbols", type=int, default=0, help="采集股票数")
    parser.add_argument("--records", type=int, default=0, help="采集数据条数")
    parser.add_argument("--runtime", type=float, default=0, help="执行耗时（秒）")
    parser.add_argument("--error", default="", help="错误信息")
    parser.add_argument("--traceback", default="", help="错误追踪信息")
    
    args = parser.parse_args()
    
    notifier = AlertNotifier()
    
    # 根据不同场景生成不同内容
    if args.status == "failure" or args.error:
        title = "❌ 缠论系统采集失败"
        content = format_error_report(
            args.error or args.message or "未知错误",
            args.traceback
        )
        status = "failure"
    else:
        title = f"✅ 缠论系统采集成功"
        content = format_collection_report(
            args.status,
            args.symbols,
            args.records,
            args.runtime,
            args.message
        )
        status = args.status
    
    # 发送通知
    results = notifier.send_all(title, content, status)
    
    # 返回状态码
    success_count = sum(1 for v in results.values() if v)
    if success_count > 0:
        print(f"\n✅ 至少一个通知渠道发送成功")
        sys.exit(0)
    else:
        print(f"\n⚠️  所有通知渠道发送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
