# Beep Before Bang — Demo v2

**We monitor a compute cluster from two independent perspectives and raise a warning before the partition becomes operationally visible.**

---

## What this demo shows

A 4-node compute cluster is monitored simultaneously from two independent signal layers:

| Layer | Engine | What it measures |
|-------|--------|-----------------|
| Temporal | Rupture engine (Rust, PELT) | Load regime shifts — when cluster behaviour departs from its established baseline |
| Structural | Boundary invariants (Python, Betti numbers) | Topology violations — when the cluster's physical connectivity departs from its certified design state |

Both layers observe the same object. Neither layer knows about the other. When both fire together, the system is in structural failure.

---

## The scenario

A 4-node compute cluster in ring topology: `s0 — s1 — s2 — s3 — s0`.

Three phases, 20 bars each:

| Phase | Dates | Load | Topology | Engine behaviour |
|-------|-------|------|----------|-----------------|
| Calm | 2020-03-12 | Normal, stable | b=[1,1] intact | No confirmed alarms |
| Stress onset | 2020-04-09 | Elevated, volatile | b=[1,0] ring broken | Candidate raised 2020-04-08 · Confirmed 2020-04-10 |
| Collapse | 2020-05-07 | High, erratic | b=[2,0] cluster split | Continued elevated state |

The rupture candidate fires on **2020-04-08 — the last day of the calm phase**. Confirmation arrives **two days into stress onset**. That is the "beep before bang".

---

## What the structural certificate means

The Betti numbers are algebraically exact:

```
b₀ = number of connected components   (b₀=1: all nodes reachable)
b₁ = number of independent ring paths (b₁=1: ring routing valid)
```

| State | b₀ | b₁ | Meaning |
|-------|----|----|---------|
| Nominal | 1 | 1 | Cluster intact. Ring routing valid. |
| Link fault | 1 | 0 | Ring path destroyed. Fallback routing required. [WARNING] |
| Partition | 2 | 0 | Cluster split into 2 islands. Cross-island traffic impossible. [CRITICAL] |

When `b₁` drops to 0, the ring path **provably no longer exists** — not as a heuristic, as a theorem about the declared topology.

---

## Files in this bundle

| File | Purpose |
|------|---------|
| `scenA_base_ohlcv.csv` | 110-row fixture (50 warmup + 20 calm + 20 stressed + 20 collapse) |
| `scenA_base_meta.json` | Phase boundary metadata (row indices and timestamps) |
| `stress_demo.toml` | Calibrated rupture engine config (`rho_rupture=1.25`, `robust_scale_n=15`) |
| `beep_output.json` | Full pipeline output (machine-readable) |
| `beep_report.html` | Human-readable report: risk banner, phase timeline, Betti table |
| `calibration_summary.txt` | All 4 fixture variants PASS the calibration criterion |

---

## How to run

```bash
cd ~/beep_work
./run_beep.sh
# produces: beep_output.json  beep_report.html
```

---

## Fusion rule

```
risk_score = 0.55 × rupture_score + 0.45 × invariant_score
```

Rupture is weighted slightly higher because temporal instability fires earlier — it detects the regime shift as it begins, before topology fully breaks. The invariant score confirms structural departure. All constants in `~/beep_work/fusion_config.py`.

---

## Warmup rows

The fixture has 50 warmup rows (rows 0–49) that precede the narrative. These fill the rupture engine's capacity window (`capacity_l=50`) so the `rho` estimate stabilises before Phase 1 begins. The warmup absorbs the engine's initialization transient and is hidden from the HTML report.

---

## Calibration

`stress_demo.toml` was calibrated so that:
- During calm: residuals are zero, `rho ≈ 1.0` (below `rho_rupture=1.25`)
- During stress: residuals spike, `strain` grows above `capacity`, `rho > 1.25` → detection

The key diagnosis: `soft_max_combine(0,0,0,tau) = tau·ln(3) ≈ 0.385`, not zero. At steady state, `rho = strain/capacity → 1.0` regardless of data. The original `rho_rupture=1.00` triggered on any startup transient. Raising it to 1.25 and prepending 50 warmup rows solved this structurally.

---

## What is not yet done

These are polish items, not conceptual gaps:

1. **Phase 3 second alarm.** The collapse phase does not produce a new confirmed alarm because the engine's capacity adapts to Phase 2 levels. A second alarm is achievable by raising Phase 3 sigma to ~0.060 in `gen_fixtures.py`. Product-design choice, not a bug.

2. **Infrastructure-native timestamps.** Dates read as financial calendar (2020-03-12 etc.) because the rupture engine was originally built for equity data. Relabelling to uptime or wall-clock hours is cosmetic.

Neither changes the core claim.

---

## Version history

| Version | Key change |
|---------|-----------|
| v1 (2026-04-05) | First calibrated demo. Cross-domain: financial rupture + chiplet topology. Proved the pipeline works. |
| v2 (2026-04-05) | Unified domain. Both signals observe the same 4-node compute cluster. Closed the "two separate worlds" objection. |

**Demo v2 — frozen 2026-04-05.**
Do not modify this directory. Experiment in `~/beep_work/` and copy outputs here when stable.
