"""Config loader — the single way any module reads config.yaml (plan working rule 1).

Usage:
    from src.config import load
    cfg = load()              # profile from config.yaml (default quick)
    cfg = load("full")        # deliberate act: the 15-year profile

Merges the profile's date block to top level (`data_start_date`, `walkforward_months`)
and validates the invariants later phases rely on. `python -m src.config` runs the self-check.
"""
import sys

import yaml


def load(profile: str | None = None) -> dict:
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    profile = profile or cfg["profile"]
    if profile not in ("quick", "full"):
        raise ValueError(f"profile must be quick|full, got {profile!r}")
    cfg["profile"] = profile
    cfg["data_start_date"] = cfg[profile]["start_date"]
    cfg["walkforward_months"] = cfg[profile]["walkforward_months"]
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    adj_start = cfg.get("adj_history_start")
    assert isinstance(adj_start, str) and len(adj_start) == 10 \
        and adj_start[4] == "-" and adj_start[7] == "-", \
        f"adj_history_start must be an ISO date, got {adj_start!r}"
    assert adj_start < cfg["data_start_date"], \
        (f"adj_history_start {adj_start} must precede the profile window "
         f"{cfg['data_start_date']} — features need adjusted prices for their lookback")
    cutoff = cfg["download"].get("publish_cutoff_ist")
    assert isinstance(cutoff, str) and len(cutoff) == 5 and cutoff[2] == ":" \
        and cutoff[:2].isdigit() and cutoff[3:].isdigit() \
        and 0 <= int(cutoff[:2]) <= 23 and 0 <= int(cutoff[3:]) <= 59, \
        f"download.publish_cutoff_ist must be HH:MM IST, got {cutoff!r}"
    retry_min = cfg["download"].get("refresh_retry_minutes")
    assert isinstance(retry_min, int) and 1 <= retry_min <= 240, \
        f"download.refresh_retry_minutes must be 1..240 minutes, got {retry_min!r}"
    v = cfg["validate"]
    assert 80 <= v["min_year_coverage_pct"] <= 100, f"coverage floor is a percent, got {v['min_year_coverage_pct']}"
    assert 0 <= v["max_join_mismatch_pct"] <= 10, f"join mismatch cap is a percent, got {v['max_join_mismatch_pct']}"
    assert 0 < v["canary_min_adj_coverage"] <= 1, f"adj coverage floor is a fraction, got {v['canary_min_adj_coverage']}"
    assert v["canary_min_ic_months"] > 0 and v["canary_min_ic_names"] > 0 and v["canary_min_deliv_pairs"] > 0, \
        f"canary sample floors must be positive, got {v}"
    assert -1 < v["canary_min_deliv_autocorr"] < 1, f"autocorr floor is a correlation, got {v['canary_min_deliv_autocorr']}"

    u, p, b, s = cfg["universe"], cfg["portfolio"], cfg["backtest"], cfg["stats"]
    assert u["top_n"] > 0 and u["liquidity_lookback_months"] > 0, f"universe rank params must be positive, got {u}"
    assert u["min_price"] > 0 and u["min_listed_months"] > 0, f"eligibility floors must be positive, got {u}"
    assert isinstance(u["allowed_series"], list) and u["allowed_series"], \
        f"universe.allowed_series must be a non-empty list of series codes, got {u['allowed_series']}"
    assert u["min_median_turnover_cr"] >= 0, \
        (f"universe.min_median_turnover_cr is a floor (0.0 = guard off), got "
         f"{u['min_median_turnover_cr']}")
    assert isinstance(u["gsm_asm_max_allowed_stage"], int) and u["gsm_asm_max_allowed_stage"] >= 0, \
        (f"universe.gsm_asm_max_allowed_stage must be an int stage >= 0 (0 = any listing excludes), "
         f"got {u['gsm_asm_max_allowed_stage']!r}")
    assert 0 < u["rank_percentiles"]["sell_below_top_pct"] <= 1 and 0 < u["rank_percentiles"]["replace_above_top_pct"] <= 1, \
        f"rank cutoffs are percentiles in (0, 1], got {u['rank_percentiles']}"
    assert u["rank_percentiles"]["replace_above_top_pct"] < u["rank_percentiles"]["sell_below_top_pct"], \
        "replacement bar must be stricter (lower percentile) than the sell trigger"
    assert p["n_slots"] > 0, f"n_slots must be positive, got {p['n_slots']}"
    mm = p["midmonth"]
    assert 0 < mm["trigger_b_stop_pct"] < 1 and 0 < mm["trigger_b_trail_pct"] < 1, \
        f"trigger B thresholds are fractions < 1, got {mm['trigger_b_stop_pct']}, {mm['trigger_b_trail_pct']}"
    assert 0 < b["cost_per_side_pct"] < 5, f"cost_per_side_pct is a percent, got {b['cost_per_side_pct']}"
    assert len(b["cost_sensitivity_pct"]) == 3, "E006 needs exactly three cost levels"
    assert 0 < s["winner_top_pct"] < 1 and 0 < s["baseline_hit_rate"] < 1, f"winner/baseline must be fractions, got {s}"
    assert s["winner_top_pct"] == s["baseline_hit_rate"], "baseline must equal the winner definition (BRD §11)"
    assert cfg["walkforward_months"] > 0, f"walkforward_months must be positive, got {cfg['walkforward_months']}"


if __name__ == "__main__":
    for prof in ("quick", "full"):
        c = load(prof)
        assert c["data_start_date"] and c["walkforward_months"], f"{prof}: date block merge failed"
        assert c["adj_history_start"] < c["data_start_date"], f"{prof}: adj history floor drifted"
        assert c["universe"]["top_n"] == 1500, f"{prof}: top_n drifted from BRD §4"
        assert c["stats"]["winner_top_pct"] == 0.05, f"{prof}: winner definition drifted from BRD §4"
        assert c["backtest"]["cost_sensitivity_pct"] == [0.20, 0.50, 1.00], f"{prof}: E006 levels drifted from BRD §9"
    print("PASS: config loads for both profiles, all BRD invariants hold")
    sys.exit(0)
