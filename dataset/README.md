# Dataset: provenance and limits

**Source: 100% synthetic.** `make_dataset.py` generates 70 e-mails with a fixed seed (42),
so the dataset is reproducible: `python3 dataset/make_dataset.py`.

| Kind           | Label    | Count | What it tests                                   |
|----------------|----------|-------|-------------------------------------------------|
| cred           | phishing | 15    | credential phishing, failed auth, typo domains  |
| attach         | phishing | 8     | attachment with a YARA-matching marker          |
| iplink         | phishing | 6     | link to a raw IP address                        |
| **hard**       | phishing | 6     | compromised account, SPF/DKIM/DMARC all pass    |
| internal       | legit    | 20    | normal internal mail                            |
| **hard**       | legit    | 8     | marketing mail full of urgency words            |
| misconfigured  | legit    | 7     | legitimate sender with a softfail              |

## Why the results are optimistic

- The rules and the mails were written by the same people, so the score fits the dataset.
- The "hard" kinds are included on purpose. They show what the score cannot see
  (compromised accounts) and what it over-flags (urgent marketing).
- No public corpus (SpamAssassin, Nazario) has been added yet. Adding real samples is the
  next step before the results can be called realistic.
- The evaluation runs the local rules only (`reputation` empty), so it does not measure
  URLhaus or CIRCL.

Results and the chosen thresholds: `eval/results.txt`.
