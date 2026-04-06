(** beep_bridge_types.ml

    Type definitions for the BEEP → LoopAudit bridge.

    These types correspond exactly to the fields in beep.loopaudit.bridge.v1
    and serve as the shared vocabulary between ingestion, mapping, and audit.

    Design constraint: no fusion scores, risk levels, or presentation fields
    appear here. This module sits entirely inside the trusted boundary. *)


(* -------------------------------------------------------------------------
   Region identifiers
   ------------------------------------------------------------------------- *)

type region_id = string

type local_region = {
  region_id   : region_id;
  start_index : int;
  end_index   : int;
  start_ts    : string;
  end_ts      : string;
}


(* -------------------------------------------------------------------------
   Cluster certificates
   A certificate is the structural invariant attached to one region.
   b0 = connected components, b1 = independent ring paths (Betti numbers).
   ------------------------------------------------------------------------- *)

type cluster_certificate = {
  b0        : int;         (* connected components *)
  b1        : int;         (* ring paths *)
  advisories : string list; (* advisory codes emitted for this region *)
}

type local_section = {
  region : region_id;
  system : string;         (* declared system name, e.g. "cluster_nominal" *)
  cert   : cluster_certificate;
}


(* -------------------------------------------------------------------------
   Transitions
   A transition records the before/after delta between two adjacent regions
   and the compatibility label assigned by the bridge exporter.
   ------------------------------------------------------------------------- *)

type compatibility_status =
  | Coherent
  | RingBroken
  | Partitioned
  | RingBrokenAndPartitioned
  | UnknownStatus of string

type transition = {
  src                  : region_id;
  dst                  : region_id;
  delta_b0             : int * int;   (* (from, to) *)
  delta_b1             : int * int;   (* (from, to) *)
  compatibility_status : compatibility_status;
}


(* -------------------------------------------------------------------------
   Rupture observations
   Rupture events are empirical witnesses, not formal proof objects.
   They support — but do not constitute — an obstruction claim.
   ------------------------------------------------------------------------- *)

type rupture_obs = {
  candidate_index : int;
  candidate_ts    : string;
  confirmed_index : int option;
  confirmed_ts    : string option;
  peak_rho        : float;
}


(* -------------------------------------------------------------------------
   Timeline
   ------------------------------------------------------------------------- *)

type timeline = {
  total_rows : int;
  regions    : local_region list;
}


(* -------------------------------------------------------------------------
   Full bridge payload
   This is the complete input model for the LoopAudit bridge audit.
   ------------------------------------------------------------------------- *)

type bridge_payload = {
  schema_version          : string;
  scenario_id             : string;
  timeline                : timeline;
  structural_observations : local_section list;
  rupture_observations    : rupture_obs list;
  derived_transitions     : transition list;
}


(* -------------------------------------------------------------------------
   Audit result types
   ------------------------------------------------------------------------- *)

(** The three theorem families the audit checks. *)
type theorem_family =
  | RingLoss       (** b1 baseline > 0, later b1 = 0: ring returnability lost *)
  | Partition      (** b0 increases: global coherence fails *)
  | ObstructionLift (** transported certificate ≠ observed certificate *)

(** A mismatch between expected-transported and observed certificates. *)
type certificate_mismatch = {
  src_region     : region_id;
  dst_region     : region_id;
  expected_cert  : cluster_certificate;  (* what transport predicts *)
  observed_cert  : cluster_certificate;  (* what the stage actually reports *)
  theorems_fired : theorem_family list;
}

(** A failed-transport triple is a triple of regions (A, B, C) where:
    - A is the baseline (coherent source)
    - B is where the first degradation is observed
    - C is where a further degradation compounds the incompatibility
    This is the primary obstruction witness shape for this bridge. *)
type obstruction_triple = {
  region_a      : region_id;
  region_b      : region_id;
  region_c      : region_id;
  baseline_cert : cluster_certificate;   (* cert at A *)
  observed_b    : cluster_certificate;   (* cert at B *)
  observed_c    : cluster_certificate;   (* cert at C *)
  failure_modes : string list;
}

type audit_status =
  | SS_Coherent
  | SS_Obstructed of obstruction_triple list

type audit_result = {
  scenario_id          : string;
  status               : audit_status;
  mismatches           : certificate_mismatch list;
  rupture_witness_count : int;  (* number of rupture obs supporting the claim *)
}
