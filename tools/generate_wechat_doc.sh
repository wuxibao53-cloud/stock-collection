#!/usr/bin/env bash
# 说明: 使用 pandoc 将 Markdown 转为 DOCX / HTML
# 需求: 安装 pandoc
# macOS: brew install pandoc

set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

MD="SOCIAL_WECHAT_DOC.md"
OUT_DOCX="SOCIAL_WECHAT_DOC.docx"
OUT_HTML="SOCIAL_WECHAT_DOC.html"

if ! command -v pandoc >/dev/null 2>&1; then
  echo "pandoc 未安装，请先安装: brew install pandoc"
  exit 1
fi

pandoc "$MD" -o "$OUT_DOCX" --resource-path=assets
pandoc "$MD" -o "$OUT_HTML" --resource-path=assets

echo "生成完成: $OUT_DOCX, $OUT_HTML"
