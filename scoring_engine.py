"""
scoring_engine.py
------------------
Turns quant_engine outputs (+ optional ai_reasoning outputs) into the
6-pillar composite score and a final recommendation bucket.

Design choice that matters: governance is NOT just a 10% weight.
A hard red flag caps the recommendation at "Avoid" regardless of how
good the other five pillars look. This directly encodes the instruction
sitting in the user's own "post analysis checklist" tab: red flags are
never just averaged away.
"""

from __future__ import annotations
import statistics
import quant_engine as qe

PILLAR_WEIGHTS = {
    "moat": 0.25,
    "financial_health": 0.20,
    "growth": 0.15,
    "valuation": 0.20,
    "technical": 0.10,
    "governance": 0.10,
}

HARD_RED_FLAGS = {
    "promoter_pledge_pct": lambda v: v is not None and v > 0.10,
    "promoter_holding_change_yoy": lambda v: v is not None and v < -0.03,
    "share_dilution_pct_yoy": lambda v: v is not None and v > 0.05,
    "auditor_changed_last_5y": lambda v: v is True,
    "related_party_transactions_flag": lambda v: v is True,
    "results_delayed_flag": lambda v: v is True,
}


def _clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def score_financial_health(d: dict) -> float:
    test = qe.two_minute_test(d)
    lev = qe.leverage(d)
    fcf = qe.fcf_metrics(d)

    test_score = sum(1 for k, v in test.items() if k not in ("market_cap_cr",) and v is True)
    test_score = test_score / 7 * 100  # 7 boolean checks in two_minute_test

    de_latest = lev["debt_to_equity"][-1] or 0
    de_score = 100 if de_latest < 0.3 else (60 if de_latest < 1 else (30 if de_latest < 2 else 0))

    fcf_positive_years = sum(1 for f in fcf["fcf"] if f > 0)
    fcf_consistency_score = fcf_positive_years / len(fcf["fcf"]) * 100

    return _clamp(0.5 * test_score + 0.25 * de_score + 0.25 * fcf_consistency_score)


def score_growth(d: dict) -> float:
    sales_h = qe.multi_horizon_cagr(d["sales"], horizons=(3, 5, 9))
    np_h = qe.multi_horizon_cagr(d["net_profit"], horizons=(3, 5, 9))

    def cagr_to_score(c):
        if c is None:
            return None
        # 0% CAGR -> 20, 15%+ CAGR -> 100, roughly linear in between
        return _clamp(20 + (c / 0.15) * 80)

    sales_scores = [cagr_to_score(v) for v in sales_h.values() if v is not None]
    np_scores = [cagr_to_score(v) for v in np_h.values() if v is not None]
    base = statistics.mean(sales_scores + np_scores) if (sales_scores or np_scores) else 50

    consistency = qe.growth_consistency(d["net_profit"])
    penalty = {"accelerating or stable": 1.0, "decelerating, but not sharply": 0.85,
               "decelerating sharply": 0.6, "insufficient data": 0.9}[consistency]

    return _clamp(base * penalty)


def score_valuation(d: dict) -> float:
    iv = qe.intrinsic_value_range(d)
    rv = qe.relative_valuation(d)
    mcap = iv["current_market_cap"]

    if mcap <= iv["iv_low"]:
        iv_score = 100
    elif mcap <= iv["iv_high"]:
        # linear from 100 at iv_low down to 40 at iv_high
        span = iv["iv_high"] - iv["iv_low"]
        pos = (mcap - iv["iv_low"]) / span if span else 0
        iv_score = 100 - pos * 60
    else:
        premium = (mcap / iv["iv_high"]) - 1
        iv_score = max(0, 40 - premium * 100)

    bonus = (10 if rv["cheaper_than_own_history"] else -10) + (10 if rv["attractive_vs_bonds"] else -5)
    return _clamp(iv_score + bonus)


def score_technical(technical_data: dict | None) -> float:
    """Momentum, % delivery, derivative positioning, FII/DII flow, analyst
    target gap -- the Edelweiss-screener layer. Defaults to a neutral 50
    when live market data isn't wired in yet (see data_fetcher.py)."""
    if not technical_data:
        return 50.0
    score = 50.0
    if technical_data.get("price_above_50dma"):
        score += 10
    if technical_data.get("price_above_200dma"):
        score += 10
    if technical_data.get("delivery_pct_trend") == "rising":
        score += 10
    if technical_data.get("derivative_positioning") == "long_buildup":
        score += 10
    elif technical_data.get("derivative_positioning") == "short_buildup":
        score -= 15
    if technical_data.get("analyst_target_upside", 0) > 0.1:
        score += 10
    return _clamp(score)


def check_red_flags(governance_flags: dict, ai_red_flags: list[str] | None = None) -> dict:
    triggered_hard = []
    for key, test in HARD_RED_FLAGS.items():
        if test(governance_flags.get(key)):
            triggered_hard.append(key)
    soft_flags = list(ai_red_flags or [])
    return {
        "hard_flags": triggered_hard,
        "soft_flags": soft_flags,
        "veto": len(triggered_hard) > 0,
    }


def composite_score(pillar_scores: dict) -> float:
    return round(sum(pillar_scores[p] * w for p, w in PILLAR_WEIGHTS.items()), 1)


def recommendation_bucket(score: float, vetoed: bool) -> dict:
    if vetoed:
        return {"call": "Avoid", "label": "Red flag override", "core_or_satellite": "N/A"}
    if score >= 75:
        return {"call": "Strong Buy", "label": "Core candidate", "core_or_satellite": "Core"}
    if score >= 60:
        return {"call": "Buy", "label": "Tactical buy", "core_or_satellite": "Satellite"}
    if score >= 45:
        return {"call": "Hold", "label": "Watchlist", "core_or_satellite": "Satellite"}
    if score >= 30:
        return {"call": "Avoid", "label": "Not attractive at current price", "core_or_satellite": "N/A"}
    return {"call": "Sell/Avoid", "label": "Weak across most pillars", "core_or_satellite": "N/A"}


def run_full_score(d: dict, ai_output: dict | None = None, technical_data: dict | None = None) -> dict:
    """Top-level entry point: combine quant + AI pillars into the final call."""
    ai_output = ai_output or {}
    pillars = {
        "moat": ai_output.get("moat_score", 50),
        "financial_health": score_financial_health(d),
        "growth": score_growth(d),
        "valuation": score_valuation(d),
        "technical": score_technical(technical_data),
        "governance": ai_output.get("governance_score", 70),
    }
    flags = check_red_flags(d.get("governance_flags", {}), ai_output.get("red_flags"))
    score = composite_score(pillars)
    rec = recommendation_bucket(score, flags["veto"])
    return {
        "pillar_scores": {k: round(v, 1) for k, v in pillars.items()},
        "composite_score": score,
        "red_flags": flags,
        "recommendation": rec,
    }
