Require Export beep_bridge_kernel.

Section AuditCoverageContract.

Variable region : Type.
Variable P : bridge_payload region.

Record audit_coverage_contract (P : bridge_payload region) : Prop := {
  audit_region_checked : region -> Prop;
  audit_edge_checked : region -> region -> Prop;
  audit_reported_ring_loss : region -> Prop;
  audit_reported_partition : region -> Prop;

  acc_all_regions_checked :
    forall r,
      reachable P (baseline_region P) r ->
      audit_region_checked r;

  acc_all_edges_checked :
    forall r1 r2,
      adjacent P r1 r2 ->
      audit_edge_checked r1 r2;

  acc_ring_loss_detection_complete :
    forall r,
      ring_loss_at P r ->
      audit_reported_ring_loss r;

  acc_partition_detection_complete :
    forall r,
      partition_at P r ->
      audit_reported_partition r;

  acc_reported_ring_loss_implies_actual :
    forall r,
      audit_reported_ring_loss r ->
      ring_loss_at P r;

  acc_reported_partition_implies_actual :
    forall r,
      audit_reported_partition r ->
      partition_at P r;

  acc_semantic_coverage :
    (~ exists H : global_history, global_history_realises_payload P H) ->
    exists r, audit_reported_ring_loss r \/ audit_reported_partition r;
}.

Theorem audit_coverage_from_contract :
  forall (P : bridge_payload),
    bridge_payload_well_formed P ->
    audit_coverage_contract P ->
    (~ exists H : global_history, global_history_realises_payload P H) ->
    audit_obstructed P.
Proof.
  intros P Hwf Hcontract Hno_history.
  destruct Hcontract as [region_checked edge_checked ring_report part_report
                         ring_complete part_complete
                         ring_sound part_sound semantic].
  destruct (semantic Hno_history) as [r | r]; [| destruct r].
  - left. eapply ring_sound; eassumption.
  - right. eapply part_sound; eassumption.
Qed.

End AuditCoverageContract.
