"""
Deterministic matching engine.

Compares each internal booking to its corresponding external confirmation
field by field, within defined tolerances. This layer makes NO use of the
LLM - all numeric/threshold decisions happen here so they are reproducible
and auditable. The output feeds the break classifier, which only reasons
about breaks this engine has already detected.
"""

import csv
from datetime import date

PRICE_TOLERANCE_PCT = 0.005     # 0.5% - anything beyond this is a genuine break
NOTIONAL_TOLERANCE_PCT = 0.005  # 0.5%
SETTLEMENT_DATE_TOLERANCE_DAYS = 0  # any difference is a break


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def index_by_trade_id(rows):
    return {row["trade_id"]: row for row in rows}


def pct_diff(a, b):
    a, b = float(a), float(b)
    if a == 0:
        return 0.0 if b == 0 else 1.0
    return abs(a - b) / abs(a)


def compare_trade(internal, external):
    """Returns a list of field-level break dicts. Empty list = clean match."""
    breaks = []

    if pct_diff(internal["price"], external["price"]) > PRICE_TOLERANCE_PCT:
        breaks.append({
            "field": "price",
            "internal_value": internal["price"],
            "external_value": external["price"],
        })

    if pct_diff(internal["notional"], external["notional"]) > NOTIONAL_TOLERANCE_PCT:
        breaks.append({
            "field": "notional",
            "internal_value": internal["notional"],
            "external_value": external["notional"],
        })

    if internal["settlement_date"] != external["settlement_date"]:
        breaks.append({
            "field": "settlement_date",
            "internal_value": internal["settlement_date"],
            "external_value": external["settlement_date"],
        })

    if internal["ssi"] != external["ssi"]:
        breaks.append({
            "field": "ssi",
            "internal_value": internal["ssi"],
            "external_value": external["ssi"],
        })

    if internal["counterparty"] != external["counterparty"]:
        breaks.append({
            "field": "counterparty",
            "internal_value": internal["counterparty"],
            "external_value": external["counterparty"],
        })

    if internal["isin"] != external["isin"]:
        breaks.append({
            "field": "isin",
            "internal_value": internal["isin"],
            "external_value": external["isin"],
        })

    return breaks


def run_matching(internal_path, external_path):
    internal_rows = load_csv(internal_path)
    external_by_id = index_by_trade_id(load_csv(external_path))

    results = []
    for internal in internal_rows:
        trade_id = internal["trade_id"]
        external = external_by_id.get(trade_id)

        if external is None:
            results.append({
                "trade_id": trade_id,
                "status": "BREAK",
                "breaks": [{
                    "field": "confirmation",
                    "internal_value": "booked",
                    "external_value": "MISSING - no confirmation received",
                }],
                "internal": internal,
                "external": None,
            })
            continue

        field_breaks = compare_trade(internal, external)

        results.append({
            "trade_id": trade_id,
            "status": "BREAK" if field_breaks else "AFFIRMED",
            "breaks": field_breaks,
            "internal": internal,
            "external": external,
        })

    return results


if __name__ == "__main__":
    results = run_matching(
        "data/internal_bookings.csv",
        "data/external_confirmations.csv",
    )

    affirmed = [r for r in results if r["status"] == "AFFIRMED"]
    broken = [r for r in results if r["status"] == "BREAK"]

    print(f"Total trades: {len(results)}")
    print(f"Affirmed clean: {len(affirmed)}")
    print(f"Breaks detected: {len(broken)}")
    print()
    for r in broken[:5]:
        fields = ", ".join(b["field"] for b in r["breaks"])
        print(f"  {r['trade_id']}: break in [{fields}]")
