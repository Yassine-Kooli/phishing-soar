"""Approval gate and purge: nothing is deleted without an approved record, and the
approval token cannot be reused, forged, or used after it expires."""
import time
import pytest
from fastapi import HTTPException
from email.message import EmailMessage

import app


class FakeMailpit:
    """Stands in for the Mailpit HTTP API: a list of messages, raw bytes, and DELETE."""
    def __init__(self):
        self.msgs = {}

    def add(self, mid, to, subject, body, frm="it@corp-verify.test"):
        m = EmailMessage()
        m["From"], m["To"], m["Subject"], m["Message-ID"] = frm, to, subject, "<%s@t>" % mid
        m.set_content(body)
        self.msgs[mid] = bytes(m)

    def get(self, url, params=None, timeout=None):
        class R:
            pass
        r = R()
        if url.endswith("/api/v1/messages"):
            r.json = lambda: {"messages": [
                {"ID": k, "Subject": email_subject(v), "To": [{"Address": email_to(v)}]}
                for k, v in self.msgs.items()]}
            r.raise_for_status = lambda: None
        else:
            mid = url.split("/api/v1/message/")[1].split("/")[0]
            r.content = self.msgs[mid]
            r.raise_for_status = lambda: None
        return r

    def delete(self, url, json=None, timeout=None):
        class R:
            pass
        r = R()
        for mid in json["IDs"]:
            self.msgs.pop(mid, None)
        r.raise_for_status = lambda: None
        return r


def email_subject(raw):
    import email as em
    from email import policy
    return em.message_from_bytes(raw, policy=policy.default)["Subject"]


def email_to(raw):
    import email as em
    from email import policy
    return em.message_from_bytes(raw, policy=policy.default)["To"]


PHISH_BODY = "Verify now: https://secure-login.corp-verify.test/login"


@pytest.fixture
def mailbox(monkeypatch):
    fake = FakeMailpit()
    monkeypatch.setattr(app, "requests", type("Req", (), {"get": fake.get, "delete": fake.delete}))
    # no sinkhole in unit tests: the DNS check reports what the blocklist says (live DNS is tested on the stack)
    monkeypatch.setattr(app, "verify_dns", lambda d: {"blocked": d in app.BLOCK, "domain": d})
    # the campaign in three employee mailboxes, plus the reporter's forwarded copy
    fake.add("v1", "alice@corp.local", "Action required: verify your Corp account", PHISH_BODY)
    fake.add("v2", "bob@corp.local", "Action required: verify your Corp account 2", PHISH_BODY)
    fake.add("v3", "carol@corp.local", "Action required: verify your Corp account", PHISH_BODY)
    fake.add("fwd", "reports@corp.local", "Fwd: Action required: verify your Corp account", PHISH_BODY)
    fake.add("ok", "alice@corp.local", "Team meeting", "Agenda")
    return fake


def report_analysis(mailbox):
    """The analysis of the forwarded report as the analyzer would produce it."""
    raw = mailbox.msgs["v1"]
    return app.analyze_bytes(raw)


def test_only_phishing_verdict_creates_an_approval(mailbox):
    assert app.create_approval({"verdict": "review", "analysis": {}})["approval"] is None
    assert app.create_approval({"verdict": "safe", "analysis": {}})["approval"] is None
    assert app.create_approval({"verdict": "phishing", "analysis": report_analysis(mailbox),
                                "report_id": "r1", "campaign_id": 1})["approval"]["id"]


def _approval(mailbox, ttl=600):
    return app.create_approval({"verdict": "phishing", "analysis": report_analysis(mailbox),
                                "report_id": "r-%s" % time.time(), "campaign_id": 1,
                                "ttl_seconds": ttl})["approval"]


