#!/usr/bin/env bash
# Frozen demo mode — runs from packaged outputs in demo_v2_frozen/.
# No external engine dependencies. Runs identically every time.
# For live mode (requires rupture-engine + boundary-invariants), use run_beep.sh.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Beep Before Bang — Frozen Demo"
echo "==> Using packaged outputs from demo_v2_frozen/"

mkdir -p output
install -m 644 demo_v2_frozen/beep_output.json output/beep_output.json

echo "==> Generating text report..."
python3 report.py

echo "==> Generating HTML report..."
python3 report_html.py

echo
echo "Output files:"
echo "  $ROOT/output/beep_output.json"
echo "  $ROOT/output/beep_report.html"
