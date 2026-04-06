Require Import beep_bridge_kernel.
Require Import scenA_runtime_discharge.

Module ScenARuntimeAdjacencyBridge.

  Import ScenARuntimeDischarge.

  Lemma scenA_payload_adjacency_faithful :
    forall r1 r2 : scenA_region,
      runtime_adjacent scenA_runtime r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    intros r1 r2.
    rewrite scenA_runtime_adjacent_exact.
    simpl.
    tauto.
  Qed.

  Lemma scenA_adjacent_iff_runtime :
    forall r1 r2 : scenA_region,
      runtime_adjacent scenA_runtime r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    exact scenA_runtime_adjacent_exact.
  Qed.

End ScenARuntimeAdjacencyBridge.