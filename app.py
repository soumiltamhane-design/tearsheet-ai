import streamlit as st
import data_fetcher as df
import quant_engine as qe
import scoring_engine as se
import ai_reasoning as ar

st.set_page_config(page_title="Institutional Tear Sheet AI", layout="wide")

st.title("📊 Institutional-Grade Investment Analysis Tool")
st.subheader("Unified Research Stack: Macro → Moat → Quant → Valuation → Governance")

# Left Sidebar Controls
st.sidebar.header("Control Panel")

analysis_mode = st.sidebar.radio(
    "Select Data Input Method:",
    ["Use Preloaded Demo Stocks", "Upload any Screener.in Excel (Open Market)"]
)

raw_data = None

if analysis_mode == "Use Preloaded Demo Stocks":
    company_choice = st.sidebar.selectbox("Choose Company:", ["Bajaj Auto", "Hero MotoCorp"])
    ticker_map = {"Bajaj Auto": "bajaj_auto", "Hero MotoCorp": "hero_motocorp"}
    raw_data = df.load_sample(ticker_map[company_choice])
else:
    uploaded_file = st.sidebar.file_uploader("Upload 'Export to Excel' file from Screener.in", type=["xlsx", "xlsm"])
    if uploaded_file is not None:
        try:
            raw_data = df.parse_screener_excel(uploaded_file)
            st.sidebar.success(f"Successfully loaded parsed data!")
        except Exception as e:
            st.sidebar.error(f"Error parsing file: {e}")

ai_mode = st.sidebar.selectbox("AI Commentary Mode:", ["Free: copy-paste into Claude.ai", "Paid API Key"])
api_key = ""
if ai_mode == "Paid API Key":
    api_key = st.sidebar.text_input("Enter Anthropic API Key:", type="password")

# Run Pipeline Execution
if raw_data and st.sidebar.button("Run Comprehensive Analysis", type="primary"):
    
    # 1. Run the universal math/quant engine
    metrics = qe.compute_all_ratios(raw_data) # Automatically maps metrics, DuPont, and SSGR
    
    # 2. Run the scoring engine weights and the Governance Veto check
    final_score, pillar_scores, veto_triggered = se.score_investment(raw_data, metrics)
    
    # Visual Layout Output (The Gulf Oil Template Style)
    st.header(f"Investment Tear Sheet: {raw_data['metadata']['company_name']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"₹{raw_data['metadata']['current_price']}")
    col2.metric("Market Cap", f"₹{raw_data['metadata']['market_cap_cr']} Cr")
    
    if veto_triggered:
        col3.error("FINAL CALL: AVOID (Governance Veto)")
    else:
        if final_score >= 70:
            col3.success(f"FINAL CALL: BUY / CORE HOLDING ({final_score}/100)")
        elif final_score >= 50:
            col3.warning(f"FINAL CALL: TACTICAL / SATELLITE ({final_score}/100)")
        else:
            col3.error(f"FINAL CALL: AVOID ({final_score}/100)")

    # Pillar Scores Table Layout
    st.subheader("🛡️ Research Pillar Breakdown")
    st.table(pillar_scores)
    
    # AI Free Copy Paste Section
    st.subheader("🤖 AI Reasoning Layer")
    if ai_mode == "Free: copy-paste into Claude.ai":
        st.info("Copy the block below and paste it into Claude to get your institutional narrative summary for free:")
        
        # Format a beautifully clear prompt template for the user to copy
        prompt_payload = f"""
        I am analyzing {raw_data['metadata']['company_name']} ({raw_data['metadata']['sector']}).
        Here is the computed quantitative data: {metrics}
        Please provide a narrative teardown covering: Moat quality, pricing power, catalysts, downside risks, and structural uncertainties.
        """
        st.code(prompt_payload, language="text")
        
        user_reply = st.text_area("Paste Claude's response here to print it on the final report PDF:")
        if user_reply:
            st.write(user_reply)
            
    elif ai_mode == "Paid API Key" and api_key:
        with st.spinner("Claude is analyzing financial statements..."):
            ai_analysis = ar.analyze_with_claude(raw_data, metrics, api_key)
            st.write(ai_analysis)
            
    # Audit Trail Expanded View
    with st.expander("🔍 View Raw Quant Engine Audit Trail"):
        st.json(metrics)

elif not raw_data:
    st.info("Please select a preloaded stock or upload a Screener.in Excel sheet from the sidebar to begin.")
