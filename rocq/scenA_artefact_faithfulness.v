Require Import beep_bridge_kernel.
Require Import scenA_runtime_discharge.
Require Import scenA_canonical_edges.

Module ScenAArtefactFaithfulness.

  Import ScenARuntimeDischarge.
  Import ScenACanonicalEdges.

  (* Theorem: decoded edges match the formal adjacency *)
  Theorem decoded_edges_match_formal :
    forall r1 r2 : scenA_region,
      edge_in decoded_scenA_edges r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    intros r1 r2.
    rewrite decoded_edges_match_runtime.
    rewrite scenA_runtime_adjacent_exact.
    reflexivity.
  Qed.

End ScenAArtefactFaithfulness.