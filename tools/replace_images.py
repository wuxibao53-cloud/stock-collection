#!/usr/bin/env python3
"""
Usage:
  python tools/replace_images.py /path/to/screenshot1.png /path/to/screenshot2.png [...]

This script copies provided image files into ./assets/ with pre-defined target names:
  assets/wechat_cover.png
  assets/wechat_fig_report.png
  assets/wechat_fig_log.png

It will back up existing placeholders (svg) by renaming them with .bak suffix.
"""
import sys
import os
import shutil

TARGETS = [
    ("wechat_cover.png", "assets/wechat_cover.svg"),
    ("wechat_fig_report.png", "assets/wechat_fig_report.svg"),
    ("wechat_fig_log.png", "assets/wechat_fig_log.svg"),
]


def main(paths):
    os.makedirs('assets', exist_ok=True)
    for i, p in enumerate(paths[:3]):
        target_name, placeholder = TARGETS[i]
        dest = os.path.join('assets', target_name)
        # backup existing placeholder
        if os.path.exists(placeholder):
            bak = placeholder + '.bak'
            if not os.path.exists(bak):
                os.rename(placeholder, bak)
        shutil.copy2(p, dest)
        print(f'Copied {p} -> {dest}')
    print('Done. Please update SOCIAL_WECHAT_HTML.html/SOCIAL_WECHAT_READY.md to use .png names if needed.')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python tools/replace_images.py /path/to/cover.png /path/to/report.png /path/to/log.png')
        sys.exit(1)
    main(sys.argv[1:])
