(** beep_bridge_kernel.v

    Soundness theorem for the BEEP → LoopAudit bridge.

    ===================================================================
    THE THRESHOLD THEOREM
    ===================================================================

    Theorem global_history_obstruction_soundness :
      forall (P : bridge_payload),
        bridge_payload_well_formed P ->
        audit_obstructed P ->
        ~ exists H : global_history,
            global_history_realises_payload P H.

    This theorem marks the return to the formally verified path.

    What it says in plain English:
      For every well-formed bridge payload, if the audit returns an
      obstruction witness, then no globally coherent history exists
      that realises the observed regional certificates while satisfying
      the baseline transport laws.

    What counts as success:
      This theorem is proved when the audit's SS_Obstructed verdict has
      kernel-backed meaning — not just a computed tag, but a statement
      of impossibility relative to the bridge semantics.

    What this theorem does NOT say:
      - A physical failure will occur
      - A rupture event is predicted
      - The risk score is formally justified

    It says only:
      The observed structural certificate sequence cannot be explained
      by any coherent, fault-free global structural history.

    That is the honest and strong version of "beep before bang."

    ===================================================================
    CORRESPONDENCE WITH THE OCAML AUDIT
    ===================================================================

    The predicates here correspond exactly to the OCaml implementation:

      Rocq predicate           OCaml function
      ─────────────────────    ──────────────────────────────────────
      cluster_certificate      beep_bridge_types.cluster_certificate
      baseline_transport       implicit in check_ring_loss /
                               check_partition (baseline preserved)
      global_history           region -> cluster_certificate
      globally_coherent        baseline_transport over adjacent pairs
      ring_loss_at             check_ring_loss (baseline.b1>0, obs.b1=0)
      partition_at             check_partition (obs.b0 > baseline.b0)
      audit_obstructed         exists_obstruction_witness (any triple)

    The ObstructionLift predicate (check_obstruction_lift in OCaml)
    is stated here as a separate theorem requiring an explicit
    permitted_transport relation. It is admitted pending that definition.

    ===================================================================
    PROOF STATUS
    ===================================================================

      coherent_preserves_along_path  PROVED
      ring_loss_soundness            PROVED
      partition_soundness            PROVED
      global_history_obstruction_soundness  PROVED
      obstruction_lift_soundness     ADMITTED (see §5)
      global_history_obstruction_completeness  ADMITTED (see §6)

    ===================================================================
*)

Require Import Coq.Arith.Arith.
Require Import Lia.

(* ==========================================================================
   §1  Types
   ========================================================================== *)

(** Cluster certificate: the local structural invariant for one region.
    b0 = number of connected components (Betti-0).
    b1 = number of independent ring paths (Betti-1).

    Corresponds to cluster_certificate in beep_bridge_types.ml. *)
Record cluster_certificate : Type := mk_cert {
  b0 : nat;
  b1 : nat;
}.

(** The region type is abstract here.
    Concrete instances use string identifiers; formally, only identity
    and adjacency matter. *)
Section BridgeKernel.

Variable region : Type.

(** A bridge payload provides:
      - the baseline region (the coherent, unperturbed reference)
      - an observed certificate for every region
      - an adjacency relation between directly connected regions

    Corresponds to the kernel fields of bridge_payload in beep_bridge_types.ml.
    (schema_version, scenario_id, timestamps are excluded from the kernel.) *)
Record bridge_payload : Type := mk_payload {
  baseline_region : region;
  observed_cert   : region -> cluster_certificate;
  adjacent        : region -> region -> Prop;
}.


(* ==========================================================================
   §2  Baseline transport, global history, and coherence
   ========================================================================== *)

(** Baseline transport: in a fault-free history, the certificate at any
    region is identical to the certificate at all preceding regions.
    Both b0 and b1 are preserved.

    This is the conservative baseline.  It is NOT the declared-event
    transport (which permits announced ring loss, partition, etc.).
    It is the transport law a coherent, unperturbed system would satisfy.

    This is where the impossibility lives: the observed certificates
    violate even this minimal baseline expectation. *)
