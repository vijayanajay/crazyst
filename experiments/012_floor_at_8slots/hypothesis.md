# E012 — the E009 floor at the 8-slot notional: re-measure, then decide

Written BEFORE any run (BRD §12). E009 (ADOPTED 2026-09-26) set
`universe.min_median_turnover_cr: 0.75` from the fill gate's arithmetic at the then-shipped
Rs 250k/slot: a buy refuses when notional > 5% of trailing-20 median turnover, so the
boundary sits at med20 >= 20 × S — 0.5cr at S250k — and E009's floor (boundary × the
measured med20/med3 shrinkage ≈ 1.5×) was derived AT THAT NOTIONAL. E011 (ADOPTED
2026-09-26) moved the shipped portfolio to 8 equal-weight slots: per-slot notional halves
to ~Rs 125k (start capital unchanged, equal weight across free slots), so the gate's
boundary moves to med20 >= 0.25cr. The floor's arithmetic moved underneath it.

**Question:** at the 8-slot notional (S = Rs 125k), is the 0.75cr floor still the right
guard — or does it now exclude reachable, non-garbage names the wider book could trade?

**Mechanism (why the answer might change):** the floor exists to keep picks inside the
fill gate's reachability. At S250k the un-floored universe left 38.8% of pick-months
refused (E009 R1). At S125k E009's own sensitivity row says the un-floored refusal was
29.4% with a BETTER reachability-corrected pick mean (+2.669% vs the floor arm's +2.614%
at S250k) — the thinner tail is less poisonous at smaller order sizes, exactly as the
gate arithmetic implies. E010 adds the cost side: modelled impact scales with S/med20, so
the band between the 0.25cr boundary and the 0.75cr floor costs ~half as much to trade at
S125k. The floor may now be over-tight by construction.

## Arms (fixed before the run)

Measurement universe and machinery are E009's, imported module-to-module so nothing
drifts: baseline chain at floor 0.0 (full profile, E007._build_chain), liq_daily20 built
once (chain-independent), the frozen 2020-02 sample re-verified row-for-row, the member
recompute, top-5% composite_2f pick sets over ALL labeled months (E009's semantics),
reachability = refused iff med20 < 20 × S.

- **Baseline (floor 0.0):** MUST reproduce E009's committed R1_by_slot rows BIT-FOR-BIT
  at all four slot sizes (S125k/S250k/S500k/S1000k) — the zero-drift guard. No comparison
  is valid without it.
- **Arm 0.375:** floor 0.375 (the boundary × the same 1.5× headroom E009 used, at the NEW
  notional: 0.25cr × 1.5) — the arithmetic-consistent floor at 8 slots.
- **Arm 0.5:** floor 0.5 (the OLD 4-slot gate boundary; the loosest candidate that still
  sits strictly above the new boundary).
- **Arm 0.75 (reference):** the shipped floor; its S250k reachability row MUST equal
  E009's committed R2 row (same chain, same code, same data) — second guard.
- Each arm through the REAL pipeline: chain rebuilt at that floor, eligible counts and
  turnover-reason exclusions counted, ICs on the 145-month validation slice, paired t vs
  the baseline arm (P41._paired_t, E009's construction).

## Decision rule (fixed before the run)

Evaluate the MOVING candidates (0.375, 0.5) at the 8-slot notional, each against the
0.75 reference, and ADOPT the LOOSEST floor clearing ALL bars (ties keep the shipped
0.75; if none clears, KEEP 0.75). Bars, mirroring E009's rule set with one tolerance:

1. **Corrected mean holds:** corrected_mean(arm) >= corrected_mean(0.75) − 0.0005
   (5bp/month tolerance — E009's bars had none because its gap was huge; here the arms
   are adjacent and tie-swap noise is real; 5bp ≈ E010's impact-tier noise).
2. **IC holds:** paired t(arm vs baseline) >= −2.0 (E009's bar verbatim).
3. **Gate still fixed:** refused_pct(arm at S125k) <= refused_pct(baseline at S125k) / 3
   (E009's relative bar verbatim, re-based to the same notional).
4. **Boundary coverage (arithmetic):** floor_cr >= 20 × 125000 / 1e7 = 0.25 — the floor
   must still sit at or above the gate's own boundary at the 8-slot notional.

Reported alongside, never load-bearing: per-arm modelled impact at S125k over the arm's
picks (min(1%, 0.10 × S/med20) — the E010 decomposition at the new notional), eligible
counts, exclusion reasons, and the 0.75 arm's S125k row.

**Consequences.** ADOPT 0.5 or 0.375 → config.yaml floor moves with the citation, the
smoke's E009-era pins (3,902 picks / floor-arm IC) are re-pinned to the adopted arm's
chain with the E009-to-E006 retirement precedent, the harness reference run is archived
and re-run (§10.3), BRD §4 amended. KEEP 0.75 → config untouched; the verdict records the
measured over-tightness bound (how much corrected mean the loosest passing candidate
would have added/lost) as the standing answer to "should the floor scale with slots".

**Scope.** No portfolio, engine, or model change; the fill gate and its config keys are
untouched. One lever: `universe.min_median_turnover_cr`, in-memory per arm, restored in a
`finally` (E009's hard-guarantee pattern: the in-memory config never leaks an arm floor;
the shipped-state chain is rebuilt and verified last). Restore guards: the 0.0 chain's
IC equals P4.1b's frozen 0.0681243229 (1e-9) and the R1 rows re-equal E009's — the exact
double restore-guard E009 ran. Expected direction (soft, pre-registered): the corrected
means of 0.375/0.5 sit at or above 0.75's at S125k; if they do not, the floor's reach
argument was about poison, not arithmetic, and it stands.
