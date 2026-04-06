#!/usr/bin/env bash
# bridge/run_regression.sh
#
# Full regression suite for the BEEP → LoopAudit bridge.
#
# Steps:
#   1. Run the Python bridge regression (unit tests + scenario classification)
#   2. If OCaml is available, build and run the OCaml regression suite
#   3. Optionally run the OCaml audit runner on each fixture and check exit codes
#
# Usage:
#   bash bridge/run_regression.sh
#   bash bridge/run_regression.sh --skip-ocaml

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$REPO_ROOT/bridge/fixtures"
OUTPUT="$REPO_ROOT/output"
SCENA_PAYLOAD="$OUTPUT/beep_loopaudit_payload.json"

SKIP_OCAML=0
for arg in "$@"; do
  [[ "$arg" == "--skip-ocaml" ]] && SKIP_OCAML=1
done

echo "========================================================"
echo " BEEP → LoopAudit bridge regression"
echo " repo root: $REPO_ROOT"
echo "========================================================"

# ── Step 0: make sure the scenA payload exists ─────────────────────────────
if [[ ! -f "$SCENA_PAYLOAD" ]]; then
  echo ""
  echo "▶ scenA payload not found — generating..."
  python3 "$REPO_ROOT/bridge/export_loopaudit_payload.py" \
    --input  "$REPO_ROOT/beep_output.json" \
    --output "$SCENA_PAYLOAD"
fi

# ── Step 1: Python regression suite ────────────────────────────────────────
echo ""
echo "▶ Python regression suite"
echo "──────────────────────────────────────────────────────"
python3 "$REPO_ROOT/bridge/test_bridge_scenarios.py"
PYTHON_EXIT=$?

# ── Step 2: OCaml build + regression ───────────────────────────────────────
OCAML_EXIT=0

if [[ "$SKIP_OCAML" -eq 0 ]]; then
  if command -v dune &>/dev/null; then
    echo ""
    echo "▶ OCaml build"
    echo "──────────────────────────────────────────────────────"
    (cd "$REPO_ROOT/ocaml" && dune build ./beep_bridge_test.exe ./run_beep_bridge_audit.exe)

    echo ""
    echo "▶ OCaml regression suite"
    echo "──────────────────────────────────────────────────────"
    "$REPO_ROOT/ocaml/_build/default/beep_bridge_test.exe" \
      "$FIXTURES" \
      "$SCENA_PAYLOAD"
    OCAML_REG_EXIT=$?

    # ── Step 3: audit runner exit-code checks ─────────────────────────────
    echo ""
    echo "▶ Audit runner exit-code checks"
    echo "──────────────────────────────────────────────────────"
    AUDIT="$REPO_ROOT/ocaml/_build/default/run_beep_bridge_audit.exe"

    check_exit() {
      local label="$1"
      local payload="$2"
      local expected_exit="$3"
      local report="$OUTPUT/obstruction_report_${label}.json"

      "$AUDIT" "$payload" "$report" >/dev/null 2>&1
      local actual=$?
      if [[ "$actual" -eq "$expected_exit" ]]; then
        echo "  PASS  $label: exit $actual (expected $expected_exit)"
      else
        echo "  FAIL  $label: exit $actual (expected $expected_exit)"
        OCAML_EXIT=1
      fi
    }

    check_exit "scenA" "$SCENA_PAYLOAD"                                     2
    check_exit "scenB" "$FIXTURES/scenB_coherent_payload.json"              0
    check_exit "scenC" "$FIXTURES/scenC_ring_loss_only_payload.json"        2
    check_exit "scenD" "$FIXTURES/scenD_partition_no_rupture_payload.json"  2

    [[ "$OCAML_REG_EXIT" -ne 0 ]] && OCAML_EXIT=1

  else
    echo ""
    echo "  SKIP  dune not found — skipping OCaml tests"
    echo "        install: opam install dune yojson"
  fi
else
  echo ""
  echo "  SKIP  OCaml tests disabled via --skip-ocaml"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo " Summary"
echo "  Python suite : $([ $PYTHON_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "  OCaml suite  : $([ $OCAML_EXIT  -eq 0 ] && echo 'PASS' || echo 'FAIL (or skipped)')"
echo "========================================================"

if [[ "$PYTHON_EXIT" -ne 0 || "$OCAML_EXIT" -ne 0 ]]; then
  exit 1
fi
