# Trade Confirmation & Affirmation Copilot

A working AI prototype built for the Accenture Strategy & Consulting Capital Markets
hiring challenge — agentic reasoning applied to trade confirmation/affirmation,
one of the core daily workflows in post-trade operations.

## What it does

Every day, post-trade teams compare incoming trade confirmations from counterparties
against their own internal booking records. Most match cleanly. The ones that don't
need an analyst to figure out *what kind* of break occurred and draft a query to the
counterparty — today, done manually.

This prototype automates that judgment call:

1. **Matches** each internal booking against its external confirmation, field by
   field, within defined tolerances (price, notional, settlement date, SSI,
   counterparty, ISIN) — fully deterministic, no LLM involved.
2. **Classifies** every genuine break into an operational category (timing
   difference, static data error, genuine repricing, missing confirmation) with a
   severity rating and rationale — this is where the agent reasons.
3. **Drafts** a ready-to-send query message to the counterparty's operations desk.
4. **Displays** everything in a dashboard: exception queue with drill-down, and a
   clean-affirmed trades tab.

## Architecture

```
data/generate_mock_data.py   → internal_bookings.csv
                                external_confirmations.csv
                    │
                    ▼
src/matching_engine.py       → field-by-field comparison, tolerance-based
                                (deterministic — no LLM)
                    │
                    ▼
src/break_classifier.py      → Claude API: classifies break type, severity,
                                drafts resolution message
                                (falls back to rule-based mock if no API key set)
                    │
                    ▼
src/run_pipeline.py          → output/exception_report.json / .csv
                    │
                    ▼
src/dashboard.py             → Streamlit UI (exception queue + affirmed trades)
```

## Quick start

```bash
pip install -r requirements.txt
python3 data/generate_mock_data.py   # generate mock trades
python3 src/run_pipeline.py          # run matching + classification
streamlit run src/dashboard.py       # view the dashboard
```

To get live Claude reasoning instead of the rule-based mock classifier, set your
own key first:

```bash
export ANTHROPIC_API_KEY=your-key-here
python3 src/run_pipeline.py
```

## Sample output

Running the pipeline on the seeded dataset (60 trades, ~35% seeded break rate)
produces roughly:

| Metric            | Value |
|--------------------|-------|
| Total trades       | 60    |
| Affirmed clean     | ~44   |
| Breaks detected    | ~16   |

Break categories: static data errors (wrong SSI/counterparty) are flagged HIGH
severity given settlement-risk implications; genuine repricing and timing
differences are flagged MEDIUM; missing confirmations are flagged HIGH pending
counterparty response.

## Design principle

Claude decides **what kind** of break occurred and **what to say** about it.
Deterministic Python code decides **the numbers** — tolerance thresholds, exact
matching logic. This keeps the numeric/financial decisions auditable and
reproducible, while using the LLM specifically for the judgment call that
benefits from it: operational classification and communication drafting.

## Related work

This project extends the reconciliation and exception-classification approach
built in [`multi-venue-settlement-monitor`](https://github.com/Kaviya04/multi-venue-settlement-monitor)
into the trade confirmation/affirmation stage of the lifecycle, and reuses logic
patterns from `payment-reconciliation-engine`.

## Disclaimer

All trade data in this repository is synthetic, generated for demonstration
purposes. No real client, counterparty, or trade data is used.

##Further References

1. Mock Dashboard: [[http://localhost:8501/#trade-confirmation-and-affirmation-copilot]](https://trade-confirmation-copilot-jqxfflspuxv29zvxjn9rpc.streamlit.app/)] 
2. For detailed read: [https://app.notion.com/p/Trade-Confirmation-Affirmation-Copilot-Project-Doc-3abcf8fc0ddc8145acc8f56639b36e42]
