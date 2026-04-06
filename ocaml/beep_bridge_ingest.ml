(** beep_bridge_ingest.ml

    JSON decoder for beep.loopaudit.bridge.v1 payloads.

    Reads the canonical bridge JSON produced by export_loopaudit_payload.py
    and constructs the typed {!Beep_bridge_types.bridge_payload} record.

    Only structural fields are decoded. Risk scores and HTML fields are
    absent from the bridge schema and are not decoded here. *)

open Beep_bridge_types


(* -------------------------------------------------------------------------
   Helpers for Yojson member extraction
   ------------------------------------------------------------------------- *)

let member key = function
  | `Assoc kvs ->
    (match List.assoc_opt key kvs with
     | Some v -> v
     | None   -> failwith (Printf.sprintf "beep_bridge_ingest: missing key %S" key))
  | _ -> failwith (Printf.sprintf "beep_bridge_ingest: expected object for key %S" key)

let to_string = function
  | `String s -> s
  | v -> failwith (Printf.sprintf "beep_bridge_ingest: expected string, got %s"
                     (Yojson.Basic.to_string v))

let to_int = function
  | `Int n    -> n
  | `Float f  -> int_of_float f
  | v -> failwith (Printf.sprintf "beep_bridge_ingest: expected int, got %s"
                     (Yojson.Basic.to_string v))

let to_float = function
  | `Float f -> f
  | `Int n   -> float_of_int n
  | v -> failwith (Printf.sprintf "beep_bridge_ingest: expected float, got %s"
                     (Yojson.Basic.to_string v))

let to_list = function
  | `List xs -> xs
  | v -> failwith (Printf.sprintf "beep_bridge_ingest: expected list, got %s"
                     (Yojson.Basic.to_string v))

let to_string_list json =
  List.map to_string (to_list json)

let to_option f = function
  | `Null -> None
  | v     -> Some (f v)


(* -------------------------------------------------------------------------
   Compatibility status decoder
   ------------------------------------------------------------------------- *)

let decode_compatibility_status = function
  | "coherent"                   -> Coherent
  | "ring_broken"                -> RingBroken
  | "partitioned"                -> Partitioned
  | "ring_broken_and_partitioned" -> RingBrokenAndPartitioned
  | s                            -> UnknownStatus s


(* -------------------------------------------------------------------------
   Individual field decoders
   ------------------------------------------------------------------------- *)

let decode_region json : local_region = {
  region_id   = to_string (member "region_id"   json);
  start_index = to_int    (member "start_index" json);
  end_index   = to_int    (member "end_index"   json);
  start_ts    = to_string (member "start_ts"    json);
  end_ts      = to_string (member "end_ts"      json);
}

let decode_timeline json : timeline = {
  total_rows = to_int  (member "total_rows" json);
  regions    = List.map decode_region (to_list (member "regions" json));
}

let decode_structural_obs json : local_section =
  let b0         = to_int    (member "b0"         json) in
  let b1         = to_int    (member "b1"         json) in
  let advisories = to_string_list (member "advisories" json) in
  {
    region = to_string (member "region_id" json);
    system = to_string (member "system"    json);
    cert   = { b0; b1; advisories };
  }

let decode_delta_pair json : int * int =
  match to_list json with
  | [a; b] -> (to_int a, to_int b)
  | _ -> failwith "beep_bridge_ingest: delta pair must have exactly 2 elements"

let decode_transition json : transition =
  let delta   = member "delta" json in
  let delta_b0 = decode_delta_pair (member "b0" delta) in
  let delta_b1 = decode_delta_pair (member "b1" delta) in
  {
    src                  = to_string (member "from_region"          json);
    dst                  = to_string (member "to_region"            json);
    delta_b0;
    delta_b1;
    compatibility_status = decode_compatibility_status
                             (to_string (member "compatibility_status" json));
  }

let decode_rupture_obs json : rupture_obs = {
  candidate_index = to_int               (member "candidate_index" json);
  candidate_ts    = to_string            (member "candidate_ts"    json);
  confirmed_index = to_option to_int     (member "confirmed_index" json);
  confirmed_ts    = to_option to_string  (member "confirmed_ts"    json);
  peak_rho        = to_float             (member "peak_rho"        json);
}


(* -------------------------------------------------------------------------
   Top-level decoder
   ------------------------------------------------------------------------- *)

