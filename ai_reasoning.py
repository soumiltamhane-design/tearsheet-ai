"""
ai_reasoning.py
----------------
The judgment layer. quant_engine.py computes ratios; this module scores
the things that genuinely need reading and reasoning -- moat strength,
governance/red-flag review, and the narrative tear sheet in the same
shape as the Gulf Oil tear sheet template the user supplied (thesis,
uncertainties, catalysts, downside risks, core vs satellite view).

In a production build, `qualitative_context` below should be populated
with real excerpts: annual report MD&A, concall transcripts, recent
news. This demo passes only the quant_engine output + general knowledge,
clearly labeled as such -- the architecture is what matters here, not
pretending this prototype has read a 10-K it hasn't.

If ANTHROPIC_API_KEY isn't set, this module returns a clearly-labeled
stub so the rest of the pipeline (and the Streamlit app) still runs.
"""

from __future__ import annotations
import os
import json

SYSTEM_PROMPT = """You are a buy-side equity research associate scoring a stock \
against a specific checklist, not giving generic commentary.

Score MOAT using these criteria (Buffett checklist + Porter's five forces): \
consumer monopoly / pricing power, durability of competitive advantage, \
conservative financing, capital allocation discipline, low reinvestment \
need to sustain growth, competitive intensity in the industry.

Score GOVERNANCE using this red-flag checklist: promoter pledging, insider \
selling, rising receivable days unexplained by business model, related-party \
transactions, auditor changes, delayed results, lack of investor \
communication (no concalls/no clear shareholder letter), opaque related \
entities or political connections. Penalize for any you can reasonably \
infer or that show up in the provided data; do not invent specifics you \
cannot support.

Write the narrative fields in the voice of an internal tear sheet, not a \
press release -- specific, willing to state uncertainty, willing to say \
what would change the thesis.

Return ONLY valid JSON, no markdown fences, no preamble, matching exactly \
this schema:
{
  "moat_score": <0-100 integer>,
  "moat_rationale": "<2-3 sentences>",
  "governance_score": <0-100 integer>,
  "red_flags": ["<short flag>", ...],
  "thesis": "<2-3 sentences: is this mispriced and why>",
  "uncertainties": "<1-2 sentences>",
  "catalysts_3_to_7y": "<1-2 sentences: how could this double in 3-7 years>",
  "downside_risks": "<1-2 sentences: what kills the thesis>",
  "core_or_satellite_view": "<1 sentence recommendation with reasoning>"
}
"""


def _build_user_prompt(company: str, sector: str, quant_summary: dict, qualitative_context: str = "") -> str:
    return f"""Company: {company}
Sector: {sector}

Computed financial summary (from a deterministic quant engine, already validated):
{json.dumps(quant_summary, indent=2)}

Additional qualitative context (annual report excerpts, concall notes, news -- \
empty means none was provided, score moat/governance from the financial \
pattern and your general knowledge of the company instead, and say so \
plainly in the rationale rather than fabricating specifics):
{qualitative_context or "(none provided in this demo run)"}
"""


def analyze(company: str, sector: str, quant_summary: dict, qualitative_context: str = "") -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _stub_response(company, reason="No ANTHROPIC_API_KEY set in environment")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(company, sector, quant_summary, qualitative_context)}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        return _stub_response(company, reason=f"API call failed: {e}")


def _stub_response(company: str, reason: str) -> dict:
    return {
        "moat_score": 50,
        "moat_rationale": f"[STUB -- {reason}. Set ANTHROPIC_API_KEY to get a real moat assessment.]",
        "governance_score": 70,
        "red_flags": [],
        "thesis": f"[STUB] No live AI reasoning was run for {company} in this session.",
        "uncertainties": "[STUB]",
        "catalysts_3_to_7y": "[STUB]",
        "downside_risks": "[STUB]",
        "core_or_satellite_view": "[STUB] Connect an API key to generate a real recommendation narrative.",
        "_stub": True,
    }
