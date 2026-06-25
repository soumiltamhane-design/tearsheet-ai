import os, json

def analyze(company, sector, quant_summary, qualitative_context=""):
    api_key = os.environ.get("GROQ_API_KEY") or "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"
    if not api_key or "YOURKEY" in api_key:
        return _stub_response(company, "No key")
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = "You are a senior equity analyst. Analyze " + company + " (" + sector + ") for an Indian portfolio. Use a FULL 0-100 scale where 50=average Indian listed company, 70=good quality, 85+=exceptional. Bajaj Auto and Hero Motocorp are well-run, profitable, debt-free Indian market leaders with strong moats — score them accordingly (moat 65-80, governance 75-90). Data: " + json.dumps(quant_summary)[:2000] + ". Return JSON with these exact keys: moat_score (integer), moat_rationale (2-3 sentences), governance_score (integer), red_flags (list), thesis (2-3 sentences), uncertainties (1-2 sentences), catalysts_3_to_7y (1-2 sentences), downside_risks (1-2 sentences), core_or_satellite_view (1 sentence)"
        r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.3, max_tokens=800, response_format={"type":"json_object"})
        p = json.loads(r.choices[0].message.content)
        for k in ["red_flags","uncertainties","core_or_satellite_view"]:
            p.setdefault(k, "")
        return p
    except Exception as e:
        return _stub_response(company, str(e)[:100])

def _stub_response(company, reason):
    return {"moat_score":50,"moat_rationale":"["+reason+"]","governance_score":70,"red_flags":[],"thesis":"[AI unavailable]","uncertainties":"","catalysts_3_to_7y":"","downside_risks":"","core_or_satellite_view":"","_stub":True}
