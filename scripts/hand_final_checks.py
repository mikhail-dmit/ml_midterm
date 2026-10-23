#!/usr/bin/env python3
"""Write explicit AP arithmetic and independently rejoin the original manual user."""

import bisect
import csv
import filecmp
import json
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from ranking_metrics import average_precision_at_k
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_check"
DATA = ROOT / "sweettv-tv-program-recommender"
TZ = ZoneInfo("Europe/Kyiv")


def read(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write(name, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def epoch(text, scheduled=False):
    value = datetime.strptime(text, "%d.%m.%Y %H:%M:%S") if scheduled else datetime.fromisoformat(text)
    return int(value.replace(tzinfo=TZ).timestamp())


def local(value):
    return datetime.fromtimestamp(value, TZ).isoformat()


def main():
    result = json.loads((OUT / "latest_run.json").read_text())
    if result["status"] != "passed" or result["logical_stage_differences"]:
        raise AssertionError("Resolve the scratch replay before completing the final check")
    work = ROOT / result["run_directory"]
    input_manifest = json.loads((work / "input_manifest.json").read_text())
    initial_hashes = {k: digest(ROOT / p) for k, p in input_manifest["paths"].items()}
    if initial_hashes != input_manifest["sha256"]:
        raise AssertionError("An input changed since scratch fitting")
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    # Pick the same readable warm, light validation user by rebuilt training
    # counts only. The AP arithmetic below does not use the evaluator's result.
    users = read(work / "interaction_reports/validation_users.csv")
    candidates = [r for r in users if r["primary_validation_eligible"] == "True" and int(r["train_watched_airings"]) > 0]
    ap_user = min(candidates, key=lambda r: (int(r["train_watched_airings"]), r["user_id"]))["user_id"]
    truth_rows = {r["user_id"]: [int(i) for i in r["tv_show_id"].split()] for r in read(work / "interaction_reports/validation_ground_truth.csv")}
    pred_rows = {r["user_id"]: [int(i) for i in r["tv_show_id"].split()] for r in read(work / "validation/predictions_hybrid_007.csv")}
    actual, predicted = truth_rows[ap_user], pred_rows[ap_user]
    check("AP example has five unique predictions and five true IDs", len(actual) == len(set(actual)) == len(predicted) == len(set(predicted)) == 5)
    ap_steps, hits, total = [], 0, Fraction(0)
    for rank, item in enumerate(predicted, 1):
        relevant = item in actual
        hits += int(relevant)
        precision = Fraction(hits, rank)
        numerator_term = precision if relevant else Fraction(0)
        contribution = numerator_term/5
        total += contribution
        ap_steps.append({"user_id": ap_user, "rank": rank, "tv_show_id": item, "is_hit": relevant, "hits_so_far": hits,
                         "precision_at_rank_exact": str(precision), "numerator_term_exact": str(numerator_term),
                         "AP_contribution_exact": str(contribution), "cumulative_AP_exact": str(total)})
    evaluated = average_precision_at_k(actual, predicted)
    check("worked hit pattern and explicit 29/60 arithmetic", [r["is_hit"] for r in ap_steps] == [True, False, True, True, False] and total == Fraction(29, 60))
    check("hand AP fraction equals evaluator", abs(float(total)-evaluated) < 1e-14)
    saved_metric = next(r for r in read(work / "validation/per_user_hybrid_007.csv") if r["user_id"] == ap_user)
    check("hand AP fraction equals scratch per-user metric", abs(float(total)-float(saved_metric["ap_at_5"])) < 1e-14)
    write("hand_ap_ranks.csv", ap_steps)
    # Independently rejoin raw log and schedules for both this AP user's truth
    # and the original manual join example. Saved example values are comparison
    # targets only, never inputs to interval arithmetic.
    old_example = json.loads((ROOT / "reports/interactions/manual_example/example.json").read_text())
    manual_user = old_example["user_id"]
    selected_users = {manual_user, ap_user}
    lower, upper = epoch("2020-05-18 00:00:00"), epoch("2020-07-27 00:00:00")
    raw_records, views = [], defaultdict(list)
    with (DATA / "dataset11-30.csv").open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            if row["user_id"] not in selected_users:
                continue
            start, end = epoch(row["start_time"]), epoch(row["stop_time"])
            assert end-start == int(row["duraton"])
            channel = int(row["vsetv_id"])
            copied = {**row, "source_csv_record": number, "start_epoch": start, "end_epoch": end}
            raw_records.append(copied)
            if start < upper and end > lower:
                views[(row["user_id"], channel)].append((max(start, lower), min(end, upper)))
    write("manual_join_raw_views.csv", [r for r in raw_records if r["user_id"] == manual_user])
    unions = {}
    for key, intervals in views.items():
        pieces = []
        for a, b in sorted(set(intervals)):
            if pieces and a <= pieces[-1][1]:
                pieces[-1] = (pieces[-1][0], max(pieces[-1][1], b))
            else:
                pieces.append((a, b))
        unions[key] = (pieces, [b for a, b in pieces])
    channels = {c for u, c in views}
    requested_records = {(r["schedule_file"], r["schedule_csv_record"]) for r in old_example["worked_airings"]}
    schedule, targets = {}, {}
    for filename in ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]:
        with (DATA / filename).open(newline="", encoding="utf-8") as stream:
            for number, row in enumerate(csv.DictReader(stream), 2):
                channel, item, duration = int(row["channel_id"]), int(row["tv_show_id"]), int(row["duration"])
                if not item or duration <= 0 or channel not in channels:
                    continue
                a = epoch(row["start_time"], scheduled=True)
                b = a+duration
                if a >= upper or b <= lower:
                    continue
                airing = {"channel_id": channel, "tv_show_id": item, "start": a, "end": b, "duration": duration,
                          "title": row["tv_show_title"], "category": row["tv_show_category"], "source_file": filename, "source_csv_record": number}
                schedule.setdefault((channel, item, a, b), airing)
                if (filename, number) in requested_records:
                    targets[(filename, number)] = airing
    joined, counts, joins_by_key = [], defaultdict(int), {}
    for identity, airing in schedule.items():
        channel, item, a, b = identity
        for user in selected_users:
            pieces, ends = unions.get((user, channel), ([], []))
            observed = []
            for x, y in pieces[bisect.bisect_right(ends, a):]:
                if x >= b:
                    break
                if min(y, b) > max(x, a):
                    observed.append((max(x, a), min(y, b)))
            seconds = sum(y-x for x, y in observed)
            if not seconds:
                continue
            qualified = 5*seconds >= 4*airing["duration"]
            joins_by_key[(user, *identity)] = observed
            if qualified:
                counts[(user, item)] += 1
            joined.append({"user_id": user, **airing, "watched_seconds": seconds, "watched_80pct": qualified})
    write("manual_join_independent_airings.csv", joined)
    for user in selected_users:
        ranked = sorted([(i, n) for (u, i), n in counts.items() if u == user], key=lambda pair: (-pair[1], pair[0]))
        check(f"raw-source validation Top-5 matches scratch truth: {user}", [i for i, n in ranked[:5]] == truth_rows[user])
    ap_actual = sorted([(i, n) for (u, i), n in counts.items() if u == ap_user], key=lambda pair: (-pair[1], pair[0]))
    write("hand_ap_truth.csv", [{"rank": n, "user_id": ap_user, "tv_show_id": i, "raw_reconstructed_qualified_airings": count} for n, (i, count) in enumerate(ap_actual, 1)])
    manual_counts = sorted([(i, n) for (u, i), n in counts.items() if u == manual_user], key=lambda pair: (-pair[1], pair[0]))
    write("manual_join_programme_counts.csv", [{"rank": n, "user_id": manual_user, "tv_show_id": i, "qualified_airings": count, "in_local_Top5": n <= 5} for n, (i, count) in enumerate(manual_counts, 1)])
    check("original manual user raw row count reproduced", len([r for r in raw_records if r["user_id"] == manual_user]) == old_example["raw_view_rows"] == 783)
    check("original manual user's six once-watched positives and local Top-5 reproduced", len(manual_counts) == old_example["validation_qualified_programmes"] == 6 and all(n == 1 for i, n in manual_counts) and [i for i, n in manual_counts[:5]] == old_example["validation_top5_ids"])
    fragments, union_rows, cases = [], [], []
    for previous in old_example["worked_airings"]:
        airing = targets[(previous["schedule_file"], previous["schedule_csv_record"])]
        key = (manual_user, airing["channel_id"], airing["tv_show_id"], airing["start"], airing["end"])
        observed = joins_by_key[key]
        watched = sum(b-a for a, b in observed)
        fraction = Fraction(watched, airing["duration"])
        watched_flag = fraction >= Fraction(4, 5)
        for row in raw_records:
            if row["user_id"] != manual_user or int(row["vsetv_id"]) != airing["channel_id"]:
                continue
            a, b = max(row["start_epoch"], airing["start"], lower), min(row["end_epoch"], airing["end"], upper)
            if b > a:
                fragments.append({"user_id": manual_user, "tv_show_id": airing["tv_show_id"], "channel_id": airing["channel_id"],
                                  "log_csv_record": row["source_csv_record"], "raw_view_start": row["start_time"], "raw_view_stop": row["stop_time"],
                                  "clipped_start_local": local(a), "clipped_end_local": local(b), "overlap_seconds_before_union": b-a})
        for n, (a, b) in enumerate(observed, 1):
            union_rows.append({"tv_show_id": airing["tv_show_id"], "union_piece": n, "start_local": local(a), "end_local": local(b), "seconds": b-a})
        check(f"manual programme {airing['tv_show_id']}: exact raw-source duration/watch decision reproduced", airing["tv_show_id"] == previous["tv_show_id"] and airing["duration"] == previous["duration"] and watched == previous["watched_seconds"] and watched_flag == previous["watched"])
        check(f"manual programme {airing['tv_show_id']}: union pieces match the original worked case", [(local(a), local(b), b-a) for a, b in observed] == [(p["start_local"], p["end_local"], p["seconds"]) for p in previous["union_intervals"]])
        cases.append({**airing, "watched_seconds": watched, "coverage_fraction": str(fraction), "coverage": float(fraction), "watched": watched_flag,
                      "five_times_watched": 5*watched, "four_times_duration": 4*airing["duration"], "union_pieces": [{"start": local(a), "end": local(b), "seconds": b-a} for a, b in observed]})
    write("manual_join_raw_fragments.csv", fragments)
    write("manual_join_union_intervals.csv", union_rows)
    ap_lines = ["# AP@5 worked step by step", "", f"Validation user **{ap_user}**, the minimum-nonzero strict-training viewer from the rebuilt cohort. Method: validation-trained final **007 hybrid**.",
                "", "## Inputs", "", "True five-ID set (raw-source counts independently checked): **"+" ".join(map(str, actual))+"**.",
                "Predicted order: **"+" ".join(map(str, predicted))+"**.", "", "A hit means membership anywhere in the true set. Its frequency order is not a required matching rank. Denominator is min(5, five distinct true IDs) = **5**.",
                "", "| Rank | Predicted ID | Hit? | Hits so far | Precision at this rank | Added AP credit |", "|---:|---:|---|---:|---|---|"]
    for row in ap_steps:
        ap_lines.append(f"| {row['rank']} | {row['tv_show_id']} | {'yes' if row['is_hit'] else 'no'} | {row['hits_so_far']} | {row['precision_at_rank_exact']} | {row['AP_contribution_exact']} |")
    terms = [r["numerator_term_exact"] for r in ap_steps]
    ap_lines += ["", "## Arithmetic", "", "AP@5 = ("+" + ".join(terms)+") / 5", "", "= (1 + 2/3 + 3/4) / 5", "", "= ((12 + 8 + 9) / 12) / 5", "", f"= **{total} = {float(total):.12f}**.",
                 "", "Ranks 2 and 5 consume positions but add zero credit. The two later hits receive precision 2/3 and 3/4; they are not each automatically worth 1/5. The evaluator and the scratch per-user CSV independently agree with the worked fraction.",
                 "", "CSV worksheets: hand_ap_ranks.csv and hand_ap_truth.csv. This is assistant-worked arithmetic for the student to inspect; student-personal verification is not claimed.", ""]
    (OUT / "hand_ap.md").write_text("\n".join(ap_lines), encoding="utf-8")
    join_lines = ["# Original manual log-to-schedule example: independent raw-source recheck", "", f"User **{manual_user}**. Read the original log and both raw historical schedules with the standard library; no interaction-core join, saved watch flag or cached matched-schedule file is used for these calculations.",
                  "", "Rule: same channel, positive half-open time intersection; union overlapping/touching raw fragments per user/channel, clip observed time to validation, and divide by the **full scheduled duration**. Supplied times are interpreted as Europe/Kyiv; schedule end is start plus elapsed seconds."]
    for case in cases:
        join_lines += ["", f"## Programme {case['tv_show_id']}: {case['title']}", "", f"Raw schedule: `{case['source_file']}`, CSV record **{case['source_csv_record']}**, channel **{case['channel_id']}**.",
                       f"Airing: **{local(case['start'])} → {local(case['end'])}**, duration **{case['duration']} seconds**.",
                       "", "| Non-overlapping clipped union piece | Explicit seconds calculation | Seconds |", "|---|---|---:|"]
        for piece in case["union_pieces"]:
            h, rest = divmod(piece["seconds"], 3600)
            m, s = divmod(rest, 60)
            join_lines.append(f"| {piece['start']} → {piece['end']} | {h}×3600 + {m}×60 + {s} | {piece['seconds']} |")
        join_lines += ["", "Union watched time = "+" + ".join(str(p["seconds"]) for p in case["union_pieces"])+f" = **{case['watched_seconds']} seconds**.",
                       f"Coverage = {case['watched_seconds']} / {case['duration']} = **{case['coverage_fraction']} = {case['coverage']:.12f}**.",
                       f"Exact 80% test: 5×{case['watched_seconds']} = **{case['five_times_watched']}** {'≥' if case['watched'] else '<'} 4×{case['duration']} = **{case['four_times_duration']}**.",
                       f"Decision: **{'watched / counts once' if case['watched'] else 'not watched / does not count'}**."]
    join_lines += ["", "## Programme counts and boundary tie", "", "The independent full-validation rejoin recovers **six qualifying programmes**, with one qualifying airing each. Sorting frequency descending and numeric ID ascending reproduces **"+" ".join(str(i) for i, n in manual_counts[:5])+"**. All six tie at the Top-5 boundary; this is the documented local tie convention, not proof of the organiser's hidden tie rule.",
                   "", "| Rank | Programme ID | Qualifying airings | In local Top-5? |", "|---:|---:|---:|---|"]
    join_lines += [f"| {rank} | {item} | {count} | {'yes' if rank <= 5 else 'no'} |" for rank, (item, count) in enumerate(manual_counts, 1)]
    join_lines += ["", "## Source evidence", "", "- manual_join_raw_views.csv: all 783 original rows for this user, with source CSV records.",
                   "- manual_join_raw_fragments.csv: original matching rows and their clipped intersections for the two worked airings.",
                   "- manual_join_union_intervals.csv: the union pieces used in the arithmetic.",
                   "- manual_join_independent_airings.csv: independently reconstructed positive validation intersections for the manual and AP users.",
                   "- manual_join_programme_counts.csv: complete manual-user qualified counts and local Top-5 flags.",
                   "", "Both the positive 6,752/7,200 case and the negative (4,336+836)/6,900 case exactly match the original interactions example. These are assistant-executed raw-source checks; student personal verification remains pending.", ""]
    (OUT / "hand_join.md").write_text("\n".join(join_lines), encoding="utf-8")
    rebuilt = ROOT / result["rebuilt_submission"]
    check("rebuilt final CSV remains byte-identical after hand checks", filecmp.cmp(rebuilt, ROOT / result["published_submission"], shallow=False))
    with rebuilt.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    template_ids = [r["user_id"] for r in read(DATA / "submission.csv")]
    pool = {int(r["tv_show_id"]) for r in read(work / "final/candidate_scores.csv")}
    check("scratch final format: header, exact 1260 template strings/order, five distinct eligible IDs", rows[0] == ["user_id", "tv_show_id"] and len(rows)-1 == 1260 and [r[0] for r in rows[1:]] == template_ids and all(len(r) == 2 and len(r[1].split()) == len(set(r[1].split())) == 5 and all(i.isdecimal() and int(i) > 0 and int(i) in pool for i in r[1].split()) for r in rows[1:]))
    check("frozen raw inputs/configs/code/reference CSV unchanged after all checks", initial_hashes == {k: digest(ROOT / p) for k, p in input_manifest["paths"].items()})
    hand_result = {"status": "passed", "checks": checks, "ap_user": ap_user, "ap_exact": str(total), "ap_decimal": float(total),
                   "ap_predictions": predicted, "ap_truth": actual, "manual_user": manual_user, "manual_cases": cases,
                   "manual_user_raw_rows": 783, "manual_user_qualified_programmes": len(manual_counts), "hand_checker_sha256": digest(Path(__file__))}
    dump(OUT / "hand_checks.json", hand_result)
    combined = {"status": "passed", "scratch_rebuild": result, "hand_checks": hand_result,
                "meaning": "Frozen final-strategy reproducibility and assistant-worked arithmetic only; no new tuning, upload, score claim or student-personal verification"}
    dump(OUT / "verification.json", combined)
    commands = json.loads((work / "commands.json").read_text())
    summary_lines = ["# Final reproducibility and hand checks", "", "**PASS: a fresh raw-CSV rebuild produces the exact original submission_007.csv.**", "",
                     f"- Fresh output: `{result['rebuilt_submission']}`.", f"- Original: `{result['published_submission']}`.",
                     f"- **Byte-identical: yes. Changed users: 0 / {result['rows']}.**",
                     f"- All **{result['logical_stage_comparisons']} logical intermediate comparisons match exactly**, including raw-derived interactions/labels, counts, MF factors, graph, rules, CBF vectors/profiles, model scores and validation rankings.",
                     "- Separate guarded processes deny reads of old artifacts/reports/submissions during fitting. The access logs show **zero forbidden old-derived accesses**. Old results are read only afterwards for comparison.",
                     "- Raw files, frozen configurations, compute code and the published CSV remain unchanged.", "", "SHA-256 of both CSVs:", "", "```text", result["rebuilt_sha256"], "```", "",
                     "## What was replayed", "", "Raw data audit → fresh split interactions and labels → all six selected validation strategies (popularity, CBF, weekly rules, eight-week MF/PPR and final007 fusion) → fresh full weeks11–30 rejoin → new final007 factors, co-view graph, rule mining, scores and fusion. Parameters stay frozen; the historical search is not rerun. This is reproducibility verification, not a new experiment or submission.",
                     "", "## Hand checks", "", f"1. **[hand_ap.md](hand_ap.md):** validation user `{ap_user}`; hit pattern yes/no/yes/yes/no. AP@5 = (1 + 2/3 + 3/4)/5 = **29/60 = 0.483333333333**. Raw-source truth and the scorer agree.",
                     f"2. **[hand_join.md](hand_join.md):** original user `{manual_user}`. Programme700389: **6752/7200 = 0.937777777778**, qualifies. Programme90076035: **(4336+836)/6900 = 0.749565217391**, does not qualify. Raw record references, clipped fragments, union pieces and all six validation programme counts are saved.",
                     "", "## Reproduce / inspect", "", "```bash", "python3 scripts/run_final_check.py", "python3 scripts/hand_final_checks.py", "```", "",
                     "Each replay creates a new numbered rebuild folder and keeps earlier runs. `latest_run.json` identifies the run. `rebuild_result.json`, `stage_reconciliation.csv` and `verification.json` summarize outcomes. The rebuild folder contains `configuration.json`, `input_manifest.json`, `commands.json`, all fresh model/interactions artifacts and logs/access manifests. Commands and environment are saved there.",
                     f"This run took {result['elapsed_seconds']:.1f}s for audit/build/model/comparison stages; stage times: "+", ".join(f"{c['stage']} {c['seconds']:.1f}s" for c in commands)+".",
                     "", "No differences were found to investigate. JSON report generation times and container metadata are not treated as model differences; model/interactions values and ordering are compared directly, and the final CSV is compared byte-for-byte. Local timezone/fragment-union and frequency-tie assumptions remain the documented reconstruction choices. All checks here were performed by the assistant; the student's personal checks are not claimed.", ""]
    (OUT / "README.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Hand AP: {total} = {float(total):.12f}; original join decisions exactly reproduced.")
    print(f"Saved {OUT / 'README.md'}, hand_ap.md, hand_join.md, worksheets and source evidence.")


if __name__ == "__main__":
    main()
