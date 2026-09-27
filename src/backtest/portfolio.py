"""Task 5.3 — portfolio rules on top of the engine (BRD §8): monthly review, Trigger A/B/C,
churn cap, cash slots.

Layering: this module makes DECISIONS from FACTS; `src.backtest.engine` does FILLS. Facts
(closes, DMA-below streaks, delivery-fall streaks, month highs, rank percentiles, scores,
surveillance stages) are computed by the caller from the database — hand-built Facts are
exactly what the self-check tests. State moves at decision time; `apply_fill` reconciles
positions/cash after the engine reports a fill (no averaging down: buys only for empty slots).

Rules (all thresholds from config `portfolio.*`, BRD §8):
- §8.1 monthly review (last trading day, close): SELL if out of universe, model rank below
  the top percentile (`sell_below_top_pct`), or 50-DMA-below for `ma_below_consecutive_closes`
  closes. REPLACE from the top-ranked candidate that ranks in the top `replace_above_top_pct`;
  otherwise the slot holds CASH.
- §8.2 Trigger A (weekly close): a candidate's score exceeds a held score by more than
  `trigger_a_score_excess` (relative) -> sell held, buy candidate — capped at
  `trigger_a_cap` mid-month replacements per month, portfolio-wide.
- §8.2 Trigger B (any close): stop 8% below entry OR 12% below the month's trailing high
  (first hit wins); 2 consecutive closes below the 50-DMA; delivery% z < -2 for 3
  consecutive days while price falls; GSM/ASM stage >= `gsm_asm_stage_exit` (forced, no
  exceptions). E008b (config-gated OFF by default): while market breadth
  (`Facts.breadth_pct`, None = gate inert — checkpoint/smoke untouched) is below
  `trigger_b_breadth_threshold`, the trail giveback shrinks by
  `trigger_b_breadth_trail_tighten` pp (sell earlier into stress).
- §8.2 Trigger C: A and B on the same stock -> sell, hold cash until the next monthly
  selection (never auto-buy the A candidate that day).
- §8.3: no averaging down; every decision logged with trigger + scores; churn
  (mid-month replacements/month) reported and flagged above `churn_report_threshold`.

python -m src.backtest.portfolio runs hand-built price-path tests: monthly review sells and
cash-slot replacement, each Trigger A/B/C clause, the churn cap, no-averaging-down, and the
cash fallback — with fills always handed to the engine layer.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

# ---- facts (caller-computed; hand-built in tests) ----------------------------------------------


@dataclass
class Facts:
    """Everything a rule may look at, for one date. Missing values are the honest None."""
    date: str
    closes: dict[str, list[float]] = field(default_factory=dict)   # symbol -> close history
    dma50: dict[str, float | None] = field(default_factory=dict)   # symbol -> 50-day avg or None
    dma_below_streak: dict[str, int] = field(default_factory=dict) # symbol -> consecutive closes below DMA
    deliv_z_fall_streak: dict[str, int] = field(default_factory=dict)  # z < -2 while price falls, days
    month_high: dict[str, float] = field(default_factory=dict)     # symbol -> trailing month high
    rank_pct: dict[str, float] = field(default_factory=dict)       # symbol -> percentile rank (1 = best)
    scores: dict[str, float] = field(default_factory=dict)         # symbol -> model score
    eligible: set[str] = field(default_factory=set)
    surveillance_stage: dict[str, int] = field(default_factory=dict)   # symbol -> max stage as of D
    breadth_pct: float | None = None    # market breadth % at D's close (E008b); None = gate inert

    def close(self, symbol: str) -> float | None:
        hist = self.closes.get(symbol) or []
        return hist[-1] if hist else None


@dataclass
class Decision:
    """One rule output: sell/buy a symbol, with the trigger and the scores used (§8.3)."""
    action: str                 # sell | buy
    symbol: str
    trigger: str                # monthly_review | trigger_a | trigger_b_stop | trigger_b_trail |
                                # trigger_b_dma | trigger_b_deliv | trigger_b_gsm | replace
    score_sold: float | None = None
    score_bought: float | None = None
    note: str = ""


# ---- the rule layer ----------------------------------------------------------------------------


class Portfolio:
    """Slots, positions, cash and the decision functions. Fills belong to the engine."""

    def __init__(self, cfg: dict):
        p = cfg["portfolio"]
        self.cfg = p
        self.n_slots = p["n_slots"]
        self.slots: list[str | None] = [None] * self.n_slots     # None = cash slot
        self.entry_price: dict[str, float] = {}
        self.churn_this_month = 0

    def held(self) -> list[str]:
        return [s for s in self.slots if s is not None]

    def _slot_of(self, symbol: str) -> int | None:
        return self.slots.index(symbol) if symbol in self.slots else None

    def apply_fill(self, symbol: str, qty: int, price: float) -> None:
        """Reconcile state after the engine fills. Buys only land on empty slots (§8.3)."""
        if qty > 0:
            if symbol in self.slots:
                raise ValueError(f"averaging down refused: {symbol} is already held")
            slot = self.slots.index(None)
            self.slots[slot] = symbol
            self.entry_price[symbol] = price
        else:
            slot = self._slot_of(symbol)
            if slot is not None:
                self.slots[slot] = None
            self.entry_price.pop(symbol, None)

    # -- §8.1 monthly review -------------------------------------------------------------------

    def monthly_review(self, f: Facts) -> list[Decision]:
        """Sell on drop-out / rank fade / DMA streak; replace from the top-ranked candidate
        within the replace percentile, else hold cash."""
        out: list[Decision] = []
        for sym in self.held():
            reasons = []
            if sym not in f.eligible:
                reasons.append("monthly_review: out of eligible universe")
            rp = f.rank_pct.get(sym)
            if rp is not None and rp > self._sell_below_pct():
                reasons.append("monthly_review: rank below sell threshold")
            streak = f.dma_below_streak.get(sym, 0)
            if streak >= self.cfg["monthly_review"]["ma_below_consecutive_closes"]:
                reasons.append(f"monthly_review: below 50-DMA for {streak} closes")
            if reasons:
                out.append(Decision("sell", sym, "monthly_review", score_sold=f.scores.get(sym),
                                    note="; ".join(reasons)))
        out += self._replace(f, after_monthly=True, pending_sells=len(out))
        return out

    def _sell_below_pct(self) -> float:
        """`sell_below_top_pct` as a percentile threshold (rank_pct is '1 = best')."""
        return self.cfg["monthly_review_sell_below_top_pct"]

    def _replace(self, f: Facts, after_monthly: bool, pending_sells: int = 0) -> list[Decision]:
        """Fill empty slots from the best candidate in the replace percentile (else cash).

        The bound is free slots PLUS `pending_sells` — sells already emitted in this
        decision batch whose fills have not landed (apply_fill moves state only after
        T+1 fills). Bounding by `self.slots.count(None)` alone would emit zero replacement
        buys for the standard §8.1 flow (fully invested, one holding sold, replaced);
        the pre-fix bug was the mirror image: the loop never mutated `self.slots`, so it
        emitted a buy for EVERY candidate in the replace percentile. Callers that apply
        sell fills between a sell pass and a buy pass (checkpoint, smoke) re-call
        monthly_review with slots already freed — pending_sells defaults to 0 there."""
        out: list[Decision] = []
        held_set = set(self.held())
        top_pct = self.cfg["monthly_review_replace_above_top_pct"]
        free = self.slots.count(None) + pending_sells
        candidates = sorted((f.rank_pct[s], s) for s in f.eligible - held_set
                            if f.rank_pct.get(s) is not None and f.rank_pct[s] <= top_pct)
        for _, best in candidates[:max(free, 0)]:
            out.append(Decision("buy", best, "replace", score_bought=f.scores.get(best)))
            held_set.add(best)
        return out

    # -- §8.2 Trigger A (weekly) ---------------------------------------------------------------

    def trigger_a(self, f: Facts) -> list[Decision]:
        if self.churn_this_month >= self.cfg["midmonth"]["trigger_a_cap"]:
            return []
        out: list[Decision] = []
        excess = self.cfg["midmonth"]["trigger_a_score_excess"]
        pending_sold: set[str] = set()
        pending_bought: set[str] = set()
        for sym in self.held():
            if self.churn_this_month >= self.cfg["midmonth"]["trigger_a_cap"]:
                break
            if sym in pending_sold or sym in pending_bought:
                continue
            held_score = f.scores.get(sym)
            if held_score is None:
                continue
            taken = set(self.slots) | pending_bought - pending_sold
            better = [(s, sc) for s, sc in f.scores.items()
                      if s not in taken and sc > held_score * (1 + excess)
                      and f.rank_pct.get(s, 1.0) <= self.cfg["monthly_review_replace_above_top_pct"]]
            if better:
                cand = max(better, key=lambda p: p[1])[0]
                out.append(Decision("sell", sym, "trigger_a", score_sold=held_score,
                                    score_bought=f.scores[cand],
                                    note=f"candidate {cand}"))
                out.append(Decision("buy", cand, "trigger_a", score_bought=f.scores[cand]))
                pending_sold.add(sym)
                pending_bought.add(cand)
                self.churn_this_month += 1
        return out

    # -- §8.2 Trigger B (any close) ------------------------------------------------------------

    def _armed_trail_pct(self, f: Facts) -> float:
        """E008b's breadth-tightened trail: `trail_pct` + `trail_tighten` pp when market
        breadth is below `breadth_threshold`; unchanged when the caller passes no breadth
        (None = gate inert — pre-breadth history, or callers that never set the fact)."""
        tighten = self.cfg["midmonth"].get("trigger_b_breadth_trail_tighten")
        if not tighten or f.breadth_pct is None:
            return self.cfg["midmonth"]["trigger_b_trail_pct"]
        if f.breadth_pct < self.cfg["midmonth"]["trigger_b_breadth_threshold"]:
            # tighten is config-scaled in pp (40.0-scale like the threshold); trail_pct is
            # a fraction (0.12). Tightening = SMALLER allowed giveback (the exit limit
            # rises toward the month high, selling earlier into stress) — subtract, or
            # 4.0 pp silently becomes a 412% trail via +=
            return self.cfg["midmonth"]["trigger_b_trail_pct"] - tighten / 100.0
        return self.cfg["midmonth"]["trigger_b_trail_pct"]

    def trigger_b(self, f: Facts) -> list[Decision]:
        out: list[Decision] = []
        trail_pct = self._armed_trail_pct(f)
        for sym in self.held():
            px = f.close(sym)
            if px is None or self.entry_price.get(sym) is None:
                continue
            stage = f.surveillance_stage.get(sym, 0)
            if stage >= self.cfg["midmonth"]["gsm_asm_stage_exit"]:
                out.append(Decision("sell", sym, "trigger_b_gsm",
                                    score_sold=f.scores.get(sym),
                                    note=f"stage {stage} >= forced exit"))
                continue
            if px <= self.entry_price[sym] * (1 - self.cfg["midmonth"]["trigger_b_stop_pct"]):
                out.append(Decision("sell", sym, "trigger_b_stop", score_sold=f.scores.get(sym)))
                continue
            high = f.month_high.get(sym)
            if high is not None and px <= high * (1 - trail_pct):
                out.append(Decision("sell", sym, "trigger_b_trail", score_sold=f.scores.get(sym),
                                    note=(f"breadth {f.breadth_pct:.0f}% < "
                                          f"{self.cfg['midmonth']['trigger_b_breadth_threshold']:.0f}%"
                                          if trail_pct < self.cfg["midmonth"]["trigger_b_trail_pct"]
                                          else "")))
                continue
            if f.dma_below_streak.get(sym, 0) >= self.cfg["midmonth"]["trigger_b_ma_close_below"]:
                out.append(Decision("sell", sym, "trigger_b_dma", score_sold=f.scores.get(sym)))
                continue
            if f.deliv_z_fall_streak.get(sym, 0) >= self.cfg["midmonth"]["trigger_b_deliv_days"]:
                out.append(Decision("sell", sym, "trigger_b_deliv", score_sold=f.scores.get(sym)))
        return out

    # -- §8.2 Trigger C -------------------------------------------------------------------------

    def trigger_c(self, sells: list[Decision]) -> list[Decision]:
        """A and B firing on the same stock: the A-buy for that slot is cancelled — cash
        until the next monthly selection. Call after collecting A and B sells."""
        b_syms = {d.symbol for d in sells if d.trigger.startswith("trigger_b")}
        out = []
        for d in sells:
            if d.action == "buy" and d.trigger == "trigger_a" and d.note and \
                    any(f"candidate {s}" in d.note and s in b_syms for s in b_syms):
                continue                                  # cancelled: cash until monthly
            if d.action == "buy" and d.trigger == "trigger_a" and \
                    self._c_pair_in(d, sells, b_syms):
                continue
            out.append(d)
        return out

    def _c_pair_in(self, buy: Decision, sells: list[Decision], b_syms: set[str]) -> bool:
        """The sell paired with this A-buy (same note candidate) hit Trigger B."""
        for d in sells:
            if d.trigger == "trigger_a" and d.action == "sell" and \
                    f"candidate {buy.symbol}" in (d.note or "") and d.symbol in b_syms:
                return True
        return False

    def new_month(self) -> None:
        self.churn_this_month = 0


# ---- synthetic self-check: hand-built price paths ------------------------------------------------


def _cfg() -> dict:
    return {"portfolio": {
        "n_slots": 2, "cash_earns": 0.0,
        "monthly_review_sell_below_top_pct": 0.25,
        "monthly_review_replace_above_top_pct": 0.15,
        "monthly_review": {"ma_below_consecutive_closes": 5},
        "midmonth": {"trigger_a_score_excess": 0.20, "trigger_a_cap": 2,
                     "trigger_b_stop_pct": 0.08, "trigger_b_trail_pct": 0.12,
                     "trigger_b_ma_close_below": 2, "trigger_b_deliv_z": -2.0,
                     "trigger_b_deliv_days": 3, "gsm_asm_stage_exit": 2,
                     "trigger_b_breadth_threshold": 40.0,
                     "trigger_b_breadth_trail_tighten": None},
        "churn_report_threshold": 1.5,
    }}


def _facts(**kw) -> Facts:
    base = dict(date="2026-01-09", closes={}, dma50={}, dma_below_streak={},
                deliv_z_fall_streak={}, month_high={}, rank_pct={}, scores={},
                eligible=set(), surveillance_stage={})
    base.update(kw)
    return Facts(**base)


def _check() -> None:
    cfg = _cfg()

    # --- monthly review: rank fade sells, replacement comes from the top percentile -------
    pf = Portfolio(cfg)
    pf.slots = ["HELD", None]
    pf.entry_price["HELD"] = 100.0
    f = _facts(closes={"HELD": [100.0]}, rank_pct={"HELD": 0.40, "NEW": 0.05},
               scores={"HELD": 0.5, "NEW": 0.6}, eligible={"HELD", "NEW"},
               dma_below_streak={"HELD": 0})
    out = pf.monthly_review(f)
    sells = [d for d in out if d.action == "sell"]
    buys = [d for d in out if d.action == "buy"]
    assert len(sells) == 1 and sells[0].symbol == "HELD" and "rank" in sells[0].note, out
    assert len(buys) == 1 and buys[0].symbol == "NEW" and buys[0].trigger == "replace", out

    # --- replacement percentile miss -> the slot holds CASH --------------------------------
    pf = Portfolio(cfg)
    pf.slots = ["HELD", None]
    f = _facts(rank_pct={"HELD": 0.40, "MID": 0.50}, eligible={"HELD", "MID"},
               scores={"HELD": 0.5}, dma_below_streak={"HELD": 0})
    out = pf.monthly_review(f)
    buys = [d for d in out if d.action == "buy"]
    assert buys == [], f"a rank-0.50 candidate must not replace (top 15% required): {out}"

    # --- _replace bound: one free slot, three candidates -> exactly ONE buy (the pre-fix
    #     loop never mutated self.slots, so it emitted a buy for EVERY top-15% name) ------
    pf = Portfolio(cfg)
    pf.slots = ["HELD", None]
    f = _facts(rank_pct={"HELD": 0.01, "A": 0.05, "B": 0.10, "C": 0.12},
               scores={"A": 0.9, "B": 0.8, "C": 0.7}, eligible={"HELD", "A", "B", "C"},
               dma_below_streak={"HELD": 0})
    out = pf.monthly_review(f)
    buys = [d for d in out if d.action == "buy"]
    assert [d.symbol for d in buys] == ["A"], f"one slot -> one buy (the best): {out}"

    # --- _replace bound mirror: fully invested, one sell in THIS batch -> one replacement.
    #     count(None) == 0 here: the sell frees its slot only at the T+1 fill, so the bound
    #     must count the batch's pending sells or the §8.1 flow emits zero buys ----------
    pf = Portfolio(cfg)
    pf.slots = ["HELD", "OUT"]
    pf.entry_price = {"HELD": 100.0, "OUT": 100.0}
    f = _facts(rank_pct={"HELD": 0.01, "OUT": 0.90, "NEW": 0.05},
               scores={"HELD": 0.5, "NEW": 0.9}, eligible={"HELD", "OUT", "NEW"},
               dma_below_streak={"HELD": 0, "OUT": 0})
    out = pf.monthly_review(f)
    sells = [d for d in out if d.action == "sell"]
    buys = [d for d in out if d.action == "buy"]
    assert [d.symbol for d in sells] == ["OUT"], out        # rank 0.90 > sell threshold
    assert [d.symbol for d in buys] == ["NEW"], \
        f"one pending sell -> one replacement buy: {out}"

    # --- Trigger B stop: 8% below entry, first hit wins over the trail ---------------------
    pf = Portfolio(cfg)
    pf.slots = ["HELD", None]
    pf.entry_price["HELD"] = 100.0
    f = _facts(closes={"HELD": [91.9]}, month_high={"HELD": 105.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"})
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_stop"], out      # stop (8%) before trail

    # --- Trigger B trail: 12% off the month's high -----------------------------------------
    f = _facts(closes={"HELD": [93.0]}, month_high={"HELD": 106.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"})
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_trail"], out    # 93 = 106 x 0.877 < 88% of high

    # --- Trigger B DMA: two consecutive closes below the 50-DMA ----------------------------
    f = _facts(closes={"HELD": [100.0, 99.0]}, month_high={"HELD": 101.0},
               dma50={"HELD": 105.0}, dma_below_streak={"HELD": 2}, eligible={"HELD"})
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_dma"], out

    # --- Trigger B delivery: z < -2 while falling, 3 consecutive days ----------------------
    f = _facts(closes={"HELD": [100.0, 99.0, 98.0]}, month_high={"HELD": 101.0},
               dma_below_streak={"HELD": 0}, deliv_z_fall_streak={"HELD": 3}, eligible={"HELD"})
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_deliv"], out

    # --- Trigger B GSM/ASM: stage >= 2 forces the exit first, no exceptions ----------------
    f = _facts(closes={"HELD": [50.0]}, month_high={"HELD": 101.0},
               surveillance_stage={"HELD": 2},
               dma_below_streak={"HELD": 0}, eligible={"HELD"})
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_gsm"], out      # forced exit wins over all

    # --- E008b breadth-tightened trail: armed below the threshold, inert when None/off ----
    # tape: entry 100 (stop limit 92 not hit), high 106, close 95. Armed (giveback
    # 12-4 = 8%): 95 <= 106 x 0.92 = 97.52 -> trail exit. Unarmed (12%): 95 > 93.28 -> kept.
    tight = _cfg()
    tight["portfolio"]["midmonth"]["trigger_b_breadth_trail_tighten"] = 4.0
    pf = Portfolio(tight)
    pf.slots = ["HELD", None]
    pf.entry_price["HELD"] = 100.0
    f = _facts(closes={"HELD": [95.0]}, month_high={"HELD": 106.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"}, breadth_pct=39.9)
    out = pf.trigger_b(f)
    assert [d.trigger for d in out] == ["trigger_b_trail"] and "breadth" in (out[0].note or ""), out
    # same tape, breadth 40.0 (not below the 40 line) -> the unarmed 12% trail keeps it
    f = _facts(closes={"HELD": [95.0]}, month_high={"HELD": 106.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"}, breadth_pct=40.0)
    assert pf.trigger_b(f) == [], "breadth at the threshold must not arm the gate"
    # None breadth (the checkpoint/smoke contract) -> gate inert, no exit at 88
    f = _facts(closes={"HELD": [95.0]}, month_high={"HELD": 106.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"}, breadth_pct=None)
    assert pf.trigger_b(f) == [], "breadth None must leave the trail unarmed"
    # gate OFF (default config): same tape, breadth 10 -> no exit
    pf = Portfolio(cfg)
    pf.slots = ["HELD", None]
    pf.entry_price["HELD"] = 100.0
    f = _facts(closes={"HELD": [95.0]}, month_high={"HELD": 106.0},
               dma_below_streak={"HELD": 0}, eligible={"HELD"}, breadth_pct=10.0)
    assert pf.trigger_b(f) == [], "gate OFF (tighten null) must ignore breadth"

    # --- Trigger A: +20% relative excess buys the candidate; cap 2/month holds -------------
    pf = Portfolio(cfg)
    pf.slots = ["A", "B"]
    f = _facts(scores={"A": 1.0, "B": 1.0, "C": 1.30, "D": 1.45},
               rank_pct={"C": 0.05, "D": 0.03},
               eligible={"A", "B", "C", "D"})
    out = pf.trigger_a(f)
    assert [(d.action, d.symbol) for d in out] == [("sell", "A"), ("buy", "D"),
                                                   ("sell", "B"), ("buy", "C")], out
    assert pf.churn_this_month == 2, pf.churn_this_month
    # the cap: a third candidate must be refused
    out2 = pf.trigger_a(f)
    assert out2 == [] and pf.churn_this_month == 2, (out2, pf.churn_this_month)

    # --- Trigger C: B fires on the stock A wanted to replace -> that A-buy is cancelled ----
    pf = Portfolio(cfg)
    pf.slots = ["A", "B"]
    pf.entry_price = {"A": 100.0, "B": 100.0}
    a_sells = [Decision("sell", "A", "trigger_a", score_sold=1.0, score_bought=1.3,
                        note="candidate C")]
    a_buys = [Decision("buy", "C", "trigger_a", score_bought=1.3)]
    b_sells = [Decision("sell", "A", "trigger_b_stop", score_sold=1.0)]
    kept = pf.trigger_c(a_sells + b_sells + a_buys)
    buys = [d for d in kept if d.action == "buy"]
    assert buys == [], f"Trigger C must cancel the A-buy: {kept}"

    # --- no averaging down: a second buy of a held name is refused, sell frees the slot ----
    pf = Portfolio(cfg)
    assert pf.slots == [None, None], "a fresh portfolio is all cash"
    pf.apply_fill("A", 10, 100.0)
    assert pf.slots == ["A", None] and pf.entry_price["A"] == 100.0, (pf.slots, pf.entry_price)
    try:
        pf.apply_fill("A", 5, 100.0)
        raise AssertionError("averaging down must be refused")
    except ValueError:
        pass
    pf.apply_fill("B", 5, 50.0)
    assert pf.slots == ["A", "B"], pf.slots
    pf.apply_fill("A", -10, 110.0)
    assert pf.slots == [None, "B"] and "A" not in pf.entry_price, pf.slots

    # --- churn reporting threshold (§8.3): > 1.5/month is flagged by the caller metric ------
    assert cfg["portfolio"]["churn_report_threshold"] == 1.5

    print("PASS: portfolio rules (monthly review + cash fallback, replace percentile, "
          "Trigger B stop/trail/DMA/delivery/GSM order, E008b breadth-tightened trail "
          "armed/inert/off, Trigger A cap, Trigger C cancellation, "
          "no averaging down)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _check()