Definition baseline_transport (c1 c2 : cluster_certificate) : Prop :=
  b0 c1 = b0 c2 /\ b1 c1 = b1 c2.

(** A global history is an assignment of a certificate to every region.
    It is the object that "realises" the local observations as a single
    globally consistent whole. *)
Definition global_history : Type := region -> cluster_certificate.

(** A history matches the observations if it assigns the observed
    certificate to every region that has an observation.
    (Here we require it everywhere; the well-formedness predicate
    restricts attention to regions with declared observations.) *)
Definition history_matches_observations
    (P : bridge_payload) (H : global_history) : Prop :=
  forall r, H r = observed_cert P r.

(** A history is globally coherent if every pair of adjacent regions
    satisfies baseline transport: no structural change is permitted
    between neighbouring regions unless an explicit destructive event
    is declared.

    Note: this coherence predicate uses BASELINE transport, not the
    declared-event transport.  The soundness theorem says that if the
    audit fires, even this weaker (baseline) coherence is impossible. *)
Definition globally_coherent (P : bridge_payload) (H : global_history) : Prop :=
  forall r1 r2, adjacent P r1 r2 -> baseline_transport (H r1) (H r2).

(** The combined realisation predicate. *)
Definition global_history_realises_payload
    (P : bridge_payload) (H : global_history) : Prop :=
  history_matches_observations P H /\ globally_coherent P H.


(* ==========================================================================
   §3  Reachability and the coherence-along-path lemma
   ========================================================================== *)

(** Reachability: there is a finite directed path of adjacent steps
    from r1 to r2. *)
Inductive reachable (P : bridge_payload) : region -> region -> Prop :=
  | reach_refl :
      forall r,
        reachable P r r
  | reach_step :
      forall r1 r2 r3,
        adjacent P r1 r2 ->
        reachable P r2 r3 ->
        reachable P r1 r3.

(** Key structural lemma: a globally coherent history preserves baseline
    transport along any reachable path.

    Proof: by induction on the reachability relation.
      Base: reflexivity of baseline_transport.
      Step: if r1→r2 by adjacency and r2→*r3 by path,
            coherence gives transport(H r1, H r2),
            IH gives transport(H r2, H r3),
            transitivity gives transport(H r1, H r3). *)
Lemma coherent_preserves_along_path :
  forall (P : bridge_payload) (H : global_history) (r1 r2 : region),
    globally_coherent P H ->
    reachable P r1 r2 ->
    baseline_transport (H r1) (H r2).
Proof.
  intros P H r1 r2 Hcoh Hreach.
  induction Hreach as [r | r1 r2 r3 Hadj _Hreach23 IH].
  - (* r1 = r2: identity *)
    unfold baseline_transport. auto.
  - (* r1 → r2 → ... → r3 *)
    destruct (Hcoh r1 r2 Hadj) as [Hb0_12 Hb1_12].
    destruct IH as [Hb0_23 Hb1_23].
    split.
    + rewrite Hb0_12. exact Hb0_23.
    + rewrite Hb1_12. exact Hb1_23.
Qed.


(* ==========================================================================
   §4  Well-formedness, audit predicates, and soundness
   ========================================================================== *)

(** Bridge payload well-formedness.

    Requires:
      1. The baseline region has the expected nominal certificate
         (b0 = 1: fully connected; b1 = 1: ring routing valid).
      2. Every region where the audit might fire (b1 dropped to 0,
         or b0 increased) is reachable from the baseline.

    Condition 2 is the reachability assumption that grounds the proofs.
    For the BEEP demo, it holds because every phase is connected to
    warmup through consecutive declared transitions. *)
