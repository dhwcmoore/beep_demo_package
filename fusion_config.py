# fusion_config.py
# Scoring constants and thresholds for the Beep Before Bang fusion rule.
#
# Signal meanings:
#
#   rupture_score   — measures temporal instability in sequential data.
#                     Derived from the rupture-engine (PELT algorithm).
#                     peak_rho reflects the magnitude of the largest detected
#                     change-point; event count reflects how many breaks occurred.
#                     A high rupture score means the signal's statistical regime
#                     has shifted sharply — the system is not behaving as before.
#
#   invariant_score — measures structural integrity against a certified baseline.
#                     Derived from the boundary-invariants engine (Betti numbers).
#                     b0 counts connected components; b1 counts independent cycles.
#                     Deviations from the nominal topology trigger advisories.
#                     A high invariant score means the structural contract has
#                     been violated — the system's topology no longer matches
#                     its certified design.
#
# Fusion rationale:
#
#   We weight rupture slightly higher (0.55 vs 0.45) because temporal instability
#   is the earlier signal — it fires as a regime begins to shift, before topology
#   fully breaks. The invariant score is a confirming signal: if both fire together,
#   the system is in active structural failure. The 0.55/0.45 split reflects this
#   ordering: instability first, structural break as confirmation.
#
# Thresholds:
#
#   LOW      0.0 – 2.0   Nominal. No intervention required.
#   MEDIUM   2.0 – 4.0   Early warning. Monitor closely.
#   HIGH     4.0 – 7.0   Elevated risk. Prepare mitigation.
#   CRITICAL 7.0 – 10.0  Structural failure in progress. Act now.

# Fusion weights (must sum to 1.0)
RUPTURE_WEIGHT   = 0.55
INVARIANT_WEIGHT = 0.45

# Rupture sub-scoring
RUPTURE_PEAK_MULTIPLIER  = 0.3   # contribution from magnitude of largest change-point
RUPTURE_COUNT_MULTIPLIER = 0.8   # contribution from number of detected change-points
RUPTURE_MAX              = 10.0

# Invariant sub-scoring
INV_SCORE_B1_ZERO        = 3.0   # b1==0: cycle destroyed (ring/loop broken)
INV_SCORE_B0_SPLIT       = 5.0   # b0>1:  network partitioned
INV_SCORE_WARNING        = 1.0   # per WARNING advisory
INV_SCORE_CRITICAL       = 3.0   # per CRITICAL advisory
INV_MAX                  = 10.0

# Risk thresholds
THRESHOLD_CRITICAL = 7.0
THRESHOLD_HIGH     = 4.0
THRESHOLD_MEDIUM   = 2.0
