"""
quant_engine.py
----------------
Deterministic financial computation layer. Every function here ports a
formula straight out of the Safal Niveshak Stock Analysis Excel (Ver 5.0)
or the Investor Diary Stock Analysis Excel templates the user supplied.

No LLM calls happen in this file on purpose: ratios, growth rates, and
intrinsic value models should be reproducible and auditable, not
generated. The AI reasoning layer (ai_reasoning.py) handles the parts
that genuinely need judgment (moat, governance, narrative).

All functions take plain lists/dicts so they're trivial to unit test
against the known Excel outputs in sample_data/*.json
("_ground_truth_for_validation").
"""

from __future__ import annotations
import statistics


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def safe_div(num, den):
    """Returns None instead of crashing when den is 0/None/missing, or
    num is None. This is the single chokepoint for every ratio in this
    file -- live data (yfinance) routinely has zero/missing line items
    that clean Excel-sourced sample data never had."""
    if num is None or den is None:
        return None
    try:
        if den == 0:
            return None
        return num / den
    except (TypeError, ZeroDivisionError):
        return None


def safe_mean(values: list) -> float | None:
    """statistics.mean() throws StatisticsError on an empty list -- this
    happens whenever every ROE/PE/etc value in a window came back None
    (filtered out) for a given company."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return statistics.mean(clean)


# ---------------------------------------------------------------------------
# Growth
# ---------------------------------------------------------------------------

def cagr(values: list[float], n_years: int | None = None) -> float | None:
    """CAGR between the first and last value in the series.
    n_years defaults to (len(values) - 1), matching the Excel '9-Year CAGR'
    style convention for 10 yearly data points.
    """
    if not values or values[0] in (0, None) or values[-1] is None:
        return None
    n = n_years or (len(values) - 1)
    if n <= 0:
        return None
    if values[0] < 0 or values[-1] < 0:
        return None
    ratio = safe_div(values[-1], values[0])
    if ratio is None:
        return None
    return ratio ** (1 / n) - 1


def multi_horizon_cagr(values: list[float], horizons=(3, 5, 7, 9)) -> dict:
    """Sales/PBT/NP growth at multiple lookback windows, the way the
    Investor Diary 'Growth' sheet checks whether recent growth is
    accelerating or decelerating vs the long-term trend."""
    out = {}
    for h in horizons:
        if len(values) > h:
            out[f"{h}y"] = cagr(values[-(h + 1):], h)
        else:
            out[f"{h}y"] = None
    return out


def yoy_growth(values: list[float]) -> list[float | None]:
    out = [None]
    for i in range(1, len(values)):
        out.append(safe_div(values[i] - values[i - 1], values[i - 1]))
    return out


def growth_consistency(values: list[float]) -> str:
    """Buffett checklist: prefer companies whose recent (3y) growth rate
    is not collapsing relative to the long-term (9y/10y) rate."""
    h = multi_horizon_cagr(values, horizons=(3, 9))
    g3, g9 = h.get("3y"), h.get("9y")
    if g3 is None or g9 is None:
        return "insufficient data"
    if g3 >= g9:
        return "accelerating or stable"
    if g3 >= g9 * 0.5:
        return "decelerating, but not sharply"
    return "decelerating sharply"


# ---------------------------------------------------------------------------
# Margins & turnover
# ---------------------------------------------------------------------------

def margins(d: dict) -> dict:
    sales = d["sales"]
    op = d["operating_profit"]
    pbt = d["pbt"]
    npft = d["net_profit"]
    return {
        "operating_margin": [safe_div(o, s) for o, s in zip(op, sales)],
        "pbt_margin": [safe_div(p, s) for p, s in zip(pbt, sales)],
        "net_margin": [safe_div(n, s) for n, s in zip(npft, sales)],
    }


def turnover_ratios(d: dict) -> dict:
    sales = d["sales"]
    debtors = d["debtors"]
    inventory = d["inventory"]
    net_block = d["net_block"]
    return {
        "debtor_days": [
            (365 * r) if (r := safe_div(deb, s)) is not None else None
            for deb, s in zip(debtors, sales)
        ],
        "inventory_turnover": [safe_div(s, inv) for s, inv in zip(sales, inventory)],
        "fixed_asset_turnover": [safe_div(s, nb) for s, nb in zip(sales, net_block)],
    }


# ---------------------------------------------------------------------------
# Leverage & returns
# ---------------------------------------------------------------------------

def equity_series(d: dict) -> list[float]:
    return [(ec or 0) + (r or 0) for ec, r in zip(d["equity_capital"], d["reserves"])]


def leverage(d: dict) -> dict:
    eq = equity_series(d)
    borr = d["borrowings"]
    interest = d["interest"]
    pbt = d["pbt"]
    coverage = []
    for p, i in zip(pbt, interest):
        if not i:
            coverage.append(float("inf"))
        else:
            ratio = safe_div((p or 0) + i, i)
            coverage.append(ratio if ratio is not None else float("inf"))
    return {
        "debt_to_equity": [safe_div(b, e) for b, e in zip(borr, eq)],
        "interest_coverage": coverage,
    }


def returns_ratios(d: dict) -> dict:
    """ROE, ROCE, ROIC -- matches the Key Ratios / Profitability sheets
    to within ~1% (validated against sample_data ground truth)."""
    eq = equity_series(d)
    borr = d["borrowings"]
    pbt = d["pbt"]
    interest = d["interest"]
    npft = d["net_profit"]
    tax = d["tax"]
    cash = d.get("cash", [0] * len(eq))

    roe, roce, roic = [], [], []
    for i in range(len(eq)):
        capital_employed = eq[i] + (borr[i] or 0)
        ebit = (pbt[i] or 0) + (interest[i] or 0)
        tax_rate = safe_div(tax[i], pbt[i]) or 0
        nopat = ebit * (1 - tax_rate)
        invested_capital = capital_employed - (cash[i] or 0)

        roe.append(safe_div(npft[i], eq[i]))
        roce.append(safe_div(ebit, capital_employed))
        roic.append(safe_div(nopat, invested_capital))

    return {"roe": roe, "roce": roce, "roic": roic}


def dupont(d: dict) -> dict:
    """Net margin x asset turnover x financial leverage = ROE."""
    eq = equity_series(d)
    sales = d["sales"]
    npft = d["net_profit"]
    other_liab = d["other_liabilities"]
    borr = d["borrowings"]
    total_assets = [
        e + (b or 0) + (ol or 0) for e, b, ol in zip(eq, borr, other_liab)
    ]

    net_margin = [safe_div(n, s) for n, s in zip(npft, sales)]
    asset_turnover = [safe_div(s, ta) for s, ta in zip(sales, total_assets)]
    fin_leverage = [safe_div(ta, e) for ta, e in zip(total_assets, eq)]
    roe_check = [
        nm * at * fl if None not in (nm, at, fl) else None
        for nm, at, fl in zip(net_margin, asset_turnover, fin_leverage)
    ]
    return {
        "net_margin": net_margin,
        "asset_turnover": asset_turnover,
        "financial_leverage": fin_leverage,
        "roe_from_dupont": roe_check,
    }


# ---------------------------------------------------------------------------
# Cash flow quality
# ---------------------------------------------------------------------------

def fcf_metrics(d: dict) -> dict:
    cfo = d["cfo"]
    capex = d["capex"]
    sales = d["sales"]
    npft = d["net_profit"]
    fcf = [(c or 0) - (x or 0) for c, x in zip(cfo, capex)]
    return {
        "fcf": fcf,
        "fcf_to_sales": [safe_div(f, s) for f, s in zip(fcf, sales)],
        "fcf_to_net_profit": [safe_div(f, n) for f, n in zip(fcf, npft)],
        "cfo_to_capex": [safe_div(c, x) for c, x in zip(cfo, capex)],
    }


def ssgr(d: dict) -> list[float | None]:
    """Self-Sustainable Growth Rate, from the Investor Diary Growth sheet:
    SSGR = Net Fixed Asset Turnover x Net Margin x (1 - Dividend Payout) - Depreciation%NFA
    A company growing sales faster than its SSGR needs external capital
    (debt or equity) to keep growing -- worth flagging, not necessarily
    disqualifying."""
    sales = d["sales"]
    net_block = d["net_block"]
    npft = d["net_profit"]
    dpr = d["dividend_payout"]
    # Depreciation isn't in every sample dataset; default to 0 if absent.
    dep_pct_nfa = d.get("depreciation_pct_nfa", [0] * len(sales))

    out = []
    for i in range(len(sales)):
        nfat = safe_div(sales[i], net_block[i])
        npm = safe_div(npft[i], sales[i])
        if nfat is None or npm is None:
            out.append(None)
            continue
        payout = dpr[i] if dpr[i] is not None else 0
        dep = dep_pct_nfa[i] if dep_pct_nfa[i] is not None else 0
        out.append(nfat * npm * (1 - payout) - dep)
    return out


# ---------------------------------------------------------------------------
# The 2-minute test (Greenblatt-style quick screen, Investor Diary sheet)
# ---------------------------------------------------------------------------

def two_minute_test(d: dict) -> dict:
    eq = equity_series(d)
    shares_cr = safe_div(d["net_profit"][-1], d["eps"][-1])
    market_cap = (shares_cr * d["current_price"]) if shares_cr else None
    roe = returns_ratios(d)["roe"]
    fcf = fcf_metrics(d)["fcf"]
    de = leverage(d)["debt_to_equity"]

    mean_roe = safe_mean(roe)

    checks = {
        "min_quality_hurdle": market_cap is not None and market_cap > 500,
        "ever_made_operating_profit": all((op or 0) > 0 for op in d["operating_profit"]),
        "consistent_cfo": all((c or 0) > 0 for c in d["cfo"]),
        "roe_above_15_with_low_leverage": (
            mean_roe is not None and mean_roe > 0.15 and (de[-1] or 0) < 1
        ),
        "clean_balance_sheet": (de[-1] or 0) < 1,
        "generates_fcf": (fcf[-1] or 0) > 0,
        "share_dilution_under_2pct": d.get("governance_flags", {}).get(
            "share_dilution_pct_yoy", 0
        ) < 0.02,
    }
    checks["overall_pass"] = all(checks.values())
    checks["market_cap_cr"] = round(market_cap, 1) if market_cap else None
    return checks


# ---------------------------------------------------------------------------
# Profitability matrix (Investor Diary): ROE vs FCF/Sales quadrant
# ---------------------------------------------------------------------------

def profitability_matrix(latest_roe: float, latest_fcf_to_sales: float) -> str:
    good_roe = latest_roe is not None and latest_roe > 0.15
    good_fcf = latest_fcf_to_sales is not None and latest_fcf_to_sales > 0.05
    if good_roe and good_fcf:
        return "Great company"
    if good_roe and not good_fcf:
        return "Good ROE but weak free cash flow"
    if not good_roe and good_fcf:
        return "Weak ROE but good free cash flow"
    return "Avoid"


# ---------------------------------------------------------------------------
# Relative valuation
# ---------------------------------------------------------------------------

def relative_valuation(d: dict) -> dict:
    pe_series = [r for p, e in zip(d["price"], d["eps"]) if (r := safe_div(p, e)) is not None]
    current_pe = safe_div(d["current_price"], d["eps"][-1])
    avg_pe = {
        "3y": safe_mean(pe_series[-3:]) if len(pe_series) >= 3 else current_pe,
        "5y": safe_mean(pe_series[-5:]) if len(pe_series) >= 5 else current_pe,
        "10y": safe_mean(pe_series[-10:]) if len(pe_series) >= 10 else current_pe,
    }
    reference_pe = avg_pe["5y"] if avg_pe["5y"] is not None else avg_pe["3y"]
    cheaper_than_history = (
        current_pe is not None and reference_pe is not None and current_pe < reference_pe
    )

    earnings_yield = safe_div(d["eps"][-1], d["current_price"])
    bond_yield = d["govt_bond_yield"]
    yield_spread = (earnings_yield - bond_yield) if earnings_yield is not None else None

    return {
        "current_pe": round(current_pe, 2) if current_pe is not None else None,
        "avg_pe": {k: (round(v, 2) if v is not None else None) for k, v in avg_pe.items()},
        "cheaper_than_own_history": cheaper_than_history,
        "earnings_yield": round(earnings_yield, 4) if earnings_yield is not None else None,
        "govt_bond_yield": bond_yield,
        "yield_spread_vs_bond": round(yield_spread, 4) if yield_spread is not None else None,
        "attractive_vs_bonds": (yield_spread or 0) > 0,
    }


# ---------------------------------------------------------------------------
# Intrinsic value models
# ---------------------------------------------------------------------------

def ben_graham_value(eps: float, growth_rate: float, pe_no_growth: float = 8.5) -> float:
    """Value = EPS x (8.5 + 2g), g in percentage points (e.g. 10 for 10%)."""
    return (eps or 0) * (pe_no_growth + 2 * (growth_rate or 0) * 100)


def dcf_value(
    fcf0: float,
    growth_yr1_5: float,
    growth_yr6_10: float,
    discount_rate: float,
    terminal_growth: float,
    net_debt: float = 0,
) -> dict:
    pv_total = 0.0
    fcf = fcf0 or 0
    for yr in range(1, 11):
        g = growth_yr1_5 if yr <= 5 else growth_yr6_10
        fcf = fcf * (1 + (g or 0))
        pv = fcf / ((1 + discount_rate) ** yr)
        pv_total += pv
    terminal_fcf = fcf * (1 + terminal_growth)
    denom = (discount_rate - terminal_growth)
    terminal_value = safe_div(terminal_fcf, denom) or 0
    pv_terminal = terminal_value / ((1 + discount_rate) ** 10)
    equity_value = pv_total + pv_terminal - (net_debt or 0)
    return {"enterprise_value": round(pv_total + pv_terminal, 1), "equity_value": round(equity_value, 1)}


def dhandho_value(
    fcf0: float,
    growth_yr1_3: float,
    growth_yr4_6: float,
    growth_yr7_10: float,
    discount_rate: float,
    excess_cash: float = 0,
) -> float:
    """Mohnish Pabrai's reverse-FCF model: step the growth rate down every
    few years, discount each year's FCF back, add excess cash."""
    pv_total = excess_cash or 0
    fcf = fcf0 or 0
    for yr in range(1, 11):
        if yr <= 3:
            g = growth_yr1_3
        elif yr <= 6:
            g = growth_yr4_6
        else:
            g = growth_yr7_10
        fcf = fcf * (1 + (g or 0))
        pv_total += fcf / ((1 + discount_rate) ** yr)
    return round(pv_total, 1)


