# E025 — index-inclusion events: do NSE inclusion dates predict monthly returns on this universe?

Pre-registered 2026-09-27, **before any run** (BRD §12). Shortlist item #3 of
`docs/feature_family_audit.md` — the only remaining direction that is *new data*, not a new
use of the existing panel.

## Source (frozen)

NSE's `IndexInclExcl.xls` (archives.nseindia.com/content/indices/IndexInclExcl.xls): a
multi-sheet workbook of security inclusions/exclusions for NSE indices with dates, with a
"Nifty 500" sheet reported to reach back to 1998. Disclosed risks, known before the run:

1. **Staleness:** community reports say the file was last updated ~2020-07-31. The sweep
   covers whatever the file holds; a coverage guard records the last event date and the
   sweep excludes months after it from the event arm (the panel continues normally).
2. **Symbol fidelity:** the file carries company names, not guaranteed NSE symbols;
   matching to bhav symbols is by normalized name with manual verification of every match
   used. Unmatched events are counted and excluded (loudly).
3. **Format:** a legacy .xls binary; parsed with the repo's zero-dependency BIFF parser
   (a local `_xls.py`, inspired by the stdlib's OleFileIO/BIFF approach; integrity checks
   on the CFB container and every record). No new dependencies.

## Sweep (frozen)

- **Data:** labeled decision months m ∈ the 145-month validation slice; the event signal
  at month m is `is_includer(symbol) = 1` iff the file records an inclusion of that symbol
  dated within the 12 months BEFORE m (an as-of, backward-looking window — no look-ahead);
  exclusions symmetric (12 months before).
- **Measurement:** mean monthly IC of the 0/1 includer flag, one-sample t across months,
  plus the mean label gap (includers − non-includers) per month; the same for the
  excluder flag. BH not applied (two pre-registered tests).
- **Practical bar:** a usable inclusion effect must clear mean gap ≥ +1.0pp/mo for
  includers (or ≤ −1.0pp/mo for excluders) over ≥ 30 event-bearing months, mirroring the
  program's 2pp-CAGR-bar spirit (a 1pp monthly gap at the book level is the smallest
  effect worth a design).

## Decision rule (frozen)

This is an IC **screen**, not a design experiment: PASS means the effect is big enough to
justify a portfolio pre-registration; it does not promote anything. If the source is
unfetchable, the file's format defeats the parser, or matched events are too few
(< 30 event-bearing months), the result is **NOT MEASURED — source unavailable**, recorded
with the exact failure, and the audit's data direction is marked "requires a paid/vendor
or manual-composition source". Nothing ships from this experiment under any outcome.
