#!/usr/bin/env python3
"""Render verified example facts as report-ready Markdown, HTML and compact tables."""

import csv
import html
import json
from pathlib import Path

from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_examples"
METHODS = ["popularity", "cbf", "association_rules", "mf", "ppr", "hybrid_007"]
LABELS = {"popularity": "Popularity", "cbf": "CBF", "association_rules": "Association rules", "mf": "MF (8-week recency)", "ppr": "PPR (8-week recency)", "hybrid_007": "Final 007 hybrid"}


def read(name):
    with (OUT / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def md(value):
    return html.escape(str(value), quote=False).replace("|", "\\|").replace("\n", "<br>")


def markdown_table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "|"+"---|"*len(headers)] + ["| "+" | ".join(md(c) for c in row)+" |" for row in rows]


def html_table(headers, rows):
    return "<table><thead><tr>"+"".join("<th>"+html.escape(str(h))+"</th>" for h in headers)+"</tr></thead><tbody>"+"".join("<tr>"+"".join("<td>"+html.escape(str(c))+"</td>" for c in row)+"</tr>" for row in rows)+"</tbody></table>"


def main():
    verification = json.loads((OUT / "verification.json").read_text())
    assert verification["status"] == "passed"
    selection = json.loads((OUT / "selection.json").read_text())
    comments = json.loads((OUT / "comments.json").read_text())
    recs, actual, metrics = read("recommendations.csv"), read("validation_watches.csv"), read("method_metrics.csv")
    stats = {r["role"]: r for r in read("selected_users.csv")}
    side_rows = read("side_by_side.csv")
    assert len(recs) == len(side_rows) == 60
    legend_map = {}
    for r in recs + [r for r in actual if r["in_true_top5"] == "True"]:
        legend_map.setdefault(r["tv_show_id"], (r["title"], r["category"]))
    legend = [[item, *legend_map[item]] for item in sorted(legend_map, key=int)]
    with (OUT / "programme_legend.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tv_show_id", "title", "category"])
        writer.writerows(legend)
    legend_text = "✓ = member of the user's true five-ID target set; ○ = qualifying validation watch outside that set; ~ = observed partial overlap only, no >=80% qualifying watch; — = no recorded programme overlap. A hit is membership anywhere in the true set, not equality with the actual programme on the same displayed row."
    protocol = "Training: weeks 11–20, [2020-03-09, 2020-05-18). Validation: weeks 21–30, [2020-05-18, 2020-07-27), Europe/Kyiv. These are cached out-of-sample predictions from the validation-trained version of final 007; all model histories stop before validation. The uploaded 007 uses the same recipe refitted on weeks 11–30 for the later test period."
    selection_text = "Within the fixed 4,030-user primary validation cohort, select the maximum and minimum nonzero original >=80%-qualified training-airing counts. Break ties by the ascending decimal user-ID string. The unique heavy maximum is 1,845 watches; eighteen light users tie at one watch. These reproduce the previously selected examples, without inspecting predictions or AP for selection. They illustrate boundary cases rather than a representative performance sample."
    label_policy = "Prediction titles/categories are representative pre-cutoff catalogue labels. A programme ID can cover changing episodes/titles, so a SpongeBob episode title in a recommendation need not equal the later episode title. The actual column uses the latest genuinely qualified validation airing's title/category. All frequency counts aggregate by programme ID. Only labelled, nonzero-ID airtime is evaluated."
    lines = ["# Final report examples: one heavy and one light validation viewer", "",
             "Final strategy: **submission 007**, user-reported Kaggle **public 0.43707 / private 0.42472**, linked to its CSV hash and screenshot. **Experiments are closed by user instruction.**", "",
             "## Start here", "",
             "- **examples.html**: full ID/title/category tables for all six methods, with actual watches next to the predictions; browser-friendly for copying or printing.",
             "- **compact_tables.md**: rank-by-method ID tables, shared title/category legend and short comments for a compact PDF layout.",
             "- **side_by_side.md / side_by_side.csv**: each method's five predictions directly beside the user's actual five favourites.",
             "- **short_comments.md / comments.json**: concise report prose and fuller per-method explanations.",
             "- **validation_watches.csv**: every qualified validation programme (210 heavy, 5 light), not just the five targets. Raw partial overlaps and source records are retained separately.", "",
             "## Choice of viewers", "", selection_text, "", protocol, "", label_policy, "", "## Hit legend", "", legend_text, "",
             "## Local example metrics", ""]
    metric_rows = []
    for method in METHODS:
        pair = {r["role"]: r for r in metrics if r["method"] == method}
        metric_rows.append([LABELS[method], pair["heavy"]["hits_at_5"]+"/5", f"{float(pair['heavy']['AP_at_5']):.4f}", pair["light"]["hits_at_5"]+"/5", f"{float(pair['light']['AP_at_5']):.4f}"])
    lines += markdown_table(["Method", "Heavy hits", "Heavy AP@5", "Light hits", "Light AP@5"], metric_rows)
    compact = ["# Compact report tables", "", selection_text, "", protocol, "", "Use the shared programme legend below for each ID's full title/category. Hit marks are based on ID membership in the entire true Top-5.", "", legend_text, ""]
    side_md = ["# Predictions directly beside actual validation favourites", "", protocol, "", label_policy, "", legend_text, ""]
    short = ["# Short comments for the report", "", selection_text, "", "MF/PPR below are the final hybrid's eight-week-recency components, not the earlier undecayed reference runs. CBF uses the selected strict-history title/metadata TF-IDF profile; rules remain strict weekly rules; popularity remains unweighted 50%-history popularity. All use the same train/validation dates and fixed truth.", ""]
    page = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Final validation examples</title>",
            "<style>body{font:14px system-ui,sans-serif;color:#18212b;max-width:1500px;margin:24px auto;padding:0 18px}table{border-collapse:collapse;width:100%;margin:10px 0 18px;font-size:12px}th,td{border:1px solid #cad2dc;padding:6px;vertical-align:top;text-align:left}th{background:#eef2f7}h1,h2,h3{color:#17385e}.grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,1fr);gap:24px}.note{padding:10px;background:#fff8dc;border-left:4px solid #e2aa20}.muted{color:#475569}code{font-family:ui-monospace,monospace}.user{margin-top:30px;border-top:2px solid #17385e;padding-top:15px}@media(max-width:950px){.grid{display:block}}@media print{@page{size:A4 landscape;margin:12mm}body{font-size:11px;margin:0;padding:0}table{font-size:9px}th,td{padding:4px}.user{break-before:page}tr{break-inside:avoid}.all-watches{display:none}a{color:inherit}}</style></head><body>",
            "<h1>Final report: heavy/light validation examples</h1><p><b>Final 007: public 0.43707, private 0.42472. Experiments closed.</b></p>",
            "<p>"+html.escape(selection_text)+"</p><p>"+html.escape(protocol)+"</p><p class='muted'>"+html.escape(label_policy)+"</p><p class='note'>"+html.escape(legend_text)+"</p>",
            html_table(["Method", "Heavy hits", "Heavy AP@5", "Light hits", "Light AP@5"], metric_rows)]
    compact_csv = []
    for role in ["heavy", "light"]:
        user = selection["users"][role]
        st, comment = stats[role], comments[role]
        truth_rows = [r for r in actual if r["role"] == role and r["in_true_top5"] == "True"]
        heading = f"{role.title()} viewer — {user}"
        stats_text = f"Training: {int(st['train_airings_80pct']):,} >=80% watches / {int(st['train_programmes_80pct']):,} programmes; {int(st['train_airings_50pct']):,} >=50% watches / {int(st['train_programmes_50pct']):,} programmes. Validation: {int(st['validation_airings_80pct']):,} qualifying watches / {int(st['validation_programmes_80pct']):,} programmes."
        actual_display = [[r["actual_rank"], r["tv_show_id"], r["latest_watched_title"], r["latest_watched_category"], r["qualified_validation_airings"]] for r in truth_rows]
        lines += ["", "## "+heading, "", comment["selection"], "", stats_text, "", "### What the user actually watched: true Top-5", ""]
        lines += markdown_table(["Actual rank", "Show ID", "Latest watched title", "Category", ">=80% airings"], actual_display)
        lines += ["", "### All six methods, in prediction order", ""]
        # Full-title rank-by-method matrix; HTML below offers a narrower layout.
        matrix = []
        id_matrix = []
        for rank in range(1, 6):
            full, ids = [rank], [rank]
            for method in METHODS:
                r = next(r for r in recs if r["role"] == role and r["method"] == method and int(r["predicted_rank"]) == rank)
                full.append(f"{r['hit_marker']} {r['tv_show_id']} — {r['title']} [{r['category']}]")
                ids.append(f"{r['hit_marker']} {r['tv_show_id']}")
            matrix.append(full)
            id_matrix.append(ids)
            compact_csv.append([role, user, *ids])
        lines += markdown_table(["Rank"]+[LABELS[m] for m in METHODS], matrix)
        lines += ["", "### Short interpretation", "", comment["short_comment"], "", "### Per-method comments", ""]
        lines += [f"- **{LABELS[m]}:** {comment['methods'][m]}" for m in METHODS]
        lines += ["", "**Important interpretation:** "+comment["limitation"], ""]
        compact += ["## "+heading, "", stats_text, "", "**Actual Top-5:** "+"; ".join(f"{r['tv_show_id']} × {r['qualified_validation_airings']}" for r in truth_rows)+".", ""]
        compact += markdown_table(["Prediction rank"]+[LABELS[m] for m in METHODS], id_matrix)
        local_metrics = {r["method"]: r for r in metrics if r["role"] == role}
        compact += ["", "**AP@5:** "+"; ".join(LABELS[m]+f" {float(local_metrics[m]['AP_at_5']):.4f}" for m in METHODS)+".", "", comment["short_comment"], "", "**Qualification:** "+comment["limitation"], ""]
        short += ["## "+heading, "", comment["selection"], "", comment["short_comment"], "", "**Interpretation limit:** "+comment["limitation"], ""]
        side_md += ["## "+heading, "", stats_text, ""]
        page += ["<section class='user'><h2>"+html.escape(heading)+"</h2><p>"+html.escape(comment["selection"])+"</p><p>"+html.escape(stats_text)+"</p><div class='grid'><div><h3>Method predictions</h3>"]
        for method in METHODS:
            rows = [r for r in recs if r["role"] == role and r["method"] == method]
            display = [[r["predicted_rank"], r["tv_show_id"], r["title"], r["category"], r["hit_marker"], r["qualified_validation_airings"]] for r in rows]
            page += ["<h3>"+html.escape(LABELS[method])+f" — {local_metrics[method]['hits_at_5']}/5, AP@5={float(local_metrics[method]['AP_at_5']):.4f}</h3>", html_table(["Rank", "Show ID", "Title", "Category", "Hit", "Validation airings"], display)]
            side_md += ["### "+LABELS[method]+f" — AP@5={float(local_metrics[method]['AP_at_5']):.4f}", ""]
            joined = [r for r in side_rows if r["role"] == role and r["method"] == method]
            side_md += markdown_table(["Pred. rank", "Prediction: ID — title [category]", "Hit", "Predicted ID's val. watches", "Actual favourite at frequency rank r: ID — title [category]", "Actual watches"],
                                       [[r["predicted_rank"], f"{r['tv_show_id']} — {r['title']} [{r['category']}]", r["hit_marker"], r["qualified_validation_airings"],
                                         f"{r['actual_tv_show_id']} — {r['actual_latest_watched_title']} [{r['actual_latest_watched_category']}]", r["actual_qualified_airings"]] for r in joined])
            side_md += ["", comment["methods"][method], ""]
        page += ["</div><aside><h3>Actual validation favourites</h3>", html_table(["Freq. rank", "Show ID", "Latest watched title", "Category", "Airings"], actual_display),
                 "<p class='note'>"+html.escape(comment["limitation"])+"</p>", "<h3>Other recommended IDs that were watched</h3>"]
        other_ids = {r["tv_show_id"] for r in recs if r["role"] == role and r["hit_marker"] == "○"}
        extra = [r for r in actual if r["role"] == role and r["tv_show_id"] in other_ids]
        page += [html_table(["Actual rank", "ID", "Title", "Airings"], [[r["actual_rank"], r["tv_show_id"], r["latest_watched_title"], r["qualified_validation_airings"]] for r in extra]) if extra else "<p>None among these recommendations.</p>",
                 "<h3>Short interpretation</h3><p>"+html.escape(comment["short_comment"])+"</p>", "<ul>"+"".join("<li><b>"+html.escape(LABELS[m])+":</b> "+html.escape(comment["methods"][m])+"</li>" for m in METHODS)+"</ul>",
                 "<details class='all-watches'><summary>All qualified validation programmes</summary>", html_table(["Rank", "ID", "Latest watched title", "Category", "Airings"], [[r["actual_rank"], r["tv_show_id"], r["latest_watched_title"], r["latest_watched_category"], r["qualified_validation_airings"]] for r in actual if r["role"] == role]), "</details></aside></div></section>"]
    compact += ["## Shared programme legend", "", "Representative pre-cutoff labels, keyed by programme ID; episode titles can vary in validation.", ""]
    compact += markdown_table(["Show ID", "Title", "Category"], legend)
    compact += ["", "All complete actual-watch frequencies and latest watched episode labels are in validation_watches.csv. The heavy user's fifth-place tie is described above; it is retained, not silently resolved in the model's favour.", ""]
    short += ["## Overall conclusion for these examples", "", "The final hybrid is selected for cohort performance and the designated Kaggle result, yet it does not beat popularity on these two retained training-selected examples. The cases show recurring-favourite recovery, the value of partial history, metric boundary ties, and shared-error reinforcement in fusion. They are explanations, not a two-user evaluation of general superiority.", ""]
    lines += ["## Method versions and reproducibility", "", "See method_definitions.csv for exact prediction paths and thresholds. MF/PPR are the final hybrid's eight-week-recency validation components. CBF uses strict-80% history and frozen pre-cutoff title/metadata TF-IDF; weekly rules use strict history; popularity uses unweighted 50%-qualified counts. The same two viewers are used for all six methods.", "",
              f"**{len(verification['checks'])} independent checks passed**, including an independent standard-library raw-log/schedule interval rejoin for both viewers: {verification['raw_view_rows_for_selected_users']:,} raw view rows and {verification['independent_positive_airing_overlaps']:,} positive train/validation user-airing overlaps. Counts, truth, boundary ties, all sixty predictions/hits/AP values, labels and source contributions were checked. This is assistant-executed verification; student personal review remains pending.", "",
              "```bash", "python3 scripts/build_final_examples.py", "python3 scripts/verify_final_examples.py", "python3 scripts/render_final_examples.py", "```", "",
              "Evidence: frozen_inputs.json, selection.json, selected_users.csv, training_profiles.csv, validation_qualified_airings.csv, validation_programme_overlaps.csv, raw_selected_views.csv, independent_raw_airing_matches.csv, cbf_feature_contributions.csv, association_rule_contributions.csv, hybrid_score_contributions.csv and verification.json. No fitting or further model experiment is performed by these scripts.", ""]
    page += [f"<footer><p>{len(verification['checks'])} independent assistant checks passed, including raw CSV rejoining. Student personal review is pending. Exact sources and reproduction commands are in README.md.</p></footer></body></html>"]
    for filename, contents in [("README.md", "\n".join(lines)), ("compact_tables.md", "\n".join(compact)), ("side_by_side.md", "\n".join(side_md)), ("short_comments.md", "\n".join(short)), ("examples.html", "\n".join(page))]:
        (OUT / filename).write_text(contents, encoding="utf-8")
    with (OUT / "compact_cells.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["role", "user_id", "rank", *METHODS])
        writer.writerows(compact_csv)
    outputs = ["README.md", "compact_tables.md", "side_by_side.md", "short_comments.md", "examples.html", "compact_cells.csv", "programme_legend.csv"]
    dump(OUT / "render_manifest.json", {"renderer_sha256": digest(Path(__file__)), "comments_sha256": digest(OUT / "comments.json"),
         "verification_sha256": digest(OUT / "verification.json"), "outputs_sha256": {name: digest(OUT / name) for name in outputs}})
    print(f"Saved report-ready HTML, full/compact Markdown, literal side-by-side tables and short comments under {OUT}")


if __name__ == "__main__":
    main()
