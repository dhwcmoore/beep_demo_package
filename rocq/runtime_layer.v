Require Import beep_bridge_kernel.

(*
  This file introduces the runtime layer.

  Right now this is abstract.
  Later it will be connected to JSON / OCaml extraction.
*)

Module RuntimeLayer.

  (*
    A runtime graph is some structure extracted from data.
    Keep it abstract for now.
  *)
  Parameter runtime_graph : Type.

  (*
    The concrete Scenario A runtime instance.
    This will eventually come from JSON decoding.
  *)
  Parameter scenA_runtime : runtime_graph.

  (*
    Runtime adjacency relation.
    This is what your actual system will compute.
  *)
  Parameter runtime_adjacent :
    runtime_graph -> scenA_region -> scenA_region -> Prop.

End RuntimeLayer.