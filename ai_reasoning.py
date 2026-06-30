import os, json

def _json_safe(obj):
    """Fallback for json.dumps when it hits a type it doesn't recognize --
    mainly numpy.bool_, numpy.int64, numpy.float64 that leak in from the
    yfinance/pandas pipeline. Plain Python bool/int/float serialize fine;
    these numpy-flavored equivalents don't, even though they print
    identically and look like the real thing."""
    if hasattr(obj, "item"):  # numpy scalar types all have .item()
        return obj.item()
    return str(obj)  # last-resort fallback so a single bad value never crashes the whole call


def analyze(company, sector, quant_summary, qualitative_context=""):
    api_key = os.environ.get("GROQ_API_KEY") or "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"
    if not api_key or "YOURKEY" in api_key:
        return _stub_response(company, "No key")
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        quant_json = json.dumps(quant_summary, default=_json_safe)[:2000]
        prompt = "You are a senior equity analyst. Analyze " + company + " (" + sector + ") for an Indian portfolio. Use a FULL 0-100 scale where 50=average Indian listed company, 70=good quality, 85+=exceptional. Bajaj Auto and Hero Motocorp are well-run, profitable, debt-free Indian market leaders with strong moats — score them accordingly (moat 65-80, governance 75-90). Data: " + quant_json + ". Return JSON with these exact keys: moat_score (integer), moat_rationale (2-3 sentences), governance_score (integer), red_flags (list), thesis (2-3 sentences), uncertainties (1-2 sentences), catalysts_3_to_7y (1-2 sentences), downside_risks (1-2 sentences), core_or_satellite_view (1 sentence)"
        r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.3, max_tokens=800, response_format={"type":"json_object"})
        p = json.loads(r.choices[0].message.content)
        for k in ["red_flags","uncertainties","core_or_satellite_view"]:
            p.setdefault(k, "")
        return p
    except Exception as e:
        return _stub_response(company, str(e)[:100])
def _stub_response(company, reason):
    return {"moat_score":50,"moat_rationale":"["+reason+"]","governance_score":70,"red_flags":[],"thesis":"[AI unavailable]","uncertainties":"","catalysts_3_to_7y":"","downside_risks":"","core_or_satellite_view":"","_stub":True}
