Require Import beep_bridge_kernel.
Require Import scenA_runtime_discharge.
Require Import Coq.Lists.List.
Import ListNotations.

Module ScenACanonicalEdges.

  Import ScenARuntimeDischarge.

  (* Canonical edge representation: list of directed pairs *)
  Definition edge : Type := scenA_region * scenA_region.

  (* The decoded edges from the artefact - this should match what OCaml ingest produces *)
  Definition decoded_scenA_edges : list edge :=
    [(warmup, phase1); (phase1, phase2)].

  (* Check if an edge is in the list *)
  Definition edge_in (edges : list edge) (r1 r2 : scenA_region) : Prop :=
    In (r1, r2) edges.

  (* Theorem: decoded edges match the runtime adjacency *)
  Theorem decoded_edges_match_runtime :
    forall r1 r2 : scenA_region,
      edge_in decoded_scenA_edges r1 r2 <-> runtime_adjacent scenA_runtime r1 r2.
  Proof.
    intros r1 r2.
    unfold edge_in, decoded_scenA_edges, runtime_adjacent, scenA_runtime.
    destruct r1; destruct r2; simpl; intuition discriminate.
  Qed.

End ScenACanonicalEdges.