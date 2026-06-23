from __future__ import annotations
import json
import os
import pandas as pd
from typing import Dict, Any

# =====================================================================
# 1. EMBEDDED GROUND TRUTH (Prevents initial Streamlit Cloud crashes)
# =====================================================================
BAJAJ_AUTO_DATA = {
    "metadata": {
        "ticker": "BAJAJ-AUTO", "company_name": "Bajaj Auto Ltd.", "sector": "Automobiles",
        "current_price": 8200.0, "market_cap_cr": 225000.0, "pe_ratio": 29.5,
        "pb_ratio": 7.8, "ps_ratio": 5.0, "historical_pe_median": 22.0,
        "gsec_yield": 0.071, "eps": 278.0, "dpr": 0.55
    },
    "financials": {
        "years": ["FY16", "FY17", "FY18", "FY19", "FY20", "FY21", "FY22", "FY23", "FY24"],
        "sales": [22688, 21767, 25165, 30358, 29919, 27741, 33145, 36428, 44685],
        "operating_profit": [4643, 4424, 4982, 5387, 5253, 4928, 5383, 6551, 8825],
        "net_profit": [3930, 3828, 4068, 4675, 5100, 4555, 5019, 5628, 7479],
        "depreciation": [307, 307, 315, 258, 246, 259, 269, 282, 338],
        "interest": [1, 1, 1, 2, 3, 7, 9, 39, 45],
        "equity": [13282, 17578, 19106, 21782, 19927, 25203, 26669, 25424, 28863],
        "borrowings": [121, 119, 122, 125, 125, 121, 123, 125, 120],
        "total_assets": [15120, 19400, 21500, 24200, 22500, 28100, 30200, 29500, 33400],
        "fixed_assets": [1825, 1780, 1850, 1800, 1750, 1700, 1680, 1720, 1890],
        "operating_cash_flow": [3500, 4100, 4200, 4800, 5000, 3800, 4900, 5800, 7800],
        "capex": [300, 250, 280, 200, 220, 250, 210, 290, 400]
    },
    "red_flags": {
        "pledged_shares_detected": False, "insider_selling_spike": False,
        "receivables_accumulating": False, "related_party_transactions_flagged": False,
        "auditor_abrupt_change": False, "concall_silence": False
    }
}

HERO_MOTOCORP_DATA = {
    "metadata": {
        "ticker": "HEROMOCORP", "company_name": "Hero MotoCorp Ltd.", "sector": "Automobiles",
        "current_price": 4600.0, "market_cap_cr": 92000.0, "pe_ratio": 24.1,
        "pb_ratio": 5.0, "ps_ratio": 2.4, "historical_pe_median": 19.5,
        "gsec_yield": 0.071, "eps": 190.0, "dpr": 0.60
    },
    "financials": {
        "years": ["FY16", "FY17", "FY18", "FY19", "FY20", "FY21", "FY22", "FY23", "FY24"],
        "sales": [28443, 28500, 32230, 33651, 28836, 30801, 29245, 33806, 37456],
        "operating_profit": [4541, 4615, 5280, 4930, 3950, 4019, 3370, 3986, 5250],
        "net_profit": [3132, 3377, 3697, 3385, 3633, 2964, 2477, 2911, 3968],
        "depreciation": [440, 493, 556, 602, 678, 677, 650, 657, 698],
        "interest": [5, 6, 6, 9, 15, 22, 26, 20, 18],
        "equity": [8621, 10110, 11770, 12857, 14095, 15198, 15783, 16675, 18500],
        "borrowings": [0, 0, 0, 0, 0, 0, 0, 0, 0],
        "total_assets": [10500, 12400, 14200, 15500, 16800, 18100, 18900, 19800, 22000],
        "fixed_assets": [4500, 4700, 5100, 5300, 5500, 5400, 5300, 5200, 5400],
        "operating_cash_flow": [3800, 4200, 5100, 3200, 4100, 3500, 2400, 4500, 5100],
        "capex": [600, 750, 800, 700, 500, 600, 400, 550, 650]
    },
    "red_flags": {
        "pledged_shares_detected": False, "insider_selling_spike": False,
        "receivables_accumulating": False, "related_party_transactions_flagged": False,
        "auditor_abrupt_change": False, "concall_silence": False
    }
}

TICKER_ALIASES = {
    "BAJAJ-AUTO": "bajaj_auto", "BAJAJAUTO": "bajaj_auto", "BAJAJ AUTO": "bajaj_auto",
    "HEROMOTOCO": "hero_motocorp", "HERO MOTOCORP": "hero_motocorp", "HEROMOTOCORP": "hero_motocorp",
}