Record bridge_payload_well_formed (P : bridge_payload) : Prop := mk_wf {
  wf_b0_baseline :
    b0 (observed_cert P (baseline_region P)) = 1;
  wf_b1_baseline :
    b1 (observed_cert P (baseline_region P)) = 1;
  wf_reachable :
    forall r : region,
      (b1 (observed_cert P r) = 0 \/ b0 (observed_cert P r) > 1) ->
      reachable P (baseline_region P) r;
}.

(** Ring loss at region r:
    The baseline had at least one ring path (b1 > 0), but r has none (b1 = 0).
    Corresponds exactly to check_ring_loss in beep_bridge_mapping.ml. *)
Definition ring_loss_at (P : bridge_payload) (r : region) : Prop :=
  b1 (observed_cert P (baseline_region P)) > 0 /\
  b1 (observed_cert P r) = 0.

(** Partition at region r:
    The region has more connected components than the baseline.
    Corresponds exactly to check_partition in beep_bridge_mapping.ml. *)
Definition partition_at (P : bridge_payload) (r : region) : Prop :=
  b0 (observed_cert P r) > b0 (observed_cert P (baseline_region P)).

(** The audit is obstructed if any region exhibits ring_loss or partition.
    This corresponds to the existence of any obstruction_triple in the
    OCaml audit result. *)
Definition audit_obstructed (P : bridge_payload) : Prop :=
  exists r : region, ring_loss_at P r \/ partition_at P r.


(** ── Soundness lemma A: Ring loss implies no coherent history ── *)

(** If the baseline had a ring (b1=1) and region r has none (b1=0),
    then no globally coherent history can realise both observations. *)
Lemma ring_loss_soundness :
  forall (P : bridge_payload) (r : region),
    bridge_payload_well_formed P ->
    ring_loss_at P r ->
    ~ exists H : global_history, global_history_realises_payload P H.
Proof.
  intros P r Hwf [Hbase_b1 Hr_b1] [H [Hmatch Hcoh]].

  (* The history must agree with observations. *)
  assert (HH_b1_base : b1 (H (baseline_region P)) =
                       b1 (observed_cert P (baseline_region P))).
  { rewrite (Hmatch (baseline_region P)). reflexivity. }
  assert (HH_b1_r : b1 (H r) = b1 (observed_cert P r)).
  { rewrite (Hmatch r). reflexivity. }

  (* r is reachable from the baseline (by well-formedness). *)
  assert (Hreach : reachable P (baseline_region P) r).
  { apply (wf_reachable P Hwf). left. exact Hr_b1. }

  (* Coherence along the path: b1 is preserved from baseline to r. *)
  destruct (coherent_preserves_along_path P H (baseline_region P) r Hcoh Hreach)
    as [_ Hb1_preserved].
  (* Hb1_preserved : b1 (H (baseline_region P)) = b1 (H r) *)

  (* Substitute observations into Hb1_preserved. *)
  rewrite HH_b1_base in Hb1_preserved.
  rewrite HH_b1_r, Hr_b1 in Hb1_preserved.
  (* Hb1_preserved : b1 (observed_cert P (baseline_region P)) = 0 *)
  (* Hbase_b1      : b1 (observed_cert P (baseline_region P)) > 0 *)
  lia.
Qed.


(** ── Soundness lemma B: Partition implies no coherent history ── *)

(** If region r has more connected components than the baseline,
    then no globally coherent history can realise both observations. *)
Lemma partition_soundness :
  forall (P : bridge_payload) (r : region),
    bridge_payload_well_formed P ->
    partition_at P r ->
    ~ exists H : global_history, global_history_realises_payload P H.
