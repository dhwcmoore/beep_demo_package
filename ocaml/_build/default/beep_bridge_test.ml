(** beep_bridge_test.ml

    Regression suite for the BEEP bridge audit kernel.

    Tests the four scenario fixtures through the full OCaml pipeline:
      Beep_bridge_ingest → Beep_bridge_mapping → run_audit

    Expected results per scenario:

      scenA_base              SS_Obstructed  1 triple  modes=[ring_loss,partition]  rup=2
      scenB_coherent          SS_Coherent    0 triples  modes=[]                   rup=0
      scenC_ring_loss_only    SS_Obstructed  1 triple  modes=[ring_loss]            rup=1
      scenD_partition_no_rup  SS_Obstructed  1 triple  modes=[ring_loss,partition]  rup=0
                                             degenerate (B=C)

    Run with:
      dune exec ./beep_bridge_test.exe -- <fixtures_dir> <scenA_payload>
    or via bridge/run_regression.sh. *)

open Beep_bridge_types


(* -------------------------------------------------------------------------
   Audit kernel (mirrored from run_beep_bridge_audit.ml)
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
   Assertion helpers
   ------------------------------------------------------------------------- *)

let pass_count = ref 0
let fail_count = ref 0

let ok (name : string) (cond : bool) (detail : string) =
  if cond then begin
    incr pass_count;
    Printf.printf "  PASS  %s\n" name
  end else begin
    incr fail_count;
    Printf.printf "  FAIL  %s\n" name;
    if detail <> "" then
      Printf.printf "        %s\n" detail
  end

let section (title : string) =
  Printf.printf "\n── %s\n" title


(* -------------------------------------------------------------------------
   Scenario assertions
   ------------------------------------------------------------------------- *)

let assert_coherent (result : audit_result) (label : string) =
  ok (label ^ ": SS_Coherent")
    (result.status = SS_Coherent)
    (match result.status with
     | SS_Coherent -> ""
     | SS_Obstructed ts ->
       Printf.sprintf "got SS_Obstructed with %d triple(s)" (List.length ts));
  ok (label ^ ": 0 mismatches")
    (result.mismatches = [])
    (Printf.sprintf "got %d mismatch(es)" (List.length result.mismatches));
  ok (label ^ ": 0 rupture witnesses")
    (result.rupture_witness_count = 0)
    (Printf.sprintf "got %d" result.rupture_witness_count)


let assert_obstructed
    ~(label : string)
    ~(expected_triple_count : int)
    ~(expected_modes : string list)
    ~(expected_rup : int)
    ~(degenerate : bool)
    (result : audit_result) =
  let triples =
    match result.status with
    | SS_Coherent ->
      ok (label ^ ": SS_Obstructed") false "got SS_Coherent";
      []
    | SS_Obstructed ts ->
      ok (label ^ ": SS_Obstructed") true "";
      ts
  in
  ok (label ^ Printf.sprintf ": %d triple(s)" expected_triple_count)
    (List.length triples = expected_triple_count)
    (Printf.sprintf "got %d" (List.length triples));

  (match triples with
   | [] -> ()
   | triple :: _ ->
     (* Check failure modes (order-independent) *)
     let got_modes = List.sort compare triple.failure_modes in
     let exp_modes  = List.sort compare expected_modes in
     ok (label ^ ": failure_modes match")
       (got_modes = exp_modes)
       (Printf.sprintf "expected [%s] got [%s]"
          (String.concat "," exp_modes)
          (String.concat "," got_modes));

     (* Degenerate triple: B = C *)
     if degenerate then
       ok (label ^ ": degenerate triple (B=C)")
         (triple.region_b = triple.region_c)
         (Printf.sprintf "region_b=%s region_c=%s"
            triple.region_b triple.region_c)
  );

  ok (label ^ Printf.sprintf ": %d rupture witness(es)" expected_rup)
    (result.rupture_witness_count = expected_rup)
    (Printf.sprintf "got %d" result.rupture_witness_count);

  (* Mismatches must always be present if obstructed *)
  ok (label ^ ": mismatches non-empty")
    (result.mismatches <> [])
    ""


(* -------------------------------------------------------------------------
   Additional structural checks
   ------------------------------------------------------------------------- *)

