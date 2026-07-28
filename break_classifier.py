"""
Break classifier + resolution message drafter.

This is the "agentic" layer. It takes a break already DETECTED by the
deterministic matching_engine (which fields differ, and by how much) and:
  1. Classifies what kind of break it most likely is, in operational terms
     (timing difference, static data error, genuine repricing, etc.)
  2. Assigns a severity (HIGH / MEDIUM / LOW) with a one-line rationale
  3. Drafts a ready-to-send query/dispute message to the counterparty

Claude never touches the numeric tolerance decisions - those already
happened in matching_engine.py. Claude only reasons about WHAT the break
means operationally and HOW to communicate about it, which is the part
that genuinely benefits from judgment rather than fixed rules.
"""

import json
import os
import urllib.request

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a post-trade operations analyst assistant specializing in \
trade confirmation and affirmation for Capital Markets (equities, cross-border settlement).

You will be given a trade with one or more field-level breaks already detected between \
the internal booking and the external counterparty confirmation. Your job:

1. Classify the break using ONE of these categories:
   - "timing_difference" (e.g. settlement date off by 1-2 days, likely a T+ convention or \
holiday calendar mismatch)
   - "static_data_error" (e.g. wrong SSI or counterparty code, likely a static data setup issue)
   - "genuine_repricing" (price or notional differs beyond tolerance, suggesting a real \
economic discrepancy, not rounding)
   - "missing_confirmation" (counterparty has not sent a confirmation at all)
   - "unclear" (only if truly ambiguous)

2. Assign severity: HIGH, MEDIUM, or LOW, with a one-sentence rationale grounded in \
settlement risk (e.g. wrong SSI risking misdirected securities/cash is HIGH; a 1-day \
timing difference is typically LOW-MEDIUM).

3. Draft a short, professional query message (3-5 sentences) to send to the counterparty's \
operations desk, referencing the trade ID and the specific discrepancy, and asking for \
confirmation or correction.

Respond ONLY with valid JSON, no preamble, no markdown fences, in this exact shape:
{
  "break_category": "...",
  "severity": "HIGH|MEDIUM|LOW",
  "severity_rationale": "...",
  "drafted_message": "..."
}
"""


def build_user_prompt(trade_result):
    trade_id = trade_result["trade_id"]
    breaks = trade_result["breaks"]
    internal = trade_result["internal"]

    break_lines = []
    for b in breaks:
        break_lines.append(
            f"- Field: {b['field']} | Internal (our booking): {b['internal_value']} "
            f"| External (counterparty confirmation): {b['external_value']}"
        )

    counterparty = internal.get("counterparty", "unknown counterparty")
    isin = internal.get("isin", "unknown ISIN")

    return f"""Trade ID: {trade_id}
Counterparty: {counterparty}
ISIN: {isin}

Detected break(s):
{chr(10).join(break_lines)}

Classify this break and draft the resolution message."""


def call_claude(system_prompt, user_prompt):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text_blocks = [c["text"] for c in data.get("content", []) if c.get("type") == "text"]
    raw_text = "\n".join(text_blocks).strip()

    # Defensive: strip markdown fences if the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def mock_classify_break(trade_result):
    """
    Rule-based stand-in used only when no ANTHROPIC_API_KEY is available
    (e.g. running this demo without your own key configured yet). Mirrors
    the categories/severity the live Claude classifier would return, so the
    rest of the pipeline (dashboard, message queue) can be demoed end-to-end.
    Swap in a real ANTHROPIC_API_KEY to get live LLM reasoning instead.
    """
    trade_id = trade_result["trade_id"]
    breaks = trade_result["breaks"]
    fields = {b["field"] for b in breaks}
    internal = trade_result["internal"]

    if "confirmation" in fields:
        category, severity, rationale = (
            "missing_confirmation", "HIGH",
            "No confirmation received; settlement cannot be affirmed until counterparty responds.",
        )
    elif "ssi" in fields or "counterparty" in fields:
        category, severity, rationale = (
            "static_data_error", "HIGH",
            "Incorrect settlement/counterparty static data risks misdirected securities or cash.",
        )
    elif "settlement_date" in fields and len(fields) == 1:
        category, severity, rationale = (
            "timing_difference", "MEDIUM",
            "Settlement date mismatch of a day or two, likely a T+ convention or calendar difference.",
        )
    elif "price" in fields or "notional" in fields:
        category, severity, rationale = (
            "genuine_repricing", "MEDIUM",
            "Price/notional differs beyond tolerance, suggesting a real economic discrepancy rather than rounding.",
        )
    else:
        category, severity, rationale = ("unclear", "MEDIUM", "Break pattern does not clearly fit one category.")

    field_list = ", ".join(f"{b['field']} (ours: {b['internal_value']}, yours: {b['external_value']})" for b in breaks)
    message = (
        f"Dear Operations Team,\n\n"
        f"We have identified a discrepancy on trade {trade_id} "
        f"({internal.get('counterparty', 'N/A')}, {internal.get('isin', 'N/A')}). "
        f"Specifically: {field_list}. "
        f"Could you please confirm your booking details or advise on the correction needed? "
        f"We would appreciate a response ahead of settlement date to avoid further delay.\n\n"
        f"Kind regards,\nPost-Trade Operations"
    )

    return {
        "break_category": category,
        "severity": severity,
        "severity_rationale": rationale,
        "drafted_message": message,
        "mock": True,
    }


def classify_break(trade_result):
    """
    Takes a BREAK result from matching_engine and returns a classification dict.
    Uses live Claude reasoning if ANTHROPIC_API_KEY is set; otherwise falls back
    to a rule-based mock so the pipeline still runs end-to-end for demo purposes.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            user_prompt = build_user_prompt(trade_result)
            return call_claude(SYSTEM_PROMPT, user_prompt)
        except Exception:
            pass  # fall through to mock on any API error
    return mock_classify_break(trade_result)


if __name__ == "__main__":
    from matching_engine import run_matching

    results = run_matching("data/internal_bookings.csv", "data/external_confirmations.csv")
    broken = [r for r in results if r["status"] == "BREAK"]

    print(f"Classifying {len(broken)} breaks...\n")
    for r in broken[:3]:
        try:
            classification = classify_break(r)
            print(f"--- {r['trade_id']} ---")
            print(json.dumps(classification, indent=2))
            print()
        except Exception as e:
            print(f"--- {r['trade_id']} --- ERROR: {e}\n")
