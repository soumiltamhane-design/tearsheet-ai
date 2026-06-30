import os, json, time
import yfinance as yf
import pandas as pd
import streamlit as st

TICKER_ALIASES = {
    "BAJAJ-AUTO": "bajaj_auto", "BAJAJAUTO": "bajaj_auto", "BAJAJ AUTO": "bajaj_auto",
    "HEROMOTOCO": "hero_motocorp", "HERO MOTOCORP": "hero_motocorp",
}

SAMPLE_DATA = {
    "bajaj_auto": {
        "company": "Bajaj Auto Ltd", "sector": "Automobiles - Two & Three Wheelers",
        "face_value": 10, "current_price": 2900, "govt_bond_yield": 0.0668,
        "years": [2011,2012,2013,2014,2015,2016,2017,2018,2019,2020],
        "sales": [16407.62,19582.1,20025.24,20136.94,21595.44,22573.69,21754.72,26109.69,29917.75,27087.0],
        "operating_profit": [3158.47,3680.75,3648.48,4155.2,3932.17,4787.91,4423.0,4975.0,5132.0,4845.0],
        "other_income": [1405.78,501.83,797.13,681.81,424.73,1199.19,1472.7,1417.0,1516.0,1673.0],
        "interest": [2.39,22.79,1.19,0.82,6.49,1.05,1.4,1.31,4.48,3.16],
        "pbt": [4437.97,4013.06,4276.61,4654.87,4082.95,5678.89,5587.55,5933.41,6306.0,5921.0],
        "tax": [1006.29,1019.66,1228.52,1420.47,1271.05,1617.65,1508.07,1714.47,1594.0,1489.0],
        "net_profit": [3431.68,2993.4,3048.09,3234.4,2811.9,4061.24,4079.48,4218.94,4712.0,4432.0],
        "eps": [118.58,103.43,105.32,111.76,97.16,140.33,140.96,145.78,170.27,152.59],
        "price": [1463.25,1678.8,1799.55,2083.6,2016.6,2405.95,2805.45,2744.7,2905.0,2900.0],
        "dividend_payout": [0.3373,0.435,0.4272,0.4473,0.5145,0.3919,0.3901,0.4,0.4,0.42],
        "equity_capital": [289.37,289.37,289.37,289.37,289.37,289.37,289.37,289.37,289.37,289.37],
        "reserves": [4517.85,5792.35,7775.93,9877.89,10805.95,13730.94,17567.2,19000.0,21000.0,23000.0],
        "borrowings": [347.44,150.47,115.58,59.19,112.35,117.86,119.9,120.77,100.0,80.0],
        "other_liabilities": [3994.38,4894.2,4461.44,5081.31,4757.93,3102.2,3661.0,4000.0,4200.0,4100.0],
        "net_block": [1855.21,1920.03,2355.41,2659.62,2448.03,2025.67,2001.79,1900.0,1800.0,1750.0],
        "investments": [4210.92,4472.78,6058.92,8447.77,8985.25,11067.23,15477.0,17000.0,19000.0,21000.0],
        "debtors": [338.74,401.93,734.33,796.21,716.96,717.93,953.29,1491.87,1600.0,1500.0],
        "inventory": [576.25,703.61,643.96,641.21,814.15,719.07,728.38,742.58,800.0,750.0],
        "cash": [934.37,2756.44,3277.84,2790.6,6393.3,2085.35,6351.44,6558.07,7000.0,8000.0],
        "cfo": [1639.37,3246.27,2218.3,3501.71,2113.8,3689.85,3267.36,4327.84,4500.0,4200.0],
        "capex": [162.66,86.88,488.18,212.78,253.17,259.4,190.79,169.5,150.0,140.0],
        "governance_flags": {"promoter_pledge_pct":0.0,"promoter_holding_change_yoy":0.0,"share_dilution_pct_yoy":0.0,"auditor_changed_last_5y":False,"related_party_transactions_flag":False,"results_delayed_flag":False}
    },
    "hero_motocorp": {
        "company": "Hero Motocorp Ltd", "sector": "Automobiles - Two & Three Wheelers",
        "face_value": 2, "current_price": 2381.75, "govt_bond_yield": 0.0668,
        "years": [2011,2012,2013,2014,2015,2016,2017,2018,2019],
        "sales": [19397.93,23579.03,23768.11,25275.47,27585.3,28442.7,28500.46,31030.0,29700.0],
        "operating_profit": [2419.93,2886.01,2541.11,2879.07,3339.91,4439.76,4660.0,4800.0,4200.0],
        "other_income": [289.62,364.57,398.38,446.38,492.74,422.43,522.43,525.8,550.0],
        "interest": [15.17,21.3,11.91,11.82,11.09,4.89,6.05,6.25,8.6],
        "pbt": [2404.76,2864.71,2529.2,2867.25,3328.82,4434.87,4658.46,5244.16,4800.0],
        "tax": [476.86,486.58,411.04,758.17,943.18,1274.68,1281.34,1546.8,1300.0],
        "net_profit": [1927.9,2378.13,2118.16,2109.08,2385.64,3160.19,3377.12,3697.0,3500.0],
        "eps": [96.55,119.09,106.07,105.62,119.47,158.25,169.11,185.15,169.47],
        "price": [1589.45,2055.25,1542.0,2274.8,2639.8,2945.7,3221.95,3542.8,2381.75],
        "dividend_payout": [1.0876,0.3779,0.5657,0.6155,0.5023,0.455,0.5026,0.5,0.45],
        "equity_capital": [39.94,39.94,39.94,39.94,39.94,39.94,39.94,39.94,39.94],
        "reserves": [2916.12,4249.89,4966.3,5559.93,6501.39,8794.47,10071.35,11000.0,12000.0],
        "borrowings": [693.35,719.44,641.58,284.26,0.0,0.0,0.0,0.0,0.0],
        "other_liabilities": [7082.8,4886.14,4001.16,4217.97,3986.68,3796.17,4640.0,5000.0,4800.0],
        "net_block": [4080.28,3785.51,3070.98,2243.25,2912.69,3584.35,4395.59,4500.0,4400.0],
        "investments": [5128.75,3964.26,3623.83,4088.77,3154.11,4581.02,5889.85,6500.0,7000.0],
        "debtors": [130.59,272.31,665.0,920.58,1389.59,1282.8,1561.87,1520.18,1400.0],
        "inventory": [524.93,675.57,636.76,669.55,815.49,672.98,656.31,823.58,800.0],
        "cash": [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
        "cfo": [2254.16,2359.78,1890.43,2963.41,2250.0,3849.14,4028.02,3980.86,3500.0],
        "capex": [2825.7,791.45,450.47,1071.66,1067.85,1002.15,1163.62,667.89,600.0],
        "governance_flags": {"promoter_pledge_pct":0.0,"promoter_holding_change_yoy":0.0,"share_dilution_pct_yoy":0.0,"auditor_changed_last_5y":False,"related_party_transactions_flag":False,"results_delayed_flag":False}
    }
}


def list_available_samples():
    return sorted(list(SAMPLE_DATA.keys()))


def load_sample(key):
    key = TICKER_ALIASES.get(key.upper().strip(), key.lower().strip())
    if key in SAMPLE_DATA:
        return SAMPLE_DATA[key]
    raise FileNotFoundError(f"No sample data for '{key}'")


def _retry_yf_call(fn, *args, max_attempts=3, base_delay=3, **kwargs):
    """Calls fn(*args, **kwargs) with retry + exponential backoff.
    Yahoo Finance rate-limits with 'Too Many Requests' errors that are
    usually transient -- a short wait and retry often succeeds. Raises
    the last error if every attempt fails."""
    last_err = None
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            is_rate_limit = "too many requests" in msg or "rate limit" in msg or "429" in msg
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            if is_rate_limit:
                raise ValueError(
                    "Yahoo Finance is rate-limiting requests right now. "
                    "This is a temporary throttle on their end, not a bug -- "
                    "wait 5-10 minutes and try again, or try the sample companies "
                    "in the meantime."
                ) from e
            raise last_err


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live(ticker):
    """Fetch live data from Yahoo Finance for any NSE stock.
    Cached for 1 hour per ticker -- repeat clicks on the same ticker
    during testing/demo won't re-hit Yahoo at all, which is the main
    thing that triggers rate limiting."""
    # Add .NS suffix for NSE stocks if not present
    yf_ticker = ticker.upper()
    if not yf_ticker.endswith(".NS") and not yf_ticker.endswith(".BO"):
        yf_ticker = yf_ticker + ".NS"

    stock = yf.Ticker(yf_ticker)

    def _get_info():
        i = stock.info
        if not i:  # yfinance sometimes returns None/{} silently instead of raising
            raise ValueError("Empty info response from Yahoo Finance")
        return i

    try:
        info = _retry_yf_call(_get_info)
    except Exception:
        info = {}  # fall back to empty metadata rather than crashing the whole fetch

    # Get financials
    income = _retry_yf_call(lambda: stock.financials)        # Annual P&L
    balance = _retry_yf_call(lambda: stock.balance_sheet)    # Annual Balance Sheet
    cashflow = _retry_yf_call(lambda: stock.cashflow)        # Annual Cash Flow

    if income is None or income.empty:
        raise ValueError(f"No financial data found for {ticker}. Try the exact NSE ticker symbol.")

    # Extract years (columns are dates, newest first)
    years = [d.year for d in income.columns]

    def safe_row(df, *keys):
        for k in keys:
            for col in df.index:
                if k.lower() in col.lower():
                    vals = df.loc[col].fillna(0).tolist()
                    return [round(v / 1e7, 2) for v in vals]  # Convert to Crores
        return [0] * len(years)

    sales          = safe_row(income, "Total Revenue", "Revenue")
    op_profit      = safe_row(income, "Operating Income", "EBIT")
    other_income   = safe_row(income, "Other Income", "Non Operating")
    interest       = safe_row(income, "Interest Expense")
    pbt            = safe_row(income, "Pretax Income")
    tax            = safe_row(income, "Tax Provision", "Income Tax")
    net_profit     = safe_row(income, "Net Income")
    equity_capital = safe_row(balance, "Common Stock", "Share Capital")
    reserves       = safe_row(balance, "Retained Earnings", "Stockholders Equity")
    borrowings     = safe_row(balance, "Long Term Debt", "Total Debt")
    net_block      = safe_row(balance, "Net PPE", "Property Plant Equipment")
    investments    = safe_row(balance, "Investments", "Long Term Investments")
    debtors        = safe_row(balance, "Receivables", "Accounts Receivable")
    inventory      = safe_row(balance, "Inventory")
    cash           = safe_row(balance, "Cash", "Cash And Cash Equivalents")
    cfo            = safe_row(cashflow, "Operating Cash Flow", "Cash From Operations")
    capex          = safe_row(cashflow, "Capital Expenditure", "Purchase Of PPE")
    other_liab     = safe_row(balance, "Other Liabilities", "Current Liabilities")

    # EPS and price history
    eps_raw = safe_row(income, "Basic EPS", "Diluted EPS")
    if all(v == 0 for v in eps_raw):
        shares = info.get("sharesOutstanding", 1)
        eps_raw = [round((p * 1e7) / shares, 2) if shares else 0 for p in net_profit]

    price_hist = _retry_yf_call(lambda: stock.history(period="5y", interval="1mo"))
    if not price_hist.empty:
        current_price = round(price_hist["Close"].iloc[-1], 2)
    else:
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))

    # Build price list per year (approximate year-end close)
    prices = []
    for y in years:
        try:
            yr_data = price_hist[price_hist.index.year == y]
            prices.append(round(yr_data["Close"].iloc[-1], 2) if not yr_data.empty else current_price)
        except:
            prices.append(current_price)

    company_name = info.get("longName", ticker)
    sector = info.get("sector", info.get("industry", "Unknown Sector"))
    face_value = info.get("bookValue", 10)

    # Dividend payout ratio
    div_payout = []
    for i in range(len(years)):
        try:
            np = net_profit[i]
            div = info.get("dividendRate", 0) or 0
            shares = info.get("sharesOutstanding", 1e8)
            total_div = div * shares / 1e7
            div_payout.append(round(total_div / np, 4) if np > 0 else 0)
        except:
            div_payout.append(0)

    return {
        "company": company_name,
        "sector": sector,
        "face_value": face_value,
        "current_price": current_price,
        "govt_bond_yield": 0.0725,
        "years": years,
        "sales": sales,
        "operating_profit": op_profit,
        "other_income": other_income,
        "interest": interest,
        "pbt": pbt,
        "tax": tax,
        "net_profit": net_profit,
        "eps": eps_raw,
        "price": prices,
        "dividend_payout": div_payout,
        "equity_capital": equity_capital,
        "reserves": reserves,
        "borrowings": borrowings,
        "other_liabilities": other_liab,
        "net_block": net_block,
        "investments": investments,
        "debtors": debtors,
        "inventory": inventory,
        "cash": cash,
        "cfo": cfo,
        "capex": capex,
        "governance_flags": {
            "promoter_pledge_pct": 0.0,
            "promoter_holding_change_yoy": 0.0,
            "share_dilution_pct_yoy": 0.0,
            "auditor_changed_last_5y": False,
            "related_party_transactions_flag": False,
            "results_delayed_flag": False
        }
    }
