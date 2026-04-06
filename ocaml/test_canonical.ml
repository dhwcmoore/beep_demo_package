open Beep_bridge_ingest

let test_canonical_edges () =
  (* Create a simple test payload *)
  let payload : Beep_bridge_types.bridge_payload = {
    schema_version = "beep.loopaudit.bridge.v1";
    scenario_id = "scenario_a_base";
    timeline = {
      total_rows = 300;
      regions = [];
    };
    structural_observations = [];
    rupture_observations = [];
    derived_transitions = [
      {
        src = "warmup";
        dst = "phase1";
        delta_b0 = (0, 1);
        delta_b1 = (-1, 0);
        compatibility_status = RingBroken;
      };
      {
        src = "phase1";
        dst = "phase2";
        delta_b0 = (1, 1);
        delta_b1 = (0, 0);
        compatibility_status = Partitioned;
      };
    ];
  } in
  
  match verify_payload_matches_scenA payload with
  | Ok () ->
      Printf.printf "✓ Synthetic payload matches Scenario A canonical edges\n"
  | Error msg ->
      Printf.printf "✗ Synthetic payload verification failed: %s\n" msg

let test_actual_payload () =
  try
    (* Read and decode the actual payload from the output directory *)
    let payload = Beep_bridge_ingest.read "../output/beep_loopaudit_payload.json" in
    match verify_payload_matches_scenA payload with
    | Ok () ->
        Printf.printf "✓ Real payload (output/beep_loopaudit_payload.json) matches Scenario A\n"
    | Error msg ->
        Printf.printf "✗ Real payload verification failed: %s\n" msg
  with e ->
    Printf.printf "✗ Failed to read real payload: %s\n" (Printexc.to_string e)

let test_emit_json () =
  let payload = {
    canonical_edges = [(Warmup, Phase1); (Phase1, Phase2)];
  } in
  let json = emit_canonical_edge_json payload in
  Printf.printf "\nCanonical edge JSON output:\n%s\n" (Yojson.Basic.pretty_to_string json)

let test_edge_mismatch () =
  (* Test with incorrect edges to verify rejection *)
  let bad_payload : Beep_bridge_types.bridge_payload = {
    schema_version = "beep.loopaudit.bridge.v1";
    scenario_id = "bad";
    timeline = { total_rows = 0; regions = [] };
    structural_observations = [];
    rupture_observations = [];
    derived_transitions = [
      {
        src = "warmup";
        dst = "phase2";  (* Wrong: should be phase1 *)
        delta_b0 = (0, 0);
        delta_b1 = (0, 0);
        compatibility_status = RingBroken;
      };
    ];
  } in
  
  Printf.printf "\nTesting edge mismatch detection:\n";
  match verify_payload_matches_scenA bad_payload with
  | Ok () ->
      Printf.printf "✗ Bad payload should have failed verification\n"
  | Error msg ->
      Printf.printf "✓ Correctly rejected bad payload:\n  %s\n" msg

let () =
  Printf.printf "===== Canonical Edge Extraction and Verification Tests =====\n";
  test_canonical_edges ();
  test_actual_payload ();
  test_emit_json ();
  test_edge_mismatch ();
  Printf.printf "\n===== All tests complete =====\n"
