# Evaluation

Two questions: does the scoring separate phishing from legitimate mail (labelled set, offline), and does
the automated chain work end to end on the live lab, and how fast (replayed scenario)?

## 1. Scoring on the labelled set

`dataset/` holds 83 synthetic e-mails (seeded, reproducible): 34 phishing and 49 legitimate, including the
hard cases the rules are not expected to solve. Read `dataset/README.md` before quoting these numbers.
Scoring runs against the live analyzer with no reputation data (`eval/confusion_matrix.py`).

| Threshold | TP | FP | TN | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| 25 (review) | 34 | 0 | 39 | 10 | 1.00 | 0.77 |
| **40 (phishing, chosen)** | 34 | 0 | 39 | 10 | 1.00 | 0.77 |
| 60 (guide default) | 10 | 0 | 39 | 34 | 1.00 | 0.23 |
| 75 | 10 | 0 | 39 | 34 | 1.00 | 0.23 |

Where the decisions land at threshold 40:

| Mail kind | Label | Result |
|---|---|---|
| credential phishing, typo domains (15) | phishing | all caught |
| attachment with YARA marker (8) | phishing | all caught |
| link to a raw IP (6) | phishing | all caught |
| link hidden behind a redirect to a known-bad domain (5) | phishing | all caught (+10 redirect, +40 known bad) |
| compromised account, everything passes (6) | phishing | **all missed** (score 0) |
| link behind a redirect to a new domain, everything passes (4) | phishing | **all missed** (score 10) |
| internal mail (20), marketing with urgency words (8), misconfigured sender (7), search-engine redirect to a legitimate page (4) | legitimate | all pass (0 false alarms) |

**Why 40 and not 60.** At 60 the guide's rule misses 24 of 34 phishing mails. At 40 it misses the 10 cases
that carry no signal: passing authentication, no known-bad link, no brand in the sender. No threshold
can catch those with these features; the score needs the reputation sources or a compromised-account signal
(for example a mismatch with the sender's normal behaviour), which the lab does not have.

**Limit.** The threshold was chosen on the same set that is reported, so 0.77 is optimistic. Only a
separate, real corpus (for example SpamAssassin or Nazario samples) would make it an estimate. That is
listed as the next step in the limits.

Average analysis time: about 0.02 s per mail.

## 2. End-to-end scenario on the live lab

`demo/scenario.py` replays one incident: reset → GoPhish campaign to three employees → two employees report
it → the analyst's e-mail → the decision clicked through n8n → checks in the mailboxes, the analyzer and the
DNS sinkhole. It writes one JSON file per run in `eval/runs/`.

Five approve runs (the batch of the final code; `eval/scenario_results.md`):

| Timing (s) | min | median | max | What it covers |
|---|---|---|---|---|
| report → analyst e-mail | 22.2 | 24.1 | 26.2 | first report to the verdict, reasons and signed links. Mostly the 30 s poll interval of the intake. |
| decision → response | 1.5 | 2.7 | 3.6 | the click through n8n, the purge, the quarantine and the block |
| decision → purge verified | 1.6 | 2.7 | 3.7 | the same plus the mailbox and DNS checks |

| Check | Runs passed |
|---|---|
| copies quarantined and deleted from every employee mailbox | 5 / 5 |
| domains blocked and answered `0.0.0.0` by the sinkhole | 5 / 5 |
| one decision for two reports of the same campaign | 5 / 5 |
| each victim told their copy was removed (reporter excluded) | 5 / 5 |
| reporter thanked; analyst told the result | 5 / 5 |
| legitimate mail in the same mailbox untouched | 5 / 5 |

Reject (final code, one run): the status is `rejected`, all three copies remain, no domain is blocked, and the
analyst receives a `[rejected]` notice. Timeout (final code, one run, waits the full 10 minutes): the request
expires, the late approval link is refused with "expired", all copies remain and no domain is blocked.

A restore was also tested on a purged campaign: `demo/restore.py <id> --apply` re-sent the three
quarantined copies (each checked against its SHA-256 first) and removed both blocks.

### Defects found by the live runs and fixed

These are the reasons the final numbers are reliable. Each one was found by running the scenario, not by reading code.

| Defect | Effect seen | Fix |
|---|---|---|
| Report marked read and key set before analysis | a failed run lost the report silently | lock with TTL; permanent key and mark-read only after the verdict action |
| Code and expression nodes used `.first()` | a batch of two reports scored only one | per-item expressions |
| Two approval requests created in parallel | two decisions for one campaign | check and insert in one lock section |
| Verification ran before CoreDNS reloaded | "VERIFY FAILED" on a successful purge | the verify call waits up to 20 s for DNS |
| The analyst's first decision happened before the second report was processed | a second request for the same campaign | the scenario waits for one e-mail per reporter |
| Notices assumed the first reporter was alice | wrong recipients in the check | the reporter is read from the approval |
| Scripts used the guide's default ports, not `.env` | the restore reached another local mail service | the demo scripts load `.env` |

## 3. Without automation

No analyst was timed, so there is no measured manual duration, and this report does not invent one. The
comparison below counts the actions the automated chain replaces for the same incident (three mailboxes,
two reporters, two domains). Each action is a manual step in the mail client, DNS and the mail administration.

| Step done by hand | Automated by | Actions in the test incident |
|---|---|---|
| open and read each report, extract links, check headers | analyzer, score, reasons | 2 reports |
| search every mailbox for the campaign subject | `find_matches` (Mailpit API, campaign similarity) | 3 mailboxes |
| check each copy is the same campaign | Jaccard on subject, sender, links, hashes | 4 copies |
| save an evidence copy of each message before deleting | quarantine with SHA-256 | 4 copies |
| delete each copy | purge after approval | 4 deletions |
| block each domain in DNS and check it | block with allowlist refusal, sinkhole verification | 2 domains, 2 checks |
| write to each affected employee and the reporter | notices | 3 e-mails |
| write to the analyst and record the case | analyst summary, approval record | 1 e-mail, 1 record |

Human reading and decision time is the part no script can replace. The automation keeps it to one click
per campaign. To measure the gain, a timed run with an analyst following this table manually would be the
fair comparison; it is the next step.

## 4. Limits

- The labelled set is synthetic and the threshold was chosen on it.
- The hard cases (compromised accounts) are not detected. The approval gate is the control for them.
- The analyst's decision is a scripted click in the scenario; the human part is not measured.
- Purge and mail are simulated with Mailpit, which has no retention policy and no real IMAP purge.
- Only one reporter per campaign is thanked by mail (the approval belongs to the first report).
