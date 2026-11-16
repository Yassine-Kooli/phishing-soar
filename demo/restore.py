"""Undo a purge: put the quarantined copies back and lift the DNS blocks.

    python3 demo/restore.py <approval_id>            # dry run: lists what would be restored
    python3 demo/restore.py <approval_id> --apply    # re-delivers the copies and unblocks the domains

The copies are read from quarantine/<approval_id>/ (raw .eml, checked against the SHA-256 recorded at
purge time). They are re-sent over SMTP to Mailpit, so they reappear as new messages in the mailboxes.
Use this only after an analyst decision: a restore is not automatic.
"""
import argparse
import hashlib
import json
import os
import smtplib
import sys
from email import message_from_bytes
from email import policy
from pathlib import Path

import requests

import _env  # noqa: F401  (ports from .env)

ROOT = Path(__file__).resolve().parent.parent
ANALYZER = os.getenv("ANALYZER_URL", "http://localhost:8000")
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", os.getenv("MAILPIT_SMTP_PORT", "1025")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("approval_id")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    st = requests.get(ANALYZER + "/approvals/" + args.approval_id, timeout=10)
    if st.status_code != 200:
        sys.exit("unknown approval: %s" % st.text[:200])
    result = st.json().get("result") or {}
    if st.json()["status"] != "executed":
        sys.exit("approval is %s: nothing was purged, nothing to restore" % st.json()["status"])
    qdir = ROOT / "quarantine" / args.approval_id
    plan = []
    for q in result.get("quarantined", []):
        path = qdir / (q["id"] + ".eml")
        if not path.exists():
            sys.exit("missing quarantine copy: %s" % path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != q["sha256"]:
            sys.exit("checksum mismatch, refusing to restore: %s" % path)
        msg = message_from_bytes(raw, policy=policy.default)
        plan.append((msg, raw, msg.get("To", ""), msg.get("From", "")))
    print("copies to restore:", len(plan))
    for msg, _, to, _ in plan:
        print("  ->", to, "|", msg.get("Subject", ""))
    print("domains to unblock:", ", ".join(result.get("blocked", [])) or "none")
    if not args.apply:
        print("dry run: add --apply to restore")
        return
    for _, raw, to, frm in plan:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.sendmail(frm, [to], raw)
    for dom in result.get("blocked", []):
        requests.delete(ANALYZER + "/blocklist/" + dom, timeout=10)
    print("restored %d copies, unblocked %d domains" % (len(plan), len(result.get("blocked", []))))
    record = {"approval": args.approval_id, "restored": len(plan)}
    try:
        with open(qdir / "restore.json", "w") as f:
            json.dump(record, f, indent=2)
    except OSError:
        # the analyzer writes quarantine as root, so the host user may not write there; the record is printed
        print("restore record (could not be saved in quarantine/):", json.dumps(record))


if __name__ == "__main__":
    main()
