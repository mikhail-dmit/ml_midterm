#!/usr/bin/env python3
"""Evaluate user_id,tv_show_id CSVs, optionally for an explicit user subset."""

import argparse
import csv
import json
from pathlib import Path

from ranking_metrics import evaluate_rankings


def read_rankings(path):
    result = {}
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"user_id", "tv_show_id"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires user_id and tv_show_id columns")
        for row in reader:
            user = row["user_id"]
            if not user.isdecimal() or user in result:
                raise ValueError(f"Invalid or repeated user ID: {user}")
            items = row["tv_show_id"].split()
            if not items or any(not item.isdecimal() or int(item) <= 0 for item in items):
                raise ValueError(f"Expected nonzero decimal programme IDs: {user}")
            result[user] = list(map(int, items))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--users", type=Path, help="CSV containing a unique user_id column for a reporting subset")
    args = parser.parse_args()
    truth, predictions = read_rankings(args.truth), read_rankings(args.predictions)
    cohort = None
    if args.users:
        with args.users.open(encoding="utf-8", newline="") as stream:
            cohort = [row["user_id"] for row in csv.DictReader(stream)]
    result, _ = evaluate_rankings(truth, predictions, users=cohort)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