Proof.
  intros P r Hwf Hpart [H [Hmatch Hcoh]].
  unfold partition_at in Hpart.

  (* The history must agree with observations. *)
  assert (HH_b0_base : b0 (H (baseline_region P)) =
                       b0 (observed_cert P (baseline_region P))).
  { rewrite (Hmatch (baseline_region P)). reflexivity. }
  assert (HH_b0_r : b0 (H r) = b0 (observed_cert P r)).
  { rewrite (Hmatch r). reflexivity. }

  (* r is reachable from the baseline.
     We need b0(observed r) > 1.
     From well-formedness: b0(baseline) = 1, and Hpart: b0(r) > b0(baseline),
     so b0(r) > 1. *)
  assert (Hreach : reachable P (baseline_region P) r).
  { apply (wf_reachable P Hwf). right.
    rewrite (wf_b0_baseline P Hwf) in Hpart. exact Hpart. }

  (* Coherence along the path: b0 is preserved from baseline to r. *)
  destruct (coherent_preserves_along_path P H (baseline_region P) r Hcoh Hreach)
    as [Hb0_preserved _].
  (* Hb0_preserved : b0 (H (baseline_region P)) = b0 (H r) *)

  (* Substitute observations. *)
  rewrite HH_b0_base in Hb0_preserved.
  rewrite HH_b0_r in Hb0_preserved.
  (* Hb0_preserved : b0 (observed_cert P (baseline_region P)) = b0 (observed_cert P r) *)
  (* Hpart         : b0 (observed_cert P r) > b0 (observed_cert P (baseline_region P)) *)
  lia.
Qed.


(** ── Main soundness theorem ──

    The central theorem.  Proved as a direct corollary of the two lemmas. *)

Theorem global_history_obstruction_soundness :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    audit_obstructed P ->
    ~ exists H : global_history,
        global_history_realises_payload P H.
Proof.
  intros P Hwf [r [Hrl | Hpart]].
  - exact (ring_loss_soundness P r Hwf Hrl).
  - exact (partition_soundness P r Hwf Hpart).
Qed.


(* ==========================================================================
   §5  ObstructionLift soundness (requires permitted_transport)
   ========================================================================== *)

(** ObstructionLift (check_obstruction_lift in OCaml) fires when the
    declared-event transport prediction does not match the observation.
    This is distinct from the baseline-transport impossibility proved above.

    To state the soundness theorem for ObstructionLift, we need to
    formalise the permitted transport relation — the OCaml function
    expected_transport expressed as a Prop. *)

(** Permitted transport under declared compatibility_status.
    This formalises expected_transport in beep_bridge_mapping.ml.

    compatibility_status is encoded as a type below.
    The actual transport rule is given by a relation. *)

Inductive compat_label : Type :=
  | lbl_coherent
  | lbl_ring_broken
  | lbl_partitioned
  | lbl_ring_broken_and_partitioned.

(** permitted_transport label src dst: the certificate dst is a valid
    continuation of src under the declared transition label. *)
Definition permitted_transport
    (lbl : compat_label)
    (src dst : cluster_certificate) : Prop :=
  match lbl with
  | lbl_coherent =>
    (* Declared coherent: certificate is preserved exactly. *)
    b0 src = b0 dst /\ b1 src = b1 dst
  | lbl_ring_broken =>
    (* Declared ring-broken: b0 unchanged, b1 must be 0. *)
    b0 src = b0 dst /\ b1 dst = 0
  | lbl_partitioned =>
    (* Declared partitioned: b0 may increase, b1 unchanged. *)
    b0 dst > b0 src /\ b1 src = b1 dst
  | lbl_ring_broken_and_partitioned =>
    (* Declared ring-broken-and-partitioned: b0 increases, b1 = 0. *)
    b0 dst > b0 src /\ b1 dst = 0
  end.

(** ObstructionLift fires when the observed certificate at dst does not
    satisfy the permitted transport from src under the declared label. *)
Definition obstruction_lift_at
    (lbl : compat_label)
    (src_cert dst_cert : cluster_certificate) : Prop :=
  ~ permitted_transport lbl src_cert dst_cert.

(** Soundness for ObstructionLift:

    If obstruction_lift fires at an edge (r1, r2) with label lbl, then
    no history can match the observations at both r1 and r2 while also
    satisfying the declared permitted transport at that edge. *)
