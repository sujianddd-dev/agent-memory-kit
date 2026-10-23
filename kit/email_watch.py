#!/usr/bin/env python3
"""Conservative autonomous email replies.

Poll IMAP, drop obvious bulk before any model call, ask a "brain" command for a
strict JSON verdict, then reply over SMTP with proper threading headers.

Guardrails: daily cap, per-sender cooldown, Auto-Submitted loop protection,
first run only records a baseline UID.

Environment:
  IMAP_HOST, IMAP_USER, IMAP_PASSWORD
  SMTP_HOST (default same as IMAP with smtp. prefix), SMTP_PORT (465)
  BRAIN_CMD (default: "dsh --profile headless"); it must print only the prompt's
  JSON answer on stdout and accept the prompt as its last argument.
"""
from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import json
import os
import re
import shlex
import smtplib
import ssl
import subprocess
import sys
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.mime.text import MIMEText
from pathlib import Path

BULK_FROM = re.compile(r"(no-?reply|notifications?|newsletter|updates?@|billing|alerts?@|mailer-daemon|verify)", re.I)
BULK_SUBJECT = re.compile(r"(verification code|verify your|security alert|receipt|invoice|newsletter|webinar|password reset)", re.I)


def log(path: Path, msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)


def decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                except Exception:
                    continue
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""


def is_bulk(msg, sender: str, subject: str) -> str | None:
    if (msg.get("Precedence") or "").lower() in ("bulk", "list", "junk"):
        return "precedence"
    if msg.get("Auto-Submitted") and msg.get("Auto-Submitted") != "no":
        return "auto-submitted"
    if BULK_FROM.search(sender):
        return "from-pattern"
    if BULK_SUBJECT.search(subject):
        return "subject-pattern"
    return None


def ask_brain(sender: str, subject: str, body: str) -> dict:
    prompt = (
        "Decide whether this email needs a substantive reply. "
        "Marketing, notifications, verification codes, receipts and alerts never do.\n"
        f"From: {sender}\nSubject: {subject}\nBody:\n{body[:4000]}\n\n"
        'Reply with strict JSON only: {"reply": true|false, "reason": "<=30 chars", "body": "reply text <=500 chars"}'
    )
    cmd = shlex.split(os.environ.get("BRAIN_CMD", "dsh --profile headless")) + [prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    text = (proc.stdout or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {"reply": False, "reason": "no-json"}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {"reply": False, "reason": "bad-json"}


def send_reply(user: str, orig, to_addr: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if orig.get("Message-ID"):
        msg["In-Reply-To"] = orig["Message-ID"]
        refs = orig.get("References")
        msg["References"] = f"{refs} {orig['Message-ID']}" if refs else orig["Message-ID"]
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Auto-Submitted"] = "auto-replied"
    host = os.environ.get("SMTP_HOST") or "smtp." + os.environ["IMAP_HOST"].split(".")[-2] + "." + os.environ["IMAP_HOST"].split(".")[-1]
    with smtplib.SMTP_SSL(host, int(os.environ.get("SMTP_PORT", "465")), context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(user, os.environ["IMAP_PASSWORD"])
        smtp.send_message(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default="email-state.json")
    ap.add_argument("--log", default="email-watch.log")
    ap.add_argument("--daily-cap", type=int, default=3)
    ap.add_argument("--cooldown-hours", type=int, default=24)
    args = ap.parse_args()

    state_path, log_path = Path(args.state), Path(args.log)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"last_uid": 0, "sent": {}, "sends": []}
    user = os.environ["IMAP_USER"]

    imap = imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], timeout=30)
    imap.login(user, os.environ["IMAP_PASSWORD"])
    imap.select("INBOX", readonly=False)
    typ, data = imap.search(None, "ALL")
    uids = [int(x) for x in data[0].split()] if data and data[0] else []
    if not uids:
        imap.logout()
        return 0
    max_uid = max(uids)
    if state["last_uid"] == 0:
        state["last_uid"] = max_uid
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        log(log_path, f"baseline uid={max_uid}")
        imap.logout()
        return 0

    now = datetime.now()
    sent_today = len([t for t in state.get("sends", []) if (now - datetime.fromisoformat(t)).days < 1])

    for uid in [u for u in uids if u > state["last_uid"]]:
        typ, d = imap.fetch(str(uid), "(BODY.PEEK[])")
        if not d or not d[0]:
            continue
        msg = email.message_from_bytes(d[0][1])
        sender = decode(msg.get("From"))
        subject = decode(msg.get("Subject"))
        addr = email.utils.parseaddr(sender)[1]
        reason = is_bulk(msg, sender, subject)
        state["last_uid"] = max(state["last_uid"], uid)
        if reason:
            log(log_path, f"skip uid={uid} bulk={reason}")
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            continue
        last = state.get("sent", {}).get(addr)
        if last and (now - datetime.fromisoformat(last)) < timedelta(hours=args.cooldown_hours):
            log(log_path, f"skip uid={uid} cooldown")
            continue
        if sent_today >= args.daily_cap:
            log(log_path, "daily cap reached")
            break
        verdict = ask_brain(sender, subject, body_text(msg))
        reply_body = (verdict.get("body") or "").strip()
        if not (verdict.get("reply") and reply_body):
            log(log_path, f"judge uid={uid} reply=False")
            continue
        if args.dry_run:
            log(log_path, f"dry uid={uid} would reply")
            continue
        try:
            send_reply(user, msg, addr, subject, reply_body)
            sent_today += 1
            state.setdefault("sent", {})[addr] = now.isoformat(timespec="seconds")
            state.setdefault("sends", []).append(now.isoformat(timespec="seconds"))
            imap.store(str(uid), "+FLAGS", "(\\Seen)")
            log(log_path, f"sent uid={uid} to={addr}")
        except Exception as exc:
            log(log_path, f"send_fail uid={uid} {type(exc).__name__}")
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    imap.logout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