let decode_payload json : bridge_payload = {
  schema_version          = to_string (member "schema_version" json);
  scenario_id             = to_string (member "scenario_id"    json);
  timeline                = decode_timeline
                              (member "timeline" json);
  structural_observations = List.map decode_structural_obs
                              (to_list (member "structural_observations" json));
  rupture_observations    = List.map decode_rupture_obs
                              (to_list (member "rupture_observations" json));
  derived_transitions     = List.map decode_transition
                              (to_list (member "derived_transitions" json));
}


(* -------------------------------------------------------------------------
   File reader
   ------------------------------------------------------------------------- *)

(** [read path] reads and decodes a bridge payload from [path].
    Raises [Failure] if the file is missing or the JSON is malformed. *)
let read (path : string) : bridge_payload =
  let json = Yojson.Basic.from_file path in
  decode_payload json


(* -------------------------------------------------------------------------
   Canonical edge extraction and verification
   -------------------------------------------------------------------------

   This module establishes the trusted extraction boundary.
   The Rocq kernel-level proof assumes canonical edges [(warmup, phase1);
   (phase1, phase2)] for Scenario A. This code extracts the adjacency
   structure from the raw payload and verifies it matches exactly.

   *)

type region =
  | Warmup
  | Phase1
  | Phase2

type edge = region * region

type canonicalised_payload = {
  canonical_edges : edge list;
}

(** Convert a region string to the typed enum.
    This is the ingestible format from the payload. *)
let region_of_string = function
  | "warmup" -> Some Warmup
  | "phase1" -> Some Phase1
  | "phase2" -> Some Phase2
  | _ -> None

(** String representation of a region. *)
let string_of_region = function
  | Warmup -> "warmup"
  | Phase1 -> "phase1"
  | Phase2 -> "phase2"

(** Compare edges for deduplication and sorting. *)
let edge_compare ((a1, b1) : edge) ((a2, b2) : edge) : int =
  match Stdlib.compare a1 a2 with
  | 0 -> Stdlib.compare b1 b2
  | c -> c

(** Deduplicate and sort edges. *)
let dedup_and_sort_edges (edges : edge list) : edge list =
  List.sort_uniq edge_compare edges

(** The canonical edge set for Scenario A as known to the Rocq kernel. *)
let canonical_scenA_edges : edge list =
  [(Warmup, Phase1); (Phase1, Phase2)]

(** Extract canonical edges from the payload.
    Reads derived_transitions and converts src/dst region_id strings
    to the typed region enum, producing an edge list. *)
let canonicalise_payload (payload : bridge_payload) : (canonicalised_payload, string) result =
  try
    let edges =
      List.filter_map (fun (trans : transition) ->
        match region_of_string trans.src, region_of_string trans.dst with
        | Some src_r, Some dst_r -> Some (src_r, dst_r)
        | _ -> None
      ) payload.derived_transitions
    in
    Ok { canonical_edges = dedup_and_sort_edges edges }
  with e ->
    Error (Printf.sprintf "canonicalise_payload: %s" (Printexc.to_string e))

(** Verify that the canonicalised edges exactly match the Scenario A canonical set.
    This is a hard check: no warnings, no defaults, no silent recovery. *)
let verify_is_scenA_canonical_edges (edges : edge list) : (unit, string) result =
  let got = dedup_and_sort_edges edges in
  let expected = dedup_and_sort_edges canonical_scenA_edges in
  if got = expected then
    Ok ()
  else
    let show_edge (s, d) =
      "(" ^ string_of_region s ^ "," ^ string_of_region d ^ ")"
    in
    let show_edges es =
      "[" ^ String.concat "; " (List.map show_edge es) ^ "]"
    in
    Error
      (Printf.sprintf
        "Canonical edge mismatch. Expected %s but got %s"
        (show_edges expected)
        (show_edges got))

(** Check that a payload's canonicalised edges match Scenario A exactly. *)
let verify_payload_matches_scenA (payload : bridge_payload) : (unit, string) result =
  match canonicalise_payload payload with
  | Error e -> Error e
  | Ok canonicalised ->
      verify_is_scenA_canonical_edges canonicalised.canonical_edges

(** Convert an edge to JSON representation as [src_str, dst_str]. *)
let edge_to_json ((src, dst) : edge) : Yojson.Basic.t =
  `List [`String (string_of_region src); `String (string_of_region dst)]

(** Emit canonical edges as JSON in the form expected by the Rocq kernel.
    Structure: { "canonical_edges": [[src, dst], ...] } *)
let emit_canonical_edge_json (payload : canonicalised_payload) : Yojson.Basic.t =
  `Assoc [
    ("canonical_edges",
     `List (List.map edge_to_json payload.canonical_edges))
  ]
