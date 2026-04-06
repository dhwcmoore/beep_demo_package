(** run_beep_bridge_audit.ml

    Top-level runner for the BEEP → LoopAudit bridge audit.

    Pipeline:
      beep_loopaudit_payload.json
        → Beep_bridge_ingest.read
        → Beep_bridge_mapping.to_regional_model
        → audit (mismatch check + triple construction)
        → obstruction_report.json

    The obstruction report is the only output.  It contains no risk scores,
    no HTML, and no fusion weights.  It is the auditable structural record.

    Usage:
      ./run_beep_bridge_audit <payload.json> <report.json> *)

open Beep_bridge_types


(* -------------------------------------------------------------------------
   Audit kernel
   ------------------------------------------------------------------------- *)

let run_audit (payload : bridge_payload) : audit_result =
  let (mismatches, triples, rup_count) =
    Beep_bridge_mapping.to_regional_model payload
  in
  let status =
    if triples = [] then SS_Coherent
    else SS_Obstructed triples
  in
  {
    scenario_id           = payload.scenario_id;
    status;
    mismatches;
    rupture_witness_count = rup_count;
  }


(* -------------------------------------------------------------------------
   JSON emission helpers
   ------------------------------------------------------------------------- *)

let json_string s = `String s
let json_int n    = `Int n
let json_list xs  = `List xs
let json_obj kvs  = `Assoc kvs
let json_null     = `Null

let emit_cert (c : cluster_certificate) =
  json_obj [
    "b0",        json_int c.b0;
    "b1",        json_int c.b1;
    "advisories", json_list (List.map json_string c.advisories);
  ]

let emit_theorem_family = function
  | RingLoss        -> json_string "ring_loss"
  | Partition       -> json_string "partition"
  | ObstructionLift -> json_string "obstruction_lift"

let emit_mismatch (m : certificate_mismatch) =
  json_obj [
    "src_region",     json_string m.src_region;
    "dst_region",     json_string m.dst_region;
    "expected_cert",  emit_cert m.expected_cert;
    "observed_cert",  emit_cert m.observed_cert;
    "theorems_fired", json_list (List.map emit_theorem_family m.theorems_fired);
  ]

let emit_triple (t : obstruction_triple) =
  json_obj [
    "triple",        json_list (List.map json_string [t.region_a; t.region_b; t.region_c]);
    "baseline_cert", emit_cert t.baseline_cert;
    "observed_b",    emit_cert t.observed_b;
    "observed_c",    emit_cert t.observed_c;
    "failure_modes", json_list (List.map json_string t.failure_modes);
  ]

let emit_status = function
  | SS_Coherent ->
    json_obj [
      "verdict",  json_string "SS_Coherent";
      "triples",  json_list [];
    ]
  | SS_Obstructed triples ->
    json_obj [
      "verdict",  json_string "SS_Obstructed";
      "triples",  json_list (List.map emit_triple triples);
    ]

let emit_result (r : audit_result) =
  json_obj [
    "schema_version",         json_string "beep.loopaudit.obstruction.v1";
    "scenario_id",            json_string r.scenario_id;
    "status",                 emit_status r.status;
    "mismatches",             json_list (List.map emit_mismatch r.mismatches);
    "rupture_witness_count",  json_int r.rupture_witness_count;
  ]


(* -------------------------------------------------------------------------
   Summary printer
   ------------------------------------------------------------------------- *)

let print_summary (result : audit_result) =
  Printf.printf "\n=== BEEP LoopAudit Bridge — Obstruction Report ===\n";
  Printf.printf "scenario : %s\n" result.scenario_id;
  (match result.status with
   | SS_Coherent ->
     Printf.printf "verdict  : SS_Coherent\n";
     Printf.printf "           No structural obstruction detected.\n";
   | SS_Obstructed triples ->
     Printf.printf "verdict  : SS_Obstructed\n";
     Printf.printf "           %d obstruction triple(s) found.\n" (List.length triples);
     List.iter (fun t ->
       Printf.printf "\n  Triple: (%s, %s, %s)\n" t.region_a t.region_b t.region_c;
       Printf.printf "    baseline  : b0=%d  b1=%d\n"
         t.baseline_cert.b0 t.baseline_cert.b1;
       Printf.printf "    observed_b: b0=%d  b1=%d\n"
         t.observed_b.b0 t.observed_b.b1;
       Printf.printf "    observed_c: b0=%d  b1=%d\n"
         t.observed_c.b0 t.observed_c.b1;
       Printf.printf "    failures  : [%s]\n"
         (String.concat ", " t.failure_modes);
     ) triples);
  Printf.printf "\nrupture witnesses : %d\n" result.rupture_witness_count;
  Printf.printf "mismatches        : %d\n" (List.length result.mismatches);
  Printf.printf "=================================================\n\n"


(* -------------------------------------------------------------------------
   Entry point
   ------------------------------------------------------------------------- *)

let () =
  let args = Sys.argv in
  if Array.length args < 3 then begin
    Printf.eprintf "usage: %s <payload.json> <report.json>\n" args.(0);
    exit 1
  end;

  let payload_path = args.(1) in
  let report_path  = args.(2) in

  (* 1. Ingest *)
  let payload =
    try Beep_bridge_ingest.read payload_path
    with Failure msg ->
      Printf.eprintf "ingest error: %s\n" msg;
      exit 1
  in

  (* 2. Audit *)
  let result = run_audit payload in

  (* 3. Print summary to stdout *)
  print_summary result;

  (* 4. Emit obstruction report *)
  let report_json = emit_result result in
  let out = open_out report_path in
  Yojson.Basic.pretty_to_channel out report_json;
  output_char out '\n';
  close_out out;

  Printf.printf "obstruction report written → %s\n" report_path;

  (* Exit non-zero if obstructed, so CI pipelines can detect it *)
  match result.status with
  | SS_Coherent      -> exit 0
  | SS_Obstructed _  -> exit 2
