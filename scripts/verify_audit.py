#!/usr/bin/env python3
"""Independently verify core audit numbers with csv/Counter, without pandas."""

import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "sweettv-tv-program-recommender")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "data_audit")
    args = parser.parse_args()
    report = json.loads((args.report_dir / "audit.json").read_text(encoding="utf-8"))
    started = time.perf_counter()
    checks = []
    mismatch_examples = []

    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError(f"{name}: independent={actual!r}, audit={expected!r}")
        checks.append({"check": name, "value": actual, "passed": True})

    for filename, info in report["files"].items():
        print(f"Independently recounting {filename} ...", flush=True)
        path = args.data_dir / filename
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        check(filename + ": SHA-256 unchanged", digest.hexdigest(), info["sha256"])
        count, zero_count = 0, 0
        users, channels, programmes, categories = set(), set(), set(), set()
        durations = Counter()
        differences = Counter()
        min_start, max_start, max_stop = None, None, None
        above_int64 = set()
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            check(filename + ": header", reader.fieldnames, info["columns"])
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise AssertionError(f"Malformed CSV width at {filename} data row {count + 1}")
                count += 1
                if filename == "dataset11-30.csv":
                    user = int(row["user_id"])
                    users.add(user)
                    channels.add(int(row["vsetv_id"]))
                    if user > 2**63 - 1:
                        above_int64.add(user)
                    start = datetime.fromisoformat(row["start_time"])
                    stop = datetime.fromisoformat(row["stop_time"])
                    min_start = start if min_start is None else min(min_start, start)
                    max_start = start if max_start is None else max(max_start, start)
                    max_stop = stop if max_stop is None else max(max_stop, stop)
                    duration = int(row["duraton"])
                    durations[duration] += 1
                    elapsed = int((stop - start).total_seconds())
                    if elapsed != duration:
                        differences[elapsed - duration] += 1
                        zone = ZoneInfo("Europe/Kyiv")
                        utc_elapsed = int((stop.replace(tzinfo=zone).astimezone(timezone.utc)
                                           - start.replace(tzinfo=zone).astimezone(timezone.utc)).total_seconds())
                        mismatch_examples.append({
                            "user_id": row["user_id"], "start_time": row["start_time"],
                            "stop_time": row["stop_time"], "duraton": duration,
                            "naive_elapsed": elapsed, "elapsed_if_Europe_Kyiv": utc_elapsed,
                            "clock_change_hypothesis_matches": utc_elapsed == duration,
                        })
                elif filename == "submission.csv":
                    users.add(int(row["user_id"]))
                    if row["tv_show_id"].split() != ["0"] * 5:
                        raise AssertionError("Unexpected template placeholders")
                else:
                    item = int(row["tv_show_id"])
                    programmes.add(item)
                    channels.add(int(row["channel_id"]))
                    categories.add(row["tv_show_category"])
                    zero_count += item == 0
        check(filename + ": rows", count, info["rows"])
        if filename == "dataset11-30.csv":
            check("log distinct users", len(users), info["distinct_users"])
            check("log distinct channels", len(channels), info["distinct_channels"])
            check("log users above signed int64", len(above_int64), info["distinct_users_above_int64"])
            check("log first start", min_start.isoformat(), info["temporal"]["min_start"])
            check("log last start", max_start.isoformat(), info["temporal"]["max_start"])
            check("log last stop", max_stop.isoformat(), info["max_end"])
            check("log duration mismatch count", sum(differences.values()), info["duration_mismatch_rows"])
            expected_differences = {int(float(k)): v for k, v in info["naive_elapsed_minus_recorded_duration_seconds"].items()}
            check("log mismatch offsets", dict(differences), expected_differences)
            # Exact median from the empirical frequency histogram, not pandas quantile.
            positions = [(count - 1) // 2, count // 2]
            medians = []
            cumulative = 0
            for duration, frequency in sorted(durations.items()):
                medians.extend(duration for position in positions if cumulative <= position < cumulative + frequency)
                cumulative += frequency
            median = sum(medians) / 2
            check("log exact median duration", median, info["duration_seconds"]["p50"])
            check("log maximum duration", max(durations), info["duration_seconds"]["p100"])
        elif filename == "submission.csv":
            check("template unique users", len(users), report["template_checks"]["distinct_users"])
        else:
            check(filename + ": nonzero programmes", len(programmes - {0}), info["distinct_programmes_nonzero"])
            check(filename + ": channels", len(channels), info["distinct_channels"])
            check(filename + ": categories", len(categories), len(info["categories_all_rows"]))
            check(filename + ": zero IDs", zero_count, info["zero_id_rows"])
    check("clock investigation retains every mismatch", len(mismatch_examples),
          report["files"]["dataset11-30.csv"]["duration_mismatch_rows"])
    result = {
        "passed": True, "check_count": len(checks), "checks": checks,
        "method": "Independent standard-library csv/Counter recount; no pandas or audit implementation imported",
        "clock_change_investigation": {
            "mismatching_rows": len(mismatch_examples),
            "rows_matching_Europe_Kyiv_elapsed_hypothesis": sum(x["clock_change_hypothesis_matches"] for x in mismatch_examples),
            "interpretation": "Consistency with the 2020-03-29 spring clock change is evidence for a DST explanation, not proof of the source timezone. No timestamps were corrected.",
            "examples": mismatch_examples[:8],
        },
        "elapsed_seconds": time.perf_counter() - started,
        "personal_student_verification": "Assistant-executed independent check; student verification not claimed",
    }
    (args.report_dir / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Passed {len(checks)} independent checks in {result['elapsed_seconds']:.1f}s")
    print(json.dumps(result["clock_change_investigation"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
