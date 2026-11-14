# Phishing Report Box (SOAR)

A SOAR pipeline: an employee forwards a suspicious e-mail, a program analyzes it safely,
an explainable score decides, reports of the same campaign are grouped, a human approves,
the mail is purged and the domain blocked, and the result is verified.

Full plan: `Project1_Phishing_SOAR_Implementation_Guide.docx` (kept outside the repo).

## Quick start

```bash
cp .env.example .env        # optional keys; the demo works without them
make up                     # docker compose up -d --build
make test                   # analyzer unit tests (pytest, in analyzer/)
```

Check the stack:

```bash
curl -s localhost:8000/blocklist                          # {}
dig @127.0.0.1 -p 5353 secure-login.corp-verify.test +short   # 172.31.50.20 (GoPhish)
```

If port 5353 is taken on your machine (common on Linux with avahi), use another host port:
`SINKHOLE_HOST_PORT=5354 docker compose up -d` and query port 5354.

## Services (contract)

| Service  | Address                | Notes                                   |
|----------|------------------------|-----------------------------------------|
| Mailpit  | UI/API 8025, SMTP 1025 | fake mail server, localhost only        |
| n8n      | 5678                   | orchestration (workflows in `n8n/workflows/`) |
| Webdis   | 7379                   | Redis over HTTP (idempotence keys)      |
| analyzer | 8000                   | FastAPI, see `analyzer/app.py`          |
| sinkhole | UDP 53 (host 5353)     | CoreDNS, fed by the analyzer blocklist  |
| GoPhish  | 3333 (admin), 8081     | demo phishing campaign, `.test` domains |

Pinned images: `axllent/mailpit:v1.27.11`, `docker.n8n.io/n8nio/n8n:2.40.7`,
`nicolas/webdis:0.1.25`, `coredns/coredns:1.11.1`, `gophish/gophish:0.12.1`,
`python:3.12-slim`. Analyzer Python deps are pinned in `analyzer/requirements.txt`.

All host ports bind to `127.0.0.1`. Use only in the isolated lab with fake `.test` domains.

## Layout

```
analyzer/      safe e-mail reader, score, campaigns, blocklist (+ tests/)
compose.yaml   the lab
dns-sinkhole/  CoreDNS config and base hosts
gophish/       GoPhish config (campaign export comes in Step 10)
demo/          report.py (forward a mail as an employee would), send_sample.py
n8n/workflows/ exported n8n workflows (no credentials)
```

## Safety rules

- The analyzer only reads bytes. It never opens a URL and never runs an attachment.
- Allowlisted domains (`corp.local`, `google.com`, ...) are never blocked.
- Quarantine copies are written before any purge; a failed copy means no purge.
- A missing reputation source never produces a `safe` verdict.