def expected_returns_value(
    net_profit0: float,
    est_cagr_10y: float,
    current_pe: float,
    exit_pe: float,
    discount_rate: float,
    current_market_cap: float,
) -> dict:
    """Buffett's 'look-through' reverse model: project profit 10y out,
    apply an assumed exit multiple, discount the resulting market cap
    back to today, compare with the current price tag."""
    future_profit = (net_profit0 or 0) * (1 + (est_cagr_10y or 0)) ** 10
    future_mcap = future_profit * (exit_pe or 0)
    discounted_value = future_mcap / (1 + discount_rate) ** 10
    premium_or_discount = safe_div(discounted_value, current_market_cap) or 0
    premium_or_discount = premium_or_discount - 1 if current_market_cap else 0
    return {
        "future_net_profit_10y": round(future_profit, 1),
        "future_market_cap_10y": round(future_mcap, 1),
        "discounted_value_today": round(discounted_value, 1),
        "premium_discount_to_current_mcap": round(premium_or_discount, 3),
    }


def intrinsic_value_range(d: dict, assumptions: dict | None = None) -> dict:
    """Runs all four IV models with sensible defaults derived from the
    company's own historical growth, and returns a consolidated range --
    exactly what the 'Intrinsic Values' sheet does in both Excel templates."""
    a = assumptions or {}
    eps0 = d["eps"][-1] or 0
    fcf_series = fcf_metrics(d)["fcf"]
    fcf = safe_mean(fcf_series[-3:]) if len(fcf_series) >= 3 else fcf_series[-1]
    fcf = fcf or 0
    shares_cr = safe_div(d["net_profit"][-1], d["eps"][-1]) or 1.0
    market_cap = shares_cr * (d["current_price"] or 0)
    net_debt = (d["borrowings"][-1] or 0) - (d.get("cash", [0])[-1] or 0)

    sales_cagr_5y = cagr(d["sales"][-6:], 5) or 0.08
    npat_cagr_5y = cagr(d["net_profit"][-6:], 5) or 0.08

    g_low = max(npat_cagr_5y * 0.6, 0.04)
    g_high = max(npat_cagr_5y * 0.9, 0.06)

    ben_graham_low = ben_graham_value(eps0, g_low) * shares_cr
    ben_graham_high = ben_graham_value(eps0, g_high) * shares_cr

    dcf = dcf_value(
        fcf, a.get("dcf_g1", g_high), a.get("dcf_g2", g_low),
        a.get("discount_rate", 0.12), a.get("terminal_growth", 0.04), net_debt
    )

    dhandho_low = dhandho_value(fcf, g_low, g_low * 0.8, g_low * 0.5, 0.12, max(-net_debt, 0))
    dhandho_high = dhandho_value(fcf, g_high, g_high * 0.8, g_high * 0.5, 0.12, max(-net_debt, 0))

    rv = relative_valuation(d)
    exit_pe = a.get("exit_pe", rv["avg_pe"]["5y"] if rv["avg_pe"]["5y"] is not None else (rv["current_pe"] or 15))

    er = expected_returns_value(
        d["net_profit"][-1], npat_cagr_5y, rv["current_pe"],
        exit_pe, a.get("discount_rate", 0.12), market_cap
    )

    low = min(ben_graham_low, dcf["equity_value"], dhandho_low, er["discounted_value_today"])
    high = max(ben_graham_high, dcf["equity_value"], dhandho_high, er["discounted_value_today"])

    return {
        "ben_graham_range": [round(ben_graham_low, 1), round(ben_graham_high, 1)],
        "dcf_value": dcf["equity_value"],
        "dhandho_range": [round(dhandho_low, 1), round(dhandho_high, 1)],
        "expected_returns_value": er["discounted_value_today"],
        "iv_low": round(low, 1),
        "iv_high": round(high, 1),
        "current_market_cap": round(market_cap, 1),
        "premium_discount_to_low": round(safe_div(market_cap, low) - 1, 3) if low and safe_div(market_cap, low) is not None else None,
        "premium_discount_to_high": round(safe_div(market_cap, high) - 1, 3) if high and safe_div(market_cap, high) is not None else None,
    }

