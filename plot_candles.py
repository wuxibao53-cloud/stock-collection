import os
import argparse
import sqlite3
import csv
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args():
    p = argparse.ArgumentParser(description="分钟K线图绘制（SQLite或CSV）")
    p.add_argument("--source", type=str, choices=["sqlite", "csv"], default="sqlite")
    p.add_argument("--db", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "quotes.db"))
    p.add_argument("--csv", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "minute_bars_20260120.csv"))
    p.add_argument("--symbol", type=str, required=True)
    p.add_argument("--start", type=str, default=None, help="起始时间 YYYY-MM-DD HH:MM")
    p.add_argument("--end", type=str, default=None, help="结束时间 YYYY-MM-DD HH:MM")
    p.add_argument("--out", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "candle.png"))
    return p.parse_args()


def read_minutes_sqlite(db_path, symbol, start=None, end=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    q = "SELECT minute, open, high, low, close FROM minute_bars WHERE symbol=?"
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


def read_minutes_csv(csv_path, symbol, start=None, end=None):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("symbol") != symbol:
                continue
            minute = row.get("minute")
            if start and minute < start:
                continue
            if end and minute > end:
                continue
            try:
                rows.append((minute,
                             float(row.get("open")),
                             float(row.get("high")),
                             float(row.get("low")),
                             float(row.get("close"))))
            except Exception:
                pass
    rows.sort(key=lambda x: x[0])
    return rows


def plot_candles(rows, out_path, title):
    if not rows:
        print("无数据，请确认来源与时间范围")
        return False
    times = [datetime.strptime(m, "%Y-%m-%d %H:%M") for m, *_ in rows]
    opens = [o for _, o, _, _, _ in rows]
    highs = [h for _, _, h, _, _ in rows]
    lows = [l for _, _, _, l, _ in rows]
    closes = [c for _, _, _, _, c in rows]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)

    # 画蜡烛：高低线 + 实体
    width = 0.6  # 柱宽（用索引单位）
    x = list(range(len(times)))
    for i in x:
        color = "#2ecc71" if closes[i] >= opens[i] else "#e74c3c"
        # 高低线
        ax.vlines(i, lows[i], highs[i], color=color, linewidth=1)
        # 实体
        bottom = min(opens[i], closes[i])
        height = abs(closes[i] - opens[i])
        ax.add_patch(plt.Rectangle((i - width/2, bottom), width, height if height > 0 else 0.002, color=color, alpha=0.8))

    # X轴改为时间刻度（稀疏显示）
    ax.set_xticks(x[::max(1, len(x)//10)])
    ax.set_xticklabels([t.strftime("%H:%M") for t in times[::max(1, len(x)//10)]], rotation=0)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path)
    print(f"已保存蜡烛图: {out_path}")
    return True


def main():
    args = parse_args()
    if args.source == "sqlite":
        rows = read_minutes_sqlite(args.db, args.symbol, args.start, args.end)
    else:
        rows = read_minutes_csv(args.csv, args.symbol, args.start, args.end)
    title = f"{args.symbol} Minute Candles"
    plot_candles(rows, args.out, title)


if __name__ == "__main__":
    main()
