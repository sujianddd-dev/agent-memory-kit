#!/usr/bin/env python3
"""Write one categorized knowledge note into an Obsidian vault.

Layout:
  <vault>/knowledge/<category>/<YYYY-MM-DD>-<slug>.md
  <vault>/knowledge/daily/<YYYY-MM-DD>.md   (index)

The script owns formatting and dedupe (same day + same title = skip). It does
not call any model: feed it already-extracted knowledge.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

CATEGORIES = ("agents", "protocols", "memory", "tools", "projects", "insights")


def slugify(text: str, limit: int = 36) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', " ", text).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-. ")
    return (cleaned[:limit].strip("-. ") or "note")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--title", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--point", action="append", default=[])
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--source-item", action="append", default=[])
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    vault = Path(args.vault)
    target_dir = vault / "knowledge" / args.category
    daily_dir = vault / "knowledge" / "daily"
    target_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(args.title)
    note = target_dir / f"{args.date}-{slug}.md"
    if note.exists():
        print(f"skip exists: {note}")
        return 0

    tags = ", ".join(["knowledge"] + args.tag)
    body = [
        "---",
        f'title: "{args.title.replace(chr(34), chr(39))}"',
        f"date: {args.date}",
        f"created: {datetime.now().isoformat(timespec='seconds')}",
        f"category: {args.category}",
        f"tags: [{tags}]",
        "source: agent-memory-kit",
    ]
    if args.source_item:
        body.append("source_items: [" + ", ".join(args.source_item) + "]")
    body += ["---", "", f"# {args.title}", "", "## Summary", "", args.summary, ""]
    if args.point:
        body += ["## Points", ""] + [f"- {p}" for p in args.point] + [""]
    body += ["## Provenance", "", f"- date: {args.date}", "- written by agent-memory-kit"]
    note.write_text("\n".join(body) + "\n", encoding="utf-8")

    daily = daily_dir / f"{args.date}.md"
    if not daily.exists():
        daily.write_text(f"# {args.date} knowledge index\n\n", encoding="utf-8")
    with daily.open("a", encoding="utf-8") as fh:
        fh.write(f"- [{args.title}](../{args.category}/{note.name}) · {args.category}\n")

    print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
