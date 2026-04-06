# beep.loopaudit.bridge.v1 — Schema Reference

## Status

Frozen at v1. Breaking changes require a new `schema_version` string.

---

## Trusted boundary

These fields are inside the trusted boundary.
LoopAudit's audit kernel reads only these fields.
Everything else is either absent from this payload or explicitly excluded.

| Field | Status | Notes |
|---|---|---|
| `schema_version` | trusted | must be `"beep.loopaudit.bridge.v1"` |
| `scenario_id` | trusted | stable identifier for the scenario |
| `timeline.regions[*]` | trusted | region graph nodes |
| `structural_observations[*]` | trusted | local certificates (b0, b1, advisories) |
| `derived_transitions[*]` | trusted | transport edges between regions |
| `rupture_observations[*]` | empirical support only — see below | |

## Excluded fields

These fields from the `beep_output.json` pipeline output are **not included**
in the bridge payload. The OCaml audit kernel must not read or depend on them.

| Excluded field | Reason |
|---|---|
| `risk_score` | operational summary, not a theorem |
| `risk_level` | derived from fusion weights, outside proof boundary |
| `rupture_score` | weighted heuristic |
| `invariant_score` | weighted heuristic |
| `signals.invariants.raw_output` | prose, not a certificate |
| `signals.rupture.scenario_meta.phase*_params` | market simulation params |

---

## Field-by-field reference

### `timeline.regions[]`

Each region is a node in the cover of the observation graph.

```json
{
  "region_id":   "phase1",
  "start_index": 50,
  "end_index":   69,
  "start_ts":    "2020-03-12",
  "end_ts":      "2020-04-08"
}
```

`region_id` is the stable identity used throughout. Index and timestamp fields
are provided for traceability and report rendering only; the audit kernel uses
only `region_id` to cross-reference sections.

### `structural_observations[]`

Each entry is a local certificate assigned to a region.

```json
{
  "region_id":  "phase1",
  "system":     "cluster_link_fault",
  "b0":         1,
  "b1":         0,
  "advisories": ["CLUSTER_RING_VIOLATED"]
}
```

`b0` = number of connected components (Betti-0).  
`b1` = number of independent ring paths (Betti-1).  
`advisories` = advisory codes emitted for this region by the invariant engine.

**Interpretation contract:**

| b0 | b1 | Meaning |
|---|---|---|
| 1 | 1 | nominal — fully connected, ring routing valid |
| 1 | 0 | link fault — connected but ring broken |
| >1 | 0 | partition — cluster split into isolated islands |

**Note:** only regions with a declared structural stage have an entry here.
Regions without an entry (e.g. phase3 in scenA) do not participate in
mismatch detection.

### `derived_transitions[]`

Each entry declares the structural relationship between two adjacent regions.

```json
{
  "from_region":          "warmup",
  "to_region":            "phase1",
  "delta": {
    "b0": [1, 1],
    "b1": [1, 0]
  },
  "compatibility_status": "ring_broken"
}
```

`delta.b0` = [value at from_region, value at to_region].  
`delta.b1` = [value at from_region, value at to_region].

**`compatibility_status` values and their transport semantics:**

| Value | Transport prediction |
|---|---|
| `"coherent"` | expected certificate at dst = certificate at src (verbatim) |
| `"ring_broken"` | expected b1 at dst = 0; b0 unchanged |
| `"partitioned"` | expected b0 at dst = delta.b0[1]; b1 unchanged |
| `"ring_broken_and_partitioned"` | expected b0 at dst = delta.b0[1]; b1 = 0 |

**Obstruction_lift theorem:** fires when the transported (expected) certificate
differs from the observed certificate on b0 or b1, regardless of what was
declared. This catches undeclared degradations — cases where the compatibility
label does not match what the invariant engine actually observed.

### `rupture_observations[]`

Rupture events are **empirical support** for an obstruction claim.
They are not proof objects. A high `peak_rho` near a region transition
corroborates — but does not substitute for — the structural certificate
mismatch.

```json
{
  "candidate_index": 69,
  "candidate_ts":    "2020-04-08",
  "confirmed_index": 71,
  "confirmed_ts":    "2020-04-10",
  "peak_rho":        2.0175971533913386
}
```

`confirmed_index` and `confirmed_ts` may be `null` for unconfirmed candidates.

**The audit kernel uses only `len(rupture_observations)` as a witness count.**
It does not use `peak_rho` to gate or weight the obstruction verdict.

---

## What counts as a mismatch

A mismatch is recorded at destination region R when at least one of the
following theorem predicates fires:

**Theorem A — RingLoss:**  
baseline.b1 > 0 AND observed_at_R.b1 = 0

**Theorem B — Partition:**  
observed_at_R.b0 > baseline.b0

**Theorem C — ObstructionLift:**  
expected_transport(predecessor → R).b0 ≠ observed_at_R.b0
OR expected_transport(predecessor → R).b1 ≠ observed_at_R.b1

The baseline is always the first structural observation (warmup).
Transport expectations are computed from the declared `compatibility_status`
of the outgoing transition edge.

---

## What counts as empirical support

A rupture observation supports an obstruction claim when its
`candidate_index` or `confirmed_index` falls within or immediately
adjacent to the index range of a region where a mismatch was detected.

The audit reports `rupture_witness_count` as a raw count of all rupture
observations in the payload. Localisation of which rupture events support
which specific triple is left to the explanation retention layer above the
kernel.

---

## Obstruction verdict

| Verdict | Meaning |
|---|---|
| `SS_Coherent` | No mismatch detected across any transition. All transported certificates are compatible with observed certificates. |
| `SS_Obstructed` | At least one obstruction triple found. The audit returns all triples. Each triple names three regions (A, B, C) where A is the coherent baseline, B is the first degradation, and C is the compounding degradation (B=C for a degenerate single-mismatch case). |

The obstruction verdict is a structural claim about the certificate sequence.
It is not a risk level. Risk levels, if needed, should be computed by a
separate operational layer that reads the obstruction report as input.