def test_approve_then_execute_purges_quarantines_and_blocks(mailbox):
    ap = _approval(mailbox)
    assert app.decide(ap["id"], {"action": "approve", "token": ap["approve_token"]})["status"] == "approved"
    res = app.execute(ap["id"])
    assert sorted(res["deleted"]) == ["v1", "v2", "v3"]        # the forwarded copy in reports@ stays
    assert "fwd" in mailbox.msgs and "ok" in mailbox.msgs      # unrelated mail untouched
    assert "v1" not in mailbox.msgs
    assert "secure-login.corp-verify.test" in res["blocked"]
    assert res["recipients"] == ["alice@corp.local", "bob@corp.local", "carol@corp.local"]
    assert len(res["quarantined"]) == 3 and all(q["sha256"] for q in res["quarantined"])
    v = app.verify(ap["id"])
    assert v["copies_left"] == 0
    assert set(v["dns_blocked"]) == set(res["blocked"])     # DNS itself is checked on the live stack


def test_execute_refused_without_approval(mailbox):
    ap = _approval(mailbox)
    with pytest.raises(HTTPException) as e:
        app.execute(ap["id"])
    assert e.value.status_code == 409
    assert "v1" in mailbox.msgs                                 # nothing deleted


def test_reject_never_purges(mailbox):
    ap = _approval(mailbox)
    assert app.decide(ap["id"], {"action": "reject", "token": ap["reject_token"]})["status"] == "rejected"
    with pytest.raises(HTTPException):
        app.execute(ap["id"])
    assert "v1" in mailbox.msgs


def test_expired_approval_is_refused_and_nothing_is_purged(mailbox):
    ap = _approval(mailbox, ttl=10)
    app.DB.execute("update approvals set expires=? where id=?", (time.time() - 1, ap["id"]))
    app.DB.commit()
    # the token is still correctly signed for the stored expiry, but the time has passed
    stored_exp = app.DB.execute("select expires from approvals where id=?", (ap["id"],)).fetchone()[0]
    token = app._sign(ap["id"], "approve", stored_exp)
    with pytest.raises(HTTPException) as e:
        app.decide(ap["id"], {"action": "approve", "token": token})
    assert e.value.status_code == 409 and "expired" in e.value.detail
    assert app.approval_status(ap["id"])["status"] == "expired"
    with pytest.raises(HTTPException):
        app.execute(ap["id"])
    assert "v1" in mailbox.msgs


def test_forged_or_swapped_token_is_refused(mailbox):
    ap = _approval(mailbox)
    with pytest.raises(HTTPException) as e:
        app.decide(ap["id"], {"action": "approve", "token": "0" * 64})
    assert e.value.status_code == 403
    # a reject token must not approve
    with pytest.raises(HTTPException) as e:
        app.decide(ap["id"], {"action": "approve", "token": ap["reject_token"]})
    assert e.value.status_code == 403
    assert app.approval_status(ap["id"])["status"] == "pending"


def test_decision_can_only_be_used_once(mailbox):
    ap = _approval(mailbox)
    app.decide(ap["id"], {"action": "approve", "token": ap["approve_token"]})
    with pytest.raises(HTTPException) as e:
        app.decide(ap["id"], {"action": "reject", "token": ap["reject_token"]})
    assert e.value.status_code == 409


def test_executed_approval_cannot_run_twice(mailbox):
    ap = _approval(mailbox)
    app.decide(ap["id"], {"action": "approve", "token": ap["approve_token"]})
    app.execute(ap["id"])
    with pytest.raises(HTTPException):
        app.execute(ap["id"])


def test_approvals_refused_without_secret(mailbox, monkeypatch):
    monkeypatch.setattr(app, "APPROVAL_SECRET", "")
    with pytest.raises(HTTPException) as e:
        app.create_approval({"verdict": "phishing", "analysis": report_analysis(mailbox), "report_id": "x"})
    assert e.value.status_code == 503


def test_second_report_of_same_campaign_reuses_pending_approval(mailbox):
    a1 = app.create_approval({"verdict": "phishing", "analysis": report_analysis(mailbox),
                              "report_id": "first", "campaign_id": 77})["approval"]
    a2 = app.create_approval({"verdict": "phishing", "analysis": report_analysis(mailbox),
                              "report_id": "second", "campaign_id": 77})["approval"]
    assert a2["id"] == a1["id"] and a2["reused"] is True
    assert a2["approve_token"] == a1["approve_token"]
