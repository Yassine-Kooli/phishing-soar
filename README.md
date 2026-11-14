# Phishing Report Box (SOAR)

A Security Orchestration, Automation and Response (SOAR) pipeline for phishing reports.

An employee forwards a suspicious e-mail to `reports@corp.local`. A program (never a human,
never a browser) reads the e-mail, scores it with explainable reasons, groups reports of the
same campaign, asks an analyst to approve, purges the e-mail from every mailbox, blocks the
domain in DNS, **verifies** that both actions had a real effect, and replies to everyone.

The full plan is the team guide `Project1_Phishing_SOAR_Implementation_Guide.docx` (kept outside
the repository). This README describes what is in the repository today.

---

## Status

| Area | State | Evidence |
|------|-------|----------|
| Lab (Docker Compose) | Running | all services answer locally (see *Services*) |
| Analyzer: parse, defang, YARA, score | Done | 11 unit tests pass; live analysis of a forwarded phish verified |
| Analyzer: campaign grouping | Done | unit test (near-duplicates, threshold boundary, duplicate report) |
| Analyzer: DNS blocklist + verify | Done | `dig` changes to `0.0.0.0` after a block; verify endpoint reports `blocked: true` |
| n8n intake (Step 3) | Done | workflow `01-phishing-report` runs on schedule; replay is ignored |
| Evaluation (Step 5) | Done (synthetic data) | `eval/results.txt`, `dataset/README.md` |
| Reputation lookups (Step 4) | **Not started** | |
| Routing safe / review / phishing (Step 6) | **Not started** | |
| Campaign cases in DFIR-IRIS (Step 7) | **Not started** | analyzer grouping exists; no IRIS yet |
| Approval, purge, block, verify (Step 8) | **Not started** | highest-risk part |
| Replies and failure tests (Step 9) | **Not started** | |
| GoPhish demo campaign (Step 10) | **Not started** | GoPhish container runs, nothing configured |
| Timing and numbers with automation (Step 11) | **Not started** | |
| Demo script and report (Step 12) | **Not started** | |

---

## How it works

```
employee ──forward (attachment)──► reports@corp.local (Mailpit inbox)
                                          │  n8n polls every 30 s (is:unread)
                                          ▼
                 mark read ──► idempotence key in Webdis (SET NX) ──► already seen? stop
                                          │ new report
                                          ▼
                 analyzer  POST /analyze/{id}     parse, defang, YARA, auth, IOC feed
                                          │
                  (Step 4+) reputation ─► score ─► verdict: safe / review / phishing
                                          │
                  (Step 7+) campaign ─► IRIS case, approval, purge, block, verify, replies
```

Only the first part (intake and analysis) exists today. The rest is in the guide.

### Action policy (planned, from the guide)

| Action | Mode | Reversible / traced | Check after |
|--------|------|---------------------|-------------|
| Reply "safe" to reporter | Automatic | traced in n8n execution | mail visible in Mailpit |
| Create / update IRIS case | Automatic | case history | case ID stored |
| Purge e-mail from all mailboxes | **Approved by analyst** | raw copy in `quarantine/` first | search returns 0 messages |
| Block domain in DNS | **Approved by analyst** | expires by TTL, can be removed | `dig` returns `0.0.0.0` |
| Block an allowlisted domain | **Forbidden** | refused by the analyzer | n/a |

---

## Services

| Service | Host address (default) | Role |
|---------|------------------------|------|
| Mailpit | UI/API `127.0.0.1:8025`, SMTP `127.0.0.1:1025` | fake mail server; the reports inbox and the victims' mailboxes |
| n8n | `127.0.0.1:5678` | orchestration; workflows in `n8n/workflows/` |
| Webdis | `127.0.0.1:7379` | Redis over HTTP, used for idempotence keys |
| analyzer | `127.0.0.1:8000` | FastAPI service: parsing, scoring, campaigns, blocklist |
| sinkhole | UDP `127.0.0.1:5353` (container 172.31.50.53) | CoreDNS; answers from the analyzer's blocklist |
| GoPhish | admin `127.0.0.1:3333`, phish `127.0.0.1:8081` | demo phishing campaign on `.test` domains |

