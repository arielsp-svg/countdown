"""Write a sample RO table with dates relative to today.

Each row exercises a different branch of the requirements, so running the app
against this file shows the real behaviour rather than a single happy path.
"""
import csv
import sys
from datetime import date

sys.path.insert(0, ".")
from countdown.engine import add_months  # noqa: E402

TODAY = date.today()

ROWS = [
    # department, type, platform, nav, receiver, tod, comments, RO date
    ("Avionics", "Radar", "F-16 Barak", "INS-4", "R-200B", "yes",
     "inside 6 months, so weekly", add_months(TODAY, 4)),
    ("Avionics", "Comms", "F-15 Ra'am", "INS-2", "R-310", "no",
     "inside 12 months, so monthly", add_months(TODAY, 10)),
    ("Avionics", "Nav", "C-130 Shimshon", "GPS-7", "R-105", "yes",
     "beyond 12 months, no alert yet", add_months(TODAY, 18)),
    ("Avionics", "Radar", "Apache AH-64", "INS-1", "R-55", "no",
     "RO date already passed, no alert", add_months(TODAY, -3)),
    ("Avionics", "Comms", "Blackhawk", "GPS-3", "R-70", "yes",
     "free text RO date, row is skipped", "to be confirmed"),
    ("Logistics", "Radar", "Beechcraft", "INS-9", "R-12", "no",
     "another department, filtered out", add_months(TODAY, 2)),
]

HEADER = ["Department", "Type of system", "Platform", "Nav system",
          "Receiver model", "Using TOD", "Comments", "RO date"]


def main(path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        for row in ROWS:
            ro = row[-1]
            writer.writerow(list(row[:-1]) + [
                ro.strftime("%d/%m/%Y") if isinstance(ro, date) else ro])
    print(f"wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "table.csv")
