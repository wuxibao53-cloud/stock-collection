import os
import csv
import time
import json
import argparse
import requests
from datetime import datetime
import sqlite3
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except Exception:
    PARQUET_AVAILABLE = False

# 多标的：上证指数、深成指、茅台、宁德时代，可自行增删
DEFAULT_SYMBOLS = ["sh000001", "sz399001", "sh600519", "sz300750"]

URL_TMPL = "{scheme}://{domain}/list={symbols}"  # 支持 http/https 与域名切换
HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
]
REFERERS = [
    "https://finance.sina.com.cn",
    "https://money.finance.sina.com.cn",
    "https://quotes.sina.cn",
]

def rotate_headers(idx: int):
    ua = UAS[idx % len(UAS)]
    ref = REFERERS[idx % len(REFERERS)]
    SESSION.headers.update({"User-Agent": ua, "Referer": ref})


def is_trading_time(now: datetime) -> bool:
    # A股交易时段：09:30-11:30, 13:00-15:00（工作日）
    if now.weekday() >= 5:  # 5=周六, 6=周日
        return False
    hm = now.strftime("%H:%M")
    return ("09:30" <= hm <= "11:30") or ("13:00" <= hm <= "15:00")


def _float(x):
    try:
        return float(x)
    except Exception:
        return None


def _int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def parse_line(line: str):
    # 格式示例：var hq_str_sh600519="贵州茅台,今开,昨收,现价,...";
    try:
        prefix_split = line.split("var hq_str_")
        if len(prefix_split) < 2:
            raise ValueError("前缀解析失败")
        rest = prefix_split[1]
        symbol = rest.split("=")[0].strip()
        parts = line.split('"')
        if len(parts) < 2:
            raise ValueError("数据解析失败")
        fields = parts[1].split(",")
        data = {
            "name": fields[0] if len(fields) > 0 else symbol,
            "open": _float(fields[1]) if len(fields) > 1 else None,
            "yclose": _float(fields[2]) if len(fields) > 2 else None,
            "price": _float(fields[3]) if len(fields) > 3 else None,
            "high": _float(fields[4]) if len(fields) > 4 else None,
            "low": _float(fields[5]) if len(fields) > 5 else None,
            "bid": _float(fields[6]) if len(fields) > 6 else None,
            "ask": _float(fields[7]) if len(fields) > 7 else None,
            "volume": _int(fields[8]) if len(fields) > 8 else None,
            "amount": _float(fields[9]) if len(fields) > 9 else None,
            # 日期与时间在30、31下标位置（股票），指数可能不同，做兼容
            "date": fields[30] if len(fields) > 30 else None,
            "time": fields[31] if len(fields) > 31 else None,
        }
        note = ""
        # 盘前价为0时回退昨收
        if (data["price"] is None or data["price"] == 0.0) and data["yclose"]:
            data["price"] = data["yclose"]
            note = "昨收"
        # 涨跌幅
        if data["price"] and data["yclose"] and data["yclose"] != 0:
            try:
                data["pct"] = (data["price"] - data["yclose"]) / data["yclose"] * 100.0
            except Exception:
                data["pct"] = None
        else:
            data["pct"] = None
        return symbol, data, note
    except Exception as e:
        raise e


def fetch_all(symbols, scheme: str, proxy: str | None, domain: str, max_retries: int = 3, record_latency: bool = False):
    last_err = None
    url = URL_TMPL.format(scheme=scheme, domain=domain, symbols=",".join(symbols))
    delays = [0.5, 1.0, 2.0][:max_retries]
    for i, delay in enumerate(delays):
        try:
            rotate_headers(i)
            proxies = {"http": proxy, "https": proxy} if proxy else None
            start = time.time() if record_latency else None
            r = SESSION.get(url, timeout=8, proxies=proxies)
            r.raise_for_status()
            lines = [ln for ln in r.text.splitlines() if ln.strip()]
            results = {}
            latency_ms = None
            if record_latency:
                latency_ms = int((time.time() - start) * 1000)
            for line in lines:
                sym, data, note = parse_line(line)
                if record_latency:
                    data["latency_ms"] = latency_ms
                results[sym] = (data, note)
            return results
        except Exception as e:
            last_err = e
            time.sleep(delay)
    raise last_err


