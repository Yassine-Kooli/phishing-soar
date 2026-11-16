# Phishing Report Box (SOAR)

A Security Orchestration, Automation and Response (SOAR) pipeline for phishing reports, built for the
SOAR course project (topic 1, "Boîte de signalement du phishing").

An employee forwards a suspicious e-mail to `reports@corp.local`. Software (never a browser, never the
analyst's own mailbox) reads the forwarded mail, scores it with explainable reasons, and groups reports of
the same campaign. For a phishing verdict an analyst receives a decision request with signed links. Only after
the analyst approves are the copies quarantined, deleted from every employee mailbox, the domains blocked in
DNS, and both effects **verified**. Victims, the reporter and the analyst are then told the result.
Nothing is deleted on a reject, an expired request or a failed check.

The guide and the brief are kept outside the repository. `docs/` holds the technical documentation.

---

## Status

| Area | State | Evidence |
|------|-------|----------|
| Lab (Docker Compose, six services) | Done | `make up`; `docker compose ps` |
| Analyzer: parse, defang, YARA, auth, IOC, redirect wrappers | Done | unit tests (`make test`) |
| Analyzer: score with reasons, thresholds 25 / 40 | Done | `docs/evaluation.md` |
| Analyzer: campaign grouping, one decision per campaign | Done | unit tests; live runs |
| Intake workflow (poll, lock, analyze, reputation, score, route) | Done | `n8n/workflows/01-phishing-report.json` |
| Approval request with signed links (phishing only) | Done | live runs |
| Analyst decision: approve, reject, expiry | Done | `n8n/workflows/02-approval-response.json`; live runs |
| Quarantine, purge across mailboxes, block, verification | Done | live runs; `docs/architecture.md` |
| Replies to victims, reporter and analyst | Done | live runs |
| Restore after a wrong approval | Done | `demo/restore.py`, tested on the live stack |
| Redirect wrappers (links hidden in redirect parameters) | Done | unit tests; labelled set |
| GoPhish demo campaign | Done | `demo/gophish_setup.py` |
| Replayable scenario and evaluation | Done | `demo/scenario.py`, `eval/evaluate.py`, `eval/scenario_results.md` |
| DFIR-IRIS case folder | Not integrated (decision) | `docs/architecture.md`, *Decisions* |

Test results and their limits are in `docs/evaluation.md`.

---

## How it works

```
employee ──forwards mail──► reports@corp.local (Mailpit)
                                  │  n8n 01: polls every 30 s (unread)
                                  ▼
            Webdis lock (SET NX, 120 s) ─► done or in progress? stop
                                  │
            analyzer: parse, defang, auth, YARA, IOC, redirects
                                  │
            reputation (per report) ─► score ─► verdict
                 ├─ safe ───────────► reply to reporter
                 └─ review / phishing ► campaign ─► approval request (phishing only)
                                              │ analyst e-mail with signed links
                                              ▼
                            n8n 02: GET /webhook/approval?id&action&token
                                  ├─ reject  ─► mails kept, analyst told
                                  ├─ expired ─► refused, nothing done
                                  └─ approve ─► quarantine (SHA-256) ─► delete copies
                                                ─► block domains ─► verify (mailboxes + DNS)
                                                ─► notices to victims, reporter, analyst
```

Diagrams and the full node flows: `docs/architecture.md`.

### Action policy

| Action | Mode | Reversible / traced | Check after |
|--------|------|---------------------|-------------|
| Reply "safe" to reporter | Automatic | traced in n8n execution | mail visible in Mailpit |
| Request an approval for a phishing campaign | Automatic | approval record in the analyzer | status `pending` |
| Purge copies from employee mailboxes | **Analyst approval** | quarantine copy with SHA-256 first | copies left = 0 |
| Block link and sender domains in DNS | **Analyst approval** | expires by TTL (1 h); `restore.py` removes it | sinkhole answers `0.0.0.0` |
| Notices to victims, reporter, analyst | Automatic after a verified purge | traced in n8n | mail visible in Mailpit |
| Block an allowlisted domain | **Forbidden** | refused by the analyzer | n/a |
| Open or click a link in a mail | **Never** | the analyzer only reads bytes | n/a |

---

## Services

| Service | Host address (default) | Role |
|---------|------------------------|------|
| Mailpit | UI/API `127.0.0.1:8025`, SMTP `127.0.0.1:1025` | fake mail server: reports inbox, employee mailboxes, analyst and SOC mail |
| n8n | `127.0.0.1:5678` | orchestration: two workflows, the analyst's webhook |
| Webdis | `127.0.0.1:7379` | Redis over HTTP: per-report lock and done marker |
| analyzer | `127.0.0.1:8000` | FastAPI: parsing, scoring, campaigns, approvals, purge, blocklist |
| sinkhole | UDP `127.0.0.1:5353` (container `172.31.50.53`) | CoreDNS, answers from the analyzer's blocklist |
| GoPhish | admin `127.0.0.1:3333`, pages `127.0.0.1:8081` | demo phishing campaign on `.test` domains (training page, no credential capture) |

Inside the Docker network the services use their names: `mailpit:8025`, `webdis:7379`, `analyzer:8000`,
`sinkhole`. Use the name, never `localhost`, from inside n8n. The analyst's links use `WEBHOOK_URL`
(`http://localhost:5678/`), which is what the analyst's browser opens.

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

Requirements: Docker with Compose v2, `curl`, Python 3.11+ for the demo scripts, `dig` (optional).

```bash
cp .env.example .env
#   APPROVAL_SECRET   python3 -c "import secrets;print(secrets.token_hex(32))"
#   GOPHISH_API_KEY   GoPhish admin UI (https://localhost:13333 with your ports), Settings, "Show"
#   LAB_RESET=1       demo lab only: lets the scenario expire leftover requests
make up
docker compose ps        # six services Up
```

Import the two workflows into n8n once (the commands are in `docs/runbook.md`), then:

```bash
make test                # analyzer unit tests, in the analyzer container
python3 demo/gophish_setup.py      # creates the GoPhish demo objects (idempotent)
set -a; . ./.env; set +a
python3 demo/scenario.py --decision approve   # the whole incident, about one minute
```

`docs/runbook.md` has the step-by-step demo, the restore procedure and the troubleshooting table.

### Port overrides

Your machine may already use some of these ports. Set them in `.env` (git-ignored); compose reads that file.
The demo scripts read the same file, so they reach the right ports.

| Variable | Default | Used by |
|----------|---------|---------|
| `MAILPIT_UI_PORT` | 8025 | Mailpit UI/API on the host |
| `MAILPIT_SMTP_PORT` | 1025 | SMTP on the host (`demo/*.py`) |
| `SINKHOLE_HOST_PORT` | 5353 | DNS on the host (`dig -p`) |
| `GOPHISH_ADMIN_PORT` | 3333 | GoPhish admin |
| `GOPHISH_PHISH_PORT` | 8081 | GoPhish phishing pages |

---

## Analyzer API

Interactive docs: http://localhost:8000/docs when the stack is running.

| Method and path | Purpose |
|-----------------|---------|
| `POST /analyze/{mailpit_id}` | fetch a message from Mailpit and analyze it |
| `POST /analyze-raw` | analyze raw `.eml` bytes (max 10 MB) |
| `POST /score` | score an analysis, with optional reputation data; return verdict and reasons |
| `POST /campaign` | assign the report to a campaign or create one; flags duplicate reports |
| `POST /campaign/{id}/case/{case_id}` | remember an IRIS case ID for a campaign (not used yet) |
| `POST /quarantine` | save raw copies of Mailpit messages (a standalone helper) |
| `POST /approvals` | open a decision request for a phishing verdict; reuses the pending one of the campaign |
| `POST /approvals/{id}/decide` | approve or reject with a signed token; refused if forged, decided or expired |
| `GET /approvals/{id}` | status, reporter, result |
| `GET /approvals/{id}/plan` | read-only: which copies and domains the approval would act on |
| `POST /approvals/{id}/execute` | purge: quarantine, delete, block. Only for an approved request |
| `GET /approvals/{id}/verify` | copies left in mailboxes and DNS state of each blocked domain |
| `POST /lab/reset-approvals` | demo lab only (`LAB_RESET=1`): expire open requests |
| `GET /blocklist`, `POST /blocklist`, `DELETE /blocklist/{domain}` | DNS blocks with TTL (default 3600 s, max 86400 s) |
| `GET /verify/dns/{domain}` | what the sinkhole answers; `blocked` is true for `0.0.0.0` |

### What `analyze` returns

- `report_message_id`, `reporter`, `message_id`
- `from`, `from_name`, `sender_domain`, `reply_to`, `subject`, `subject_norm` (digits replaced by `#`)
- `auth`: SPF, DKIM, DMARC results from `Authentication-Results`
- `urls`: `url`, `defanged`, `domain`, `is_ip`, `punycode`, `ioc_hit`, and `nested_in` for a link found inside a
  redirect parameter (the nested link is extracted and scored; it is never opened)
- `attachments`: name, type, size, SHA-256, YARA hits
- `features`: the boolean signals used by the score

A report is a forward when the suspicious mail is attached as `message/rfc822` or as a `.eml` file.

### The score

Every point comes with a written reason in the response.

| Signal | Points | Why it matters |
|--------|--------|----------------|
| SPF, DKIM or DMARC fail (or softfail/permerror) | +20 | the sender could not prove who it is |
| Reply-To domain differs from From domain | +10 | replies go to the attacker |
| Display name spoofs a brand | +10 | "Microsoft Support" from a random domain |
| Link points to a raw IP address | +15 | legitimate companies use domain names |
| Punycode (`xn--`) domain | +10 | look-alike characters |
| Urgency words | +10 | pressure is the attacker's main tool |
| Sender domain contains a brand but is not allowlisted | +15 | look-alike sender |
| Link hidden in a redirect parameter | +10 | the real destination is wrapped in a trusted-looking link |
| Known bad URL (local feed, or URLhaus hit) | +40 | strong evidence |
| Known bad attachment hash | +40 | strong evidence |
| YARA rule match on an attachment | +30 | strong evidence |

Total is capped at 100. Verdicts:

- `safe`: below 25
- `review`: 25 to 39, the analyst decides, no purge is offered
- `phishing`: 40 or more, approval request

The phishing threshold is 40, not the guide's 60. On the labelled set, 60 reaches recall 0.23 and 40 reaches
0.77, with no false alarm in either case (`docs/evaluation.md`). The set is synthetic and was used to choose the
value, so treat the number as optimistic. `T_PHISH` in `analyzer/app.py` changes it.

**Rule:** if a configured reputation source is unavailable, the verdict can never be `safe`; it becomes `review`.

### Campaign grouping and the purge match

Each report gets tokens: the normalized subject, the sender domain, each link domain and each attachment hash.
Two reports are the same campaign when the Jaccard similarity of their tokens is at least 0.5. The purge uses
the same rule to decide which mailbox copies belong to the campaign. Copies in `reports@corp.local` (the
forwards) and in the analyst and SOC mailboxes are never matched.

### Approvals

- A phishing verdict opens one request per campaign. A second report of the same campaign reuses the pending
  request, so the analyst decides once.
- Each request has two tokens, approve and reject. Each is an HMAC-SHA256 over the request ID, the action and the
  expiry, with `APPROVAL_SECRET` from `.env`. A token cannot be swapped between approve and reject.
- A decision works once. A request expires after `APPROVAL_TTL_SECONDS` (default 600). An expired request
  changes nothing and cannot be approved later.
- Purge needs status `approved`. Each copy is saved to `quarantine/<approval_id>/` with its SHA-256 before the
  delete. If a save fails, nothing is deleted.
- Verification waits up to 20 s for the sinkhole to reload, then checks that no copy is left and every blocked
  domain answers `0.0.0.0`.

### Blocklist safety

- Domains must match a strict hostname pattern. Anything else returns 400, so a value with a newline cannot
  inject lines into the DNS hosts file.
- Allowlisted domains (`corp.local`, `google.com`, `microsoft.com`, `github.com`, and their subdomains) are
  refused with `blocked: false`.
- Blocks expire by TTL. The hosts file is written atomically, so CoreDNS never reads a half-written file.
- The blocklist lives in memory: a restart of the analyzer clears it.

---

## n8n workflows

| File | What it does |
|------|--------------|
| `n8n/workflows/01-phishing-report.json` (`phishIntake0001`) | intake: poll, lock, analyze, reputation, score, route, reply, request approval, analyst e-mail |
| `n8n/workflows/02-approval-response.json` (`approvalResp0002`) | the analyst's webhook: decide, purge, verify, notices |

Both are exported from the running n8n (`n8n export:workflow`) and contain no credentials; the SMTP
credential is referenced by name and lives in n8n.

**01, node flow:** `Poll` (30 s) → `List reports` → `One report each` → `Idempotence` (Webdis
`SET report-<id>/lock NX EX 120`) → `First time` → `Analyze` → `Reputation lookups` (per report) → `Score` →
`Verdict`:

- `safe` → `Reply safe` → `Mark done` → `Mark read`
- `review` or `phishing` → `Campaign` → `Request approval` (phishing only) → `Notify analyst` →
  `Mark done` → `Mark read`
- any HTTP failure → `DLQ`: the report stays unread, its lock expires, and the next poll retries it

**02, node flow:** `Approval link` (webhook) → `Decide` → `Approved?` → `Execute purge` → `Verify` →
`Verified?` → `Build notices` → `Send notices` → `Collect` → response to the analyst. A refused decision,
a reject, a failed purge and a failed verification each have their own response and analyst e-mail.

**Why the order matters:** Mailpit marks a message read when it is handled, so "unread" cannot be the only
record. The report is marked read only after the verdict action succeeds, and the lock becomes permanent
(`report-<id>/done`) at the same point. HTTP calls make up to three attempts; the e-mail nodes make one, so a
retry cannot send a second mail.

**Reputation rules** (in `Reputation lookups`):
- URLhaus needs `URLHAUS_AUTH_KEY` (from `.env`). Without a key it is `disabled`, which does not change the
  verdict because the local IOC feed still runs. A configured source that fails is `unavailable`, and
  `unavailable` never produces `safe`.
- CIRCL needs no key. HTTP 404 means "unknown", not clean. Any other error is `unavailable`.

**Email body format:** the Send Email node needs `emailFormat: "text"`, otherwise the body is empty.

**Exports:** after changing a workflow in the UI, export it again and remove anything secret before committing.

---

## Evaluation

Full method and numbers: `docs/evaluation.md`. Summary:

- **Labelled set (83 synthetic mails, `dataset/`):** at threshold 40, 34 of 34 phishing mails are caught except
  the 10 hard cases that pass authentication and carry no known-bad link. No legitimate mail is flagged.
- **Live scenario (`demo/scenario.py`):** five approve runs on the final code passed every check. The analyst
  e-mail arrives 22–26 s after the first report (mostly the intake's 30 s poll); a decision takes 1.5–3.6 s to
  purge and verify. A reject run and a timeout run also pass.
- **Without automation:** the manual steps the chain replaces are counted in `docs/evaluation.md`. No human
  timing was measured, and none is claimed.

---

## Safety rules

- The analyzer only reads bytes. It never opens a URL and never runs an attachment.
- Nothing is deleted without an approved record (enforced in `execute`, tested).
- Every copy is quarantined with its SHA-256 before it is deleted. A restore re-checks the hash first.
- Allowlisted domains are never blocked.
- A missing reputation source never produces a `safe` verdict.
- Lab only: all ports bind to `127.0.0.1`; use fake `.test` domains; never target real people or addresses.
  GoPhish's training page captures no credentials.
- Secrets live in `.env` (git-ignored) or n8n credentials. Only `.env.example` is committed.

---

## Repository layout

```
analyzer/
  app.py                  the analyzer (all endpoints above)
  Dockerfile, requirements*.txt
  ioc/domains.txt         local threat feed (one domain per line)
  yara-rules/demo.yar     harmless demo rule (PHISH_DEMO_MARKER)
  tests/                  pytest: parsing, redirects, campaigns, score, blocklist, approvals, purge
compose.yaml              the lab
dns-sinkhole/             CoreDNS Corefile and base hosts (the fake site)
gophish/config.json       GoPhish config (admin on 0.0.0.0:3333 inside the container)
demo/
  _env.py                 loads .env for every demo script
  report.py               forwards a mailbox message to reports@ as an employee would
  send_sample.py          sends one phish and one legitimate mail to alice
  gophish_setup.py        creates the GoPhish objects and launches a campaign (idempotent)
  scenario.py             replayable end-to-end run: approve | reject | timeout
  restore.py              undo a purge from quarantine (dry run by default)
dataset/                  synthetic labelled set (make_dataset.py, labels.csv, emls/, README.md)
eval/
  confusion_matrix.py     scores the labelled set against the live analyzer
  evaluate.py             N scenario runs + summary + confusion matrix
  results.txt             last confusion matrix
  scenario_results.md     summary of the last batch of approve runs
  runs/                   one JSON per scenario run (evidence)
n8n/workflows/            the two exported workflows (no credentials)
docs/
  architecture.md         components, both workflows, sequence diagram, safety rules, decisions
  runbook.md              install, demo, restore, troubleshooting
  evaluation.md           method, results, limits, the manual comparison
quarantine/               purged copies, one folder per approval (contents git-ignored)
Makefile                  up, down, test, scenario, evaluate, reset
.env.example              every variable and port override, with defaults
```

---

## Known limits and decisions

- **DFIR-IRIS is not integrated.** The guide suggests it for the campaign folder. The folder here is the
  campaign record in SQLite plus the analyst's e-mail. IRIS would need its own database and several GB of RAM,
  which this machine does not have to spare.
- **Phishing threshold 40** (guide: 60). Chosen on the labelled set, which is synthetic; see *The score*.
- **Hard cases are not detected:** a compromised account with passing authentication and no bad link scores 0.
  The approval gate is the control for them; the score cannot see them.
- **Only the first report's reporter is thanked by mail.** The approval belongs to the first report of a
  campaign. The other reporters are not notified yet.
- **Approval timeout = no action.** At expiry nothing is sent to the analyst; the link answers "expired".
- **Retries are unbounded in time.** A report that keeps failing is retried every 120 s with no maximum
  attempt count yet.
- **Blocklist in memory:** an analyzer restart clears blocks; the blocks expire by TTL anyway.
- **Mailpit is not a real mail system:** purge and retention differ in production.
- **Restore record:** the analyzer writes quarantine as root, so `restore.py` prints its record when it cannot
  save it next to the copies.
- **Disabled vs unavailable:** the guide says a missing URLhaus key should count as "unavailable". It is recorded
  as `disabled` so the safe reply still works. This is a design decision to state in the report.
- **Reputation:** URLhaus is wired but inactive without a key; CIRCL is live but unreachable from this sandbox.
  The local IOC feed is the only source that works offline. VirusTotal and OTX are not used.
- **Synthetic data:** results are optimistic. A public corpus (SpamAssassin, Nazario) is the next step.
- **Host ports:** this machine runs its own Mailpit on `1025`. The lab uses `11025`, `18025` and others from
  `.env`. The scripts load `.env`, so they reach the lab, not the other service.

---

## Troubleshooting

See `docs/runbook.md` for the full table. The most common ones:

| Symptom | Fix |
|---------|-----|
| `failed to bind host port ... address already in use` | set the matching variable in `.env` and `docker compose up -d` |
| n8n cannot reach a service | use the service name (`mailpit`, `analyzer`, `webdis`), not `localhost` |
| `getaddrinfo EAI_AGAIN analyzer` in n8n | transient Docker DNS failure; the report is retried |
| purge done, `dig` still shows the old address | CoreDNS reloads a few seconds later; `verify` waits up to 20 s |
| analyst link says `expired` | the 10-minute window passed; nothing was purged |
| `503 APPROVAL_SECRET is not set` | add the secret to `.env` and restart the analyzer |
| GoPhish admin password | printed once in the GoPhish logs on first start: `docker compose logs gophish` |

---

## Contributing and the team

- Two people: Person A (orchestration: n8n workflows, approval, purge, replies) and Person B
  (infrastructure, analysis, data). Work on `feat/infra-analysis` or `feat/orchestration`, merge by pull request.
- Never commit `.env`, API keys or passwords. Export n8n workflows only after removing credentials.
- Pin every new image version and record it in *Pinned versions*.
