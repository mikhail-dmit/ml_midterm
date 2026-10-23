#!/usr/bin/env python3
"""Run one scratch stage while denying access to all pre-existing derived outputs."""

import argparse
import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--access-log", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    work = args.work_dir.resolve()
    blocked_roots = [ROOT / "artifacts", ROOT / "reports", ROOT / "submissions"]
    reads, writes, denied = set(), set(), []

    def audit(event, details):
        if event != "open" or not isinstance(details[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(details[0])).resolve()
        if any(path.is_relative_to(parent) for parent in blocked_roots) and not path.is_relative_to(work):
            denied.append(str(path))
            raise PermissionError(f"Scratch rebuild attempted an old derived artifact: {path}")
        flags = details[2] if len(details) > 2 else 0
        mode = details[1] or ""
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)) or any(c in str(mode) for c in "wax+")
        (writes if writing else reads).add(str(path))

    sys.addaudithook(audit)
    forwarded = args.args[1:] if args.args[:1] == ["--"] else args.args
    sys.argv = [str(args.script), *forwarded]
    status = "passed"
    try:
        runpy.run_path(str(args.script), run_name="__main__")
    except BaseException:
        status = "failed"
        raise
    finally:
        args.access_log.write_text(json.dumps({"status": status, "work_dir": str(work), "script": str(args.script),
             "argv": forwarded, "forbidden_old_derived_accesses": denied, "read_paths": sorted(reads),
             "write_paths": sorted(writes), "policy": "Raw CSVs, source/dependency code and this new run's artifacts only; old artifacts/reports/submissions forbidden"}, indent=2)+"\n")


if __name__ == "__main__":
    main()
