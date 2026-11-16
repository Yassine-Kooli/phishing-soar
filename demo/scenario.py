"""Replayable end-to-end scenario on the live lab.

    python3 demo/scenario.py --decision approve     # analyst approves: purge, block, notify
    python3 demo/scenario.py --decision reject      # analyst rejects: nothing is deleted
    python3 demo/scenario.py --decision timeout     # no answer: link expires, nothing is deleted

Steps: reset -> GoPhish campaign -> two employees report it -> the analyst's e-mail is read
for the signed links -> the decision is clicked through n8n -> the result is checked in the
mailboxes, in the analyzer and in the DNS sinkhole. A JSON result is written to eval/runs/.
Needs the stack up (make up), GOPHISH_API_KEY in .env, and the workflows active in n8n.
"""
import argparse
import json
import os
import re
import smtplib
import sys
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

import requests

import _env  # noqa: F401  (ports from .env, before the other demo modules read them)

ROOT = Path(__file__).resolve().parent.parent
MAIL_PORT = os.getenv("MAILPIT_UI_PORT", "8025")
os.environ.setdefault("MAILPIT_URL", "http://localhost:" + MAIL_PORT)
os.environ.setdefault("SMTP_PORT", os.getenv("MAILPIT_SMTP_PORT", "1025"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gophish_setup as gp   # noqa: E402
import report as employee     # noqa: E402

MAIL = os.environ["MAILPIT_URL"]
ANALYZER = os.getenv("ANALYZER_URL", "http://localhost:8000")
N8N = os.getenv("N8N_URL", "http://localhost:5678")
DOMAINS = ["corp-verify.test", "secure-login.corp-verify.test"]
VICTIMS = ["alice@corp.local", "bob@corp.local", "carol@corp.local"]
REPORTERS = [("alice", "verify your Corp account"), ("bob", "verify your Corp account")]


def mail_all():
    r = requests.get(MAIL + "/api/v1/messages", params={"limit": 500}, timeout=10)
    r.raise_for_status()
    return r.json()["messages"]


def mail_text(mid):
    return requests.get(MAIL + "/api/v1/message/" + mid, timeout=10).json()["Text"]


def to_addrs(m):
    return [t["Address"].lower() for t in m["To"]]


def campaign_copies(since=None):
    """Simulated phishing copies that sit in employee mailboxes (not in reports@)."""
    out = []
    for m in mail_all():
        if m["From"]["Address"] != "it@corp-verify.test":
            continue
        if since and m["Created"] < since:
            continue
        out.append(m)
    return out


def wait_for(fn, timeout, step=2.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return None


def reset():
    requests.delete(MAIL + "/api/v1/messages", timeout=10)
    for d in DOMAINS:
        requests.delete(ANALYZER + "/blocklist/" + d, timeout=10)
    r = requests.post(ANALYZER + "/lab/reset-approvals", timeout=10)   # 403 unless LAB_RESET=1
    if r.status_code == 200:
        print("expired leftover requests:", r.json()["expired"])


def send_legitimate():
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "hr@corp.local", "alice@corp.local", "Team meeting Thursday"
    m.set_content("Agenda at noon in room 2.")
    with smtplib.SMTP("localhost", int(os.environ["SMTP_PORT"])) as s:
        s.send_message(m)


def find_analyst_verdict(after_iso):
    for m in mail_all():
        if "analyst@corp.local" in to_addrs(m) and m["Subject"].startswith("[phishing]") \
                and m["Created"] >= after_iso:
            return m
    return None


def click(url):
    r = requests.get(url, timeout=60)
    return r.status_code, r.text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision", choices=["approve", "reject", "timeout"], default="approve")
    args = ap.parse_args()
    if not gp.KEY:
        sys.exit("GOPHISH_API_KEY is not set (.env)")

    run = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    res = {"run": run, "decision": args.decision, "checks": {}, "timings_s": {}}
    print("run", run, "decision", args.decision)

    reset()
    send_legitimate()
    started_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    t0 = time.time()
    camp = gp.launch_campaign("Verify account simulation " + run)
    res["campaign"] = camp.get("id")
    ok_delivery = wait_for(lambda: all(
        any(t == v for m in campaign_copies() for t in to_addrs(m)) for v in VICTIMS), 90)
    res["checks"]["simulated_mail_delivered"] = bool(ok_delivery)
    if not ok_delivery:
        sys.exit("GoPhish mail did not reach every target")

    # employees report; the first report is the one the analyst decides on
    t_report = time.time()
    for user, subject in REPORTERS:
        employee.report(user, subject)
    verdict = wait_for(lambda: find_analyst_verdict(started_iso), 180)
    if not verdict:
        sys.exit("no analyst e-mail for the campaign")
    # wait for the second report too, so the analyst decides once with the whole picture
    wait_for(lambda: sum(1 for m in mail_all() if m["Subject"].startswith("[phishing]")
                         and m["Created"] >= started_iso) >= len(REPORTERS), 60)
    t_verdict = time.time()
    res["timings_s"]["report_to_analyst_email"] = round(t_verdict - t_report, 1)

    body = mail_text(verdict["ID"])
    aid = re.search(r"[?&]id=([0-9a-f]+)", body).group(1)
    tok = {a: re.search(r"action=%s&token=([0-9a-f]+)" % a, body).group(1) for a in ("approve", "reject")}
    res["approval_id"] = aid
    res["checks"]["one_decision_for_two_reports"] = len({re.search(r"[?&]id=([0-9a-f]+)", mail_text(m["ID"])).group(1)
        for m in mail_all() if m["Subject"].startswith("[phishing]") and m["Created"] >= started_iso}) == 1

    status = requests.get(ANALYZER + "/approvals/" + aid, timeout=10).json()
    if args.decision == "timeout":
        wait_s = status["expires"] - time.time() + 3
        print("waiting %.0f s for the approval to expire" % wait_s)
        time.sleep(max(0, wait_s))
        code, text = click("%s/webhook/approval?id=%s&action=approve&token=%s" % (N8N, aid, tok["approve"]))
        res["checks"]["late_approval_refused"] = "expired" in text
        res["click_response"] = text
    else:
        t_click = time.time()
        code, text = click("%s/webhook/approval?id=%s&action=%s&token=%s"
                           % (N8N, aid, args.decision, tok[args.decision]))
        res["click_response"] = text
        res["timings_s"]["click_to_response"] = round(time.time() - t_click, 1)

    def current():
        r = requests.get(ANALYZER + "/approvals/" + aid, timeout=10)
        if r.status_code != 200:
            sys.exit("analyzer refused the status check: %s %s" % (r.status_code, r.text[:200]))
        return r.json()
    final = wait_for(lambda: (lambda s: s if s["status"] in ("executed", "rejected", "failed", "expired")
                              else None)(current()), 120) if args.decision == "approve" else current()
    res["approval_status"] = final["status"]

    copies_left = [m for m in campaign_copies() if to_addrs(m)[0] in VICTIMS]
    res["copies_left"] = len(copies_left)
    if args.decision == "approve":
        t_purged = time.time()
        res["timings_s"]["click_to_purged"] = round(t_purged - t_click, 1)
        v = requests.get(ANALYZER + "/approvals/%s/verify" % aid, timeout=30).json()
        res["verify"] = v
        res["timings_s"]["click_to_verified"] = round(time.time() - t_click, 1)
        res["checks"]["all_copies_purged"] = v["copies_left"] == 0 and len(copies_left) == 0
        res["checks"]["dns_sinkholed"] = bool(v["dns_blocked"]) and all(v["dns_blocked"].values())
        reporter = final["reporter"]
        res["reporter"] = reporter
        res["checks"]["victims_notified"] = all(any(
            to_addrs(m) == [x] and m["Subject"].startswith("Phishing e-mail removed")
            for m in mail_all()) for x in VICTIMS if x != reporter)
        res["checks"]["reporter_thanked"] = any(
            to_addrs(m) == [reporter] and m["Subject"].startswith("Thanks") for m in mail_all())
        res["checks"]["analyst_informed"] = any(
            "analyst@corp.local" in to_addrs(m) and m["Subject"].startswith("[purged]") for m in mail_all())
        res["checks"]["status_executed"] = final["status"] == "executed"
    elif args.decision == "reject":
        res["checks"]["status_rejected"] = final["status"] == "rejected"
        res["checks"]["nothing_deleted"] = len(copies_left) == len(VICTIMS)
        res["checks"]["analyst_informed"] = any(
            "analyst@corp.local" in to_addrs(m) and m["Subject"].startswith("[rejected]") for m in mail_all())
        res["checks"]["no_domain_blocked"] = all(
            requests.get(ANALYZER + "/verify/dns/" + d, timeout=10).json()["blocked"] is False for d in DOMAINS)
    else:
        res["checks"]["status_expired"] = final["status"] == "expired"
        res["checks"]["nothing_deleted"] = len(copies_left) == len(VICTIMS)

    res["checks"]["legitimate_mail_untouched"] = any(
        m["Subject"] == "Team meeting Thursday" and to_addrs(m) == ["alice@corp.local"] for m in mail_all())
    res["passed"] = all(res["checks"].values())
    res["total_s"] = round(time.time() - t0, 1)
    out = ROOT / "eval" / "runs" / (run + "-" + args.decision + ".json")
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res["checks"], indent=2))
    print("timings:", res["timings_s"])
    print("PASSED" if res["passed"] else "FAILED", "-", out)
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
