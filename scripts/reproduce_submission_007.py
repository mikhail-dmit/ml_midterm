#!/usr/bin/env python3
"""Reproduce 007 from raw CSVs on a clean clone, without historical artifacts."""

import filecmp
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sweettv-tv-program-recommender"
EXPECTED = "8d3bc085cb0a830cbab5c68789470c608fd34bb840dffbe75e4dd43833f87d8c"


def main():
    started = time.perf_counter()
    required = ["dataset11-30.csv", "export_arh_11-20-final.csv", "export_arh_21-30-final.csv", "export_arh_31-42-final.csv", "submission.csv"]
    missing = [name for name in required if not (DATA / name).is_file()]
    if missing:
        raise SystemExit("Download/extract Kaggle data into " + str(DATA) + "; missing: " + ", ".join(missing))
    reference = ROOT / "submissions/submission_007.csv"
    if digest(reference) != EXPECTED:
        raise AssertionError("The designated tracked submission has changed")
    parent = ROOT / "artifacts"
    parent.mkdir(exist_ok=True)
    n = 1
    while (parent / f"reproduce_007_{n:03d}").exists():
        n += 1
    work = parent / f"reproduce_007_{n:03d}"
    work.mkdir()
    (work / "logs").mkdir()
    dump(work / "configuration.json", {"hybrid": json.loads((ROOT / "configs/final_007.json").read_text()),
         "cbf": json.loads((ROOT / "configs/cbf_selected.json").read_text()), "policy": "Frozen recipe; new raw-derived interactions and models only"})
    hashes = {name: digest(DATA / name) for name in required}
    commands = []
    def stage(name, script, args):
        cmd = [sys.executable, str(ROOT / "scripts/final_check_sandbox.py"), "--work-dir", str(work),
               "--access-log", str(work / "logs" / f"{name}_access.json"), "--script", str(ROOT / "scripts" / script), "--", *args]
        print(f"Rebuilding {name} from raw inputs ...", flush=True)
        clock = time.perf_counter()
        with (work / "logs" / f"{name}.log").open("w", encoding="utf-8") as log:
            outcome = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        commands.append({"stage": name, "command": shlex.join(cmd), "seconds": time.perf_counter()-clock, "returncode": outcome.returncode})
        dump(work / "commands.json", commands)
        if outcome.returncode:
            raise RuntimeError(f"{name} failed: inspect {work / 'logs' / (name+'.log')}")
        access = json.loads((work / "logs" / f"{name}_access.json").read_text())
        if access["status"] != "passed" or access["forbidden_old_derived_accesses"]:
            raise AssertionError("Reproduction used an old derived artifact")
    stage("interactions", "build_interactions.py", ["--data-dir", str(DATA), "--artifact-dir", str(work / "interactions"), "--report-dir", str(work / "interaction_reports")])
    stage("models", "final_check_models.py", ["--work-dir", str(work), "--data-dir", str(DATA)])
    generated = work / "final/submission_007.csv"
    identical = filecmp.cmp(generated, reference, shallow=False)
    info = {"status": "passed" if identical else "different", "generated_file": str(generated.relative_to(ROOT)),
            "reference_file": "submissions/submission_007.csv", "generated_sha256": digest(generated), "expected_sha256": EXPECTED,
            "byte_identical": identical, "elapsed_seconds": time.perf_counter()-started, "stage_times": commands,
            "raw_inputs_sha256": hashes, "old_derived_artifact_accesses": 0,
            "configuration_sha256": {name: digest(ROOT / "configs" / name) for name in ["final_007.json", "cbf_selected.json"]},
            "environment": json.loads((work / "environment.json").read_text())}
    dump(work / "reproduction_result.json", info)
    proof = ROOT / "reports/repo_reproduction"
    proof.mkdir(parents=True, exist_ok=True)
    dump(proof / "summary.json", info)
    if hashes != {name: digest(DATA / name) for name in required}:
        raise AssertionError("Raw inputs changed during reproduction")
    print(f"Generated: {generated}")
    print(f"SHA-256: {info['generated_sha256']}; byte-identical: {identical}; elapsed: {info['elapsed_seconds']:.1f}s")
    if not identical:
        raise AssertionError("Inspect the new output before claiming reproduction; reference is preserved")


if __name__ == "__main__":
    main()
