#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "==> Running Beep Before Bang pipeline..."
python3 beep_pipeline.py

echo "==> Generating text report..."
python3 report.py

echo "==> Generating HTML report..."
python3 report_html.py

echo ""
echo "Output files:"
echo "  output/beep_output.json"
echo "  output/beep_report.html"
