import json
import streamlit as st

import data_fetcher as fetcher
import quant_engine as qe
import ai_reasoning as ar
import scoring_engine as se
import excel_parser as excel_fetcher

st.set_page_config(page_title="Tearsheet AI", page_icon="📊", layout="wide")

CALL_COLORS = {
    "Strong Buy": "#1a7f37", "Buy": "#1a7f37", "Hold": "#9a6700",
    "Avoid": "#cf222e", "Sell/Avoid": "#cf222e",
}

st.sidebar.title("📊 Tearsheet AI")
st.sidebar.caption("Ticker in → 6-pillar score → tear sheet out")

mode = st.sidebar.radio("Data source", ["Sample companies", "Live NSE ticker", "Upload Screener Excel"])

uploaded_file = None
use_live = False
use_excel = False

if mode == "Sample companies":
    available = fetcher.list_available_samples()
    choice = st.sidebar.selectbox(
        "Company",
        available,
        format_func=lambda k: k.replace("_", " ").title(),
    )
elif mode == "Live NSE ticker":
    live_ticker = st.sidebar.text_input("NSE Ticker Symbol", placeholder="e.g. RELIANCE, TCS, HDFCBANK")
    choice = live_ticker.strip().upper() if live_ticker else ""
    use_live = True
    st.sidebar.caption("Examples: RELIANCE, TCS, INFY, HDFCBANK, ITC, WIPRO, TATAMOTORS")
else:  # Upload Screener Excel
    uploaded_file = st.sidebar.file_uploader(
        "Upload Screener.in Excel export (.xlsx)",
        type=["xlsx"],
        help="On Screener.in, open the company page and click 'Export to Excel'",
    )
    choice = uploaded_file.name if uploaded_file else ""
    use_excel = True
    st.sidebar.caption("Most accurate option — reads audited figures directly, no live-data guesswork.")

qualitative_context = st.sidebar.text_area(
    "Optional: paste annual report excerpts",
    height=120,
)

