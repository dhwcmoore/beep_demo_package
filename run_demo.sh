#!/bin/bash
set -e

echo "Running rupture engine..."
cd rupture_engine
cargo run --release -- --input ../docs/archive/demo_v2_frozen/scenA_base_ohlcv.csv --config ../docs/archive/demo_v2_frozen/stress_demo.toml --output-dir ../output
cd ..

echo "Running fusion pipeline..."
python3 beep_pipeline.py

echo "Sealing audit artefact..."
python3 seal_beep_output.py

echo "Verifying seal..."
python3 verify_beep_seal.py

echo "Running tamper test..."
python3 tamper_test.py

echo "Generating report..."
python3 report_html.py

echo "Done. Output in ./output/"
