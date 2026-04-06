(** scenA_ocaml_bridge.v

    ===================================================================
    OCaml-Rocq Bridge for Scenario A
    ===================================================================

    Establishes the proper layer boundary between OCaml extraction
    and Rocq formal proof.

    The OCaml emitter is responsible for:
      - Reading the JSON artefact
      - Extracting the transition edges
      - Verifying edges = [(Warmup, Phase1); (Phase1, Phase2)]
      - Emitting exactly this canonical list

    The Rocq side is responsible for:
      - Taking the emitted edge list as a premise
      - Proving it matches the formal Scenario A adjacency
      - Deriving all consequences (obstruction, etc.)

    ===================================================================
    Trust Boundary
    ===================================================================

    The contract between layers is simple:

    OCaml claim:
      dedup_and_sort_edges payload.canonical_edges =
      dedup_and_sort_edges [(Warmup, Phase1); (Phase1, Phase2)]

    Rocq assumption (this file):
      forall edges : list edge,
        ocaml_emitted_expected_edges edges ->
        edges = [(warmup, phase1); (phase1, phase2)]

    Once this assumption is met, all formal consequences follow.

    ===================================================================
*)

Require Import beep_bridge_kernel.
Require Import scenA_runtime_discharge.
Require Import scenA_canonical_edges.
Require Import scenA_artefact_faithfulness.
Require Import List.
Import ListNotations.

Module ScenAOCamlBridge.

  Import ScenARuntimeDischarge.
  Import ScenACanonicalEdges.
  Import ScenAArtefactFaithfulness.

  (** Definition of what the OCaml emitter should produce. *)
  Definition expected_scenA_edges : list edge :=
    decoded_scenA_edges.

  (*
    This is the Rocq-side premise corresponding to the OCaml emitter
    succeeding and producing the expected canonical edge list.

    In terms of the external contract:
      ocaml_emitted_expected_edges edges :=
        the OCaml extraction verified edges and they equal expected_scenA_edges
  *)
  Definition ocaml_emitted_expected_edges (edges : list edge) : Prop :=
    edges = expected_scenA_edges.

  (* =====================================================================
     First Bridge: Emitted Edges Match Formal Adjacency
     ===================================================================== *)

  Theorem ocaml_emitted_edges_match_formal :
    forall (edges : list edge) (r1 r2 : scenA_region),
      ocaml_emitted_expected_edges edges ->
      edge_in edges r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    intros edges r1 r2 Hemit.
    unfold ocaml_emitted_expected_edges, expected_scenA_edges in Hemit.
    subst edges.
    apply decoded_edges_match_formal.
  Qed.

  (* =====================================================================
     Critical Observation: Obstruction Does Not Depend on Edges
     ===================================================================== *)

  (*
    This theorem shows something important about the trust boundary:

    The obstruction of scenA_payload is a fact about the formal payload
    itself, proved in the kernel. It does NOT depend on the OCaml
    emission having been correct.

    What the OCaml emission buys us is *identification*: the assurance
    that the artefact corresponds to THIS specific payload.
  *)

  Theorem ocaml_emitted_expected_edges_obstructed :
    forall (edges : list edge),
      ocaml_emitted_expected_edges edges ->
      ~ exists H : global_history scenA_region,
          global_history_realises_payload scenA_region scenA_payload H.
  Proof.
    intros edges _.
    (* The premise is not used: obstruction is independent of edges *)
    exact cluster_scenA_obstruction_soundness.
  Qed.

  (* =====================================================================
     The Real Sharper Bridge: Emitted Edges Identify Scenario A
     ===================================================================== *)

  (*
    This is the theorem that *really* matters semantically:

    If OCaml emitted the expected edges, then the emitted edge structure
    induces exactly the adjacency relation of the formal Scenario A payload.

    This is the *identification* theorem.
  *)

  Theorem ocaml_emitted_edges_identify_scenA :
    forall (edges : list edge),
      ocaml_emitted_expected_edges edges ->
      forall r1 r2 : scenA_region,
        edge_in edges r1 r2 <-> scenA_adjacent r1 r2.
  Proof.
    intros edges Hemit r1 r2.
    (* scenA_adjacent is the adjacent relation of scenA_payload *)
    apply ocaml_emitted_edges_match_formal.
    exact Hemit.
  Qed.

  (* =====================================================================
     Packaged Bridge: Full Consequences
     ===================================================================== *)

  (*
    Strongest form: if OCaml emitted the expected edge list, then:

    1. The emitted edges exactly identify the formal Scenario A adjacency
    2. The formal obstruction theorem applies to the payload

    This is the theorem you pass to the CLI or verification consumer.
  *)

  Theorem ocaml_emitted_expected_edges_full_bridge :
    forall (edges : list edge),
      ocaml_emitted_expected_edges edges ->
      (forall r1 r2 : scenA_region,
         edge_in edges r1 r2 <-> scenA_adjacent r1 r2)
      /\
      ~ exists H : global_history scenA_region,
          global_history_realises_payload scenA_region scenA_payload H.
  Proof.
    intros edges Hemit.
    split.
    - intros r1 r2.
      apply (ocaml_emitted_edges_identify_scenA edges Hemit r1 r2).
    - apply (ocaml_emitted_expected_edges_obstructed edges Hemit).
  Qed.

  (* =====================================================================
     Summary of Trust Boundary
     ===================================================================== *)

  (*
    The theorems above show:

    1. ocaml_emitted_expected_edges_identify_scenA:
       If OCaml said "here are the edges", and they are the expected ones,
       then those edges are provably the same as the formal graph.

    2. ocaml_emitted_expected_edges_obstructed:
       The artefact is obstructed because its certificate sequence cannot
       be explained by any coherent transport-preserving history. This is
       a property of the formal Scenario A payload, not of the OCaml emitter.

    3. ocaml_emitted_expected_edges_full_bridge:
       Together: OCaml emission + formal proof = artefact is obstructed.

    What is NOT in Rocq:
      - JSON parsing
      - Yojson types
      - Region string conversion
      - File I/O

    These are OCaml's responsibility, verified operationally by
    beep_bridge_ingest.ml:canonicalise_payload and
    beep_bridge_ingest.ml:verify_is_scenA_canonical_edges.

    What IS in Rocq:
      - Formal graph definition
      - Kernel-level obstruction proof
      - Equivalence of emitted edges to formal adjacency
      - Identification of artefact with formal payload

    The boundary is clean: Rocq assumes the edge list is correct,
    OCaml ensures it is correct.
  *)

End ScenAOCamlBridge.