# ---------------------------------------------------------------------------
# NEW: MASTER PIPELINE COUPLING FUNCTION FOR APP.PY
# ---------------------------------------------------------------------------

def compute_all_ratios(raw_data: dict) -> dict:
    """
    Master orchestration function called by app.py.
    Combines input components, maps key differences, sets safe fallbacks,
    and returns aggregated calculation summaries for the visual UI.
    """
    meta = raw_data.get("metadata", {})
    fin = raw_data.get("financials", {})
    
    sales_series = fin.get("sales", [1.0])
    n = len(sales_series)
    
    # Standardize flat data mapping layer for custom imports
    d = {
        "sales": sales_series,
        "operating_profit": fin.get("operating_profit", [0.0] * n),
        "net_profit": fin.get("net_profit", [0.0] * n),
        "pbt": fin.get("pbt", fin.get("net_profit", [0.0] * n)),
        "depreciation": fin.get("depreciation", [0.0] * n),
        "interest": fin.get("interest", [0.0] * n),
        "tax": fin.get("tax", [0.0] * n),
        "cfo": fin.get("cfo", fin.get("operating_cash_flow", [0.0] * n)),
        "capex": fin.get("capex", [0.0] * n),
        "borrowings": fin.get("borrowings", [0.0] * n),
        "cash": fin.get("cash", [0.0] * n),
        "debtors": fin.get("debtors", [0.0] * n),
        "inventory": fin.get("inventory", [0.0] * n),
        "net_block": fin.get("net_block", fin.get("fixed_assets", [1.0] * n)),
        "other_liabilities": fin.get("other_liabilities", [0.0] * n),
        "depreciation_pct_nfa": fin.get("depreciation_pct_nfa", [0.0] * n),
        "equity_capital": fin.get("equity_capital", fin.get("equity", [1.0] * n)),
        "reserves": fin.get("reserves", [0.0] * n),
        "current_price": meta.get("current_price", 100.0),
        "govt_bond_yield": meta.get("gsec_yield", 0.071),
        "eps": fin.get("eps", [meta.get("eps", 1.0)] * n),
        "price": fin.get("price", [meta.get("current_price", 100.0)] * n),
        "dividend_payout": fin.get("dividend_payout", [meta.get("dpr", 0.3)] * n),
        "governance_flags": raw_data.get("red_flags", {})
    }

    # Guard against any None slipping into a zero-default field (yfinance
    # sometimes returns None rather than omitting the key entirely).
    for key in (
        "sales", "operating_profit", "net_profit", "pbt", "interest", "tax",
        "cfo", "capex", "borrowings", "cash", "debtors", "inventory",
        "net_block", "other_liabilities", "depreciation_pct_nfa",
        "equity_capital", "reserves", "eps", "price", "dividend_payout",
    ):
        d[key] = [v if v is not None else 0.0 for v in d[key]]
    
    # Fire off individual computation sequences
    m_out = margins(d)
    l_out = leverage(d)
    r_out = returns_ratios(d)
    f_out = fcf_metrics(d)
    s_out = ssgr(d)
    v_out = relative_valuation(d)
    i_out = intrinsic_value_range(d)
    
    latest_roe = r_out["roe"][-1] if r_out["roe"] else 0.0
    latest_fcf_to_sales = f_out["fcf_to_sales"][-1] if f_out["fcf_to_sales"] else 0.0
    
    return {
        "sales_cagr_3y": multi_horizon_cagr(d["sales"]).get("3y", 0.0),
        "sales_cagr_9y": multi_horizon_cagr(d["sales"]).get("9y", 0.0),
        "growth_consistency": growth_consistency(d["sales"]),
        "latest_operating_margin": m_out["operating_margin"][-1] if m_out["operating_margin"] else 0.0,
        "latest_net_margin": m_out["net_margin"][-1] if m_out["net_margin"] else 0.0,
        "latest_debt_to_equity": l_out["debt_to_equity"][-1] if l_out["debt_to_equity"] else 0.0,
        "latest_interest_coverage": l_out["interest_coverage"][-1] if l_out["interest_coverage"] else float("inf"),
        "latest_roe": latest_roe,
        "latest_roce": r_out["roce"][-1] if r_out["roce"] else 0.0,
        "latest_fcf": f_out["fcf"][-1] if f_out["fcf"] else 0.0,
        "latest_fcf_to_sales": latest_fcf_to_sales,
        "latest_ssgr": s_out[-1] if s_out else 0.0,
        "profitability_matrix": profitability_matrix(latest_roe, latest_fcf_to_sales),
        "relative_valuation": v_out,
        "intrinsic_value_range": i_out
    }
