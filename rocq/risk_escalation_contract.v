(** risk_escalation_contract.v

    A small qualitative risk escalation contract for the BEEP bridge.

    This file defines a risk level lattice and a simple rupture presence
    predicate, then states the escalation rule that protects against
    understating risk when the OCaml structural judgement reports a
    structural break and there is positive rupture evidence.

    The contract is intentionally lightweight: it does not formalise the
    numeric fusion score, only the qualitative lower bound on risk.
*)

Require Import beep_bridge_kernel.
Require Import structural_judgement_contract.
From Stdlib Require Import Arith Lia.

Section RiskEscalationContract.

  Inductive risk_level : Type :=
    | RL_LOW
    | RL_MEDIUM
    | RL_HIGH
    | RL_CRITICAL.

  Definition risk_level_rank (rl : risk_level) : nat :=
    match rl with
    | RL_LOW => 0
    | RL_MEDIUM => 1
    | RL_HIGH => 2
    | RL_CRITICAL => 3
    end.

  Definition risk_at_least (actual expected : risk_level) : Prop :=
    risk_level_rank actual >= risk_level_rank expected.

  Definition rupture_present (rupture_score : nat) : Prop :=
    rupture_score > 0.

  Definition risk_escalation_rule
      (sj : structural_judgement)
      (rupture_score : nat)
      (rl : risk_level) : Prop :=
    match sj with
    | SJ_ConnectivityPartition =>
        rupture_present rupture_score -> rl = RL_CRITICAL
    | SJ_CycleLoss =>
        rupture_present rupture_score -> rl = RL_HIGH \/ rl = RL_CRITICAL
    | SJ_NoBreak => True
    end.

  Theorem partition_with_rupture_must_be_critical :
    forall rupture_score rl,
      risk_escalation_rule SJ_ConnectivityPartition rupture_score rl ->
      rupture_present rupture_score ->
      rl = RL_CRITICAL.
  Proof.
    intros rupture_score rl Hrule Hrupt.
    simpl in Hrule.
    exact (Hrule Hrupt).
  Qed.

  Theorem cycle_loss_with_rupture_must_be_high_or_critical :
    forall rupture_score rl,
      risk_escalation_rule SJ_CycleLoss rupture_score rl ->
      rupture_present rupture_score ->
      rl = RL_HIGH \/ rl = RL_CRITICAL.
  Proof.
    intros rupture_score rl Hrule Hrupt.
    simpl in Hrule.
    exact (Hrule Hrupt).
  Qed.

  Lemma risk_at_least_reflexive :
    forall rl,
      risk_at_least rl rl.
  Proof.
    intros rl. unfold risk_at_least. simpl. lia.
  Qed.

End RiskEscalationContract.
