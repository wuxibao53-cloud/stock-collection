import os
import argparse
import shutil
from datetime import datetime, timedelta


def parse_args():
    p = argparse.ArgumentParser(description="归档/清理日志文件")
    p.add_argument("--logs", type=str, default=os.path.join(os.path.dirname(__file__), "logs"))
    p.add_argument("--days", type=int, default=7, help="归档阈值天数，早于此的文件将归档")
    p.add_argument("--compress", action="store_true", help="归档后压缩为zip")
    return p.parse_args()


def is_target_file(name: str):
    return (
        name.startswith("realtime_quotes_") and (name.endswith(".csv") or name.endswith(".jsonl"))
    ) or name.startswith("minute_bars_") and name.endswith(".csv")


def main():
    args = parse_args()
    root = args.logs
    archive_dir = os.path.join(root, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    cutoff = datetime.now() - timedelta(days=args.days)
    moved = []

    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        if not is_target_file(name):
            continue
        # 提取日期部分
        date_part = None
        try:
            if name.startswith("realtime_quotes_"):
                date_part = name.split("_")[-1].split(".")[0]
            elif name.startswith("minute_bars_"):
                date_part = name.replace("minute_bars_", "").split(".")[0]
            if date_part and len(date_part) == 8:
                file_date = datetime.strptime(date_part, "%Y%m%d")
                if file_date < cutoff:
                    dest_dir = os.path.join(archive_dir, date_part)
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, name)
                    shutil.move(path, dest_path)
                    moved.append(dest_path)
        except Exception:
            pass

    if args.compress and moved:
        zip_path = os.path.join(archive_dir, f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        shutil.make_archive(zip_path.replace('.zip',''), 'zip', archive_dir)
        print(f"已压缩归档为: {zip_path}")
    else:
        print(f"已归档文件数: {len(moved)}")


if __name__ == "__main__":
    main()
