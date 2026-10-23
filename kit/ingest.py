#!/usr/bin/env python3
"""Ingest atomic facts into mem0 with redaction, hash dedupe and dry-run.

Input: JSONL, one object per line:
  {"text": "...", "metadata": {"scene": "working", "layer": "experience"}}

The mem0 CLI is called once per line with `--no-infer`, so the stored text is
exactly what was written (no server-side re-extraction).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SECRET_KEY = re.compile(
    r"(?i)(api[_ ]?key|access[_ ]?key|token|password|passwd|secret|密码|授权码|密钥)"
    r"\s*[:：=]\s*[^\s,;，。]+"
)
SECRET_SPACE = re.compile(r"(?i)(密钥|密码|授权码)\s+([A-Za-z0-9!@#$%^&*._-]{4,})")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WIN_PATH = re.compile(r"(?i)[A-Z]:\\\\?Users\\\\?[^\s,;，。、)]+")
HOME_PATH = re.compile(r"(?i)~?[\\/]\.(ssh|aws|config|dsh|hermes)[\\/][^\s,;，。、)]*")


def redact(text: str) -> str:
    text = re.sub(r"m0-[A-Za-z0-9]{16,}", "[APIKEY]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[APIKEY]", text)
    text = SECRET_KEY.sub(r"\1=[REDACTED]", text)
    text = SECRET_SPACE.sub(r"\1 [REDACTED]", text)
    text = EMAIL.sub("[EMAIL]", text)
    text = WIN_PATH.sub("[PATH]", text)
    text = HOME_PATH.sub("[PATH]", text)
    return text.strip()


def digest(text: str) -> str:
    norm = re.sub(r"\s+", "", text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def load_ledger(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def add_to_mem0(text: str, metadata: dict) -> tuple[bool, str]:
    cmd = [
        "mem0", "add", text,
        "-u", os.environ.get("MEM0_USER_ID", "dsh"),
        "--agent-id", os.environ.get("MEM0_AGENT_ID", "dsh"),
        "--app-id", os.environ.get("MEM0_APP_ID", "agent-memory-kit"),
        "-m", json.dumps(metadata, ensure_ascii=False),
        "--no-infer", "-o", "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0, (proc.stdout or proc.stderr or "")[-300:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--ledger", default=os.environ.get("MEM0_LEDGER", "ledger.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    seen = load_ledger(ledger_path)
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    added = skipped = failed = 0
    for row in rows:
        text = redact(str(row.get("text", "")))
        if len(text) < 8:
            skipped += 1
            continue
        h = digest(text)
        if h in seen:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry] {text[:80]}")
            skipped += 1
            continue
        ok, detail = add_to_mem0(text, row.get("metadata") or {})
        if ok:
            added += 1
            seen.add(h)
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(h + "\n")
            print(f"[add] {text[:60]}")
        else:
            failed += 1
            print(f"[fail] {detail}", file=sys.stderr)

    print(f"done added={added} skipped={skipped} failed={failed} ledger={len(seen)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
