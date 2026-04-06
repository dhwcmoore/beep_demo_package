(** beep_bridge_mapping.ml

    Transport expectations and mismatch predicates for the BEEP bridge.

    This module defines what it means for a structural certificate to be
    "coherently transported" from one region to the next, and what constitutes
    a mismatch — the raw material for obstruction witnesses.

    Transport semantics (conservative baseline):
      If no declared destructive event is present in the transition, the
      certificate is expected to be preserved verbatim.  If a destructive
      event is declared (ring_broken, partitioned, etc.), transport is
      expected to fail at that site, and the failure is itself auditable.

    The three theorem families checked here correspond directly to:
      A. RingLoss       — b1 baseline > 0, later b1 = 0
      B. Partition      — b0 increases across a transition
      C. ObstructionLift — transported cert ≠ observed cert at destination *)

open Beep_bridge_types


(* -------------------------------------------------------------------------
   Certificate lookup helpers
   ------------------------------------------------------------------------- *)

(** Find the local section for [region_id] in the payload's observation list. *)
let find_section (payload : bridge_payload) (rid : region_id)
    : local_section option =
  List.find_opt (fun s -> s.region = rid) payload.structural_observations


(** Return the first section in the payload (the baseline region). *)
let baseline_section (payload : bridge_payload) : local_section option =
  match payload.structural_observations with
  | []     -> None
  | hd :: _ -> Some hd


(* -------------------------------------------------------------------------
   Transport expectation
   "What certificate would we observe at [dst] if coherence were preserved?"
   ------------------------------------------------------------------------- *)

(** Conservative transport: the expected certificate at [dst] is identical to
    the certificate at [src], unless the declared transition at that edge
    carries a non-coherent compatibility_status (in which case the transport
    is expected to fail and we record the mismatch explicitly).

    This is intentionally conservative: any undeclared degradation is flagged. *)
let expected_transport
    (payload : bridge_payload)
    (src_section : local_section)
    : cluster_certificate =
  (* Find the declared transition leaving src. *)
  let transition_opt =
    List.find_opt
      (fun t -> t.src = src_section.region)
      payload.derived_transitions
  in
  match transition_opt with
  | None ->
    (* No declared transition: conservatively preserve the certificate. *)
    src_section.cert
  | Some t ->
    (match t.compatibility_status with
     | Coherent ->
       (* Declared coherent: transport preserves the certificate. *)
       src_section.cert
     | RingBroken ->
       (* Declared ring-broken: transport predicts b1 = 0, b0 unchanged. *)
       { src_section.cert with b1 = 0; advisories = [] }
     | Partitioned ->
       (* Declared partitioned: transport predicts b0 increases to fst delta_b0. *)
       let (_, b0_after) = t.delta_b0 in
       { src_section.cert with b0 = b0_after; advisories = [] }
     | RingBrokenAndPartitioned ->
       let (_, b0_after) = t.delta_b0 in
       { src_section.cert with b0 = b0_after; b1 = 0; advisories = [] }
     | UnknownStatus _ ->
       (* Unknown: conservatively preserve and let the audit flag it. *)
       src_section.cert)


(* -------------------------------------------------------------------------
   Theorem predicate checks
   ------------------------------------------------------------------------- *)

(** Theorem A: RingLoss.
    Fires when b1 was positive in the baseline and has dropped to 0 at dst. *)
let check_ring_loss
    (baseline : cluster_certificate)
    (observed : cluster_certificate)
    : bool =
  baseline.b1 > 0 && observed.b1 = 0


(** Theorem B: Partition.
    Fires when b0 has strictly increased relative to the baseline. *)
let check_partition
    (baseline : cluster_certificate)
    (observed : cluster_certificate)
    : bool =
  observed.b0 > baseline.b0


(** Theorem C: ObstructionLift.
    Fires when the transported certificate differs from the observed certificate
    on any structural field (b0 or b1).  Advisory differences are informational
    only and do not fire this theorem. *)
let check_obstruction_lift
    (expected : cluster_certificate)
    (observed : cluster_certificate)
    : bool =
  expected.b0 <> observed.b0 || expected.b1 <> observed.b1


(** Collect all theorem families that fire for a given (baseline, expected,
    observed) triple. *)
let theorems_fired
    (baseline : cluster_certificate)
    (expected : cluster_certificate)
    (observed : cluster_certificate)
    : theorem_family list =
  let acc = ref [] in
  if check_ring_loss baseline observed       then acc := RingLoss :: !acc;
  if check_partition baseline observed       then acc := Partition :: !acc;
  if check_obstruction_lift expected observed then acc := ObstructionLift :: !acc;
  List.rev !acc


(* -------------------------------------------------------------------------
   Mismatch detection
   ------------------------------------------------------------------------- *)

(** Compute certificate mismatches across all consecutive structural
    observation pairs.

    For each transition (src → dst):
      1. Look up the observed certificate at dst.
      2. Compute the expected certificate via [expected_transport].
      3. Check all theorem predicates against the baseline.
      4. If any theorem fires, record a [certificate_mismatch].

    The baseline is always the first (warmup) section. *)
let compute_mismatches (payload : bridge_payload) : certificate_mismatch list =
  match payload.structural_observations with
  | [] | [_] -> []
  | baseline_sec :: rest ->
    let baseline_cert = baseline_sec.cert in
    List.filter_map (fun dst_sec ->
      let src_region = baseline_sec.region in  (* conceptual baseline *)
      let _ = src_region in                    (* used below in mismatch *)
      (* For adjacent-pair transport, find the predecessor. *)
      let src_sec_opt =
        (* predecessor = most recent section before dst_sec in observation list *)
        let all = payload.structural_observations in
        let rec find_pred = function
          | [] | [_] -> None
          | a :: ((b :: _) as rest) ->
            if b.region = dst_sec.region then Some a
            else find_pred rest
        in
        find_pred all
      in
      match src_sec_opt with
      | None -> None
      | Some src_sec ->
        let expected = expected_transport payload src_sec in
        let observed = dst_sec.cert in
        let fired    = theorems_fired baseline_cert expected observed in
        if fired = [] then None
        else Some {
          src_region    = src_sec.region;
          dst_region    = dst_sec.region;
          expected_cert = expected;
          observed_cert = observed;
          theorems_fired = fired;
        }
    ) rest


(* -------------------------------------------------------------------------
   Obstruction triple construction
   ------------------------------------------------------------------------- *)

(** Build the canonical obstruction witness triple (A, B, C) from the
    mismatch list.

    For this bridge, the triple spans:
      A = warmup  (coherent baseline)
      B = first region where a mismatch is detected
      C = next region where additional degradation compounds

    If only one mismatch exists, C = B (degenerate triple). *)
let build_obstruction_triples
    (payload : bridge_payload)
    (mismatches : certificate_mismatch list)
    : obstruction_triple list =
  match mismatches with
  | [] -> []
  | _ ->
    let baseline_sec_opt = baseline_section payload in
    (match baseline_sec_opt with
     | None -> []
     | Some baseline_sec ->
       let baseline_cert = baseline_sec.cert in
       (* Group mismatches into triples: each consecutive pair of mismatches
          anchored to the same baseline forms one triple. *)
       let rec build_triples = function
         | [] -> []
         | [single] ->
           (* Degenerate: B = C = the single mismatch destination. *)
           let modes = List.filter_map (fun tf ->
             match tf with
             | RingLoss        -> Some "ring_loss"
             | Partition       -> Some "partition"
             | ObstructionLift -> Some "obstruction_lift"
           ) single.theorems_fired in
           [ { region_a      = baseline_sec.region;
               region_b      = single.dst_region;
               region_c      = single.dst_region;
               baseline_cert;
               observed_b    = single.observed_cert;
               observed_c    = single.observed_cert;
               failure_modes = modes; } ]
         | m1 :: ((m2 :: _) as rest) ->
           let modes =
             let all_fired = List.sort_uniq compare
               (m1.theorems_fired @ m2.theorems_fired) in
             List.filter_map (fun tf ->
               match tf with
               | RingLoss        -> Some "ring_loss"
               | Partition       -> Some "partition"
               | ObstructionLift -> Some "obstruction_lift"
             ) all_fired
           in
           let triple = {
             region_a      = baseline_sec.region;
             region_b      = m1.dst_region;
             region_c      = m2.dst_region;
             baseline_cert;
             observed_b    = m1.observed_cert;
             observed_c    = m2.observed_cert;
             failure_modes = modes;
           } in
           triple :: build_triples rest
       in
       build_triples mismatches)


(* -------------------------------------------------------------------------
   Regional model construction
   (entry point for run_beep_bridge_audit.ml)
   ------------------------------------------------------------------------- *)

(** [to_regional_model payload] converts the bridge payload into the
    intermediate model used by the audit runner.

    Returns (mismatches, obstruction_triples, rupture_count). *)
let to_regional_model (payload : bridge_payload)
    : certificate_mismatch list * obstruction_triple list * int =
  let mismatches  = compute_mismatches payload in
  let triples     = build_obstruction_triples payload mismatches in
  let rup_count   = List.length payload.rupture_observations in
  (mismatches, triples, rup_count)
