import os
import sys
import hashlib
import json

# Make engine and export importable
HERE = os.path.dirname(__file__)
PYTHON_DIR = os.path.abspath(os.path.join(HERE, ".."))
ENGINE_DIR = os.path.abspath(os.path.join(HERE, "..", "engine"))
for _p in (PYTHON_DIR, ENGINE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from export.invariants_writer import build_v1_payload, write_v1_payload  # type: ignore

# Import your engine modules
import examples  # type: ignore
from chain_complex import build_chain_complex  # type: ignore
from homology import compute_homology  # type: ignore

def sha256_hex_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def main() -> int:
    system = examples.example_triangle_classical()

    cc = build_chain_complex(system)
    hom = compute_homology(cc)

    max_dim = cc.max_dim
    cell_counts = {k: cc.rank(k) for k in range(max_dim + 1)}
    boundary_ok = cc.is_valid
    thin_ok = None

    betti = {k: hom[k].betti for k in hom}
    torsion = {k: hom[k].torsion for k in hom}

    # Compute a simple inputs_hash from a JSON serialisation of the system if possible
    try:
        if hasattr(system, "to_json"):
            inputs_blob = json.dumps(system.to_json(), sort_keys=True).encode("utf-8")
        else:
            inputs_blob = repr(system).encode("utf-8")
    except Exception:
        inputs_blob = repr(system).encode("utf-8")

    inputs_hash = sha256_hex_bytes(inputs_blob)

    payload = build_v1_payload(
        engine="whitehead_good",
        engine_version="0.1.0",
        inputs_hash=inputs_hash,
        max_dim=int(max_dim),
        cell_counts=cell_counts,
        boundary_squared_zero_verified=bool(boundary_ok),
        thinness_verified=thin_ok,
        betti=betti,
        torsion=torsion,
    )

    out_path = os.path.abspath(os.path.join(HERE, "..", "..", "schemas", "audit_invariants.v1.generated.json"))
    write_v1_payload(out_path, payload)
    print(out_path)
    print("payload_sha256 =", payload["integrity"]["payload_sha256"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
