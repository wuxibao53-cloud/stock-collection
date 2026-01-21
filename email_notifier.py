#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件通知系统 - 带K线图和信号标记

功能：
1. 生成K线图（matplotlib + 分型/中枢/买卖点标记）
2. HTML邮件模板
3. SMTP发送
4. 信号内容组织
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use('Agg')  # 非GUI后端
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import pandas as pd
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib未安装，图表功能不可用")


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, 
                 smtp_server: str = 'smtp.163.com',
                 smtp_port: int = 465,
                 from_email: str = '',
                 password: str = '',
                 to_emails: List[str] = None):
        """
        初始化邮件通知器
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口（465为SSL）
            from_email: 发件人邮箱
            password: 邮箱密码或授权码
            to_emails: 收件人列表
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.password = password
        self.to_emails = to_emails or []
    
    def generate_kline_chart(self, 
                            symbol: str, 
                            klines: List[Dict],
                            fractals: List = None,
                            centers: List = None,
                            signals: List = None,
                            output_path: str = 'logs/chart.png') -> str:
        """
        生成K线图（带标记）
        
        Args:
            symbol: 股票代码
            klines: K线数据
            fractals: 分型列表
            centers: 中枢列表
            signals: 信号列表
            output_path: 输出路径
        
        Returns:
            图片文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib未安装")
            return None
        
        if not klines:
            logger.warning(f"{symbol} 无K线数据")
            return None
        
        # 准备数据
        df = pd.DataFrame(klines)
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')
        
        # 创建图表
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        
        # 绘制K线
        for idx, row in df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            # K线实体
            ax.plot([idx, idx], [row['low'], row['high']], color='black', linewidth=0.5)
            height = abs(row['close'] - row['open'])
            bottom = min(row['open'], row['close'])
            rect = Rectangle((mdates.date2num(idx) - 0.0003, bottom), 0.0006, height, 
                           facecolor=color, edgecolor='black', linewidth=0.5)
            ax.add_patch(rect)
        
        # 标记分型
        if fractals:
            top_times = [f.time for f in fractals if f.fractal_type == 'top']
            top_prices = [f.price for f in fractals if f.fractal_type == 'top']
            bottom_times = [f.time for f in fractals if f.fractal_type == 'bottom']
            bottom_prices = [f.price for f in fractals if f.fractal_type == 'bottom']
            
            if top_times:
                ax.scatter(pd.to_datetime(top_times), top_prices, 
                          marker='v', color='purple', s=100, label='顶分型', zorder=5)
            if bottom_times:
                ax.scatter(pd.to_datetime(bottom_times), bottom_prices, 
                          marker='^', color='orange', s=100, label='底分型', zorder=5)
        
        # 标记中枢
        if centers:
            for center in centers[-3:]:  # 最近3个中枢
                start_time = pd.to_datetime(center.start_time)
                end_time = pd.to_datetime(center.end_time)
                ax.axhspan(center.low, center.high, 
                          xmin=mdates.date2num(start_time)/mdates.date2num(df.index[-1]),
                          xmax=mdates.date2num(end_time)/mdates.date2num(df.index[-1]),
                          alpha=0.2, color='blue', label='中枢')
        
        # 标记买卖点
        if signals:
            for sig in signals:
                sig_time = pd.to_datetime(sig.time)
                if 'buy' in sig.signal_type.value:
                    ax.scatter([sig_time], [sig.price], marker='*', 
                             color='red', s=300, label=sig.signal_type.value.upper(), zorder=10)
                else:
                    ax.scatter([sig_time], [sig.price], marker='*', 
                             color='green', s=300, label=sig.signal_type.value.upper(), zorder=10)
        
        # 设置标题和标签
        ax.set_title(f'{symbol} K线图与缠论信号', fontsize=16, fontweight='bold')
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('价格', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        
        # 格式化x轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=45)
        
        # 保存图片
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✓ 图表已生成: {output_path}")
        return output_path
    
    def compose_html_email(self, 
                          symbol: str, 
                          signal_type: str,
                          price: float,
                          reason: str,
                          suggested_entry: float,
                          stop_loss: float,
                          take_profit: float,
                          confidence: float,
                          chart_path: str = None) -> str:
        """
        组织HTML邮件内容
        
        Returns:
            HTML内容字符串
        """
        signal_color = '#FF4444' if 'buy' in signal_type.lower() else '#44FF44'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background-color: {signal_color}; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .signal-type {{ font-size: 24px; font-weight: bold; }}
                .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .info-table td {{ padding: 12px; border-bottom: 1px solid #eee; }}
                .info-table .label {{ font-weight: bold; width: 150px; color: #666; }}
                .info-table .value {{ color: #333; }}
                .chart {{ text-align: center; margin: 20px 0; }}
                .chart img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 5px; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 2px solid #eee; color: #999; font-size: 12px; text-align: center; }}
                .confidence {{ font-size: 18px; font-weight: bold; color: {signal_color}; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="signal-type">🚨 {signal_type.upper()} 信号</div>
                    <div style="margin-top: 10px;">{symbol} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                </div>
                
                <table class="info-table">
                    <tr>
                        <td class="label">📊 当前价格</td>
                        <td class="value">¥{price:.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">💡 信号理由</td>
                        <td class="value">{reason}</td>
                    </tr>
                    <tr>
                        <td class="label">🎯 建议入场</td>
                        <td class="value" style="color: #FF4444; font-weight: bold;">¥{suggested_entry:.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">🛡️ 止损位</td>
                        <td class="value" style="color: #FF8800;">¥{stop_loss:.2f} ({(stop_loss/price-1)*100:+.2f}%)</td>
                    </tr>
                    <tr>
                        <td class="label">💰 止盈位</td>
                        <td class="value" style="color: #44AA44;">¥{take_profit:.2f} ({(take_profit/price-1)*100:+.2f}%)</td>
                    </tr>
                    <tr>
                        <td class="label">⭐ 置信度</td>
                        <td class="value"><span class="confidence">{confidence:.0%}</span></td>
                    </tr>
                </table>
                
                {"<div class='chart'><img src='cid:chart' alt='K线图' /></div>" if chart_path else ""}
                
                <div class="footer">
                    <p>此邮件由缠论交易系统自动发送</p>
                    <p>技术分析仅供参考，投资需谨慎</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_signal_email(self, 
                         symbol: str,
                         signal: Dict,
                         chart_path: str = None) -> bool:
        """
        发送信号邮件
        
        Args:
            symbol: 股票代码
            signal: 信号字典
            chart_path: K线图路径
        
        Returns:
            是否成功
        """
        if not self.from_email or not self.password:
            logger.error("邮箱配置未设置")
            return False
        
        if not self.to_emails:
            logger.error("收件人列表为空")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('related')
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[{signal.get('signal_type', '').upper()}] {symbol} 交易信号"
            
            # HTML内容
            html_content = self.compose_html_email(
                symbol=symbol,
                signal_type=signal.get('signal_type', ''),
                price=signal.get('price', 0),
                reason=signal.get('reason', ''),
                suggested_entry=signal.get('suggested_entry', 0),
                stop_loss=signal.get('stop_loss', 0),
                take_profit=signal.get('take_profit', 0),
                confidence=signal.get('confidence', 0),
                chart_path=chart_path
            )
            
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 附加图片
            if chart_path and os.path.exists(chart_path):
                with open(chart_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<chart>')
                    msg.attach(img)
            
            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            logger.info(f"✓ 邮件已发送: {symbol} {signal.get('signal_type')}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 测试用例
    notifier = EmailNotifier(
        smtp_server='smtp.163.com',
        from_email='your-email@163.com',  # 需要配置
        password='your-password',  # 需要配置
        to_emails=['receiver@example.com']
    )
    
    # 模拟信号
    test_signal = {
        'signal_type': 'BUY1',
        'price': 1850.00,
        'reason': '向下笔完成，形成底分型于1845.50',
        'suggested_entry': 1860.00,
        'stop_loss': 1810.00,
        'take_profit': 1920.00,
        'confidence': 0.85
    }
    
    print("邮件通知系统已就绪")
    print("请配置SMTP设置后测试")