let check_triple_regions
    ~(label : string)
    ~(expected_a : string)
    ~(expected_b : string)
    ~(expected_c : string)
    (result : audit_result) =
  match result.status with
  | SS_Coherent -> ()
  | SS_Obstructed (t :: _) ->
    ok (label ^ ": triple region_a = " ^ expected_a)
      (t.region_a = expected_a)
      (Printf.sprintf "got %s" t.region_a);
    ok (label ^ ": triple region_b = " ^ expected_b)
      (t.region_b = expected_b)
      (Printf.sprintf "got %s" t.region_b);
    ok (label ^ ": triple region_c = " ^ expected_c)
      (t.region_c = expected_c)
      (Printf.sprintf "got %s" t.region_c)
  | SS_Obstructed [] -> ()


(* -------------------------------------------------------------------------
   Test runner
   ------------------------------------------------------------------------- *)

let run_scenario_tests (fixtures_dir : string) (scena_path : string option) =

  let load path =
    try Beep_bridge_ingest.read path
    with Failure msg ->
      Printf.eprintf "load error (%s): %s\n" path msg;
      exit 1
  in

  (* scenA: ring_loss + partition, 2 rupture witnesses *)
  (match scena_path with
   | None ->
     Printf.printf "\n── scenA skipped (path not provided)\n"
   | Some p ->
     section "scenA_base — ring_loss + partition, 2 rupture witnesses";
     let result = run_audit (load p) in
     assert_obstructed
       ~label:"scenA"
       ~expected_triple_count:1
       ~expected_modes:["ring_loss"; "partition"]
       ~expected_rup:2
       ~degenerate:false
       result;
     check_triple_regions
       ~label:"scenA"
       ~expected_a:"warmup"
       ~expected_b:"phase1"
       ~expected_c:"phase2"
       result
  );

  (* scenB: all coherent, no structural change *)
  section "scenB_coherent — nominal run, expected SS_Coherent";
  let result_b = run_audit (load (fixtures_dir ^ "/scenB_coherent_payload.json")) in
  assert_coherent result_b "scenB";

  (* scenC: ring loss only — no partition *)
  section "scenC_ring_loss_only — ring broken, connectivity intact";
  let result_c = run_audit (load (fixtures_dir ^ "/scenC_ring_loss_only_payload.json")) in
  assert_obstructed
    ~label:"scenC"
    ~expected_triple_count:1
    ~expected_modes:["ring_loss"]
    ~expected_rup:1
    ~degenerate:false
    result_c;
  check_triple_regions
    ~label:"scenC"
    ~expected_a:"warmup"
    ~expected_b:"phase1"
    ~expected_c:"phase2"
    result_c;
  ok "scenC: partition NOT in failure modes"
    (match result_c.status with
     | SS_Obstructed (t :: _) -> not (List.mem "partition" t.failure_modes)
     | _ -> false)
    "";

  (* scenD: direct partition without rupture precursor *)
  section "scenD_partition_no_rupture — partition with no rupture support";
  let result_d = run_audit (load (fixtures_dir ^ "/scenD_partition_no_rupture_payload.json")) in
  assert_obstructed
    ~label:"scenD"
    ~expected_triple_count:1
    ~expected_modes:["ring_loss"; "partition"]
    ~expected_rup:0
    ~degenerate:true
    result_d


(* -------------------------------------------------------------------------
   Entry point
   ------------------------------------------------------------------------- *)

let () =
  Printf.printf "BEEP bridge OCaml regression suite\n";
  Printf.printf "%s\n" (String.make 50 '=');

  let argc = Array.length Sys.argv in
  let fixtures_dir =
    if argc >= 2 then Sys.argv.(1)
    else "bridge/fixtures"
  in
  let scena_path =
    if argc >= 3 then Some Sys.argv.(2)
    else None
  in

  run_scenario_tests fixtures_dir scena_path;

  Printf.printf "\n%s\n" (String.make 50 '=');
  Printf.printf "Results: %d passed, %d failed\n" !pass_count !fail_count;

  if !fail_count > 0 then exit 1
  else begin
    Printf.printf "All tests passed.\n";
    exit 0
  end
