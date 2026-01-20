
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import Exchange, Interval

print("VnPy 导入成功！")
print(f"可用的交易所: {[e.value for e in Exchange][:3]}")  # 显示前3个交易所
print(f"可用的时间周期: {[i.value for i in Interval][:3]}")  # 显示前3个时间周期