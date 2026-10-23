#!/usr/bin/env python3
"""Record user-supplied scores against exact CSV bytes; never call Kaggle."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "submissions/results.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--public-score", type=float, required=True)
    parser.add_argument("--private-score", type=float, required=True)
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    if not all(0 <= score <= 1 for score in [args.public_score, args.private_score]):
        parser.error("Scores must be finite numbers in [0,1]")
    submission = ROOT / args.submission
    name = submission.stem
    report_dir = ROOT / "reports" / ("final_11_30" if name == "submission_001" else name)
    manifest_path = report_dir / "summary.json"
    manifest = json.loads(manifest_path.read_text())
    actual_hash = digest(submission)
    if actual_hash != manifest["submission_sha256"]:
        raise AssertionError("CSV differs from the saved generation manifest")
    screenshot = ROOT / args.screenshot if args.screenshot else None
    record = {"submission_id": name, "csv_path": str(submission.relative_to(ROOT)), "csv_sha256": actual_hash,
              "strategy": manifest["selected_id"], "public_score": args.public_score, "private_score": args.private_score,
              "provenance": "User-supplied Kaggle result; no API score retrieval", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
              "screenshot_path": str(screenshot.relative_to(ROOT)) if screenshot else None,
              "screenshot_sha256": digest(screenshot) if screenshot else None,
              "generation_manifest": str(manifest_path.relative_to(ROOT))}
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"competition": "sweettv-tv-program-recommender", "selection_metric": "returned public score", "results": []}
    previous = next((r for r in ledger["results"] if r["submission_id"] == name), None)
    if previous and any(previous[k] != record[k] for k in ["csv_sha256", "public_score", "private_score"]):
        raise AssertionError("Conflicting existing score record; investigate before replacing it")
    if previous:
        record["recorded_at_utc"] = previous["recorded_at_utc"]
    ledger["results"] = sorted([r for r in ledger["results"] if r["submission_id"] != name]+[record], key=lambda r: r["submission_id"])
    dump(LEDGER, ledger)
    columns = ["submission_id", "strategy", "public_score", "private_score", "csv_sha256", "screenshot_path"]
    with (LEDGER.parent / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for result in ledger["results"]:
            row = {k: result[k] for k in columns}
            for key in ["public_score", "private_score"]:
                row[key] = f"{row[key]:.5f}"
            writer.writerow(row)
    dump(report_dir / "kaggle_result.json", record)
    manifest["kaggle_status"] = "Completed upload; returned scores supplied by user"
    manifest["reported_kaggle_scores"] = {"public": args.public_score, "private": args.private_score,
                                          "result_record": str((report_dir / "kaggle_result.json").relative_to(ROOT))}
    dump(manifest_path, manifest)
    print(f"Recorded {name}: public {args.public_score:.5f}, private {args.private_score:.5f}; CSV SHA-256 {actual_hash}")


if __name__ == "__main__":
    main()
