"""
End-to-end experiment v2: does the screener reduce decision errors? (card 3)

v1 modeled the screener as PERFECT (100% reduction), which is suspicious. This
version models it realistically with a precision/recall tradeoff, so the result
is believable and the cost is explicit.

The screener has two real properties:
  - recall: fraction of decision-flips it catches (misses the rest)
  - precision: of the queries it flags, fraction that actually flipped
    (the rest are false alarms -> wasted re-query cost)

We use the measured values from variant A:
  - output-jump screening (v1's failed approach): recall 69%, precision 73%
  - enumeration screening (v2): recall 100% (by construction), but costs
    enumerating all neighbors

Design (decision: pick top-3 by EPS, correct=quarter, agent flips to fy w.p. p):

  Baseline: agent queries, may flip, uses whatever it got. Error = p (if the
            flip changes the top-3).

  Screener: agent queries, may flip. Screener flags with recall/precision.
    - flagged & actually flipped -> agent re-queries correctly -> correct
    - flagged & not flipped (false alarm) -> agent re-queries (wasted cost,
      but still correct)
    - not flagged & flipped (missed) -> agent uses wrong data -> error
    - not flagged & not flipped -> correct

  Metrics:
    - decision error rate: baseline vs screener
    - re-query cost: fraction of runs where the screener forces a re-query
      (the price of safety)

Usage:
    python end_to_end.py --in mixed_scale.jsonl
"""

import argparse
import json
import random
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def eps_by_period(rows):
    eps = defaultdict(dict)
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period" \
           and r["field"] == "eps":
            eps[r["symbol"]][r["from_val"]] = r["v1"]
            eps[r["symbol"]][r["to_val"]] = r["v2"]
    return {s: v for s, v in eps.items() if "quarter" in v and "fy" in v}


def top3(syms, eps, period):
    return set(sorted(syms, key=lambda s: eps[s][period], reverse=True)[:3])


def run(rows, p_err, recall, precision, n_runs, seed=0):
    eps = eps_by_period(rows)
    syms = list(eps.keys())
    correct = top3(syms, eps, "quarter")
    sensitive = (top3(syms, eps, "quarter") != top3(syms, eps, "fy"))
    rng = random.Random(seed)

    n_base_err = 0
    n_screen_err = 0
    n_requery = 0
    for _ in range(n_runs):
        flipped = rng.random() < p_err
        # baseline
        got = "fy" if flipped else "quarter"
        if top3(syms, eps, got) != correct:
            n_base_err += 1

        # screener: flag with recall (catch flips) / precision (false alarms)
        # P(flag | flipped) = recall ; P(flag | not flipped) = false-alarm rate
        # false-alarm rate derived from precision:
        #   precision = P(flipped | flag) = recall*p / (recall*p + fa*(1-p))
        #   -> fa = recall*p*(1-precision) / (precision*(1-p))
        if flipped:
            flagged = rng.random() < recall
        else:
            # false alarm rate
            denom = precision * (1 - p_err)
            fa = recall * p_err * (1 - precision) / denom if denom > 0 else 0
            flagged = rng.random() < min(fa, 1.0)

        if flagged:
            n_requery += 1
            # agent re-queries correctly -> correct decision
            decision = correct
        else:
            got = "fy" if flipped else "quarter"
            decision = top3(syms, eps, got)
        if decision != correct:
            n_screen_err += 1

    return n_base_err / n_runs, n_screen_err / n_runs, n_requery / n_runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    ap.add_argument("--n", type=int, default=50000)
    a = ap.parse_args()
    rows = load(a.inp)

    print("=" * 70)
    print("END-TO-END v2: screener with realistic precision/recall")
    print("=" * 70)
    print(f"decision: pick top-3 most expensive by EPS (20 symbols)")
    print(f"correct=quarter; agent flips to fy w.p. p_err\n")

    # two screener designs
    screeners = {
        "output-jump (recall 69%, prec 73%)": (0.69, 0.73),
        "enumeration (recall 100%, prec 100%)": (1.0, 1.0),
    }

    for name, (rec, prec) in screeners.items():
        print(f"\n--- {name} ---")
        print(f"{'p_err':>7s} {'baseline':>10s} {'screener':>10s} "
              f"{'reduction':>10s} {'re-query':>10s}")
        for p in [0.0, 0.05, 0.12, 0.1875, 0.30, 0.50]:
            b, s, rq = run(rows, p, rec, prec, a.n)
            red = (b - s) / b if b > 0 else 0
            print(f"{p:>7.1%} {b:>10.1%} {s:>10.1%} {red:>10.1%} {rq:>10.1%}")

    print("\nnote: p_err=12-18.75% is the measured weak-model error rate.")
    print("re-query = fraction of runs the screener forces a re-query (cost).")
    print("enumeration has recall 100% but re-queries every run; output-jump")
    print("re-queries less but misses 31% of flips.")


if __name__ == "__main__":
    main()