run = st.sidebar.button("Run analysis", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.caption(
    "✨ AI layer: Auto-powered by Google Gemini (free). No copy-pasting needed."
)

if not run:
    st.title("Tearsheet AI")
    st.write("Pick a company and hit **Run analysis**.")
    st.info("Validated against Safal Niveshak / Investor Diary Excel templates.", icon="✅")
    st.stop()

with st.spinner("Running quant engine..."):
    if use_live and choice:
        with st.spinner(f"Fetching live data for {choice} from NSE..."):
            try:
                d = fetcher.fetch_live(choice)
            except Exception as e:
                st.error(f"Could not fetch data for {choice}: {e}")
                st.stop()
    elif use_excel:
        if not uploaded_file:
            st.warning("Upload a Screener.in Excel export to run analysis.")
            st.stop()
        with st.spinner("Parsing Screener Excel file..."):
            try:
                d = excel_fetcher.parse_screener_excel(uploaded_file)
            except Exception as e:
                st.error(f"Could not parse this file: {e}")
                st.stop()
    else:
        d = fetcher.load_sample(choice)

    quant_summary = {
        "margins": {k: v[-1] for k, v in qe.margins(d).items()},
        "returns": {k: v[-1] for k, v in qe.returns_ratios(d).items()},
        "leverage": {k: v[-1] for k, v in qe.leverage(d).items()},
        "growth": qe.multi_horizon_cagr(d["sales"]),
        "growth_consistency": qe.growth_consistency(d["net_profit"]),
        "fcf": {k: v[-1] for k, v in qe.fcf_metrics(d).items()},
        "intrinsic_value_range": qe.intrinsic_value_range(d),
         "relative_valuation": qe.relative_valuation(d),
        "two_minute_test": qe.two_minute_test(d),
    }

with st.spinner("Running AI analysis (Gemini)..."):
    ai_out = ar.analyze(d["company"], d["sector"], quant_summary, qualitative_context)

with st.spinner("Computing final score..."):
    result = se.run_full_score(d, ai_output=ai_out)

iv = quant_summary["intrinsic_value_range"]
rv = quant_summary["relative_valuation"]
roe_latest = quant_summary["returns"]["roe"]
fcf_to_sales_latest = quant_summary["fcf"]["fcf_to_sales"]
quadrant = qe.profitability_matrix(roe_latest, fcf_to_sales_latest)

col1, col2 = st.columns([3, 1])
with col1:
    st.title(d["company"])
    st.caption(f"{d['sector']}  ·  CMP ₹{d['current_price']:,.0f}  ·  Mcap ₹{iv['current_market_cap']:,.0f} cr")
with col2:
    call = result["recommendation"]["call"]
    color = CALL_COLORS.get(call, "#57606a")
    st.markdown(
        f"<div style='text-align:right'>"
        f"<span style='background:{color}22;color:{color};padding:6px 14px;border-radius:8px;font-weight:600;font-size:15px'>"
        f"{call} · {result['composite_score']}/100</span><br>"
        f"<span style='color:#57606a;font-size:13px'>{result['recommendation']['core_or_satellite']} position</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

if result["red_flags"]["veto"]:
    st.error(f"⚠️ Red-flag override: {', '.join(result['red_flags']['hard_flags'])}")

st.divider()

st.subheader("Pillar scores")
cols = st.columns(6)
labels = {"moat": "Moat & quality", "financial_health": "Financial health", "growth": "Growth",
          "valuation": "Valuation", "technical": "Technical & flows", "governance": "Governance"}
for col, (key, label) in zip(cols, labels.items()):
    col.metric(label, f"{result['pillar_scores'][key]:.0f}")
st.caption(f"Profitability: **{quadrant}**")

st.divider()

st.subheader("Intrinsic value range vs current price")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ben Graham", f"₹{iv['ben_graham_range'][0]:,.0f}–{iv['ben_graham_range'][1]:,.0f} cr")
c2.metric("DCF", f"₹{iv['dcf_value']:,.0f} cr")
c3.metric("Dhandho", f"₹{iv['dhandho_range'][0]:,.0f}–{iv['dhandho_range'][1]:,.0f} cr")
c4.metric("Expected Returns", f"₹{iv['expected_returns_value']:,.0f} cr")

low, high, mcap = iv["iv_low"], iv["iv_high"], iv["current_market_cap"]
pos = max(0.0, min(1.0, (mcap - low) / (high - low))) if high > low else 0.5
st.markdown(
    f"<div style='position:relative;height:24px;margin:8px 0;'>"
    f"<div style='position:absolute;left:0;top:9px;width:100%;height:6px;background:#eaeef2;border-radius:3px;'></div>"
    f"<div style='position:absolute;left:0;top:9px;width:100%;height:6px;background:#1a7f37;border-radius:3px;opacity:0.5;'></div>"
    f"<div style='position:absolute;left:{pos*100:.1f}%;top:0;width:3px;height:24px;background:#1f2328;'></div>"
    f"</div>"
    f"<div style='display:flex;justify-content:space-between;color:#57606a;font-size:13px'>"
    f"<span>Low: ₹{low:,.0f} cr</span><span>Current: ₹{mcap:,.0f} cr</span><span>High: ₹{high:,.0f} cr</span>"
    f"</div>",
    unsafe_allow_html=True,
)

st.divider()

st.subheader("Red flags")
all_flags = result["red_flags"]["hard_flags"] + result["red_flags"]["soft_flags"]
if all_flags:
    st.write(" ".join(f"`{f}`" for f in all_flags))
else:
    st.success("No red flags triggered.")

st.divider()

st.subheader("AI reasoning (Gemini-powered)")

if ai_out.get("_stub"):
    st.warning(ai_out["moat_rationale"])
else:
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Moat Score (AI)", f"{ai_out['moat_score']}/100")
    with col2:
        st.metric("Governance Score (AI)", f"{ai_out['governance_score']}/100")
    
    st.markdown(f"**Moat rationale** — {ai_out['moat_rationale']}")
    st.markdown(f"**Thesis** — {ai_out['thesis']}")
    st.markdown(f"**Uncertainties** — {ai_out['uncertainties']}")
    st.markdown(f"**3–7y catalysts** — {ai_out['catalysts_3_to_7y']}")
    st.markdown(f"**Downside risks** — {ai_out['downside_risks']}")
    st.markdown(f"**Core/satellite view** — {ai_out['core_or_satellite_view']}")
    
    if ai_out.get("red_flags"):
        st.warning(f"🚩 Red flags: {', '.join(ai_out['red_flags'])}")

with st.expander("Raw quant engine output (audit trail)"):
    st.json(quant_summary)
