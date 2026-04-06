# Audit Coverage Traceability

This document records the remaining audit contract clauses, where they are implemented in OCaml, how they are currently tested, and what still needs to be proved or validated.

## 1. Formal contract clauses

The Rocq-facing contract is defined in `rocq/audit_coverage_contract.v`.
It consists of the following clauses:

1. `acc_all_regions_checked`
   - formal clause: every reachable region from the baseline is inspected by the audit.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `compute_mismatches`.
   - status: partially tested by scenario fixtures; coverage tests still needed.

2. `acc_all_edges_checked`
   - formal clause: every adjacent pair is checked for transport compatibility.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `expected_transport` and predecessor selection in `compute_mismatches`.
   - status: assumed by code inspection; explicit edge-coverage tests are desirable.

3. `acc_ring_loss_detection_complete`
   - formal clause: any `ring_loss_at P r` must be reported by the audit.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `check_ring_loss`.
   - test evidence: `ocaml/beep_bridge_test.ml` scenarios `scenA_base` and `scenC_ring_loss_only`.
   - status: tested for canonical scenarios.

4. `acc_partition_detection_complete`
   - formal clause: any `partition_at P r` must be reported by the audit.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `check_partition`.
   - test evidence: `ocaml/beep_bridge_test.ml` scenarios `scenA_base` and `scenD_partition_no_rup`.
   - status: tested for canonical scenarios.

5. `acc_reported_ring_loss_implies_actual`
   - formal clause: when the audit reports ring loss, the payload must satisfy `ring_loss_at`.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `check_ring_loss`.
   - status: implicit in the current implementation; should be made explicit in contract documentation.

6. `acc_reported_partition_implies_actual`
   - formal clause: when the audit reports partition, the payload must satisfy `partition_at`.
   - implementation: `ocaml/beep_bridge_mapping.ml` via `check_partition`.
   - status: implicit in the current implementation; should be made explicit in contract documentation.

7. `acc_semantic_coverage`
   - formal clause: if no global coherent history exists, the audit must report ring loss or partition.
   - implementation: this is the remaining assumed boundary.
   - status: currently assumed as `audit_coverage`; needs explicit validation.

## 2. Contract-to-implementation mapping table

| Contract clause | OCaml file | Function(s) | Test / evidence | Status |
|---|---|---|---|---|
| all reachable regions are checked | `ocaml/beep_bridge_mapping.ml` | `compute_mismatches` | scenario fixtures / code inspection | partially tested |
| all edges are checked | `ocaml/beep_bridge_mapping.ml` | `compute_mismatches`, `expected_transport` | code inspection | needs explicit coverage tests |
| ring loss detection complete | `ocaml/beep_bridge_mapping.ml` | `check_ring_loss` | `ocaml/beep_bridge_test.ml` scenA, scenC | tested |
| partition detection complete | `ocaml/beep_bridge_mapping.ml` | `check_partition` | `ocaml/beep_bridge_test.ml` scenA, scenD | tested |
| reported ring loss implies actual ring loss | `ocaml/beep_bridge_mapping.ml` | `check_ring_loss` | code inspection | implicit |
| reported partition implies actual partition | `ocaml/beep_bridge_mapping.ml` | `check_partition` | code inspection | implicit |
| non-realisable payloads imply ring loss/partition reported | kernel contract | `audit_coverage_contract` | assumed | needs validation |

## 3. Negative coverage tests to add

The following regression cases should be added to prevent the audit contract from floating free of the implementation:

- payload with an edge compatibility failure that is not captured by site-only rules, to ensure the audit does not silently rely on an incomplete local predicate set.
- payload where a reachable region is present but the audit predecessor selection would skip it if the structural-observation ordering is malformed.
- payload where a partition should be detected but one region is silently ignored by `compute_mismatches`.
- malformed-but-parseable payloads that must be rejected or reported, not silently accepted.

These tests should fail if `audit_coverage` is false but the OCaml pipeline still returns `SS_Coherent`.

## 4. Status summary

- `ring_loss_soundness`: proved in `rocq/beep_bridge_kernel.v`.
- `partition_soundness`: proved in `rocq/beep_bridge_kernel.v`.
- `global_history_obstruction_soundness`: proved in `rocq/beep_bridge_kernel.v`.
- `audit_coverage`: currently an explicit contract rather than a proved theorem.
- remaining boundary: `acc_semantic_coverage` must be justified by the OCaml audit contract.

## 5. Recommended immediate action

1. Keep `audit_coverage` as an engineering contract for now.
2. Add a small negative regression suite in `ocaml/` that exercises edge skipping and missing-region coverage.
3. Use `rocq/audit_coverage_contract.v` as the formal skeleton to ensure the OCaml audit evidence is connected to the contract.
4. If stronger guarantees are needed later, mirror `compute_mismatches` in Rocq and prove the contract from that mirror implementation.
