import os
import pytest
from email.message import EmailMessage
from fastapi import HTTPException

import app


def build(subject="Hello", frm="Someone <someone@example.test>", to="alice@corp.local",
          body="hi", auth=None, reply_to=None, mid="<m1@test>"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = frm, to, subject, mid
    if auth:
        m["Authentication-Results"] = auth
    if reply_to:
        m["Reply-To"] = reply_to
    m.set_content(body)
    return m


def report(inner, rid="<r1@test>"):
    """An employee's report: the suspicious mail attached as message/rfc822."""
    outer = EmailMessage()
    outer["From"], outer["To"] = "alice@corp.local", "reports@corp.local"
    outer["Subject"], outer["Message-ID"] = "Fwd: " + str(inner["Subject"]), rid
    outer.set_content("Hello, this e-mail looks suspicious. Can you check it?")
    outer.add_attachment(inner)
    return bytes(outer)


# (1) plain-text mail
def test_plain_text_mail():
    a = app.analyze_bytes(bytes(build(subject="Team meeting", body="Agenda at noon.",
                                      frm="hr@corp.local",
                                      auth="mx.corp.local; spf=pass; dkim=pass; dmarc=pass")))
    assert a["subject"] == "Team meeting"
    assert a["from"] == "hr@corp.local"
    assert a["urls"] == []
    assert a["features"]["auth_fail"] is False


# (2) HTML mail with a base64 body
def test_html_base64_body_is_decoded_and_urls_found():
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "it@corp-verify.test", "alice@corp.local", "Login"
    m.set_content('<html><body><a href="https://secure-login.corp-verify.test/login">Log in</a>'
                  "</body></html>", subtype="html", cte="base64")
    a = app.analyze_bytes(bytes(m))
    assert [u["domain"] for u in a["urls"]] == ["secure-login.corp-verify.test"]
    assert a["urls"][0]["ioc_hit"] is True
    assert a["features"]["ioc_domain_hit"] is True


# (3) report containing a nested .eml attachment: the inner mail is what gets analyzed
def test_nested_eml_attachment_is_the_analyzed_mail():
    inner = build(subject="Action required: verify your Corp account",
                  frm='"Corp IT Support" <it@corp-verify.test>',
                  body="Verify: http://secure-login.corp-verify.test/login",
                  auth="mx.corp.local; spf=fail; dkim=none; dmarc=fail",
                  reply_to="help@mail-helpdesk.test")
    a = app.analyze_bytes(report(inner, rid="<report-42@corp.local>"))
    assert a["sender_domain"] == "corp-verify.test"
    assert a["report_message_id"] == "<report-42@corp.local>"
    assert a["reporter"] == "alice@corp.local"
    assert a["features"]["auth_fail"] is True
    assert a["features"]["reply_to_mismatch"] is True
    assert a["features"]["urgency"] is True


# (4) URL using an IP address
def test_url_with_ip_address_is_flagged_and_defanged():
    a = app.analyze_bytes(bytes(build(subject="Quick favor", frm="ceo@corp-mail.test",
                                      body="Open http://203.0.113.5/doc now.")))
    u = a["urls"][0]
    assert u["is_ip"] is True
    assert u["defanged"] == "hxxp://203[.]0[.]113[.]5/doc"
    assert a["features"]["url_ip"] is True


# (5) near-duplicate mails share a campaign; a different mail starts a new one
def test_campaign_grouping():
    def analysis(i, subject, frm, url):
        raw = bytes(build(subject=subject, frm=frm, body="see " + url, mid="<c%d@t>" % i))
        return app.analyze_bytes(raw)

    c1 = app.campaign(analysis(1, "Invoice 123", "billing@invoice-now.test", "http://pay-now.test/x"))
    c2 = app.campaign(analysis(2, "Invoice 456", "billing@invoice-now.test", "http://pay-now.test/y"))
    assert c1["is_new"] is True
    assert c2["is_new"] is False
    assert c2["campaign_id"] == c1["campaign_id"]          # same subject shape, sender, link domain

    # exactly at the 0.5 Jaccard threshold: still the same campaign
    c3 = app.campaign(analysis(3, "Invoice 789", "billing@invoice-now.test", "http://other-pay.test/z"))
    assert c3["campaign_id"] == c1["campaign_id"]

    c4 = app.campaign(analysis(4, "Team lunch", "hr@corp.local", "https://github.com/corp/lunch"))
    assert c4["is_new"] is True
    assert c4["campaign_id"] != c1["campaign_id"]

    # the same report delivered twice is flagged, not counted twice
    again = app.campaign(analysis(2, "Invoice 456", "billing@invoice-now.test", "http://pay-now.test/y"))
    assert again["duplicate_report"] is True


# ---------- score: explainable and never "safe" when a source is missing ----------
def test_score_phishing_has_reasons():
    a = app.analyze_bytes(report(build(subject="Action required: verify your Corp account",
                                       frm='"Corp IT Support" <it@corp-verify.test>',
                                       body="Verify: http://secure-login.corp-verify.test/login",
                                       auth="mx.corp.local; spf=fail; dkim=none; dmarc=fail",
                                       reply_to="help@mail-helpdesk.test")))
    s = app.score({"analysis": a, "reputation": {}})
    assert s["verdict"] == "phishing"
    assert "auth_fail: +20" in s["reasons"]
    assert "known_bad_url: +40" in s["reasons"]


def test_missing_reputation_source_is_never_safe():
    a = app.analyze_bytes(bytes(build(subject="Team meeting", frm="hr@corp.local",
                                      body="Agenda", auth="mx; spf=pass; dkim=pass; dmarc=pass")))
    s = app.score({"analysis": a, "reputation": {"unavailable": ["urlhaus"]}})
    assert s["score"] == 0
    assert s["verdict"] == "review"


def test_yara_match_on_attachment():
    pytest.importorskip("yara")
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "billing@invoice-now.test", "alice@corp.local", "Invoice 1"
    m.set_content("See attached invoice.")
    m.add_attachment(b"AutoOpen PHISH_DEMO_MARKER", maintype="application",
                     subtype="octet-stream", filename="invoice.doc")
    a = app.analyze_bytes(bytes(m))
    assert a["attachments"][0]["yara"] == ["Demo_Macro_Marker"]
    assert "yara_match: +30" in app.score({"analysis": a, "reputation": {}})["reasons"]


# ---------- blocklist safety ----------
def test_allowlisted_domain_is_refused():
    assert app.block({"domain": "corp.local"})["blocked"] is False
    assert app.block({"domain": "mail.corp.local"})["blocked"] is False


def test_blocklist_rejects_newline_injection():
    with pytest.raises(HTTPException):
        app.block({"domain": "evil.test\n10.0.0.1 corp.local"})


def test_block_writes_sinkhole_file_atomically():
    r = app.block({"domain": "secure-login.corp-verify.test", "ttl_seconds": 120})
    assert r["blocked"] is True
    path = os.path.join(os.environ["DATA_DIR"], "blocklist.hosts")
    with open(path) as f:
        assert "0.0.0.0 secure-login.corp-verify.test" in f.read()
    app.unblock("secure-login.corp-verify.test")
