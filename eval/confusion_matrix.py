"""Score the labelled dataset with the live analyzer and print the confusion matrix per threshold.

Run from the repository root with the stack up:
    python3 eval/confusion_matrix.py > eval/results.txt
"""
import csv
import os
import sys
import time

import requests

A = os.getenv("ANALYZER_URL", "http://localhost:8000")
rows = list(csv.DictReader(open("dataset/labels.csv")))
results = []
for r in rows:
    with open("dataset/emls/" + r["file"], "rb") as f:
        raw = f.read()
    t = time.time()
    a = requests.post(A + "/analyze-raw", data=raw, timeout=10).json()
    # reputation is empty on purpose: the dataset has no live lookups, only the local rules
    s = requests.post(A + "/score", json={"analysis": a, "reputation": {}}, timeout=10).json()
    results.append((r["file"], r["label"], r["kind"], s["score"], time.time() - t))

if not results:
    sys.exit("no rows in dataset/labels.csv: run dataset/make_dataset.py first")


def matrix(th):
    tp = fp = tn = fn = 0
    for _, label, _, sc, _ in results:
        pred = sc >= th
        if label == "phishing" and pred:
            tp += 1
        elif label == "phishing":
            fn += 1
        elif pred:
            fp += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    return tp, fp, tn, fn, prec, rec


for th in (25, 40, 60, 75):
    tp, fp, tn, fn, p, r = matrix(th)
    print("threshold %d: TP=%d FP=%d TN=%d FN=%d precision=%.2f recall=%.2f" % (th, tp, fp, tn, fn, p, r))
print("avg analysis time: %.3f s per mail" % (sum(x[4] for x in results) / len(results)))
print("\nMissed phishing (false negatives at 60):")
for f, l, k, sc, _ in results:
    if l == "phishing" and sc < 60:
        print("  ", f, k, sc)
print("False alarms (false positives at 60):")
for f, l, k, sc, _ in results:
    if l == "legit" and sc >= 60:
        print("  ", f, k, sc)