def fetch_one(symbol: str, scheme: str, proxy: str | None, domain: str, attempt_idx: int = 0, record_latency: bool = False):
    url = URL_TMPL.format(scheme=scheme, domain=domain, symbols=symbol)
    rotate_headers(attempt_idx)
    proxies = {"http": proxy, "https": proxy} if proxy else None
    start = time.time() if record_latency else None
    r = SESSION.get(url, timeout=8, proxies=proxies)
    r.raise_for_status()
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("单标的返回为空")
    sym, data, note = parse_line(lines[0])
    if record_latency:
        data["latency_ms"] = int((time.time() - start) * 1000)
    return data, note


def get_log_path():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    fname = f"realtime_quotes_{datetime.now().strftime('%Y%m%d')}.csv"
    return os.path.join(log_dir, fname)


def write_log_row(path: str, row: list):
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["time", "symbol", "name", "price", "label", "note"])
        w.writerow(row)


def parse_args():
    parser = argparse.ArgumentParser(description="A股实时行情监听（新浪API）")
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="逗号分隔的标的列表，如 sh000001,sz399001,sh600519,sz300750",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="轮询间隔秒，默认2秒",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="只抓取一次并退出，便于截图",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="使用HTTPS请求（默认HTTP）",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="不写CSV日志，仅终端输出",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP(S)代理地址，如 http://127.0.0.1:7890",
    )
    parser.add_argument(
        "--json-log",
        action="store_true",
        help="同时写入JSON Lines日志",
    )
    parser.add_argument(
        "--show-pct",
        action="store_true",
        help="终端显示涨跌幅百分比",
    )
    parser.add_argument(
        "--only-trading",
        action="store_true",
        help="仅在交易时段输出，非交易时段跳过",
    )
    parser.add_argument(
        "--dedup",
        action="store_true",
        help="去重：价格未变化则不输出/不写日志",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="hq.sinajs.cn",
        help="可指定域名，如 hq.sinajs.cn",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="最大重试次数（默认3）",
    )
    parser.add_argument(
        "--latency",
        action="store_true",
        help="记录请求延迟（毫秒）到JSON日志",
    )
    parser.add_argument(
        "--agg",
        action="store_true",
        help="启用分钟级聚合，并写入SQLite",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "logs", "quotes.db"),
        help="SQLite数据库路径，默认 logs/quotes.db",
    )
    parser.add_argument(
        "--parquet",
        action="store_true",
        help="启用分钟聚合的Parquet导出（按日期分区）",
    )
    parser.add_argument(
        "--parquet-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "logs", "minute_bars_parquet"),
        help="Parquet根目录，默认 logs/minute_bars_parquet",
    )
    parser.add_argument(
        "--alert-pct",
        type=float,
        default=None,
        help="涨跌幅告警阈值（百分比，如 2.0）",
    )
    parser.add_argument(
        "--alert-volume",
        type=int,
        default=None,
        help="当前分钟成交量增量告警阈值（手/股，取决于返回）",
    )
    parser.add_argument(
        "--minute-summary",
        action="store_true",
        help="打印每分钟摘要（OHLC、分钟增量成交量/成交额、样本数）",
    )
    parser.add_argument(
        "--minute-csv",
        action="store_true",
        help="写入分钟CSV日志 logs/minute_bars_YYYYMMDD.csv",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    interval = max(0.5, float(args.interval))
    log_path = None if args.no_log else get_log_path()
    json_log_path = None
    if not args.no_log and args.json_log:
        base_dir = os.path.dirname(__file__)
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        json_log_path = os.path.join(log_dir, f"realtime_quotes_{datetime.now().strftime('%Y%m%d')}.jsonl")
    scheme = "https" if args.https else "http"
    proxy = args.proxy
    domain = args.domain
    max_retries = max(1, int(args.max_retries))
    record_latency = bool(args.latency)
    show_pct = bool(args.show_pct)
    only_trading = bool(args.only_trading)
    dedup = bool(args.dedup)
    last_prices = {}

    # 聚合与持久化
    agg_enabled = bool(args.agg)
    db_path = args.db_path
    parquet_enabled = bool(args.parquet)
    parquet_root = args.parquet_path
    minute_summary = bool(args.minute_summary)
    minute_csv_enabled = bool(args.minute_csv)
    db_state = {"conn": None, "cur": None}
    minute_buckets = {}  # key: (symbol, minute_str) -> dict

    def get_minute_key(now_dt: datetime):
        return now_dt.strftime("%Y-%m-%d %H:%M")

    def ensure_db():
        if db_state["conn"] is not None:
            return
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_state["conn"] = sqlite3.connect(db_path)
        db_state["cur"] = db_state["conn"].cursor()
        db_state["cur"].execute(
            """
            CREATE TABLE IF NOT EXISTS minute_bars (
                minute TEXT NOT NULL,
                symbol TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                amount REAL,
                samples INTEGER,
                start_ts TEXT,
                end_ts TEXT,
                PRIMARY KEY (symbol, minute)
            )
            """
        )
        db_state["conn"].commit()

    def update_bucket(sym: str, now_dt: datetime, data: dict):
        minute_key = get_minute_key(now_dt)
        key = (sym, minute_key)
        price = data.get("price") or 0.0
        vol = data.get("volume")
        amt = data.get("amount")
        # 如果该symbol换分钟了，先flush旧分钟
        # 查找该symbol所有旧key并过滤当前分钟
        to_flush = [k for k in minute_buckets.keys() if k[0] == sym and k[1] != minute_key]
        for old_key in to_flush:
            flush_bucket(old_key)
        # 更新当前分钟bucket
        b = minute_buckets.get(key)
        ts = now_dt.strftime("%H:%M:%S")
        if b is None:
            b = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "samples": 1,
                "start_ts": ts,
                "end_ts": ts,
                "start_cum_vol": vol,
                "end_cum_vol": vol,
                "start_cum_amt": amt,
                "end_cum_amt": amt,
            }
            minute_buckets[key] = b
        else:
            b["high"] = max(b["high"], price)
            b["low"] = min(b["low"], price)
            b["close"] = price
            b["samples"] += 1
            b["end_ts"] = ts
            if vol is not None:
                b["end_cum_vol"] = vol
            if amt is not None:
                b["end_cum_amt"] = amt

    def flush_bucket(key):
        if not agg_enabled:
            return
        ensure_db()
        sym, minute_key = key
        b = minute_buckets.get(key)
        if not b:
            return
        vol_delta = None
        amt_delta = None
        if b.get("start_cum_vol") is not None and b.get("end_cum_vol") is not None:
            try:
                vol_delta = int(max(0, b["end_cum_vol"] - b["start_cum_vol"]))
            except Exception:
                vol_delta = None
        if b.get("start_cum_amt") is not None and b.get("end_cum_amt") is not None:
            try:
                amt_delta = float(max(0.0, b["end_cum_amt"] - b["start_cum_amt"]))
            except Exception:
                amt_delta = None
        db_state["cur"].execute(
            """
            INSERT INTO minute_bars (minute, symbol, open, high, low, close, volume, amount, samples, start_ts, end_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, minute) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                amount=excluded.amount,
                samples=excluded.samples,
                start_ts=excluded.start_ts,
                end_ts=excluded.end_ts
            """,
            (
                minute_key,
                sym,
                b["open"],
                b["high"],
                b["low"],
                b["close"],
                vol_delta,
                amt_delta,
                b["samples"],
                b["start_ts"],
                b["end_ts"],
            ),
        )
        db_state["conn"].commit()

        # 终端分钟摘要
        if minute_summary:
            print(f"[MIN] {minute_key} {sym} O:{b['open']:.2f} H:{b['high']:.2f} L:{b['low']:.2f} C:{b['close']:.2f} V:{vol_delta if vol_delta is not None else '-'} A:{amt_delta if amt_delta is not None else '-'} S:{b['samples']}")

        # 写分钟CSV
        if minute_csv_enabled:
            base_dir = os.path.dirname(__file__)
            log_dir = os.path.join(base_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            csv_path = os.path.join(log_dir, f"minute_bars_{minute_key.split(' ')[0].replace('-', '')}.csv")
            write_header = not os.path.exists(csv_path)
            try:
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if write_header:
                        w.writerow(["minute", "symbol", "open", "high", "low", "close", "volume", "amount", "samples", "start_ts", "end_ts"])
                    w.writerow([minute_key, sym, b["open"], b["high"], b["low"], b["close"], vol_delta, amt_delta, b["samples"], b["start_ts"], b["end_ts"]])
            except Exception:
                pass

        # 可选：写入Parquet（按日期分区）
        if parquet_enabled and PARQUET_AVAILABLE:
            try:
                os.makedirs(parquet_root, exist_ok=True)
                # 从minute_key提取日期
                date_part = minute_key.split(" ")[0]
                row = {
                    "minute": [minute_key],
                    "symbol": [sym],
                    "open": [b["open"]],
                    "high": [b["high"]],
                    "low": [b["low"]],
                    "close": [b["close"]],
                    "volume": [vol_delta],
                    "amount": [amt_delta],
                    "samples": [b["samples"]],
                    "start_ts": [b["start_ts"]],
                    "end_ts": [b["end_ts"]],
                    "date": [date_part],
                }
                table = pa.table(row)
                pq.write_to_dataset(table, root_path=parquet_root, partition_cols=["date"])
            except Exception:
                pass
        # 刷新后删除该bucket
        del minute_buckets[key]

    print(f"开始监听：{', '.join(symbols)}（Ctrl+C 退出）")

    def one_round():
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")
        trading = is_trading_time(now)
        label = "" if trading else "(盘前)"
        if only_trading and not trading:
            return
        try:
            results = fetch_all(symbols, scheme, proxy, domain, max_retries, record_latency)
        except Exception:
            # 降级为逐标的请求
            results = {}
            for idx, sym in enumerate(symbols):
                try:
                    data, note = fetch_one(sym, scheme, proxy, domain, idx, record_latency)
                    results[sym] = (data, note)
                except Exception as e:
                    results[sym] = ({"name": sym, "price": 0.0, "yclose": None}, f"错误:{e}")
        for sym in symbols:
            data, note = results[sym]
            name = data.get("name", sym)
            price = data.get("price", 0.0) or 0.0
            yclose = data.get("yclose")
            pct = data.get("pct")
            # 先更新聚合（以便计算当前分钟增量）
            if agg_enabled:
                update_bucket(sym, now, data)
            # 去重
            if dedup:
                last = last_prices.get(sym)
                if last is not None and abs(last - price) < 1e-6:
                    continue
                last_prices[sym] = price
            pct_str = f" {pct:.2f}%" if (show_pct and isinstance(pct, (int, float)) and pct is not None) else ""
            extra = f" {note}" if note else ""
            print(f"[{ts}] {name}({sym}): {price:.2f}{pct_str} {label}{extra}")
            if log_path:
                write_log_row(log_path, [ts, sym, name, f"{price:.2f}", label, note])
            if json_log_path:
                payload = {
                    "time": ts,
                    "symbol": sym,
                    "name": name,
                    "price": price,
                    "yclose": yclose,
                    "pct": pct,
                    "label": label,
                    "note": note,
                    "open": data.get("open"),
                    "high": data.get("high"),
                    "low": data.get("low"),
                    "bid": data.get("bid"),
                    "ask": data.get("ask"),
                    "volume": data.get("volume"),
                    "amount": data.get("amount"),
                    "date": data.get("date"),
                    "time_field": data.get("time"),
                }
                if record_latency:
                    payload["latency_ms"] = data.get("latency_ms")
                with open(json_log_path, "a", encoding="utf-8") as jf:
                    jf.write(json.dumps(payload, ensure_ascii=False) + "\n")
            # 简易告警（基于当前分钟增量与涨跌幅）
            if agg_enabled:
                minute_key = get_minute_key(now)
                b = minute_buckets.get((sym, minute_key))
                vol_delta = None
                if b and b.get("start_cum_vol") is not None and b.get("end_cum_vol") is not None:
                    try:
                        vol_delta = int(max(0, b["end_cum_vol"] - b["start_cum_vol"]))
                    except Exception:
                        vol_delta = None
                if args.alert_volume is not None and vol_delta is not None and vol_delta >= int(args.alert_volume):
                    print(f"[ALERT] {sym} 当前分钟成交量增量达 {vol_delta}")
            if args.alert_pct is not None and isinstance(pct, (int, float)) and pct is not None and abs(pct) >= float(args.alert_pct):
                print(f"[ALERT] {sym} 涨跌幅达到 {pct:.2f}%")

    def flush_all_buckets():
        if not agg_enabled:
            return
        # 刷新所有仍在内存中的bucket
        for key in list(minute_buckets.keys()):
            flush_bucket(key)
        if db_state["conn"] is not None:
            db_state["conn"].close()

    try:
        if args.snapshot:
            one_round()
        else:
            while True:
                one_round()
                time.sleep(interval)
    except KeyboardInterrupt:
        print("已退出")
    except Exception as e:
        print("错误：", e)
    finally:
        # 快照或退出时强制刷新聚合数据
        flush_all_buckets()