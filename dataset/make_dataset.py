"""Generate the synthetic labelled dataset (reproducible: fixed seed).

Run from the repository root:  python3 dataset/make_dataset.py
Writes dataset/emls/mail_NNN.eml and dataset/labels.csv.

The 'hard' kinds are included on purpose: they are the cases the score is expected to miss
or to over-flag. Do not tune the rules on them and then report the result as if they were easy.
"""
import csv
import os
import random
from email.message import EmailMessage

random.seed(42)
os.makedirs("dataset/emls", exist_ok=True)

BAD_AUTH = "mx.corp.local; spf=fail; dkim=none; dmarc=fail"
OK_AUTH = "mx.corp.local; spf=pass; dkim=pass; dmarc=pass"
URG = ["Your password expires within 24 hours.", "Action required immediately.",
       "Your account will be suspended."]


def mail(i, frm, subj, body, auth, reply=None, att=None):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, "alice@corp.local", subj
    m["Message-ID"] = "<ds-%03d@test>" % i
    m["Authentication-Results"] = auth
    if reply:
        m["Reply-To"] = reply
    m.set_content(body)
    if att:
        m.add_attachment(att, maintype="application", subtype="octet-stream", filename="invoice.doc")
    fn = "mail_%03d.eml" % i
    with open("dataset/emls/" + fn, "wb") as f:
        f.write(bytes(m))
    return fn


rows, counter = [], [0]


def add(label, kind, *a, **k):
    counter[0] += 1
    rows.append((mail(counter[0], *a, **k), label, kind))


for _ in range(15):   # classic credential phishing
    d = random.choice(["corp-verify.test", "micros0ft-login.test", "paypa1-secure.test"])
    add("phishing", "cred", '"Support" <it@%s>' % d, "Verify your account",
        random.choice(URG) + " Click http://%s/login" % d, BAD_AUTH, reply="x@mail-help.test")
for _ in range(8):    # attachment phishing
    add("phishing", "attach", "billing@invoice-now.test", "Invoice %d" % random.randint(100, 999),
        "See attached invoice.", BAD_AUTH, att=b"AutoOpen PHISH_DEMO_MARKER")
for _ in range(6):    # IP link
    add("phishing", "iplink", "ceo@corp-mail.test", "Quick favor",
        "Open http://203.0.113.%d/doc now." % random.randint(2, 250), BAD_AUTH)
for _ in range(6):    # HARD: compromised account, everything passes
    add("phishing", "hard", "colleague@corp.local", "Shared document",
        "Please review: http://docs-share.test/f%d" % random.randint(1, 99), OK_AUTH)
for _ in range(20):   # normal internal / newsletters
    add("legit", "internal", "hr@corp.local", "Meeting %d" % random.randint(1, 50),
        "Agenda: https://github.com/corp/agenda", OK_AUTH)
for _ in range(8):    # HARD: marketing with urgency words
    add("legit", "hard", "news@shop.test", "Last chance - action required",
        "Order immediately, offer ends within 24 hours https://shop.test/offer", OK_AUTH)
for _ in range(7):    # legit with failing auth (misconfigured sender)
    add("legit", "misconfigured", "partner@partner.test", "Contract draft",
        "Please find the draft at https://partner.test/c",
        "mx.corp.local; spf=softfail; dkim=pass; dmarc=pass")

with open("dataset/labels.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["file", "label", "kind"])
    w.writerows(rows)
print(len(rows), "mails written")
