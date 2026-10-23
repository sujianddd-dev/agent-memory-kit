#!/usr/bin/env python3
"""Turn an accepted suggestion into a GitHub issue.

Used at step 4 of docs/WORKFLOW.md. Requires the `gh` CLI to be authenticated.
"""
from __future__ import annotations

import argparse
import subprocess


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default="")
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    body = args.body
    if args.body_file:
        body = open(args.body_file, encoding="utf-8").read()

    cmd = ["gh", "issue", "create", "--repo", args.repo, "--title", args.title, "--body", body or "(no details)"]
    for label in args.label:
        cmd += ["--label", label]

    if args.dry_run:
        print(" ".join(cmd))
        return 0

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout.strip() or proc.stderr.strip())
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
