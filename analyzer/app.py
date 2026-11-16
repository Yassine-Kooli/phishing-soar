"""Phishing analyzer: the "safe e-mail reader".

It only reads bytes. It never opens a URL and never runs an attachment.
It also owns the campaign fingerprints (SQLite) and the DNS sinkhole blocklist.
"""
import re, os, glob, time, json, hashlib, hmac, secrets, email, email.utils, sqlite3, threading, socket
from contextlib import asynccontextmanager
from email import policy
from urllib.parse import urlparse, parse_qs, unquote
import requests
import dns.resolver
from fastapi import FastAPI, HTTPException, Request

try:
    import yara
except ImportError:
    yara = None

# ---------- configuration (container defaults; tests override through env) ----------
MAILPIT = os.getenv("MAILPIT_URL", "http://mailpit:8025")
RULES_DIR = os.getenv("RULES_DIR", "/app/yara-rules")
IOC_FILE = os.getenv("IOC_FILE", "/app/ioc/domains.txt")
BASE_HOSTS = os.getenv("BASE_HOSTS", "/etc/base.hosts")
DATA_DIR = os.getenv("DATA_DIR", "/data")                  # shared with the CoreDNS sinkhole
QUARANTINE_DIR = os.getenv("QUARANTINE_DIR", "/quarantine")
STATE_DIR = os.getenv("STATE_DIR", "/state")
MAX_BODY = 10 * 1024 * 1024
APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", "")          # HMAC key for approval links (.env)
APPROVAL_TTL = int(os.getenv("APPROVAL_TTL_SECONDS", "600"))  # analyst has 10 minutes
MAILBOX_EXCLUDED = {"reports@corp.local", "analyst@corp.local", "soc@corp.local"}
REDIRECT_KEYS = {"url", "u", "q", "redirect", "redirect_url", "redirect_uri", "next", "continue",
                 "target", "dest", "destination", "return", "returnurl", "goto", "link"}

@asynccontextmanager
async def lifespan(_app):
    write_hosts()                                  # publish the blocklist before serving
    threading.Thread(target=expiry_loop, daemon=True).start()
    yield


app = FastAPI(title="phishing analyzer", lifespan=lifespan)
LOCK = threading.Lock()   # protects the campaign DB and the blocklist (sync handlers run in threads)

URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
URGENT = ["urgent", "immediately", "verify your account", "suspended",
          "password expires", "action required", "within 24 hours"]
BRANDS = ["paypal", "microsoft", "apple", "amazon", "docusign", "corp"]
ALLOW = {"corp.local", "google.com", "microsoft.com", "github.com"}  # never blocked

SAFE_ID = re.compile(r"[A-Za-z0-9]{1,64}")            # Mailpit message IDs
DOMAIN_RE = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}")


def is_allowed(dom):
    return dom in ALLOW or any(dom.endswith("." + a) for a in ALLOW)


def load_rules():
    files = {os.path.basename(f): f for f in glob.glob(os.path.join(RULES_DIR, "*.yar"))}
    return yara.compile(filepaths=files) if (yara and files) else None


RULES = load_rules()


def load_ioc():
    try:
        with open(IOC_FILE) as f:
            return {l.strip().lower() for l in f if l.strip()}
    except FileNotFoundError:
        return set()


def defang(u):
    return u.replace("http", "hxxp", 1).replace(".", "[.]")


def nested_urls(u):
    """Links hidden in a redirect parameter, e.g. https://go.test/?url=https%3A%2F%2Fevil.test%2F.
    They are never opened: they are extracted, scored and checked like any other link."""
    out = []
    for k, vals in parse_qs(urlparse(u).query).items():
        if k.lower() in REDIRECT_KEYS:
            for v in vals:
                v = unquote(v).strip()
                if re.match(r"https?://", v, re.I):
                    out.append(v.rstrip(".,;"))
    return out


def pick_target(msg):
    """A report contains the suspicious e-mail as an attachment. Return it."""
    for p in msg.walk():
        if p.get_content_type() == "message/rfc822":
            pl = p.get_payload()
            if pl:
                return pl[0]
        fn = (p.get_filename() or "").lower()
        if fn.endswith(".eml"):
            data = p.get_payload(decode=True)
            if data:
                return email.message_from_bytes(data, policy=policy.default)
    return msg   # not a forward: analyze the message itself


