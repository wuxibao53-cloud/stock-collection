# 🎯 快速参考卡 - 缠论交易系统

## 🚀 三步启动

```bash
# ① 快速测试 (推荐先试)
python3 run_complete_system.py --mode all --collect-mode hot --no-backtest

# ② 查看报告
cat logs/analysis_report.txt

# ③ 完整运行 (包括回测)
python3 run_complete_system.py --mode all --collect-mode all
```

---

## 📊 性能数据

| 操作 | 耗时 | 数据量 |
|------|------|--------|
| 采集26股 | 0.9秒 | 26-104条K线 |
| 分析26股 | 0.1秒 | 生成0-N条信号 |
| 完整流程 | ~1秒 | 采集+分析 |
| 采集5000+股 | ~6分钟 | 50,000+条K线 |

---

## 🎯 信号类型

### 买点 (对应卖点)
```
第一类: 线段完成 (下跌→上升)      置信度: 75%
第二类: 盘整突破 (上沿突破)       置信度: 70%
第三类: 多周期共振 (1m+5m+60m)   置信度: 85% ⭐
```

### 风险参数
```
单笔最大亏损: 2%
最大持仓: 10%
止损幅度: 3%
风险/收益: 1:2
```

---

## 📁 关键文件

| 文件 | 用途 |
|------|------|
| `run_complete_system.py` | ⭐ 一键启动 |
| `DEPLOYMENT_GUIDE.md` | 📖 部署指南 |
| `PROJECT_STATUS.md` | 📊 项目报告 |
| `logs/quotes.db` | 💾 数据库 |
| `logs/analysis_report.txt` | 📈 信号报告 |

---

## 🔧 故障排查

| 问题 | 解决方案 |
|------|--------|
| 采集0条 | `curl -s 'https://hq.sinajs.cn/list=sh000001'` |
| 无信号 | 需要10+条K线数据 |
| 超时 | 增加timeout: 30→45分钟 |
| 错误 | 查看 `logs/collector.log` |

---

## 🌐 GitHub Actions

```
进入: GitHub → Actions → stock-collect
运行: Run workflow
选择: hot (1分钟) / all (8分钟)
下载: Artifacts报告
```

---

**版本**: v2.0 | **状态**: ✅ 生产就绪 | **文档**: 完整
