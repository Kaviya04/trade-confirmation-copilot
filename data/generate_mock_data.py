"""
Generate mock trade data for the Trade Confirmation & Affirmation Copilot.

Simulates two sides of a trade lifecycle event:
  1. internal_bookings.csv   - what our own system booked (the "truth" we hold)
  2. external_confirmations.csv - what came back from the counterparty/broker
                                   (SWIFT MT304/MT320-style fields, flattened to CSV)

A subset of trades are seeded with realistic breaks so the matching engine
and Claude classifier have real work to do:
  - price mismatch (small FX/rounding vs. genuine repricing)
  - notional mismatch
  - settlement date mismatch (timing difference)
  - wrong SSI (standing settlement instructions)
  - wrong counterparty code (static data error)
  - missing confirmation (no external record at all)
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)

NUM_TRADES = 60
BREAK_RATE = 0.35  # ~35% of trades get a seeded break, for a rich demo

INSTRUMENTS = [
    ("DE0007236101", "Siemens AG"),
    ("US0378331005", "Apple Inc"),
    ("FR0000131104", "BNP Paribas"),
    ("NL0011821202", "ASML Holding"),
    ("DE0005190003", "BMW AG"),
    ("US88160R1014", "Tesla Inc"),
    ("GB0002374006", "Diageo plc"),
    ("CH0038863350", "Nestle SA"),
]

COUNTERPARTIES = [
    "GOLDMAN SACHS INTL",
    "MORGAN STANLEY & CO",
    "JPMORGAN CHASE BANK NA",
    "BARCLAYS BANK PLC",
    "DEUTSCHE BANK AG",
    "UBS AG LONDON",
]

SSI_CODES = ["SSI-EUR-001", "SSI-EUR-002", "SSI-USD-001", "SSI-GBP-001", "SSI-CHF-001"]

BREAK_TYPES = [
    "price_mismatch",
    "notional_mismatch",
    "settlement_date_mismatch",
    "wrong_ssi",
    "wrong_counterparty",
    "missing_confirmation",
]


def random_trade_id(i):
    return f"TRD-2026-{i:05d}"


def random_settlement_date():
    base = date(2026, 7, 28)
    return base + timedelta(days=random.randint(1, 5))


def generate_trades():
    internal_rows = []
    external_rows = []

    for i in range(1, NUM_TRADES + 1):
        trade_id = random_trade_id(i)
        isin, instrument_name = random.choice(INSTRUMENTS)
        counterparty = random.choice(COUNTERPARTIES)
        notional = round(random.uniform(50_000, 5_000_000), 2)
        price = round(random.uniform(20, 850), 4)
        settlement_date = random_settlement_date()
        ssi = random.choice(SSI_CODES)
        direction = random.choice(["BUY", "SELL"])

        internal = {
            "trade_id": trade_id,
            "isin": isin,
            "instrument_name": instrument_name,
            "counterparty": counterparty,
            "direction": direction,
            "notional": notional,
            "price": price,
            "settlement_date": settlement_date.isoformat(),
            "ssi": ssi,
        }
        internal_rows.append(internal)

        # Decide if this trade gets a seeded break
        seed_break = random.random() < BREAK_RATE
        external = dict(internal)  # start as an exact copy

        if seed_break:
            break_type = random.choice(BREAK_TYPES)

            if break_type == "price_mismatch":
                # genuine break: >0.5% price difference (not just rounding)
                external["price"] = round(price * random.uniform(1.01, 1.05), 4)

            elif break_type == "notional_mismatch":
                external["notional"] = round(notional * random.uniform(1.02, 1.10), 2)

            elif break_type == "settlement_date_mismatch":
                external["settlement_date"] = (
                    settlement_date + timedelta(days=random.choice([-1, 1, 2]))
                ).isoformat()

            elif break_type == "wrong_ssi":
                other_ssis = [s for s in SSI_CODES if s != ssi]
                external["ssi"] = random.choice(other_ssis)

            elif break_type == "wrong_counterparty":
                other_cps = [c for c in COUNTERPARTIES if c != counterparty]
                external["counterparty"] = random.choice(other_cps)

            elif break_type == "missing_confirmation":
                external = None  # no external record produced at all

        if external is not None:
            external["seeded_break_type"] = break_type if seed_break else "none"
            external_rows.append(external)
        # if external is None (missing_confirmation), we simply don't add a row -
        # the matching engine will detect the absence

    return internal_rows, external_rows


def write_csv(rows, path, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    internal_rows, external_rows = generate_trades()

    internal_fields = [
        "trade_id", "isin", "instrument_name", "counterparty",
        "direction", "notional", "price", "settlement_date", "ssi",
    ]
    external_fields = internal_fields + ["seeded_break_type"]

    write_csv(internal_rows, "data/internal_bookings.csv", internal_fields)
    write_csv(external_rows, "data/external_confirmations.csv", external_fields)

    missing = NUM_TRADES - len(external_rows)
    print(f"Generated {NUM_TRADES} internal bookings.")
    print(f"Generated {len(external_rows)} external confirmations "
          f"({missing} intentionally missing).")