Lemma obstruction_lift_soundness :
  forall (P : bridge_payload) (r1 r2 : region) (lbl : compat_label),
    obstruction_lift_at lbl (observed_cert P r1) (observed_cert P r2) ->
    ~ exists H : global_history,
        history_matches_observations P H /\
        permitted_transport lbl (H r1) (H r2).
Proof.
  (* If the observed certs at r1, r2 violate permitted_transport under lbl,
     then any H matching those observations also violates it. *)
  intros P r1 r2 lbl Hol [H [Hmatch Hperm]].
  apply Hol.
  (* H(r1) = observed(r1) and H(r2) = observed(r2) by Hmatch. *)
  rewrite <- (Hmatch r1), <- (Hmatch r2).
  exact Hperm.
Qed.

(** NOTE: The above lemma has a simplified antecedent.  The full version
    requires a payloaded transition graph and an explicit edge (r1, r2)
    with label lbl.  This is left for the next iteration, which should:
      1. Add adjacent_with_label : region -> region -> compat_label -> Prop
         to bridge_payload.
      2. State the lemma over that labelled graph.
      3. Combine with global_history_obstruction_soundness to obtain the
         full biconditional as the completeness milestone. *)


(* ==========================================================================
   §6  Completeness and the biconditional milestone (admitted)
   ========================================================================== *)

(** Audit coverage axiom: the audit's mismatch detection is exhaustive.
    
    Formally: if no globally coherent history explains the observations,
    then the audit must report an obstruction.
    
    This is the missing coverage assumption that connects the OCaml
    compute_mismatches implementation to the formal bridge semantics. *)
Axiom audit_coverage :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    (~ exists H : global_history, global_history_realises_payload P H) ->
    audit_obstructed P.

(** The stronger direction: if no coherent global history exists, the
    audit must return SS_Obstructed.

    This is the completeness half.  It requires explicit coverage: the
    audit must detect every way that global coherence can fail. *)
Theorem global_history_obstruction_completeness :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    (~ exists H : global_history, global_history_realises_payload P H) ->
    audit_obstructed P.
Proof.
  intros P Hwf Hno_history.
  exact (audit_coverage P Hwf Hno_history).
Qed.

(** The capstone theorem: equivalence.

    audit_obstructed P <-> ¬ ∃ H, global_history_realises_payload P H

    This holds when both soundness and completeness are proved.
    Soundness is proved above.  Completeness is admitted. *)
Theorem global_history_obstruction_iff :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    (audit_obstructed P <->
     ~ exists H : global_history,
         global_history_realises_payload P H).
Proof.
  intros P Hwf. split.
  - exact (global_history_obstruction_soundness P Hwf).
  - exact (global_history_obstruction_completeness P Hwf).
Qed.


(* ==========================================================================
   §7  Cluster-specific specialisation for the present demo
   ========================================================================== *)

(** For the BEEP scenA_base demo, the well-formedness conditions can be
    discharged concretely.

    The specialised theorem for the cluster bridge corresponds to
    cluster_bridge_obstruction_soundness in the architecture document.

    Its proof is the main soundness theorem instantiated to the cluster
    certificate type and the specific scenario structure, with the
    reachability condition discharged by the explicit phase ordering. *)

End BridgeKernel.


(* ==========================================================================
   §7  Concrete instantiation for scenA_base
   ==========================================================================

   The abstract kernel is now closed.  This section instantiates it for
   the concrete BEEP scenA_base scenario.

   Region type: three structurally observed regions only.
   phase3 is present in the timeline but has no structural observation
   distinct from phase2, so it is excluded from the kernel payload.
   This matches the structural_observations array in the bridge payload JSON.

   After this section, cluster_scenA_obstruction_soundness is proved
   with no Axioms and no Admitted — only the definitions below and the
   abstract kernel theorems from §3–§4. *)


(** The three structurally distinct regions of scenA_base. *)
Inductive scenA_region : Type :=
  | warmup
  | phase1
  | phase2.

