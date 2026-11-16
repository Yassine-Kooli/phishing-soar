# Runbook: install, demo, restore, troubleshooting

## 1. Install (once)

```bash
cp .env.example .env
# fill in the two secrets; never commit .env
python3 -c "import secrets;print(secrets.token_hex(32))"   # paste as APPROVAL_SECRET
#   GOPHISH_API_KEY: GoPhish admin UI (https://localhost:13333), Settings, "Show"
#   LAB_RESET=1 for the demo lab (lets the scenario expire leftover requests)
make up
docker compose ps            # six services Up
make test                    # 23+ analyzer tests (run in a container; see below)
```

Import the workflows once into n8n (they are in `n8n/workflows/`):

```bash
for f in n8n/workflows/*.json; do
  docker cp "$f" phish-soar-n8n-1:/tmp/wf.json
  docker exec phish-soar-n8n-1 n8n import:workflow --input=/tmp/wf.json
done
docker exec phish-soar-n8n-1 n8n update:workflow --id=phishIntake0001 --active=true
docker exec phish-soar-n8n-1 n8n update:workflow --id=approvalResp0002 --active=true
docker restart phish-soar-n8n-1
```

The GoPhish demo objects are created by `python3 demo/gophish_setup.py` (idempotent).

Unit tests without a local Python environment:

```bash
docker run --rm -v "$PWD/analyzer:/src" -w /src phish-soar-analyzer \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```

## 2. Live demo (replayable)

```bash
set -a; . ./.env; set +a
python3 demo/scenario.py --decision approve   # ~1 minute: purge, block, notices, verification
python3 demo/scenario.py --decision reject    # ~1 minute: nothing deleted
python3 demo/scenario.py --decision timeout   # 10 minutes: the link expires, nothing deleted
```

What the script does: resets the mailboxes and the blocklist, expires leftover requests, launches a
GoPhish campaign, has two employees report it, reads the analyst's e-mail for the signed links, clicks
the decision through n8n, then checks the mailboxes, the analyzer state and the DNS sinkhole. It writes
`eval/runs/<run>-<decision>.json` and exits non-zero if any check fails.

Watch it live: Mailpit at http://localhost:8025 (or `MAILPIT_UI_PORT`), n8n executions at http://localhost:5678,
the analyzer's API at http://localhost:8000/docs.

To decide by hand, open the link in the analyst's e-mail. The approval also shows its plan without deciding:

```bash
curl -s localhost:8000/approvals/<id>/plan | python3 -m json.tool
```

## 3. Restore after a wrong approval

```bash
python3 demo/restore.py <approval_id>           # dry run: what would come back
python3 demo/restore.py <approval_id> --apply   # re-sends the quarantined copies, unblocks the domains
```

Each copy is checked against its SHA-256 before it is sent. A restore is never automatic.

## 4. Evaluation

```bash
python3 eval/evaluate.py --runs 5    # five approve runs, then the labelled-set confusion matrix
```

Results and method: `docs/evaluation.md`, `eval/scenario_results.md`, `eval/results.txt`.

## 5. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `getaddrinfo EAI_AGAIN analyzer` in n8n | transient Docker DNS failure. The HTTP nodes retry; the report stays unread and is retried after 120 s. |
| Purge done but DNS still resolves the domain | CoreDNS reloads the hosts file a few seconds later. `GET /approvals/{id}/verify` waits up to 20 s. Check `dig @127.0.0.1 -p 5354 <domain>`. |
| Analyst link says `Refused: 409 ... expired` | the 10-minute window passed. Nothing was purged. Ask the analyst to report again. |
| Analyst link says `already executed` | the approval was used. Use `demo/restore.py` if it was a mistake. |
| `503 APPROVAL_SECRET is not set` in n8n | `.env` has no `APPROVAL_SECRET`. Set it and `docker compose up -d analyzer`. |
| GoPhish returns 500 on create | a field is missing or wrong; `docker logs phish-soar-gophish-1` shows the reason. The sender must be a bare address. |
| Scenario: `GoPhish mail did not reach every target` | the campaign failed to start: check the campaign in the GoPhish admin UI, then `Mailpit lab SMTP` host `mailpit:1025`. |
| Ports already in use | set the port in `.env` (see the README) and `docker compose up -d`. |