def list_available_samples() -> list[str]:
    return ["bajaj_auto", "hero_motocorp", "UPLOAD_ANY_SCREENER_EXCEL"]

# =====================================================================
# 2. UNIVERSAL OPEN MARKET EXCEL PARSER
# =====================================================================
def parse_screener_excel(file_path_or_buffer) -> dict:
    """
    Takes any standard raw Excel file exported directly from Screener.in
    and dynamically turns it into the exact data structure our quant engine needs.
    """
    try:
        # Read Data Sheet where all financial tables live
        df_pnl = pd.read_excel(file_path_or_buffer, sheet_name="Data Sheet", index_col=0)
        
        # Clean index names for mapping
        df_pnl.index = df_pnl.index.str.strip().str.replace(r'\s+', ' ', regex=True)
        
        # Extract target financial metrics dynamically
        def get_row_data(row_variants: list[str]) -> list[float]:
            for variant in row_variants:
                if variant in df_pnl.index:
                    return [float(v) if pd.notnull(v) else 0.0 for v in df_pnl.loc[variant].values]
            return [0.0] * 9

        years_raw = df_pnl.columns.tolist()
        years = [str(y).strip() for y in years_raw if "Unnamed" not in str(y)]
        
        parsed_data = {
            "metadata": {
                "ticker": "CUSTOM_STOCK",
                "company_name": "Uploaded Company",
                "sector": "General Market",
                "current_price": get_row_data(["Current Price", "Price"])[0] if "Current Price" in df_pnl.index else 1000.0,
                "market_cap_cr": get_row_data(["Market Capitalization", "Market Cap"])[0] if "Market Capitalization" in df_pnl.index else 5000.0,
                "pe_ratio": get_row_data(["Stock P/E", "P/E Ratio"])[0] if "Stock P/E" in df_pnl.index else 20.0,
                "pb_ratio": 3.0,
                "ps_ratio": 1.5,
                "historical_pe_median": 20.0,
                "gsec_yield": 0.071,
                "eps": get_row_data(["Earnings Per Share", "EPS"])[0] if "EPS" in df_pnl.index else 50.0,
                "dpr": 0.30
            },
            "financials": {
                "years": years[-9:],  # Keep the last 9 reporting periods
                "sales": get_row_data(["Sales", "Revenue"])[-9:],
                "operating_profit": get_row_data(["Operating Profit", "EBITDA"])[-9:],
                "net_profit": get_row_data(["Net Profit", "PAT"])[-9:],
                "depreciation": get_row_data(["Depreciation"])[-9:],
                "interest": get_row_data(["Interest"])[-9:],
                "equity": get_row_data(["Share Capital", "Equity Share Capital"])[-9:],
                "borrowings": get_row_data(["Borrowings", "Total Debt"])[-9:],
                "total_assets": get_row_data(["Total Liabilities", "Total Assets"])[-9:],
                "fixed_assets": get_row_data(["Fixed Assets"])[-9:],
                "operating_cash_flow": get_row_data(["Cash from Operating Activity", "Net CashFlow from Operating Activities"])[-9:],
                "capex": [abs(x) for x in get_row_data(["Investments in fixed assets", "Capex"])[-9:]]
            },
            "red_flags": {
                "pledged_shares_detected": False,
                "insider_selling_spike": False,
                "receivables_accumulating": False,
                "related_party_transactions_flagged": False,
                "auditor_abrupt_change": False,
                "concall_silence": False
            }
        }
        return parsed_data
    except Exception as e:
        raise ValueError(f"Failed to automatically parse Screener Excel sheet layout: {str(e)}")

# =====================================================================
# 3. COMPATIBILITY ROUTERS FOR THE UI
# =====================================================================
def load_sample(key: str) -> dict:
    """Router that handles fallback data or intercepts raw excel uploads."""
    # If a path or a direct file upload object from Streamlit is passed
    if hasattr(key, 'read') or (isinstance(key, str) and key.endswith(('.xlsx', '.xlsm'))):
        return parse_screener_excel(key)
        
    lookup = TICKER_ALIASES.get(key.upper().strip(), key.lower().strip())
    if lookup == "bajaj_auto":
        return BAJAJ_AUTO_DATA
    elif lookup == "hero_motocorp":
        return HERO_MOTOCORP_DATA
    else:
        # If it's a new ticker string, try checking if it matches a file layout
        raise FileNotFoundError(
            f"Ticker '{key}' not found in demo data. Please use the sidebar "
            f"to upload the Screener.in Excel sheets directly for market-wide analysis."
        )

def fetch_live(ticker_or_file) -> dict:
    """Direct alias to parse sheets for global stock processing."""
    return parse_screener_excel(ticker_or_file)