(** Certificate assignment from the bridge payload JSON.
    Corresponds directly to structural_observations in beep_loopaudit_payload.json:
      warmup : b0=1  b1=1  (cluster_nominal)
      phase1 : b0=1  b1=0  (cluster_link_fault)
      phase2 : b0=2  b1=0  (cluster_partition) *)
Definition scenA_cert (r : scenA_region) : cluster_certificate :=
  match r with
  | warmup => mk_cert 1 1
  | phase1 => mk_cert 1 0
  | phase2 => mk_cert 2 0
  end.

(** Adjacency relation from derived_transitions in the bridge payload:
      warmup → phase1   (ring_broken)
      phase1 → phase2   (partitioned)
    All other pairs are not adjacent. *)
Definition scenA_adjacent (r1 r2 : scenA_region) : Prop :=
  match r1, r2 with
  | warmup, phase1 => True
  | phase1, phase2 => True
  | _,      _      => False
  end.

(** The concrete bridge payload for scenA_base. *)
Definition scenA_payload : bridge_payload scenA_region :=
  {| baseline_region := warmup;
     observed_cert   := scenA_cert;
     adjacent        := scenA_adjacent |}.

(** Well-formedness proof for scenA_base.
    Three obligations:
      1. b0(warmup) = 1          — by computation.
      2. b1(warmup) = 1          — by computation.
      3. Every fault region (b1=0 or b0>1) reachable from warmup
         — by exhibiting the explicit path through the adjacency graph. *)
Lemma scenA_well_formed :
    bridge_payload_well_formed scenA_region scenA_payload.
Proof.
  constructor.
  - (* wf_b0_baseline: b0(cert warmup) = 1 *)
    reflexivity.
  - (* wf_b1_baseline: b1(cert warmup) = 1 *)
    reflexivity.
  - (* wf_reachable *)
    intros r [Hb1 | Hb0].
    + (* Case: b1(cert r) = 0 — ring has failed at r *)
      destruct r; simpl in Hb1.
      * (* warmup: b1=1 ≠ 0, vacuously discharged *)
        discriminate.
      * (* phase1: b1=0, show warmup →adj phase1 *)
        apply reach_step with (r2 := phase1).
        -- exact I.
        -- apply reach_refl.
      * (* phase2: b1=0, show warmup →adj phase1 →adj phase2 *)
        apply reach_step with (r2 := phase1).
        -- exact I.
        -- apply reach_step with (r2 := phase2).
           ++ exact I.
           ++ apply reach_refl.
    + (* Case: b0(cert r) > 1 — cluster has partitioned at r *)
      destruct r; simpl in Hb0.
      * (* warmup: b0=1, 1 > 1 is false *)
        lia.
      * (* phase1: b0=1, lia *)
        lia.
      * (* phase2: b0=2 > 1, show warmup →* phase2 *)
        apply reach_step with (r2 := phase1).
        -- exact I.
        -- apply reach_step with (r2 := phase2).
           ++ exact I.
           ++ apply reach_refl.
Qed.

(** Obstruction witness for scenA_base.
    phase1 is the witness: baseline has b1=1, phase1 has b1=0. *)
Lemma scenA_obstructed :
    audit_obstructed scenA_region scenA_payload.
Proof.
  exists phase1.
  left.
  unfold ring_loss_at. simpl.
  split.
  - lia.         (* 1 > 0 *)
  - reflexivity. (* 0 = 0 *)
Qed.

(** The concrete obstruction theorem for scenA_base.
    No Axioms.  No Admitted.
    Proved by instantiating the abstract soundness theorem with the
    concrete well-formedness and obstruction witnesses above. *)
Corollary cluster_scenA_obstruction_soundness :
  ~ exists H : global_history scenA_region,
      global_history_realises_payload scenA_region scenA_payload H.
Proof.
  exact (global_history_obstruction_soundness scenA_region scenA_payload
           scenA_well_formed scenA_obstructed).
Qed.