Inside the Docker network the services reach each other by name: `mailpit:8025`, `webdis:7379`,
`analyzer:8000`, `sinkhole`. Use the name, never `localhost`, from inside n8n.

### Pinned versions

| Component | Version |
|-----------|---------|
| Mailpit | `axllent/mailpit:v1.27.11` |
| n8n | `docker.n8n.io/n8nio/n8n:2.40.7` |
| Webdis | `nicolas/webdis:0.1.25` |
| CoreDNS | `coredns/coredns:1.11.1` |
| GoPhish | `gophish/gophish:0.12.1` |
| Analyzer base image | `python:3.12-slim` |
| Analyzer Python deps | `analyzer/requirements.txt` (FastAPI 0.115.6, uvicorn 0.34.0, requests 2.32.3, yara-python 4.5.1, dnspython 2.7.0) |

---

## Quick start

Requirements: Docker with Compose v2, Python 3.11+ (for the demo scripts and tests), `curl`, `dig` (optional).

```bash
cp .env.example .env     # ports and optional API keys; the demo works without any key
make up                  # docker compose up -d --build
docker compose ps        # every service should be Up
```

Smoke tests:

```bash
curl -s localhost:8000/blocklist                             # {}
curl -s localhost:7379/PING                                  # {"PING":[true,"PONG"]}
dig @127.0.0.1 -p 5353 secure-login.corp-verify.test +short # 172.31.50.20 (GoPhish) before a block
```

Send a sample phishing mail and a legitimate one, then report the phish as an employee would:

```bash
python3 demo/send_sample.py
python3 demo/report.py alice "verify your Corp account"
```

