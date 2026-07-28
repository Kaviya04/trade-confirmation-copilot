"""
End-to-end pipeline: matching -> classification -> exception report.

Run with:  python3 src/run_pipeline.py
Produces:  output/exception_report.json  (full detail, feeds the dashboard)
           output/exception_report.csv   (summary, easy to hand to a team lead)
"""

import csv
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from matching_engine import run_matching
from break_classifier import classify_break


def main():
    results = run_matching(
        os.path.join("data", "internal_bookings.csv"),
        os.path.join("data", "external_confirmations.csv"),
    )

    affirmed = [r for r in results if r["status"] == "AFFIRMED"]
    broken = [r for r in results if r["status"] == "BREAK"]

    print(f"Total trades:     {len(results)}")
    print(f"Affirmed clean:   {len(affirmed)}")
    print(f"Breaks detected:  {len(broken)}")
    print("\nClassifying breaks...")

    enriched = []
    for r in results:
        record = {
            "trade_id": r["trade_id"],
            "status": r["status"],
            "counterparty": r["internal"].get("counterparty"),
            "isin": r["internal"].get("isin"),
            "instrument_name": r["internal"].get("instrument_name"),
            "breaks": r["breaks"],
        }
        if r["status"] == "BREAK":
            classification = classify_break(r)
            record.update(classification)
        enriched.append(record)

    os.makedirs("output", exist_ok=True)

    with open(os.path.join("output", "exception_report.json"), "w") as f:
        json.dump(enriched, f, indent=2)

    csv_fields = [
        "trade_id", "status", "counterparty", "isin", "instrument_name",
        "break_category", "severity", "severity_rationale",
    ]
    with open(os.path.join("output", "exception_report.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for record in enriched:
            writer.writerow(record)

    print(f"\nDone. Wrote output/exception_report.json and output/exception_report.csv")


if __name__ == "__main__":
    main()