(* ==========================================================================
   §8  Coherent contrast case and label soundness
   ==========================================================================

   Two additions that complete the kernel's certification scope:

   A. Coherent contrast case (scenB)
      The kernel proves not only that scenA is obstructed but that a
      nominally-behaved payload of the same shape admits a coherent history.
      Together, scenA and scenB show the kernel distinguishes the two cases.

   B. Label soundness for scenA transitions
      The compatibility_status labels in the bridge payload are currently
      trusted — they are computed by the Python exporter and written into
      the JSON. This section proves that both labels are consistent with
      the kernel's permitted_transport semantics, formally closing that link.
      The consequence: ObstructionLift does not fire for either scenA
      transition; the obstruction is ring_loss + partition only.          *)


(* --------------------------------------------------------------------------
   §8A  Coherent contrast case
   -------------------------------------------------------------------------- *)

(** The scenB payload over the same region type: all certificates nominal.
    Same adjacency graph as scenA; only the certificate assignment differs.
    Corresponds to bridge/fixtures/scenB_coherent_payload.json. *)
Definition scenB_payload : bridge_payload scenA_region :=
  {| baseline_region := warmup;
     observed_cert   := fun _ => mk_cert 1 1;
     adjacent        := scenA_adjacent |}.

(** Positive realisation theorem for scenB.
    The constant history H := fun _ => mk_cert 1 1 is a valid global
    history for scenB_payload:
      - it matches all observations (every region has cert (1,1))
      - it is globally coherent (baseline_transport is reflexive on (1,1)) *)
Theorem cluster_scenB_coherent_realisation :
  exists H : global_history scenA_region,
    global_history_realises_payload scenA_region scenB_payload H.
Proof.
  exists (fun _ => mk_cert 1 1).
  split.
  - (* history_matches_observations: H r = observed_cert scenB_payload r *)
    intro r. reflexivity.
  - (* globally_coherent: every adjacent pair satisfies baseline_transport *)
    intros r1 r2 _.
    unfold baseline_transport. simpl. auto.
Qed.

(** Direct contrast pair.
    The kernel certifies both directions for the same region structure:
      scenA_base  →  no coherent history exists          (obstruction)
      scenB       →  a coherent history exists           (realisation)
    The difference is entirely in the certificate assignment, not the topology. *)
Corollary scenA_scenB_contrast :
  (~ exists H : global_history scenA_region,
       global_history_realises_payload scenA_region scenA_payload H)
  /\
  (exists H : global_history scenA_region,
       global_history_realises_payload scenA_region scenB_payload H).
Proof.
  exact (conj cluster_scenA_obstruction_soundness
              cluster_scenB_coherent_realisation).
Qed.


(* --------------------------------------------------------------------------
   §8B  Label soundness for scenA transitions
   --------------------------------------------------------------------------

   The bridge payload's derived_transitions carry compatibility_status labels
   computed by the Python exporter (_compatibility_status in
   export_loopaudit_payload.py). Those labels are currently trusted: the
   kernel does not verify that the Python computation was correct.

   This section proves the two scenA labels are consistent with the kernel's
   permitted_transport semantics. It is a formal certificate that the bridge
   exporter's output is correct for this scenario, narrowing the trusted
   boundary by one explicit link.

   Semantic meaning of "label is sound":
     permitted_transport lbl src dst holds
     i.e. the declared label correctly describes the src→dst transition
     i.e. obstruction_lift_at lbl src dst is FALSE
   -------------------------------------------------------------------------- *)

(** The warmup→phase1 transition is correctly labelled lbl_ring_broken.
    Kernel check: b0 is unchanged (1=1) and b1 drops to 0. *)
Lemma scenA_warmup_phase1_label_sound :
  permitted_transport lbl_ring_broken
    (scenA_cert warmup) (scenA_cert phase1).
Proof.
  unfold permitted_transport. simpl.
  split; reflexivity.
Qed.

