# BEEP Trust Summary

## Evidence Inputs

- **Rupture evidence**: detected anomaly events from the rupture engine using OHLCV data and stress config.
- **Structural inputs**: topology invariants (Betti numbers) from the invariants engine.
- **Scenario metadata**: phase thresholds and run parameters from the scenario metadata file.

## Layered Processing

1. **Rupture layer**
   - Filters events by phase thresholds.
   - Computes rupture features: event count, filtered count, max peak rho, phase threshold.
   - Produces the rupture score and classified rupture events.

2. **Structural layer**
   - Uses OCaml to compute structural judgement from nominal and fault Betti values.
   - Outputs a formal judgement (`SJ_NoBreak`, `SJ_CycleLoss`, or `SJ_ConnectivityPartition`).

3. **Fusion + guardrails layer**
   - Combines rupture score and structural score into a composite risk score.
   - Applies explicit runtime guardrails:
     - escalation-classified rupture cannot yield LOW risk
     - `SJ_ConnectivityPartition` with rupture must be CRITICAL
     - `SJ_CycleLoss` with rupture must be HIGH or CRITICAL

## Formal Constraints

- **Rocq contracts** anchor the semantic meaning of the structural and rupture decisions.
- **Structural contract**: `structural_judgement_contract.v`
- **Rupture contract**: `rupture_contract.v`
- **Risk escalation contract**: `risk_escalation_contract.v`
- These contracts make the bridge from code to formal semantics explicit.

## Sealing and Integrity

- The final JSON payload is canonicalised deterministically.
- A SHA-256 hash is computed over the canonical JSON payload.
- The payload is wrapped in a sealed envelope: `output/beep_output_sealed.json`.
- The envelope contains:
  - schema version
  - creation timestamp
  - payload
  - integrity metadata
  - verification summary

## Tamper Detection Proof

- A separate tamper test modifies the sealed payload and recomputes the hash.
- The seal verification fails when the payload is altered.
- This proves the integrity layer is not ornamental: it is cryptographically tamper-evident.

## Conclusion

This system is best described as a boundary-disciplined early-warning and audit instrument with:
- explicit semantic contracts for rupture and structural judgement,
- runtime guardrails enforcing escalation semantics,
- and tamper-evident sealing of the final audit artefact.