def body_text(msg):
    out = []
    for p in msg.walk():
        if p.get_content_type() in ("text/plain", "text/html"):
            try:
                out.append(p.get_content())
            except Exception:
                pass
    return "\n".join(out)


def auth_results(msg):
    h = " ".join(str(x) for x in (msg.get_all("Authentication-Results") or []))
    res = {}
    for k in ("spf", "dkim", "dmarc"):
        m = re.search(k + r"=(\w+)", h, re.I)
        res[k] = m.group(1).lower() if m else "none"
    return res


def analyze_bytes(raw: bytes):
    outer = email.message_from_bytes(raw, policy=policy.default)
    msg = pick_target(outer)
    iocs = load_ioc()
    text = body_text(msg)

    urls, seen = [], set()
    queue = [(x.rstrip(".,;"), None) for x in sorted(set(URL_RE.findall(text)))]
    while queue:
        u, parent = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        host = (urlparse(u).hostname or "").lower()
        urls.append({"url": u, "defanged": defang(u), "domain": host,
                     "is_ip": bool(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host)),
                     "punycode": "xn--" in host,
                     "ioc_hit": any(host == d or host.endswith("." + d) for d in iocs),
                     "nested_in": parent})
        queue.extend((n, u) for n in nested_urls(u))

    atts = []
    for p in msg.walk():
        if p.get_content_disposition() == "attachment":
            data = p.get_payload(decode=True)
            if not isinstance(data, (bytes, bytearray)):
                continue
            hits = [m.rule for m in RULES.match(data=bytes(data))] if RULES else []
            atts.append({"name": p.get_filename(), "type": p.get_content_type(),
                         "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                         "yara": hits})

    from_name, from_addr = email.utils.parseaddr(str(msg.get("From", "")))
    _, reply_addr = email.utils.parseaddr(str(msg.get("Reply-To", "")))
    _, rep_addr = email.utils.parseaddr(str(outer.get("From", "")))
    fdom = from_addr.split("@")[-1].lower()
    rdom = reply_addr.split("@")[-1].lower() if reply_addr else ""
    subject = str(msg.get("Subject", ""))
    subj_norm = re.sub(r"^(\s*(fwd?|re)\s*:\s*)+", "", subject, flags=re.I).lower()
    subj_norm = re.sub(r"\d+", "#", subj_norm).strip()
    low = (subject + " " + text).lower()
    auth = auth_results(msg)

    features = {
        "auth_fail": any(v in ("fail", "softfail", "permerror") for v in auth.values()),
        "reply_to_mismatch": bool(rdom) and rdom != fdom,
        "display_spoof": any(b in from_name.lower() and b not in fdom for b in BRANDS),
        "url_ip": any(u["is_ip"] for u in urls),
        "url_punycode": any(u["punycode"] for u in urls),
        "urgency": any(w in low for w in URGENT),
        "lookalike_domain": any(b in fdom for b in BRANDS) and fdom not in ALLOW,
        "ioc_domain_hit": any(u["ioc_hit"] for u in urls) or fdom in iocs,
        "redirect_wrapper": any(u["nested_in"] for u in urls),
    }
    # The Message-ID is the report's identity (idempotence). Fall back to a hash of the
    # bytes so that two reports without a Message-ID are not mistaken for duplicates.
    rid = str(outer.get("Message-ID", "")).strip() or "sha256:" + hashlib.sha256(raw).hexdigest()
    return {
        "report_message_id": rid,
        "reporter": rep_addr,
        "message_id": str(msg.get("Message-ID", "")),
        "from_name": from_name, "from": from_addr, "sender_domain": fdom,
        "reply_to": reply_addr, "auth": auth,
        "subject": subject, "subject_norm": subj_norm,
        "urls": urls, "attachments": atts, "features": features,
    }


@app.post("/analyze-raw")
async def analyze_raw(request: Request):
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise HTTPException(413, "e-mail too large")
    return analyze_bytes(raw)


@app.post("/analyze/{mid}")
def analyze_mailpit(mid: str):
    if not SAFE_ID.fullmatch(mid):
        raise HTTPException(400, "invalid message id")
    r = requests.get(f"{MAILPIT}/api/v1/message/{mid}/raw", timeout=5)
    r.raise_for_status()
    return analyze_bytes(r.content)


# ---------- score: every point has a written reason ----------
WEIGHTS = {"auth_fail": 20, "reply_to_mismatch": 10, "display_spoof": 10,
           "url_ip": 15, "url_punycode": 10, "urgency": 10, "lookalike_domain": 15,
           "redirect_wrapper": 10}
# Chosen on the labelled set (eval/results.txt): 40 keeps zero false alarms and recall 0.77;
# the guide default (60) reaches only 0.23. Hard cases are still missed; see docs/evaluation.md.
T_REVIEW, T_PHISH = 25, 40


@app.post("/score")
def score(d: dict):
    a, rep = d["analysis"], d.get("reputation") or {}
    f = a["features"]
    pts = {k: w for k, w in WEIGHTS.items() if f.get(k)}
    if f.get("ioc_domain_hit") or rep.get("urlhaus_hits", 0) > 0:
        pts["known_bad_url"] = 40
    if rep.get("bad_hashes", 0) > 0:
        pts["known_bad_hash"] = 40
    if any(x["yara"] for x in a["attachments"]):
        pts["yara_match"] = 30
    total = min(100, sum(pts.values()))
    verdict = "phishing" if total >= T_PHISH else "review" if total >= T_REVIEW else "safe"
    unavailable = rep.get("unavailable", [])
    if unavailable and verdict == "safe":
        verdict = "review"   # a missing source must NEVER silently become "clean"
    return {"score": total, "verdict": verdict, "unavailable": unavailable,
            "reasons": [k + ": +" + str(v) for k, v in pts.items()]}


# ---------- campaigns (SQLite) ----------
os.makedirs(STATE_DIR, exist_ok=True)
DB = sqlite3.connect(os.path.join(STATE_DIR, "campaigns.db"), check_same_thread=False)
DB.execute("create table if not exists campaigns(id integer primary key autoincrement, tokens text, count int, iris_case_id text)")
DB.execute("create table if not exists reports(report_id text primary key, campaign_id int)")
DB.commit()


def tokens(a):
    t = {"s:" + a["subject_norm"], "d:" + a["sender_domain"]}
    t |= {"u:" + u["domain"] for u in a["urls"]}
    t |= {"a:" + x["sha256"] for x in a["attachments"]}
    return t


def jaccard(x, y):
    return len(x & y) / len(x | y) if (x | y) else 0.0


@app.post("/campaign")
def campaign(a: dict):
    rid = a["report_message_id"]
    with LOCK:
        row = DB.execute("select campaign_id from reports where report_id=?", (rid,)).fetchone()
        if row:
            c = DB.execute("select id,count,iris_case_id from campaigns where id=?", (row[0],)).fetchone()
            return {"campaign_id": c[0], "is_new": False, "count": c[1], "iris_case_id": c[2], "duplicate_report": True}
        t = tokens(a)
        best, bs = None, 0.0
        for cid, tk in DB.execute("select id,tokens from campaigns").fetchall():
            s = jaccard(t, set(json.loads(tk)))
            if s > bs:
                best, bs = cid, s
        if best is not None and bs >= 0.5:
            DB.execute("update campaigns set count=count+1 where id=?", (best,))
            DB.execute("insert into reports values(?,?)", (rid, best))
            DB.commit()
            c = DB.execute("select id,count,iris_case_id from campaigns where id=?", (best,)).fetchone()
            return {"campaign_id": c[0], "is_new": False, "count": c[1], "iris_case_id": c[2],
                    "similarity": round(bs, 2), "duplicate_report": False}
        cur = DB.execute("insert into campaigns(tokens,count) values(?,1)", (json.dumps(sorted(t)),))
        DB.execute("insert into reports values(?,?)", (rid, cur.lastrowid))
        DB.commit()
        return {"campaign_id": cur.lastrowid, "is_new": True, "count": 1, "iris_case_id": None,
                "duplicate_report": False}


@app.post("/campaign/{cid}/case/{case_id}")
def set_case(cid: int, case_id: str):
    with LOCK:
        DB.execute("update campaigns set iris_case_id=? where id=?", (case_id, cid))
        DB.commit()
    return {"ok": True}


# ---------- quarantine copy before any deletion ----------
@app.post("/quarantine")
def quarantine(d: dict):
    ids = [str(i) for i in d.get("ids", [])]
    if not all(SAFE_ID.fullmatch(i) for i in ids):
        raise HTTPException(400, "invalid message id")
    # Fetch every copy first: if one fails, nothing is written and the caller must not purge.
    copies = {}
    for mid in ids:
        r = requests.get(f"{MAILPIT}/api/v1/message/{mid}/raw", timeout=5)
        r.raise_for_status()
        copies[mid] = r.content
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    out = []
    for mid, data in copies.items():
        path = os.path.join(QUARANTINE_DIR, mid + ".eml")
        with open(path, "wb") as f:
            f.write(data)
        out.append({"id": mid, "sha256": hashlib.sha256(data).hexdigest(), "path": path})
    return {"saved": len(out), "files": out}


# ---------- DNS sinkhole blocklist (with automatic expiry) ----------
BLOCK = {}   # domain -> expiry epoch (in memory: a restart clears it, and TTL undoes mistakes)


def write_hosts():
    base = {}
    if os.path.exists(BASE_HOSTS):
        with open(BASE_HOSTS) as f:
            for l in f:
                p = l.split()
                if len(p) >= 2 and not l.startswith("#"):
                    base[p[1]] = p[0]
    with LOCK:
        now = time.time()
        for d in [d for d, e in BLOCK.items() if e < now]:
            del BLOCK[d]
        blocked = set(BLOCK)
        lines = ["0.0.0.0 " + d for d in sorted(blocked)] + \
                [ip + " " + d for d, ip in base.items() if d not in blocked]
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = os.path.join(DATA_DIR, "blocklist.hosts.tmp")
        with open(tmp, "w") as f:          # write then rename: CoreDNS never sees a half file
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, os.path.join(DATA_DIR, "blocklist.hosts"))


def expiry_loop():
    while True:
        time.sleep(5)
        write_hosts()


@app.post("/blocklist")
def block(d: dict):
    dom = str(d.get("domain", "")).lower().strip()
    if len(dom) > 253 or not DOMAIN_RE.fullmatch(dom):
        raise HTTPException(400, "invalid domain")
    if is_allowed(dom):
        return {"blocked": False, "reason": "allowlisted: forbidden to block"}
    ttl = max(1, min(int(d.get("ttl_seconds", 3600)), 86400))
    with LOCK:
        BLOCK[dom] = time.time() + ttl
    write_hosts()
    return {"blocked": True, "domain": dom, "expires_in": ttl}


@app.delete("/blocklist/{domain}")
def unblock(domain: str):
    with LOCK:
        BLOCK.pop(domain.lower(), None)
    write_hosts()
    return {"unblocked": domain}


@app.get("/blocklist")
def listing():
    with LOCK:
        return {k: int(v - time.time()) for k, v in BLOCK.items()}


@app.get("/verify/dns/{domain}")
def verify_dns(domain: str):
    r = dns.resolver.Resolver(configure=False)
    r.lifetime = 3
    try:
        r.nameservers = [socket.gethostbyname("sinkhole")]
        answers = [a.to_text() for a in r.resolve(domain, "A")]
        error = None
    except Exception as e:   # NXDOMAIN, timeout, or sinkhole unreachable: report, never guess
        answers, error = [], type(e).__name__
    return {"domain": domain, "answers": answers, "blocked": "0.0.0.0" in answers, "error": error}


# ---------- approval gate: an analyst decides before anything is deleted ----------
# States: pending -> approved | rejected | expired ; approved -> executed.
# Purge needs an approved record. A link is valid for one decision and expires after APPROVAL_TTL.
DB.execute("""create table if not exists approvals(
    id text primary key, report_id text, campaign_id int, verdict text, status text,
    created real, expires real, decided real, analysis text, result text)""")
DB.commit()


def _sign(aid, action, expires):
    if not APPROVAL_SECRET:
        raise HTTPException(503, "APPROVAL_SECRET is not set: approvals are disabled")
    msg = f"{aid}|{action}|{int(expires)}".encode()
    return hmac.new(APPROVAL_SECRET.encode(), msg, hashlib.sha256).hexdigest()


def _row(aid):
    r = DB.execute("select id,status,expires,analysis,campaign_id,report_id,result from approvals where id=?",
                   (aid,)).fetchone()
    if not r:
        raise HTTPException(404, "unknown approval")
    return {"id": r[0], "status": r[1], "expires": r[2], "analysis": json.loads(r[3]),
            "campaign_id": r[4], "report_id": r[5], "result": json.loads(r[6]) if r[6] else None}


@app.post("/approvals")
def create_approval(d: dict):
    """Called for every report. Only a `phishing` verdict needs a human decision."""
    if d.get("verdict") != "phishing":
        return {"approval": None}
    a = d["analysis"]
    ttl = max(10, min(int(d.get("ttl_seconds", APPROVAL_TTL)), 3600))
    with LOCK:   # check and insert in one section: two reports at once must not open two requests
        open_ap = DB.execute("select id,expires from approvals where campaign_id=? and status='pending' "
                             "and expires>? order by created desc limit 1",
                             (d.get("campaign_id"), time.time())).fetchone()
        if open_ap:
            aid, expires = open_ap
            return {"approval": {"id": aid, "expires": int(expires), "reused": True,
                                 "approve_token": _sign(aid, "approve", expires),
                                 "reject_token": _sign(aid, "reject", expires)}}
        aid = secrets.token_hex(8)
        expires = time.time() + ttl
        DB.execute("insert into approvals(id,report_id,campaign_id,verdict,status,created,expires,analysis) "
                   "values(?,?,?,?,?,?,?,?)",
                   (aid, d.get("report_id"), d.get("campaign_id"), "phishing", "pending",
                    time.time(), expires, json.dumps(a)))
        DB.commit()
    return {"approval": {"id": aid, "expires": int(expires),
                         "approve_token": _sign(aid, "approve", expires),
                         "reject_token": _sign(aid, "reject", expires)}}


@app.post("/approvals/{aid}/decide")
def decide(aid: str, d: dict):
    action = str(d.get("action", ""))
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    with LOCK:
        r = _row(aid)
        if not hmac.compare_digest(str(d.get("token", "")), _sign(aid, action, r["expires"])):
            raise HTTPException(403, "bad token")
        if r["status"] != "pending":
            raise HTTPException(409, "already " + r["status"])
        if time.time() > r["expires"]:
            DB.execute("update approvals set status='expired' where id=?", (aid,))
            DB.commit()
            raise HTTPException(409, "expired: no action taken")
        new = "approved" if action == "approve" else "rejected"
        DB.execute("update approvals set status=?, decided=? where id=?", (new, time.time(), aid))
        DB.commit()
    return {"id": aid, "status": new, "reporter": r["analysis"]["reporter"],
            "subject": r["analysis"]["subject"]}


@app.post("/lab/reset-approvals")
def lab_reset_approvals():
    """Lab only (LAB_RESET=1): expire every open request so a replayed scenario starts clean."""
    if os.getenv("LAB_RESET") != "1":
        raise HTTPException(403, "lab reset is disabled (set LAB_RESET=1 in .env for the demo lab)")
    with LOCK:
        cur = DB.execute("update approvals set status='expired' where status='pending'")
        DB.commit()
    return {"expired": cur.rowcount}


@app.get("/approvals/{aid}")
def approval_status(aid: str):
    r = _row(aid)
    return {"id": aid, "status": r["status"], "expires": int(r["expires"]), "reporter": r["analysis"]["reporter"],
            "report_id": r["report_id"], "campaign_id": r["campaign_id"], "result": r["result"]}


# ---------- purge: find, quarantine, delete, block (only after approval) ----------
def norm_subject(s):
    s = re.sub(r"^(\s*(fwd?|re)\s*:\s*)+", "", s, flags=re.I).lower()
    return re.sub(r"\d+", "#", s).strip()


def find_matches(a):
    """Copies of the reported campaign in employee mailboxes.
    A mailbox copy belongs to the campaign when it is in the same campaign as the report:
    the same Jaccard rule as campaign() (token similarity >= 0.5). Reporter copies are never matched."""
    r = requests.get(f"{MAILPIT}/api/v1/messages", params={"limit": 500}, timeout=10)
    r.raise_for_status()
    base = tokens(a)
    matches = []
    for m in r.json().get("messages", []):
        to = [t["Address"].lower() for t in m.get("To", [])]
        if not to or all(t in MAILBOX_EXCLUDED for t in to):
            continue
        raw = requests.get(f"{MAILPIT}/api/v1/message/{m['ID']}/raw", timeout=5)
        raw.raise_for_status()
        other = analyze_bytes(raw.content)
        score = jaccard(base, tokens(other))
        if score >= 0.5:
            matches.append({"id": m["ID"], "to": to, "subject": m.get("Subject", ""),
                            "similarity": round(score, 2), "raw": raw.content})
    return matches


def _block_targets(a):
    doms = {u["domain"] for u in a["urls"]} | {a["sender_domain"]}
    return sorted(d for d in doms if d and not is_allowed(d))


@app.get("/approvals/{aid}/plan")
def plan(aid: str):
    """What an approval would purge. Read-only: the analyst can preview before deciding."""
    r = _row(aid)
    ms = find_matches(r["analysis"])
    return {"matches": [{k: v for k, v in m.items() if k != "raw"} for m in ms],
            "block": _block_targets(r["analysis"])}


@app.post("/approvals/{aid}/execute")
def execute(aid: str):
    with LOCK:
        r = _row(aid)
        if r["status"] != "approved":
            raise HTTPException(409, "not approved (status: %s)" % r["status"])
        DB.execute("update approvals set status='executing' where id=?", (aid,))
        DB.commit()
    try:
        ms = find_matches(r["analysis"])
        # 1. quarantine every copy first; if one write fails, nothing is deleted
        qdir = os.path.join(QUARANTINE_DIR, aid)
        os.makedirs(qdir, exist_ok=True)
        copies = []
        for m in ms:
            path = os.path.join(qdir, m["id"] + ".eml")
            with open(path, "wb") as f:
                f.write(m["raw"])
            copies.append({"id": m["id"], "to": m["to"], "sha256": hashlib.sha256(m["raw"]).hexdigest(),
                           "path": path})
        # 2. delete from every mailbox that had a copy
        deleted = []
        if ms:
            dr = requests.delete(f"{MAILPIT}/api/v1/messages", json={"IDs": [m["id"] for m in ms]}, timeout=10)
            dr.raise_for_status()
            deleted = [m["id"] for m in ms]
        # 3. block the link and sender domains (allowlisted domains are refused by block())
        blocked = []
        for dom in _block_targets(r["analysis"]):
            if block({"domain": dom, "ttl_seconds": 3600}).get("blocked"):
                blocked.append(dom)
        result = {"quarantined": copies, "deleted": deleted, "blocked": blocked,
                  "recipients": sorted({t for m in ms for t in m["to"]})}
        with LOCK:
            DB.execute("update approvals set status='executed', result=? where id=?", (json.dumps(result), aid))
            DB.commit()
        return result
    except Exception as e:
        with LOCK:
            DB.execute("update approvals set status='failed', result=? where id=?",
                       (json.dumps({"error": type(e).__name__, "detail": str(e)[:300]}), aid))
            DB.commit()
        raise HTTPException(500, "purge failed, nothing else done: " + type(e).__name__)


@app.get("/approvals/{aid}/verify")
def verify(aid: str):
    """Did the purge and the block really take effect?"""
    r = _row(aid)
    left = len(find_matches(r["analysis"]))
    targets = (r["result"] or {}).get("blocked", [])
    # CoreDNS picks up the new hosts file a few seconds after the write: wait for it, up to 20 s
    deadline = time.time() + 20
    while True:
        dns = {d: verify_dns(d)["blocked"] for d in targets}
        if all(dns.values()) or time.time() > deadline:
            break
        time.sleep(1)
    ok = left == 0 and all(dns.values()) and (r["result"] is not None)
    return {"id": aid, "copies_left": left, "dns_blocked": dns, "ok": ok}
