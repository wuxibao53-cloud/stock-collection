import os
import argparse
import sqlite3
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def parse_args():
    p = argparse.ArgumentParser(description="从SQLite绘制分钟收盘线图")
    p.add_argument("--db", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "quotes.db"))
    p.add_argument("--symbol", type=str, required=True)
    p.add_argument("--start", type=str, default=None, help="起始时间，格式 YYYY-MM-DD HH:MM")
    p.add_argument("--end", type=str, default=None, help="结束时间，格式 YYYY-MM-DD HH:MM")
    p.add_argument("--out", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "plot.png"))
    return p.parse_args()

def query_minutes(db_path, symbol, start=None, end=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    q = "SELECT minute, close FROM minute_bars WHERE symbol=?"
    params = [symbol]
    if start:
        q += " AND minute>=?"
        params.append(start)
    if end:
        q += " AND minute<=?"
        params.append(end)
    q += " ORDER BY minute"
    rows = cur.execute(q, params).fetchall()
    conn.close()
    return rows

def main():
    args = parse_args()
    rows = query_minutes(args.db, args.symbol, args.start, args.end)
    if not rows:
        print("无数据，请确认参数或持续运行采集后再试。")
        return
    x = [datetime.strptime(m, "%Y-%m-%d %H:%M") for m, _ in rows]
    y = [float(c) if c is not None else None for _, c in rows]
    plt.figure(figsize=(10, 4))
    plt.plot(x, y, label=f"{args.symbol} close")
    plt.xlabel("Time")
    plt.ylabel("Close")
    plt.title(f"Minute Close - {args.symbol}")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    plt.savefig(args.out)
    print(f"已保存图像: {args.out}")

if __name__ == "__main__":
    main()
