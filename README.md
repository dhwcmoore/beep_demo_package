## Beep Before Bang — Structural Early Warning Demo

### What this is

A prototype system that detects structural failure risk before threshold-based alarms trigger.

It combines:

* Time-series rupture detection (Rust)
* Structural invariant signals (Python)
* Audit consistency layer (OCaml)
* Formal guarantees (Rocq, partial)

---

### What it demonstrates

Local signals can pass while global structure fails.

The system detects:

* strain accumulation
* regime inconsistency
* structural instability

---

### How to run

```
./run_demo.sh
```

---

### Output

Results are written to:

```
output/
```

Includes:

* rupture events
* fused risk score
* HTML report

---

### Important notes

* Invariant layer is now fully integrated (real engine, not stub)
* Formal proofs are partial and documented in `/rocq`
* This is a research prototype, not production software