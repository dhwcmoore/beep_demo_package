# BEEP Trust Chain: From Rupture Evidence to Sealed Artefact

## Executive Summary

The BEEP (Beep Before Bang) system provides a formally disciplined assessment of structural risk in distributed systems. This document outlines the complete trust chain from raw evidence to immutable audit artefacts.

## Trust Chain Overview

```
Raw Evidence → Semantic Processing → Risk Assessment → Integrity Sealing → Verification
```

## 1. Raw Evidence Layer

**Inputs:**
- **Rupture Data**: Time-series market data (OHLCV) from `scenA_base_ohlcv.csv`
- **Configuration**: Stress test parameters from `stress_demo.toml`
- **Metadata**: Scenario phases and parameters from `scenA_base_meta.json`

**Processing:**
- Rust rupture engine detects anomalous behavior patterns
- OCaml structural classifier analyzes topology invariants
- Evidence is timestamped and phase-classified

## 2. Semantic Processing Layer

**Rupture Semantics:**
- Events filtered by phase thresholds (phase2_start = 70)
- Scoring: `score = min(peak_multiplier × max_peak_rho + count_multiplier × filtered_count, max_score)`
- Classification: Primary Rupture, Escalation, etc.
- **Contract**: `rupture_contract.v` (Rocq formalization)

**Structural Semantics:**
- Betti numbers computed from topology invariants
- Judgement: ConnectivityPartition, CycleLoss, or NoBreak
- **Contract**: `structural_judgement_contract.v` (Rocq formalization)

**Guardrails:**
- Escalation-classified ruptures cannot yield LOW risk
- SJ_ConnectivityPartition with rupture must be CRITICAL
- SJ_CycleLoss with rupture must be HIGH/CRITICAL

## 3. Risk Assessment Layer

**Fusion Logic:**
- `risk_score = rupture_weight × rupture_score + invariant_weight × invariant_score`
- Risk levels: LOW (<2.0), MEDIUM (2.0-4.0), HIGH (4.0-7.0), CRITICAL (≥7.0)
- **Contract**: `risk_escalation_contract.v` (Rocq formalization)

**Provenance:**
- Exact rupture features exposed (event counts, peak rho, thresholds)
- Structural classifier inputs logged verbatim
- Semantic versions tracked (v1)

## 4. Integrity Sealing Layer

**Canonicalization:**
- JSON payload normalized with sorted keys and compact separators
- Deterministic SHA-256 hashing (`json_c14n_v1`)

**Sealing:**
- Payload wrapped in envelope with metadata
- Integrity block includes canonical hash and seal information
- Timestamped and versioned

**Verification:**
- Independent verification against stored hash
- Seal status reported in HTML artefacts

## 5. Verification Layer

**Artefact Integrity:**
- SHA-256 verification of payload against sealed hash
- Tamper detection: any modification breaks verification
- Immutable identity for audit trails

**Report Transparency:**
- Integrity status displayed ("valid" or "invalid")
- Full payload hash exposed for independent verification
- Semantic contracts and guardrails documented

## Trust Properties

✅ **Semantic Discipline**: All judgements anchored in Rocq contracts  
✅ **Provenance Tracking**: Exact inputs and features exposed  
✅ **Guardrail Enforcement**: Runtime checks prevent invalid escalations  
✅ **Integrity Assurance**: SHA-256 sealing with tamper detection  
✅ **Audit Transparency**: Immutable artefacts with verification status  

## File Artefacts

- `beep_output.json`: Raw assessment payload
- `beep_output_sealed.json`: Integrity-sealed artefact
- `beep_report.html`: Human-readable report with integrity status
- `rocq/*.v`: Formal semantic contracts
- `veribound_core/`: Integrity implementation

## Verification Commands

```bash
# Verify seal integrity
python3 verify_beep_seal.py

# Test tamper resistance
python3 tamper_test.py

# Full pipeline
./run_demo.sh
```

The BEEP system transforms interpretive risk assessment into a formally disciplined, integrity-assured audit instrument.