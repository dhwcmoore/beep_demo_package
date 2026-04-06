(** structural_judgement_contract.v

    Formalises the OCaml structural judgement classifier in Rocq.

    This file defines the exact case split that the OCaml bridge must
    satisfy and proves the corresponding Rocq-side lemmas.

    The contract is:

      fault_b0 > nominal_b0
        -> ConnectivityPartition
      fault_b0 = nominal_b0 /\ fault_b1 < nominal_b1
        -> CycleLoss
      otherwise
        -> NoBreak

    This gives the bridge a tight, auditable semantics: the OCaml
    classifier is not just an implementation detail, it is anchored in
    the formal Rocq kernel.
*)

Require Import beep_bridge_kernel.
Require Import Coq.Arith.Arith.
Require Import Coq.Arith.PeanoNat.
Require Import Coq.Bool.Bool.
Require Import Lia.

Section StructuralJudgement.

  (** Structural judgement categories for the invariant delta. *)
  Inductive structural_judgement : Type :=
    | SJ_NoBreak
    | SJ_CycleLoss
    | SJ_ConnectivityPartition.

  (** The formal semantics of the OCaml structural classifier. *)
  Definition structural_judgement_of
      (nominal fault : cluster_certificate) : structural_judgement :=
    if (b0 nominal <? b0 fault) then
      SJ_ConnectivityPartition
    else if (b0 fault =? b0 nominal) && (b1 fault <? b1 nominal) then
      SJ_CycleLoss
    else
      SJ_NoBreak.

  Lemma structural_judgement_of_partition :
    forall nominal fault,
      b0 fault > b0 nominal ->
      structural_judgement_of nominal fault = SJ_ConnectivityPartition.
  Proof.
    intros nominal fault Hgt.
    unfold structural_judgement_of.
    destruct (b0 nominal <? b0 fault) eqn:Hbranch.
    - reflexivity.
    - apply Nat.ltb_ge in Hbranch.
      lia.
  Qed.

  Lemma structural_judgement_of_cycle_loss :
    forall nominal fault,
      b0 fault = b0 nominal ->
      b1 fault < b1 nominal ->
      structural_judgement_of nominal fault = SJ_CycleLoss.
  Proof.
    intros nominal fault Heq Hlt.
    unfold structural_judgement_of.
    destruct (b0 nominal <? b0 fault) eqn:Hgt.
    - apply Nat.ltb_lt in Hgt.
      rewrite Heq in Hgt.
      lia.
    - destruct ((b0 fault =? b0 nominal) && (b1 fault <? b1 nominal)) eqn:Hbranch.
      + reflexivity.
      + apply andb_false_iff in Hbranch.
        destruct Hbranch as [Hneq | Hnot].
        * apply Nat.eqb_neq in Hneq.
          lia.
        * apply Nat.ltb_ge in Hnot.
          lia.
  Qed.

  Lemma structural_judgement_of_no_break :
    forall nominal fault,
      b0 fault <= b0 nominal ->
      (b0 fault < b0 nominal \/ b1 nominal <= b1 fault) ->
      structural_judgement_of nominal fault = SJ_NoBreak.
  Proof.
    intros nominal fault Hle Hcase.
    unfold structural_judgement_of.
    destruct (b0 nominal <? b0 fault) eqn:Hgt.
    - apply Nat.ltb_lt in Hgt.
      lia.
    - destruct ((b0 fault =? b0 nominal) && (b1 fault <? b1 nominal)) eqn:Hbranch.
      + apply andb_true_iff in Hbranch as [Heqb Hltb].
        apply Nat.eqb_eq in Heqb.
        apply Nat.ltb_lt in Hltb.
        destruct Hcase as [Hlt | Hge]; lia.
      + reflexivity.
  Qed.

  Section BridgePayload.
    Variable region : Type.
    Variable P : bridge_payload region.

    Definition structural_judgement_at (r : region) : structural_judgement :=
      structural_judgement_of
        (@observed_cert region P (@baseline_region region P))
        (@observed_cert region P r).

    Lemma structural_judgement_at_partition :
      forall r : region,
        @partition_at region P r ->
        structural_judgement_at r = SJ_ConnectivityPartition.
    Proof.
      intros r Hpart.
      unfold structural_judgement_at.
      apply structural_judgement_of_partition.
      unfold partition_at in Hpart.
      assumption.
    Qed.

    Lemma structural_judgement_at_cycle_loss :
      forall r : region,
        b0 (@observed_cert region P r) =
          b0 (@observed_cert region P (@baseline_region region P)) ->
        b1 (@observed_cert region P r) <
          b1 (@observed_cert region P (@baseline_region region P)) ->
        structural_judgement_at r = SJ_CycleLoss.
    Proof.
      intros r Heq Hlt.
      unfold structural_judgement_at.
      apply structural_judgement_of_cycle_loss.
      - exact Heq.
      - assumption.
    Qed.

  End BridgePayload.

End StructuralJudgement.
