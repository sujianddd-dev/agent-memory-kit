# agent-memory-kit

[![ci](https://github.com/sujianddd-dev/agent-memory-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/sujianddd-dev/agent-memory-kit/actions/workflows/ci.yml)


Two-layer memory for AI coding agents, extracted from a working deployment:

- **mem0** holds atomic facts (preferences, decisions, project state) behind a
  strict `user_id` namespace.
- **Obsidian** holds reusable knowledge as dated, categorized Markdown notes.
- A local **ledger** (SHA-256) keeps ingestion idempotent.
- **Email / message auto-reply** runs behind hard guardrails: bulk filters,
  quotas, per-sender cooldown, and loop protection.

The point is not "store everything in one database". It is: **every kind of
memory lives where it can be retrieved correctly, and the same content is never
maintained twice**.

## Why this exists

After running this setup for a few weeks we hit three failures that are easy to
reproduce and expensive to debug:

1. A sandboxed child process running the sender CLI: the parent only checked the
   exit code, so "0" looked healthy while nothing was ever sent.
2. Reading a UTF-8 stream with the system ANSI code page: the JSON broke in the
   middle of a CJK string.
3. Assuming the server replays undelivered messages: it does not. One failed
   parse means a permanently dropped message unless you reconcile.

The guardrails in this repo are the fixes for those failures.

## Layout

```
kit/ingest.py          # JSONL -> mem0, with redaction + hash ledger + dry-run
kit/obsidian_note.py   # write one knowledge note + daily index entry
kit/email_watch.py     # IMAP poll -> rules -> optional LLM judge -> SMTP reply
docs/DESIGN.md         # principles, invariants, failure modes
examples/queue.jsonl   # input format for ingest.py
```

## Quick start

```bash
# 1. ingest facts (dry-run first)
python kit/ingest.py --input examples/queue.jsonl --ledger ./ledger.jsonl --dry-run

# 2. write a knowledge note
python kit/obsidian_note.py --vault /path/to/vault \
  --category protocols --title "Unattended agents need receipts" \
  --summary "Exit code is not delivery." \
  --point "Check a receipt, not a return code." \
  --source-item 123

# 3. email watcher (needs env, see below)
python kit/email_watch.py --once --dry-run
```

## Environment

| Variable | Used by | Meaning |
|---|---|---|
| `MEM0_USER_ID` | ingest.py | mem0 scope (default `dsh`) |
| `MEM0_AGENT_ID` | ingest.py | mem0 agent scope |
| `MEM0_APP_ID` | ingest.py | mem0 app scope |
| `MEM0_LEDGER` | ingest.py | path to the dedupe ledger |
| `BRAIN_CMD` | email_watch.py | command that answers a prompt on stdout (default `dsh --profile headless`) |
| `IMAP_HOST` / `IMAP_USER` / `IMAP_PASSWORD` | email_watch.py | mailbox |
| `SMTP_HOST` / `SMTP_PORT` | email_watch.py | sending |

No credentials are stored in this repo.

## Guardrails (non-negotiable)

- Ingestion is **append-only** and deduped by SHA-256 of normalized text.
- Secrets, emails and absolute paths are redacted **before** anything leaves
  the machine.
- Auto-replies have a daily cap, a per-sender cooldown, and an
  `Auto-Submitted: auto-replied` header so they cannot loop.
- `--no-infer` is used when exact text matters; inference is opt-in.

## License

MIT

