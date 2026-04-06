Require Import beep_bridge_kernel.
Require Import Coq.Lists.List.
Import ListNotations.

Module ScenARuntimeDischarge.

  Definition runtime_graph : Type := scenA_region -> list scenA_region.

  Definition runtime_adjacent (g : runtime_graph) (r1 r2 : scenA_region) : Prop :=
    In r2 (g r1).

  Definition scenA_runtime : runtime_graph :=
    fun r =>
      match r with
      | warmup => [phase1]
      | phase1 => [phase2]
      | phase2 => []
      end.

  Theorem scenA_runtime_adjacent_exact :
    forall r1 r2 : scenA_region,
      runtime_adjacent scenA_runtime r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    intros r1 r2.
    unfold runtime_adjacent, scenA_runtime, scenA_adjacent.
    destruct r1; destruct r2; simpl; intuition discriminate.
  Qed.

End ScenARuntimeDischarge.