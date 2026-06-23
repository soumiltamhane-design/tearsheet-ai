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
    return (values[-1] / values[0]) ** (1 / n) - 1


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
        prev = values[i - 1]
        out.append(None if not prev else (values[i] - prev) / prev)
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
        "operating_margin": [o / s for o, s in zip(op, sales)],
        "pbt_margin": [p / s for p, s in zip(pbt, sales)],
        "net_margin": [n / s for n, s in zip(npft, sales)],
    }


def turnover_ratios(d: dict) -> dict:
    sales = d["sales"]
    debtors = d["debtors"]
    inventory = d["inventory"]
    net_block = d["net_block"]
    return {
        "debtor_days": [365 * deb / s if s else None for deb, s in zip(debtors, sales)],
        "inventory_turnover": [s / inv if inv else None for s, inv in zip(sales, inventory)],
        "fixed_asset_turnover": [s / nb if nb else None for s, nb in zip(sales, net_block)],
    }


# ---------------------------------------------------------------------------
# Leverage & returns
# ---------------------------------------------------------------------------

def equity_series(d: dict) -> list[float]:
    return [ec + r for ec, r in zip(d["equity_capital"], d["reserves"])]


def leverage(d: dict) -> dict:
    eq = equity_series(d)
    borr = d["borrowings"]
    interest = d["interest"]
    pbt = d["pbt"]
    return {
        "debt_to_equity": [b / e if e else None for b, e in zip(borr, eq)],
        "interest_coverage": [
            (p + i) / i if i else float("inf") for p, i in zip(pbt, interest)
        ],
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
        capital_employed = eq[i] + borr[i]
        ebit = pbt[i] + interest[i]
        tax_rate = tax[i] / pbt[i] if pbt[i] else 0
        nopat = ebit * (1 - tax_rate)
        invested_capital = capital_employed - cash[i]

        roe.append(npft[i] / eq[i] if eq[i] else None)
        roce.append(ebit / capital_employed if capital_employed else None)
        roic.append(nopat / invested_capital if invested_capital else None)

    return {"roe": roe, "roce": roce, "roic": roic}


def dupont(d: dict) -> dict:
    """Net margin x asset turnover x financial leverage = ROE."""
    eq = equity_series(d)
    sales = d["sales"]
    npft = d["net_profit"]
    other_liab = d["other_liabilities"]
    borr = d["borrowings"]
    total_assets = [e + b + ol for e, b, ol in zip(eq, borr, other_liab)]

    net_margin = [n / s for n, s in zip(npft, sales)]
    asset_turnover = [s / ta if ta else None for s, ta in zip(sales, total_assets)]
    fin_leverage = [ta / e if e else None for ta, e in zip(total_assets, eq)]
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
    fcf = [c - x for c, x in zip(cfo, capex)]
    return {
        "fcf": fcf,
        "fcf_to_sales": [f / s if s else None for f, s in zip(fcf, sales)],
        "fcf_to_net_profit": [f / n if n else None for f, n in zip(fcf, npft)],
        "cfo_to_capex": [c / x if x else None for c, x in zip(cfo, capex)],
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
        nfat = sales[i] / net_block[i] if net_block[i] else None
        npm = npft[i] / sales[i] if sales[i] else None
        if nfat is None or npm is None:
            out.append(None)
            continue
        out.append(nfat * npm * (1 - dpr[i]) - dep_pct_nfa[i])
    return out


# ---------------------------------------------------------------------------
# The 2-minute test (Greenblatt-style quick screen, Investor Diary sheet)
# ---------------------------------------------------------------------------

def two_minute_test(d: dict) -> dict:
    eq = equity_series(d)
    shares_cr = d["net_profit"][-1] / d["eps"][-1] if d["eps"][-1] else None
    market_cap = (shares_cr * d["current_price"]) if shares_cr else None
    roe = returns_ratios(d)["roe"]
    fcf = fcf_metrics(d)["fcf"]
    de = leverage(d)["debt_to_equity"]

    checks = {
        "min_quality_hurdle": market_cap is not None and market_cap > 500,
        "ever_made_operating_profit": all(op > 0 for op in d["operating_profit"]),
        "consistent_cfo": all(c > 0 for c in d["cfo"]),
        "roe_above_15_with_low_leverage": (
            statistics.mean([r for r in roe if r is not None]) > 0.15
            and (de[-1] or 0) < 1
        ),
        "clean_balance_sheet": (de[-1] or 0) < 1,
        "generates_fcf": fcf[-1] > 0,
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
    pe_series = [p / e for p, e in zip(d["price"], d["eps"]) if e]
    current_pe = d["current_price"] / d["eps"][-1]
    avg_pe = {
        "3y": statistics.mean(pe_series[-3:]),
        "5y": statistics.mean(pe_series[-5:]) if len(pe_series) >= 5 else None,
        "10y": statistics.mean(pe_series[-10:]) if len(pe_series) >= 10 else None,
    }
    cheaper_than_history = current_pe < (avg_pe["5y"] or avg_pe["3y"])

    earnings_yield = d["eps"][-1] / d["current_price"]
    yield_spread = earnings_yield - d["govt_bond_yield"]

    return {
        "current_pe": round(current_pe, 2),
        "avg_pe": {k: (round(v, 2) if v else None) for k, v in avg_pe.items()},
        "cheaper_than_own_history": cheaper_than_history,
        "earnings_yield": round(earnings_yield, 4),
        "govt_bond_yield": d["govt_bond_yield"],
        "yield_spread_vs_bond": round(yield_spread, 4),
        "attractive_vs_bonds": yield_spread > 0,
    }


# ---------------------------------------------------------------------------
# Intrinsic value models
# ---------------------------------------------------------------------------

def ben_graham_value(eps: float, growth_rate: float, pe_no_growth: float = 8.5) -> float:
    """Value = EPS x (8.5 + 2g), g in percentage points (e.g. 10 for 10%)."""
    return eps * (pe_no_growth + 2 * growth_rate * 100)


def dcf_value(
    fcf0: float,
    growth_yr1_5: float,
    growth_yr6_10: float,
    discount_rate: float,
    terminal_growth: float,
    net_debt: float = 0,
) -> dict:
    pv_total = 0.0
    fcf = fcf0
    for yr in range(1, 11):
        g = growth_yr1_5 if yr <= 5 else growth_yr6_10
        fcf = fcf * (1 + g)
        pv = fcf / ((1 + discount_rate) ** yr)
        pv_total += pv
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** 10)
    equity_value = pv_total + pv_terminal - net_debt
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
    pv_total = excess_cash
    fcf = fcf0
    for yr in range(1, 11):
        if yr <= 3:
            g = growth_yr1_3
        elif yr <= 6:
            g = growth_yr4_6
        else:
            g = growth_yr7_10
        fcf = fcf * (1 + g)
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
    future_profit = net_profit0 * (1 + est_cagr_10y) ** 10
    future_mcap = future_profit * exit_pe
    discounted_value = future_mcap / (1 + discount_rate) ** 10
    premium_or_discount = (discounted_value / current_market_cap) - 1
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
    eps0 = d["eps"][-1]
    # Use a 3-year average FCF as the DCF/Dhandho base, not the single
    # latest year -- this matches the "Average FCF (3 Years)" cell both
    # source templates use, and avoids one bad/great year distorting the
    # whole intrinsic value range.
    fcf_series = fcf_metrics(d)["fcf"]
    fcf = statistics.mean(fcf_series[-3:])
    shares_cr = d["net_profit"][-1] / d["eps"][-1]
    market_cap = shares_cr * d["current_price"]
    eq = equity_series(d)
    net_debt = d["borrowings"][-1] - d.get("cash", [0])[-1]

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

    er = expected_returns_value(
        d["net_profit"][-1], npat_cagr_5y, relative_valuation(d)["current_pe"],
        a.get("exit_pe", relative_valuation(d)["avg_pe"]["5y"] or relative_valuation(d)["current_pe"]),
        a.get("discount_rate", 0.12), market_cap
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
        "premium_discount_to_low": round((market_cap / low) - 1, 3) if low else None,
        "premium_discount_to_high": round((market_cap / high) - 1, 3) if high else None,
    }
