# Design freeze — `<name>` (one line summary)

Copy this file to `docs/prospective/<name>/design.md`, fill every field, and get it into
the repo (committed, or its SHA-256 recorded in the LEDGER) **before** the first fold month
you intend to score closes. Fields marked **frozen** may never be edited after the freeze;
anything added later goes into `results.json` as a disclosed amendment.

## 1. Family and claim — frozen

- Family (new only — closed families listed in docs/prospective_protocol.md):
- The claim, one sentence, directional:
- Mechanism (why should this predict next-month returns on THIS universe?):

## 2. Exact construction — frozen

- Feature inputs (columns/tables, as-of semantics):
- Scoring rule (the exact function of a decision month's rows → per-symbol score):
- Selection / portfolio rule if any (book construction, weights, caps, holds, costs):
- NaN contract (what a missing input does to a score):
- The registered scorer (module:function — must be importable by src.prospective.score):
  `src.prospective.designs.<name>:score_month`

## 3. Guards — frozen

- G1 (identity/PIT guard, must be assertable per fold):
- G2 (any anchor to a committed pin, or "none"):
- G3 (coverage bar: minimum scored rows / legs per fold):

## 4. Bar and decision rule — frozen

- Screen or design bar (state the number and its units):
- Minimum folds before the verdict may be written (n): ___ (≥ 12 recommended)
- What counts as a fail short of n (early-stop condition, fail direction only):
- Verdict goes to `runs/prospective/<name>/verdict.md` + a LEDGER row; a PASS licenses the
  next pre-registration, it does not ship anything.

## 5. Disclosure log (append-only)

| date | change | reason |
|---|---|---|
