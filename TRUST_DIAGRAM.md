# BEEP Trust Diagram

```mermaid
flowchart LR
    A[Rupture Evidence]
    B[Structural Inputs]
    A --> C[Fusion + Guardrails]
    B --> D[OCaml Judgement + Rocq Contracts]
    D --> C
    C --> E[Sealed Audit Artefact]
    E --> F[Verification]

    subgraph "" 
      D --- G[Structural Semantics Contract]
      C --- H[Risk Escalation Contract]
      A --- I[Rupture Contract]
    end
```

## Diagram Notes

- **Rupture Evidence**: raw event detections, peak rho, event counts, phase thresholds.
- **Structural Inputs**: Betti numbers and invariant features fed into OCaml judgement.
- **OCaml Judgement + Rocq Contracts**: formal semantics for structural decisions.
- **Fusion + Guardrails**: combines scores, enforces escalation rules.
- **Sealed Audit Artefact**: final payload canonicalised and hashed.
- **Verification**: validates the seal and detects tampering.
