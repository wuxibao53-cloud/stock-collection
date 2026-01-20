# 缠论综合交易系统配置

## 交易参数配置

# 分型识别参数
FRACTAL_SETTINGS = {
    'min_bars': 3,  # 分型最少K线数
    'use_close_price': False,  # 是否用收盘价判断分型
}

# 线段识别参数
STROKE_SETTINGS = {
    'min_fractal_count': 2,  # 线段最少分型数
}

# 中枢检测参数
PIVOT_SETTINGS = {
    'min_bars': 5,  # 中枢最少K线数
    'min_overlap': 0.8,  # 最小重叠度
}

# 买卖点算法参数
TRADING_SIGNAL_SETTINGS = {
    'min_fractal_count': 2,  # 最少分型数
    'volume_threshold': 1000,  # 成交量阈值
}

# 区间套分析参数
INTERVAL_ANALYSIS_SETTINGS = {
    'fast_cycle_minutes': 15,  # 快周期K线数
    'mid_cycle_minutes': 5,   # 中周期聚合分钟数
    'slow_cycle_minutes': 60,  # 慢周期聚合分钟数
    'breakout_threshold': 0.01,  # 突破阈值（百分比）
}

# 提醒等级阈值
ALERT_SETTINGS = {
    'weak_level': 1,    # 弱信号阈值
    'medium_level': 2,  # 中等信号阈值
    'strong_level': 3,  # 强信号阈值
    'sync_bonus': 0.3,  # 三周期同步加分
}

# 通知配置
NOTIFICATION_SETTINGS = {
    'enable_dingtalk': False,  # 是否启用钉钉通知
    'dingtalk_webhook': '',    # 钉钉机器人webhook
    'enable_wechat': False,    # 是否启用企业微信通知
    'wechat_webhook': '',      # 企业微信webhook
    'enable_console': True,    # 是否在控制台输出
}

# 回测参数
BACKTEST_SETTINGS = {
    'start_date': '2026-01-01',
    'end_date': '2026-01-31',
    'symbols': ['sh000001', 'sh600519', 'sz300750', 'sz399001'],
    'initial_capital': 100000,  # 初始资金
    'commission_rate': 0.001,   # 手续费率
}

# 数据库配置
DATABASE_SETTINGS = {
    'db_path': 'logs/quotes.db',
    'keep_days': 30,  # 保留数据天数
}

# 日志配置
LOG_SETTINGS = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'file': 'logs/chan_system.log',
    'max_size': 10485760,  # 10MB
    'backup_count': 5,
}
