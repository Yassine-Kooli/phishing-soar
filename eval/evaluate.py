"""Evaluation of the live pipeline: N replayed scenario runs + the labelled-set confusion matrix.

    python3 eval/evaluate.py --runs 5

1. runs demo/scenario.py --decision approve N times (each run is a full replay on the lab);
2. summarises the timings (min / median / max) and the pass rate of every check;
3. runs eval/confusion_matrix.py on the labelled set and writes eval/results.txt.

Timings measure the automation only: report -> analyst e-mail (the verdict, the score and the links),
and decision -> purge -> verification. The analyst's own reading and decision time is NOT included,
because a scripted click has none. The manual baseline is described in docs/evaluation.md.
"""
import argparse
import glob
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_scenarios(n, decision):
    for i in range(n):
        print("== run %d/%d (%s)" % (i + 1, n, decision), flush=True)
        subprocess.run([sys.executable, str(ROOT / "demo" / "scenario.py"), "--decision", decision], check=False)


def summary(paths):
    runs = [json.load(open(p)) for p in paths]
    lines = ["# Scenario results", "", "Runs: %d, decision: %s" % (len(runs), runs[0]["decision"] if runs else "-"), ""]
    keys = sorted({k for r in runs for k in r.get("timings_s", {})})
    lines += ["| Timing (s) | min | median | max |", "|---|---|---|---|"]
    for k in keys:
        vals = [r["timings_s"][k] for r in runs if k in r.get("timings_s", {})]
        if vals:
            lines.append("| %s | %.1f | %.1f | %.1f |" % (k, min(vals), statistics.median(vals), max(vals)))
    lines += ["", "| Check | passed |", "|---|---|"]
    checks = sorted({k for r in runs for k in r.get("checks", {})})
    for c in checks:
        ok = sum(1 for r in runs if r.get("checks", {}).get(c))
        lines.append("| %s | %d / %d |" % (c, ok, len(runs)))
    lines += ["", "Runs passed completely: %d / %d" % (sum(1 for r in runs if r.get("passed")), len(runs))]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--decision", default="approve")
    ap.add_argument("--skip-runs", action="store_true", help="only summarise existing eval/runs files")
    ap.add_argument("--since", default="", help="earliest run id to summarise (YYYYmmdd-HHMMSS)")
    args = ap.parse_args()
    since = args.since or time.strftime("%Y%m%d-%H%M%S")   # run ids start with a timestamp (local time)
    if not args.skip_runs:
        run_scenarios(args.runs, args.decision)
    # only this batch: earlier debugging runs stay on disk but are not summarised here
    paths = sorted(p for p in glob.glob(str(ROOT / "eval" / "runs" / ("*-%s.json" % args.decision)))
                   if os.path.basename(p) >= since)
    out = summary(paths)
    (ROOT / "eval" / "scenario_results.md").write_text(out)
    print(out)
    with open(ROOT / "eval" / "results.txt", "w") as f:
        subprocess.run([sys.executable, str(ROOT / "eval" / "confusion_matrix.py")], stdout=f, check=False,
                       cwd=ROOT)
    print("wrote eval/scenario_results.md and eval/results.txt")


if __name__ == "__main__":
    main()
