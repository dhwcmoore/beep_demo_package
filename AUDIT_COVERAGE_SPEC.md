# Audit Coverage Specification

This document defines the exact contract between the OCaml audit implementation and the Rocq kernel assumption currently expressed by `audit_coverage` in `rocq/beep_bridge_kernel.v`.

## 1. Current formal state

In `rocq/beep_bridge_kernel.v`:

- `ring_loss_soundness` is proved.
- `partition_soundness` is proved.
- `global_history_obstruction_soundness` is proved.
- `audit_coverage` is currently an explicit external assumption.
- `global_history_obstruction_completeness` is derived directly from `audit_coverage`.

Thus the only remaining formal dependency is the audit coverage contract: a non-realisable payload must be reported obstructed.

## 2. OCaml audit boundary

The canonical executable audit boundary is:

- Input ingestion: `ocaml/beep_bridge_ingest.ml`
- Audit logic: `ocaml/beep_bridge_mapping.ml`
- Audit verdict emission: `ocaml/run_beep_bridge_audit.ml`

The contract is against the audit layer implemented by:

- `Beep_bridge_mapping.compute_mismatches`
- `Beep_bridge_mapping.check_ring_loss`
- `Beep_bridge_mapping.check_partition`
- `Beep_bridge_mapping.check_obstruction_lift`
- `Beep_bridge_mapping.expected_transport`
- `Beep_bridge_mapping.to_regional_model`

`run_beep_bridge_audit.ml` converts the mismatch list into an `audit_result`.

## 3. Inputs the OCaml audit reads

The executable audit reads a `Beep_bridge_types.bridge_payload` value.
The relevant fields are:

- `structural_observations : local_section list`
- `derived_transitions : transition list`
- `rupture_observations : rupture_obs list` (used only for rupture count)

A `local_section` contains:

- `region : region_id`
- `cert : cluster_certificate`

A `cluster_certificate` contains:

- `b0 : int`
- `b1 : int`
- `advisories : string list`

A `transition` contains:

- `src : region_id`
- `dst : region_id`
- `delta_b0 : int * int`
- `delta_b1 : int * int`
- `compatibility_status : compatibility_status`

## 4. What the OCaml audit computes

The core audit computation is `compute_mismatches`.

For each destination section `dst_sec` in `structural_observations` after the first section:

1. Find the predecessor section `src_sec` immediately before `dst_sec` in the list.
2. Compute `expected = expected_transport payload src_sec`.
3. Let `observed = dst_sec.cert`.
4. Fire theorem predicates against the baseline certificate and the expected certificate.
5. If any predicate fires, emit one `certificate_mismatch` for that destination.

The baseline certificate is always the first `structural_observations` section.

## 5. What counts as detecting `ring_loss_at`

The OCaml audit predicate is:

```ocaml
let check_ring_loss (baseline : cluster_certificate) (observed : cluster_certificate) : bool =
  baseline.b1 > 0 && observed.b1 = 0
```

This corresponds exactly to the Rocq kernel predicate:

```coq
ring_loss_at P r :=
  b1 (observed_cert P (baseline_region P)) > 0 /\
  b1 (observed_cert P r) = 0
```

So the contract requires that the audit must detect any region whose observed `b1` drops to `0` when the baseline `b1` is positive.

## 6. What counts as detecting `partition_at`

The OCaml audit predicate is:

```ocaml
let check_partition (baseline : cluster_certificate) (observed : cluster_certificate) : bool =
  observed.b0 > baseline.b0
```

This corresponds exactly to the Rocq kernel predicate:

```coq
partition_at P r :=
  b0 (observed_cert P r) > b0 (observed_cert P (baseline_region P))
```

So the contract requires that the audit must detect every region whose observed `b0` exceeds the baseline `b0`.

## 7. What the audit must cover

The exact contract is:

- For every well-formed payload `P` (in the Rocq sense), if no `global_history` exists such that `global_history_realises_payload P H`, then the OCaml audit must report obstruction.
- Concretely, this means `compute_mismatches P` must contain at least one mismatch whose `theorems_fired` includes `RingLoss` or `Partition`.
- Equivalently, `run_audit P` must return `SS_Obstructed _`.

This is the minimal contract needed to justify the kernel assumption `audit_coverage`.

### Important subtlety

The OCaml audit also computes `ObstructionLift`, but the current Rocq kernel does not use it in `audit_obstructed`.
Therefore the contract must be phrased in terms of `RingLoss` and `Partition`, not merely "some mismatch exists".

## 8. The case table

| Failure mode in formal model | Kernel predicate | OCaml detection predicate | Required coverage guarantee |
|---|---|---|---|
| Baseline `b1 = 1` and observed `b1 = 0` at region `r` | `ring_loss_at P r` | `check_ring_loss baseline observed` | must fire `RingLoss` |
| Observed `b0 > baseline.b0` at region `r` | `partition_at P r` | `check_partition baseline observed` | must fire `Partition` |
| Any other non-realisable payload under well-formedness | should reduce to one of the above | audit must still report obstruction via those predicates | coverage must be exhaustive |
| Payload is coherent | no obstruction | no mismatch list | must return `SS_Coherent` |

## 9. Exact contract statement

The audit coverage contract is:

> For all payloads `P` that satisfy the Rocq `bridge_payload_well_formed` assumptions,
> if there is no global history `H` with `global_history_realises_payload P H`,
> then the OCaml audit must report `SS_Obstructed` and `compute_mismatches P` must contain at least one mismatch with `RingLoss` or `Partition`.

In Rocq-style notation, this is the theorem shape the implementation must support:

```coq
Theorem audit_coverage_contract :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    (~ exists H : global_history, global_history_realises_payload P H) ->
    audit_obstructed P.
```

## 10. Implementation mapping

To justify `audit_coverage`, the following functions are the relevant implementation points:

- `ocaml/beep_bridge_mapping.ml`:
  - `check_ring_loss`
  - `check_partition`
  - `expected_transport`
  - `compute_mismatches`
  - `to_regional_model`
- `ocaml/run_beep_bridge_audit.ml`:
  - `run_audit`

The contract should be enforced by tests that exercise `compute_mismatches` and `run_audit` on payloads representative of all non-realisable cases.

## 11. Recommended next strategy

### Light route (recommended)

Treat the audit contract as a trusted boundary and document it crisply.
Then build a test harness that checks:

- every formally non-realisable payload observed in the domain yields `SS_Obstructed`
- each non-realisable payload yields a mismatch with `RingLoss` or `Partition`
- coherent payloads yield `SS_Coherent`

### Strong route

If a stronger verification path is needed, mirror the OCaml logic in Rocq as a model of `compute_mismatches` and prove that this model implies `audit_coverage`.
The current contract is the right starting point for that stronger mirror.

## 12. Summary

This specification fixes the missing assumption precisely:

- it makes `audit_coverage` a contract about `RingLoss` and `Partition` coverage;
- it ties that contract to `compute_mismatches` and `run_audit` in the OCaml code;
- it makes the boundary testable by checking that every non-realisable payload triggers obstruction through the stated predicates.
