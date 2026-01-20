import os
import argparse
import sqlite3
import csv
from collections import defaultdict


def parse_args():
    p = argparse.ArgumentParser(description="每小时小结与日终统计（来自SQLite或分钟CSV）")
    p.add_argument("--source", type=str, choices=["sqlite", "csv"], default="sqlite")
    p.add_argument("--db", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "quotes.db"))
    p.add_argument("--csv", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "minute_bars_20260120.csv"))
    p.add_argument("--date", type=str, required=False, help="日期YYYY-MM-DD，仅SQLite时用于筛选")
    p.add_argument("--out-hourly", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "hourly_summary.csv"))
    p.add_argument("--out-daily", type=str, default=os.path.join(os.path.dirname(__file__), "logs", "daily_report.md"))
    return p.parse_args()


def read_minutes_sqlite(db_path, date=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    q = "SELECT minute,symbol,open,high,low,close,volume,amount FROM minute_bars"
    params = []
    if date:
        q += " WHERE minute LIKE ?"
        params.append(f"{date}%")
    q += " ORDER BY minute"
    rows = cur.execute(q, params).fetchall()
    conn.close()
    return rows


def read_minutes_csv(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append((row.get("minute"), row.get("symbol"), float(row.get("open")), float(row.get("high")), float(row.get("low")), float(row.get("close")),
                             int(row.get("volume")) if row.get("volume") else 0,
                             float(row.get("amount")) if row.get("amount") else 0.0))
            except Exception:
                pass
    rows.sort(key=lambda x: x[0])
    return rows


def compute_hourly_summary(rows):
    # rows: (minute, symbol, open, high, low, close, volume, amount)
    buckets = defaultdict(lambda: defaultdict(list))
    for minute, sym, o, h, l, c, v, a in rows:
        hour = minute[:13]  # YYYY-MM-DD HH
        buckets[hour][sym].append((o, h, l, c, v, a))
    hourly = []
    for hour, symdict in buckets.items():
        for sym, items in symdict.items():
            o = items[0][0]
            h = max(x[1] for x in items)
            l = min(x[2] for x in items)
            c = items[-1][3]
            v = sum(x[4] for x in items if x[4] is not None)
            a = sum(x[5] for x in items if x[5] is not None)
            rng = h - l
            hourly.append((hour, sym, o, h, l, c, v, a, rng, len(items)))
    return hourly


def compute_daily_report(rows):
    # For each symbol: first open, last close, total volume/amount, max/min
    by_sym = defaultdict(list)
    for minute, sym, o, h, l, c, v, a in rows:
        by_sym[sym].append((o, h, l, c, v, a))
    report = []
    for sym, items in by_sym.items():
        o0 = items[0][0]
        cL = items[-1][3]
        vmax = max(x[4] for x in items)  # volume
        asum = sum(x[5] for x in items)
        hmax = max(x[1] for x in items)
        lmin = min(x[2] for x in items)
        pct = (cL - o0) / o0 * 100.0 if o0 else 0.0
        report.append((sym, o0, cL, pct, vmax, asum, hmax, lmin))
    # Rankings by pct and volume
    top_pct = sorted(report, key=lambda x: x[3], reverse=True)
    top_vol = sorted(report, key=lambda x: x[4], reverse=True)
    return report, top_pct, top_vol


def write_hourly_csv(hourly, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hour", "symbol", "open", "high", "low", "close", "volume", "amount", "range", "samples"])
        w.writerows(hourly)
    print(f"已写入小时小结: {out_path}")


def write_daily_md(report, top_pct, top_vol, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lines = ["# 日终统计\n\n"]
    lines.append("## 所有标的汇总\n")
    lines.append("symbol | open | close | pct% | maxVol | sumAmt | high | low\n")
    lines.append("---|---:|---:|---:|---:|---:|---:|---:\n")
    for sym, o0, cL, pct, vmax, asum, hmax, lmin in report:
        lines.append(f"{sym} | {o0:.2f} | {cL:.2f} | {pct:.2f} | {vmax} | {asum:.0f} | {hmax:.2f} | {lmin:.2f}\n")
    lines.append("\n## 涨跌幅排行榜（Top 10）\n")
    lines.append("symbol | pct%\n")
    lines.append("---|---:\n")
    for sym, o0, cL, pct, vmax, asum, hmax, lmin in top_pct[:10]:
        lines.append(f"{sym} | {pct:.2f}\n")
    lines.append("\n## 成交量排行榜（Top 10）\n")
    lines.append("symbol | volume\n")
    lines.append("---|---:\n")
    for sym, o0, cL, pct, vmax, asum, hmax, lmin in top_vol[:10]:
        lines.append(f"{sym} | {vmax}\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"已写入日终统计: {out_path}")


def main():
    args = parse_args()
    if args.source == "sqlite":
        rows = read_minutes_sqlite(args.db, args.date)
    else:
        rows = read_minutes_csv(args.csv)
    if not rows:
        print("无分钟数据，请检查来源或先运行采集")
        return
    hourly = compute_hourly_summary(rows)
    write_hourly_csv(hourly, args.out_hourly)
    report, top_pct, top_vol = compute_daily_report(rows)
    write_daily_md(report, top_pct, top_vol, args.out_daily)


if __name__ == "__main__":
    main()
