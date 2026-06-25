"""
ai_reasoning.py
----------------
AI judgment layer using Google's FREE Gemini API.
Scores moat/governance and writes the narrative tear sheet.
"""
from __future__ import annotations
import os
import json

SYSTEM_PROMPT = """You are a buy-side equity research associate scoring a stock for an Indian investment portfolio.

Score MOAT (0-100) using: consumer monopoly, pricing power, competitive advantage, 
capital allocation discipline, low reinvestment need, competitive intensity.

Score GOVERNANCE (0-100) using red flags: promoter pledging, insider selling, rising 
receivables, related-party transactions, auditor changes, delayed results, opaque entities.

Write narrative fields as internal tear sheet commentary. Be specific and willing to state 
uncertainty. Keep responses concise and actionable.

Return ONLY valid JSON, no markdown fences, no extra text:
{
  "moat_score": <0-100>,
  "moat_rationale": "<2-3 sentences>",
  "governance_score": <0-100>,
  "red_flags": ["<flag1>", "<flag2>"],
  "thesis": "<2-3 sentences on investment thesis>",
  "uncertainties": "<1-2 sentences>",
  "catalysts_3_to_7y": "<1-2 sentences>",
  "downside_risks": "<1-2 sentences>",
  "core_or_satellite_view": "<1 sentence>"
}"""


def analyze(company: str, sector: str, quant_summary: dict, qualitative_context: str = "") -> dict:
    """Call Gemini API to score moat/governance and generate narrative."""

    # Get API key — from environment (secrets) OR hardcoded fallback
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        return _stub_response(company, reason="No API key found in environment")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Try models in order of preference — handles deprecations gracefully
        models_to_try = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-pro",
        ]

        user_prompt = f"""Company: {company}
Sector: {sector}

Quantitative summary (computed from financial statements):
{json.dumps(quant_summary, indent=2)}

{("Additional context: " + qualitative_context) if qualitative_context else "(No additional qualitative context provided)"}

Analyze this Indian stock across moat quality, governance/red flags, and investment thesis.
Return ONLY the JSON object — no markdown, no explanation, nothing else before or after the JSON."""

        last_error = None
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_PROMPT,
                    generation_config={
                        "temperature": 0.4,
                        "max_output_tokens": 1000,
                        "response_mime_type": "application/json",  # Force JSON output
                    }
                )
                response = model.generate_content(user_prompt)
                text = response.text.strip()

                # Clean any accidental markdown fences
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                text = text.strip()

                parsed = json.loads(text)

                # Validate required keys exist
                required = ["moat_score", "moat_rationale", "governance_score",
                            "thesis", "catalysts_3_to_7y", "downside_risks"]
                if all(k in parsed for k in required):
                    parsed.setdefault("red_flags", [])
                    parsed.setdefault("uncertainties", "")
                    parsed.setdefault("core_or_satellite_view", "")
                    return parsed
                else:
                    last_error = f"Missing keys in response: {[k for k in required if k not in parsed]}"
                    continue

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error with {model_name}: {str(e)[:80]}"
                continue
            except Exception as e:
                err_str = str(e)
                if "not found" in err_str.lower() or "deprecated" in err_str.lower() or "404" in err_str:
                    last_error = f"Model {model_name} not available"
                    continue
                else:
                    # Real error (auth, rate limit, etc.) — don't keep trying
                    return _stub_response(company, reason=f"Gemini error: {err_str[:100]}")

        return _stub_response(company, reason=f"All models failed. Last error: {last_error}")

    except ImportError:
        return _stub_response(company, reason="google-generativeai not installed. Run: pip install google-generativeai")
    except Exception as e:
        return _stub_response(company, reason=f"Unexpected error: {str(e)[:100]}")


def _stub_response(company: str, reason: str) -> dict:
    """Fallback when API isn't available."""
    return {
        "moat_score": 50,
        "moat_rationale": f"[Gemini unavailable: {reason}. Using placeholder score.]",
        "governance_score": 70,
        "red_flags": [],
        "thesis": "[AI analysis unavailable] Refer to quantitative pillars above for the investment case.",
        "uncertainties": f"[Gemini API not accessible: {reason}]",
        "catalysts_3_to_7y": "[Gemini API not accessible]",
        "downside_risks": "[Gemini API not accessible]",
        "core_or_satellite_view": "[Gemini API not accessible]",
        "_stub": True,
        "_stub_reason": reason,
    }