(** The phase1→phase2 transition is correctly labelled lbl_partitioned.
    Kernel check: b0 strictly increases (2>1) and b1 is unchanged (0=0). *)
Lemma scenA_phase1_phase2_label_sound :
  permitted_transport lbl_partitioned
    (scenA_cert phase1) (scenA_cert phase2).
Proof.
  unfold permitted_transport. simpl.
  split; [lia | reflexivity].
Qed.

(** ObstructionLift does NOT fire for the warmup→phase1 transition.
    The ring loss at phase1 was declared: the label correctly predicted it.
    This obstruction is RingLoss-sourced, not a labelling artefact. *)
Corollary scenA_no_obstruction_lift_warmup_phase1 :
  ~ obstruction_lift_at lbl_ring_broken
      (scenA_cert warmup) (scenA_cert phase1).
Proof.
  unfold obstruction_lift_at.
  intro H. exact (H scenA_warmup_phase1_label_sound).
Qed.

(** ObstructionLift does NOT fire for the phase1→phase2 transition.
    The partition at phase2 was declared: the label correctly predicted it.
    This obstruction is Partition-sourced, not a labelling artefact. *)
Corollary scenA_no_obstruction_lift_phase1_phase2 :
  ~ obstruction_lift_at lbl_partitioned
      (scenA_cert phase1) (scenA_cert phase2).
Proof.
  unfold obstruction_lift_at.
  intro H. exact (H scenA_phase1_phase2_label_sound).
Qed.

(** Combined label soundness certificate for scenA_base.
    Both transition labels in the bridge payload are kernel-verified:
    neither transition carries an undeclared or mislabelled degradation.
    The two obstruction sources (ring_loss and partition) are the only
    ones active in this scenario. *)
Lemma scenA_all_labels_sound :
  permitted_transport lbl_ring_broken
    (scenA_cert warmup) (scenA_cert phase1)
  /\
  permitted_transport lbl_partitioned
    (scenA_cert phase1) (scenA_cert phase2).
Proof.
  exact (conj scenA_warmup_phase1_label_sound
              scenA_phase1_phase2_label_sound).
Qed.


(*
  ==========================================================================
  PROOF STATUS SUMMARY
  ==========================================================================

  PROVED — kernel-backed, no Axioms, no Admitted:
    coherent_preserves_along_path              §3
    ring_loss_soundness                        §4
    partition_soundness                        §4
    global_history_obstruction_soundness       §4  ← THRESHOLD THEOREM
    obstruction_lift_soundness                 §5
    scenA_well_formed                          §7
    scenA_obstructed                           §7
    cluster_scenA_obstruction_soundness        §7  ← OBSTRUCTION CERTIFIED
    cluster_scenB_coherent_realisation         §8A ← COHERENCE CERTIFIED
    scenA_scenB_contrast                       §8A ← KERNEL DISTINGUISHES BOTH
    scenA_warmup_phase1_label_sound            §8B ← LABEL LINK CLOSED
    scenA_phase1_phase2_label_sound            §8B ← LABEL LINK CLOSED
    scenA_no_obstruction_lift_warmup_phase1    §8B
    scenA_no_obstruction_lift_phase1_phase2    §8B
    scenA_all_labels_sound                     §8B

  ADMITTED — require further work:
    global_history_obstruction_completeness    §6  (audit coverage model)
    global_history_obstruction_iff             §6  (follows from completeness)

  TRUSTED BOUNDARY STATUS:
    Closed (kernel-proved):
      certificate types and their semantics
      baseline transport and coherence
      reachability and path lemma
      ring_loss and partition obstruction theorems
      scenA concrete well-formedness and obstruction witness
      scenB concrete coherent realisation (contrast)
      scenA transition label correctness (both edges)

    Still trusted (not yet kernel-proved):
      audit coverage: compute_mismatches visits all reachable regions
      completeness: no coherent history ↔ audit_obstructed
      scenA adjacency is the unique correct graph for the JSON topology

  ==========================================================================
*)
