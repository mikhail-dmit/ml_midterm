#!/usr/bin/env python3
"""Check staged Git blob sizes against the requested 50 MB per-file limit."""

import subprocess
import sys

LIMIT = 50_000_000


def main():
    records = subprocess.check_output(["git", "ls-files", "--stage", "-z"]).split(b"\0")
    entries = []
    for record in records:
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        entries.append((oid.decode(), path.decode("utf-8")))
    objects = sorted({oid for oid, path in entries})
    query = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                           input="\n".join(objects)+"\n", text=True, check=True, capture_output=True)
    sizes = {line.split()[0]: int(line.split()[2]) for line in query.stdout.splitlines()}
    bad = [(path, sizes[oid]) for oid, path in entries if sizes[oid] > LIMIT]
    total = sum(sizes[oid] for oid, path in entries)
    print(f"Staged files: {len(entries)}; total uncompressed bytes: {total:,}; per-file limit: {LIMIT:,}.")
    for path, size in bad:
        print(f"TOO LARGE: {path}: {size:,} bytes")
    if bad:
        sys.exit(1)
    print("PASS: no staged file exceeds 50 MB.")


if __name__ == "__main__":
    main()
