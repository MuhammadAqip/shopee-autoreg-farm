#!/usr/bin/env bash
# sap_reverse.sh — one-shot: analisa bundle Shopee (Sense + SAP) dgn REA + tools lokal.
# Usage: sap_reverse.sh <bundle.js|dir> [outdir]
set -euo pipefail
TARGET="${1:-/tmp/sap_analysis}"
OUT="${2:-/root/shopee-farm/sdk}"
mkdir -p "$OUT"

echo "=== 1. REA static JS analysis (source graph) ==="
export GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-/opt/ghidra_dl/ghidra_11.4.2_PUBLIC}"
cd /tmp/rea
node scripts/rea.mjs analyze-javascript-application "$TARGET" --format json 2>/dev/null \
  | grep -v rea_progress > "$OUT/rea_analysis.json" || true
echo "  → $OUT/rea_analysis.json ($(wc -c < "$OUT/rea_analysis.json" 2>/dev/null || echo 0) bytes)"

echo "=== 2. Decode string table (ak) ==="
cd /root/shopee-farm
if [ -f "$TARGET/../bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js" ]; then
  python3 ak_decode.py "$TARGET/../bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js" \
    | tail -n +4 > "$OUT/strings_sfu.txt" 2>/dev/null || true
fi
echo "  → $OUT/strings_sfu.txt"

echo "=== 3. Sense payload decrypt/forge self-test ==="
python3 sense_decrypt.py 2>&1 | tail -2
python3 pure_aes.py

echo "=== 4. Sniff semua capture untuk body Sense ==="
for j in capture/run_*.jsonl; do
  [ -f "$j" ] && python3 sense_cli.py sniff "$j" 2>/dev/null | grep -E "crc_ok|total" | head -2
done | head -10

echo "=== DONE ==="
