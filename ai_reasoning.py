"""
ai_reasoning.py
----------------
The judgment layer using Google's FREE Gemini API (no credit card needed).
Scores moat/governance qualitatively and writes the narrative tear sheet.

Every analysis costs $0. Gemini gives 1500 free requests/day.
"""

from __future__ import annotations
import os
import json

SYSTEM_PROMPT = """You are a buy-side equity research associate scoring a stock against a specific checklist.

Score MOAT (0-100) using: consumer monopoly, pricing power, competitive advantage durability, 
capital allocation discipline, low reinvestment need, competitive intensity.

Score GOVERNANCE (0-100) using red flags: promoter pledging, insider selling, rising receivables, 
related-party transactions, auditor changes, delayed results, opaque entities.

Write narrative fields (thesis, catalysts, risks) as internal tear sheet commentary — specific, 
willing to state uncertainty. Keep responses concise and actionable.

Return ONLY valid JSON, no markdown fences:
{
  "moat_score": <0-100>,
  "moat_rationale": "<2-3 sentences>",
  "governance_score": <0-100>,
  "red_flags": ["<flag>", ...],
  "thesis": "<2-3 sentences>",
  "uncertainties": "<1-2 sentences>",
  "catalysts_3_to_7y": "<1-2 sentences>",
  "downside_risks": "<1-2 sentences>",
  "core_or_satellite_view": "<1 sentence>"
}
"""


def analyze(company: str, sector: str, quant_summary: dict, qualitative_context: str = "") -> dict:
    """Call Google Gemini API (free) to score moat/governance and generate narrative."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _stub_response(company, reason="No GEMINI_API_KEY in environment")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        user_prompt = f"""Company: {company}
Sector: {sector}

Quantitative summary:
{json.dumps(quant_summary, indent=2)}

{"Qualitative context: " + qualitative_context if qualitative_context else "(No additional context provided)"}

Analyze this stock across moat quality, governance/red flags, and investment thesis. 
Return only JSON, no other text."""
        
        response = model.generate_content(
            user_prompt,
            system_instruction=SYSTEM_PROMPT,
            generation_config={"temperature": 0.7, "max_output_tokens": 800}
        )
        
        text = response.text.strip()
        # Clean markdown fences if present
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        
        parsed = json.loads(text)
        return parsed
        
    except Exception as e:
        return _stub_response(company, reason=f"Gemini API error: {str(e)[:50]}")


def _stub_response(company: str, reason: str) -> dict:
    """Fallback when API isn't available."""
    return {
        "moat_score": 50,
        "moat_rationale": f"[Could not connect to Gemini API: {reason}. Showing neutral score.]",
        "governance_score": 70,
        "red_flags": [],
        "thesis": f"[AI analysis unavailable] Refer to quantitative pillars above.",
        "uncertainties": "[Gemini API not accessible]",
        "catalysts_3_to_7y": "[Gemini API not accessible]",
        "downside_risks": "[Gemini API not accessible]",
        "core_or_satellite_view": "[Gemini API not accessible]",
        "_stub": True,
    }
