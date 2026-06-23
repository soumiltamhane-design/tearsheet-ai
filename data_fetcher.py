"""
data_fetcher.py
-----------------
Data ingestion layer. Two modes:

1. load_sample(ticker) -- loads the bundled JSON files in sample_data/.
   This is what the Streamlit demo uses out of the box, since this
   sandbox's network is locked down to package registries only (no
   general internet access) and can't reach screener.in or nseindia.com.

2. fetch_live(ticker) -- a documented stub for when you run this on your
   own machine, which has normal internet access. Both Excel templates
   you supplied already build their data off Screener.in's export, so
   the fastest path is to replicate that, not invent a new source.

LIVE DATA NOTES (do this on your own machine, not in a Claude sandbox):

- Fundamentals (P&L, Balance Sheet, Cash Flow, 10y history):
  Screener.in exports a clean Excel per company from
  https://www.screener.in/company/<TICKER>/consolidated/ (the "Export to
  Excel" button). You already have two templates that consume exactly
  this shape of data -- the fastest v1 is to automate that export with
  Selenium/Playwright (requires a logged-in session, premium plan gives
  more years of history) and feed the same cells this engine already
  expects. Check screener.in's terms before doing this beyond personal
  use, especially before charging anyone for it.

- Price & technical (DMA, % delivery, volume):
  `nsepython` or `jugaad-data` pull this from NSE's own public bhavcopy
  files. No login needed, free, but bhavcopy URLs and formats drift --
  expect a few hours of glue code, not a turnkey pip install.

- FII/DII flows & derivatives positioning (the Edelweiss-layer data):
  This is the hardest one to get for free at the granularity the
  Edelweiss screener has. NSE publishes daily participant-wise OI and
  FII/DII provisional figures as public PDFs/CSVs on nseindia.com --
  parseable, but undocumented and changes format occasionally. Anything
  better than that (real-time, cleaner) is a paid vendor (Trendlyne,
  Tijori, or a Bloomberg/Refinitiv terminal if you have institutional
  access through coursework).

- Annual report / concall text for the AI reasoning layer:
  BSE/NSE corporate announcements pages host the PDFs directly; pull the
  latest annual report + last 2-3 concall transcripts (many companies
  post these on their own IR pages) and pass extracted text into
  ai_reasoning.analyze()'s `qualitative_context` argument.
"""

from __future__ import annotations
import json
import os

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

TICKER_ALIASES = {
    "BAJAJ-AUTO": "bajaj_auto", "BAJAJAUTO": "bajaj_auto", "BAJAJ AUTO": "bajaj_auto",
    "HEROMOTOCO": "hero_motocorp", "HERO MOTOCORP": "hero_motocorp", "HEROMOTOCORP": "hero_motocorp",
}


def list_available_samples() -> list[str]:
    files = [f[:-5] for f in os.listdir(SAMPLE_DIR) if f.endswith(".json")]
    return sorted(files)


def load_sample(key: str) -> dict:
    key = TICKER_ALIASES.get(key.upper().strip(), key.lower().strip())
    path = os.path.join(SAMPLE_DIR, f"{key}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No sample data for '{key}'. Available: {list_available_samples()}. "
            f"Wire up fetch_live() to pull a new ticker once you're running this "
            f"outside the sandbox."
        )
    with open(path) as f:
        return json.load(f)


def fetch_live(ticker: str) -> dict:
    """Placeholder -- see the module docstring. Raises on purpose so it's
    obvious this needs to be implemented with real network access before
    the tool works on arbitrary tickers."""
    raise NotImplementedError(
        "Live fetching isn't wired up in this prototype. Run this module "
        "outside the sandbox and implement the Screener.in/NSE calls "
        "described in the module docstring, then point app.py at this "
        "function instead of load_sample()."
    )
