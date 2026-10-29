#!/bin/sh
# Rebuild runs/data/ (the layout the analysis scripts read) from what is in git:
# raw run outputs from runs/raw/, plus the labels, annotator outputs and Laya datasets
# already tracked under runs/data/ as .jsonl.gz. Existing files are kept.
# usage: sh runs/unpack_data.sh   (from the repo root)
set -e
cd "$(dirname "$0")"
mkdir -p data
cp -Rn raw/. data/ 2>/dev/null || true
rm -f data/README.md
find data -name '*.jsonl.gz' | while read -r f; do
  [ -e "${f%.gz}" ] || gzip -dk "$f"
done
echo "runs/data ready"
