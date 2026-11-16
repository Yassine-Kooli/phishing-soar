"""Simulates employees reporting phishing: forwards a mail from their Mailpit mailbox
to reports@corp.local as a message/rfc822 attachment (what a real 'report phishing' does).

usage: python demo/report.py alice bob "verify your Corp account"
"""
import os
import _env  # noqa: F401  (ports from .env)
import sys
import smtplib
import email
from email import policy
from email.message import EmailMessage

import requests

M = os.getenv("MAILPIT_URL", "http://localhost:" + os.getenv("MAILPIT_UI_PORT", "8025"))
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", os.getenv("MAILPIT_SMTP_PORT", "1025")))


def report(user, subject_part):
    q = 'to:' + user + '@corp.local subject:"' + subject_part + '"'
    found = requests.get(M + "/api/v1/search", params={"query": q}, timeout=5).json()
    if not found.get("messages"):
        sys.exit("no message for %s matching %r" % (user, subject_part))
    mid = found["messages"][0]["ID"]
    raw = requests.get(M + "/api/v1/message/" + mid + "/raw", timeout=5).content
    original = email.message_from_bytes(raw, policy=policy.default)
    msg = EmailMessage()
    msg["From"] = user + "@corp.local"
    msg["To"] = "reports@corp.local"
    msg["Subject"] = "Fwd: " + subject_part
    msg.set_content("Hello, this e-mail looks suspicious. Can you check it?")
    msg.add_attachment(original)          # attached as message/rfc822
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.send_message(msg)
    print("reported by", user)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    *users, subject = sys.argv[1:]
    for u in users:
        report(u, subject)