Then open Mailpit (http://localhost:8025, or your `MAILPIT_UI_PORT`) and look for the forwarded mail
in `reports@corp.local`. Within 30 seconds the intake workflow picks it up and marks it read.

Run the unit tests:

```bash
make test                # or: cd analyzer && python3 -m pytest -q  (needs requirements-dev.txt)
```

### Port overrides

Your machine may already use some of these ports. Set them in `.env` (git-ignored); compose reads that
file automatically. The defaults are the contract values in the guide.

| Variable | Default | Used by |
|----------|---------|---------|
| `MAILPIT_UI_PORT` | 8025 | Mailpit UI/API on the host |
| `MAILPIT_SMTP_PORT` | 1025 | SMTP on the host (`demo/*.py`) |
| `SINKHOLE_HOST_PORT` | 5353 | DNS on the host (`dig -p`) |
| `GOPHISH_ADMIN_PORT` | 3333 | GoPhish admin |
| `GOPHISH_PHISH_PORT` | 8081 | GoPhish phishing pages |

The demo scripts read `MAILPIT_URL` (default `http://localhost:8025`) and `SMTP_HOST` / `SMTP_PORT`
(default `localhost` / `1025`). Set them when you change the host ports.

---

## Analyzer API

Interactive docs: http://localhost:8000/docs when the stack is running.

| Method and path | Purpose |
|-----------------|---------|
| `POST /analyze/{mailpit_id}` | Fetch a message from Mailpit and analyze it |
| `POST /analyze-raw` | Analyze raw `.eml` bytes sent in the body (max 10 MB) |
| `POST /score` | Score an analysis, with optional reputation data, and return verdict and reasons |
| `POST /campaign` | Assign the report to a campaign (or create one); flags duplicate reports |
| `POST /campaign/{id}/case/{case_id}` | Remember the IRIS case ID for a campaign |
| `POST /quarantine` | Save raw copies of Mailpit messages to `quarantine/` before any purge |
| `GET /blocklist` | List active blocks with seconds left |
| `POST /blocklist` | Block a domain in DNS for a TTL (default 3600 s, max 86400 s) |
| `DELETE /blocklist/{domain}` | Remove a block early |
| `GET /verify/dns/{domain}` | Ask the sinkhole what a domain resolves to; `blocked` is true for `0.0.0.0` |

### What `analyze` returns

- `report_message_id`, `reporter`, `message_id`
- `from`, `from_name`, `sender_domain`, `reply_to`, `subject`, `subject_norm` (digits replaced by `#`)
- `auth`: SPF, DKIM and DMARC results from `Authentication-Results`
- `urls`: each with `url`, `defanged` (for example `hxxp://secure-login[.]corp-verify[.]test/login`),
  `domain`, `is_ip`, `punycode`, `ioc_hit`
- `attachments`: name, type, size, SHA-256, YARA rule hits
- `features`: boolean signals used by the score (below)

A report is recognized as a forward when the suspicious mail is attached as `message/rfc822` or as
a `.eml` file. Otherwise the message itself is analyzed.

### The score

Every point comes with a written reason in the response, so an analyst can see why.

| Signal | Points | Why it matters |
|--------|--------|----------------|
| SPF, DKIM or DMARC fail (or softfail/permerror) | +20 | the sender could not prove who it is |
| Reply-To domain differs from From domain | +10 | replies go to the attacker |
| Display name spoofs a brand | +10 | "Microsoft Support" from a random domain |
| Link points to a raw IP address | +15 | legitimate companies use domain names |
| Punycode (`xn--`) domain | +10 | look-alike characters |
| Urgency words | +10 | pressure is the attacker's main tool |
| Sender domain contains a brand but is not allowlisted | +15 | look-alike sender |
| Known bad URL (local feed, or URLhaus hit) | +40 | strong evidence |
| Known bad attachment hash | +40 | strong evidence |
| YARA rule match on an attachment | +30 | strong evidence |

Total is capped at 100. Verdicts:

- `safe`: below 25
- `review`: 25 to 59, analyst decides, no purge
- `phishing`: 60 or more, approval request

**Rule:** if any reputation source is unavailable, the verdict can never be `safe`; it becomes `review`.

The weights and thresholds are a heuristic, not a calibrated probability. The thresholds are the
open decision recorded in *Evaluation* below.

### Campaign grouping

Each report gets a set of tokens: the normalized subject, the sender domain, each link domain and
each attachment hash. Two reports belong to the same campaign when the Jaccard similarity of their
token sets is at least 0.5. The first report creates the campaign; later ones increment its counter.
A report ID that was already seen is returned with `duplicate_report: true` and is not counted again.

### Blocklist safety

- Domains must match a strict hostname pattern. Anything else returns 400, so a value containing a
  newline cannot inject lines into the DNS hosts file.
- Allowlisted domains (`corp.local`, `google.com`, `microsoft.com`, `github.com`, and their
  subdomains) are refused with `blocked: false`.
- Blocks expire by TTL. The hosts file is written atomically, so CoreDNS never reads a half-written file.
- The blocklist lives in memory: an analyzer restart clears it. Expired entries are dropped every 5 s.

---

## n8n workflows

| File | Status | What it does |
|------|--------|--------------|
| `n8n/workflows/01-phishing-report.json` | active | poll `reports@` every 30 s, mark read, idempotence key, analyze; error outputs go to DLQ |

Node names are fixed (other workflows refer to them in expressions). The workflow was written as JSON
and imported with the n8n CLI. It has not been exported from the n8n UI yet.

Behavior verified on the live stack:

- a forwarded phish is analyzed and its defanged URLs and auth failures appear in the output;
- the same report, seen again, takes the `ALREADY_PROCESSED` branch and the analyzer is not called.

**Before committing a workflow:** export it from n8n (Workflow menu, Download) and remove any credentials.
The repository must never contain API keys or passwords.

---

## Evaluation

The labelled dataset is **synthetic** (70 e-mails, seed 42), so the numbers are optimistic. Details and
the hard cases are in `dataset/README.md`. The evaluation runs the local rules only, with no reputation data.

Results of `eval/confusion_matrix.py` (`eval/results.txt`):

| Threshold | TP | FP | TN | FN | Precision | Recall |
|-----------|----|----|----|----|-----------|--------|
| 25 | 29 | 0 | 35 | 6 | 1.00 | 0.83 |
| 40 | 29 | 0 | 35 | 6 | 1.00 | 0.83 |
| 60 (guide default) | 5 | 0 | 35 | 30 | 1.00 | 0.14 |
| 75 | 5 | 0 | 35 | 30 | 1.00 | 0.14 |

Average analysis time: about 4 ms per mail.

**Open decision:** the guide's phishing threshold of 60 misses most of the dataset's phishing. Options are
to keep 60 and report the low recall, or to move to 40 and justify it. The missed mails are the
compromised-account "hard" cases (which pass all auth checks and score 0) and mails whose sender domain
is neither a brand nor in the local feed.

---

## Safety rules

- The analyzer only reads bytes. It never opens a URL and never runs an attachment.
- Allowlisted domains are never blocked.
- Quarantine copies are written, and their SHA-256 recorded, before any purge. If any copy fails, nothing is purged.
- A missing reputation source never produces a `safe` verdict.
- Lab only: all ports bind to `127.0.0.1`; use fake `.test` domains; never target real people or addresses.
- Secrets live in `.env` (git-ignored) or n8n credentials. Only `.env.example` is committed.

---

## Repository layout

```
analyzer/
  app.py                 the analyzer (all endpoints above)
  Dockerfile
  requirements.txt       runtime pins
  requirements-dev.txt   adds pytest
  ioc/domains.txt        local threat feed (one domain per line)
  yara-rules/demo.yar    harmless demo rule (PHISH_DEMO_MARKER)
  tests/                 pytest: parsing, campaigns, score, blocklist
compose.yaml             the lab
dns-sinkhole/            CoreDNS Corefile and base hosts (the fake site)
gophish/config.json      GoPhish config (admin on 0.0.0.0:3333 inside the container)
demo/
  report.py              forwards a mailbox message to reports@ as an employee would
  send_sample.py         sends one phish and one legitimate mail to alice
dataset/
  make_dataset.py        generates the synthetic labelled dataset
  labels.csv, emls/      the dataset (generated)
  README.md              provenance and limits
eval/
  confusion_matrix.py    scores the dataset against the live analyzer
  results.txt            last results
n8n/workflows/           exported workflows (no credentials)
quarantine/              raw copies of purged mails (git-ignored contents)
Makefile                 up, down, test, reset
.env.example             every variable and port override, with defaults
```

---

## Known limits and deviations from the guide

- **Ports:** host ports are configurable because this machine already uses 1025, 8025, 8081 and 5353.
  Defaults are unchanged.
- **Blocklist in memory:** a restart of the analyzer clears blocks. The DNS file is regenerated, so
  blocks disappear. The guide accepts this because TTLs expire anyway; state it in the report.
- **Mailpit is not Gmail or Exchange:** purge APIs differ in real life.
- **IRIS, URLhaus and VirusTotal are not integrated yet.** The local IOC feed is the only reputation source.
- **Campaign state** is in SQLite (`state` volume), not in IRIS.
- **Synthetic data:** results are optimistic; say so in the report.
- **n8n workflow JSON** was written by hand and imported with the CLI; check it in the UI once.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `failed to bind host port ... address already in use` | Set the matching variable in `.env` (see *Port overrides*) and `docker compose up -d` again |
| n8n cannot reach a service | Use the service name (`mailpit`, `analyzer`, `webdis`), not `localhost` |
| `dig` still returns the GoPhish IP after a block | wait 5 to 8 s for the CoreDNS reload; query the host port, not port 53 |
| Mailpit search returns nothing | test the query in the Mailpit search box first; quote subjects |
| Report not detected as a forward | the mail must be attached as `message/rfc822` or `.eml`; test with `/analyze-raw` |
| Workflow does not pick up a report | check it is active in n8n and the report is unread in Mailpit |
| GoPhish admin password | printed once in the GoPhish container logs on first start: `docker compose logs gophish` |

---

## Contributing and the team

- Two people: Person A (orchestration: n8n workflows, approval, purge, replies) and Person B
  (infrastructure, analysis, data). Work on `feat/infra-analysis` or `feat/orchestration`, merge by pull request.
- Never commit `.env`, API keys or passwords. Export n8n workflows only after removing credentials.
- Pin every new image version and record it in *Pinned versions*.
