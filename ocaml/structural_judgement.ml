type structural_judgement =
  | NoBreak
  | CycleLoss
  | ConnectivityPartition

let classify ~nominal_b0 ~nominal_b1 ~fault_b0 ~fault_b1 =
  if fault_b0 > nominal_b0 then ConnectivityPartition
  else if fault_b1 < nominal_b1 then CycleLoss
  else NoBreak

let string_of_judgement = function
  | NoBreak -> "SJ_NoBreak"
  | CycleLoss -> "SJ_CycleLoss"
  | ConnectivityPartition -> "SJ_ConnectivityPartition"

let parse_int arg =
  try int_of_string arg
  with Failure _ ->
    prerr_endline ("Invalid integer: " ^ arg);
    exit 1

let main () =
  let usage =
    "Usage: structural_judgement <nominal_b0> <nominal_b1> <fault_b0> <fault_b1>"
  in
  if Array.length Sys.argv <> 5 then (
    prerr_endline usage;
    exit 1
  );
  let nominal_b0 = parse_int Sys.argv.(1) in
  let nominal_b1 = parse_int Sys.argv.(2) in
  let fault_b0 = parse_int Sys.argv.(3) in
  let fault_b1 = parse_int Sys.argv.(4) in
  let judgement = classify ~nominal_b0 ~nominal_b1 ~fault_b0 ~fault_b1 in
  print_endline (string_of_judgement judgement)

let () = main ()
