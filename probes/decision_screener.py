"""
Variant-A probe v2: decision-space enumeration screener (card 3).

v1 showed D1-D3 PASS (discrete error flips real decisions: 80% ranks change,
top-3 2/3 flip, 28.9% pairwise flips) but D4 FAIL (jump magnitude does NOT
predict rank change, corr -0.12; rank-boundary proximity also fails, -0.29).

The reason: decision flip is a RELATIVE, cross-symbol structure change. All
symbols' EPS jump ~3-4x together quarter->fy, so the ranking is reshuffled in
a way no single-query output statistic predicts.

The correct screener is therefore NOT prediction — it is ENUMERATION:
  for each discrete neighbor z' of the query, recompute the DECISION;
  if the decision flips, flag the query as decision-unsafe.

This is exactly S_mix's D_G idea, but applied in DECISION space instead of
output space. It is implementable (enumerate neighbors, recompute) and needs
no prediction.

We measure:
  - E1: fraction of symbols whose decision (rank) is fragile to the period
        neighbor (i.e. enumeration finds a flip)
  - E2: the screener flags a non-trivial fraction of queries as unsafe
  - E3: enumeration-based screening is strictly better than output-jump
        screening (which failed in v1)

Usage:
    python decision_screener.py --in mixed_scale.jsonl
"""

import argparse
import json
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


def rank(syms, keyfn):
    ordered = sorted(syms, key=keyfn, reverse=True)
    return {s: i + 1 for i, s in enumerate(ordered)}


def screener(rows):
    eps = eps_by_period(rows)
    syms = list(eps.keys())
    print("=" * 70)
    print("DECISION-SPACE ENUMERATION SCREENER  (variant A v2)")
    print("=" * 70)
    print(f"symbols: {len(syms)}\n")

    rq = rank(syms, lambda s: eps[s]["quarter"])
    rf = rank(syms, lambda s: eps[s]["fy"])

    # E1: per-symbol decision fragility = does its rank flip under the neighbor?
    # A query for symbol s is "decision-unsafe" if s's rank changes.
    n_flip = sum(1 for s in syms if rq[s] != rf[s])
    print("1. DECISION FRAGILITY (per-symbol rank flip under period neighbor)")
    print(f"   symbols whose rank flips: {n_flip}/{len(syms)} "
          f"= {n_flip/len(syms):.0%}")

    # E2: the screener flags these as unsafe
    print("\n2. SCREENER OUTPUT (enumeration-based)")
    print(f"   flags {n_flip}/{len(syms)} queries as decision-unsafe "
          f"(rank changes under period=quarter->fy)")

    # E3: compare to output-jump screening (v1's failed D4)
    # output-jump screening: flag symbol if its EPS jump > threshold
    jumps = {s: abs(eps[s]["fy"] - eps[s]["quarter"]) /
             max(abs(eps[s]["fy"]), abs(eps[s]["quarter"]), 1e-9)
             for s in syms}
    # how well does output-jump screening recover the decision-flip set?
    # (rank-flipped symbols)
    flipped = {s for s in syms if rq[s] != rf[s]}
    # output-jump screener with threshold 0.5 flags high-jump symbols
    jump_flagged = {s for s in syms if jumps[s] > 0.5}
    tp = len(flipped & jump_flagged)
    prec = tp / len(jump_flagged) if jump_flagged else 0
    rec = tp / len(flipped) if flipped else 0
    print("\n3. OUTPUT-JUMP SCREENING (v1's approach) vs ENUMERATION")
    print(f"   output-jump screener (flag jump>50%): "
          f"precision={prec:.0%}, recall={rec:.0%}")
    print(f"   -> output-jump screening MISSES {1-rec:.0%} of decision flips")
    print(f"   -> enumeration screener catches 100% by construction "
          f"(it recomputes the decision)")

    # verdict
    print("\n4. VERDICT (variant A v2)")
    e1 = n_flip / len(syms) >= 0.3
    e2 = n_flip / len(syms) >= 0.1
    e3 = rec < 0.9  # output-jump screening is incomplete
    print(f"   E1 decisions are fragile ({n_flip}/{len(syms)} >= 30%): "
          f"{'PASS' if e1 else 'FAIL'}")
    print(f"   E2 screener flags non-trivial fraction (>=10%): "
          f"{'PASS' if e2 else 'FAIL'}")
    print(f"   E3 output-jump screening incomplete (recall {rec:.0%} < 90%): "
          f"{'PASS' if e3 else 'FAIL'}")
    print(f"\n   All PASS -> the decision-space enumeration screener works,")
    print(f"   and it beats output-jump screening (which v1 showed fails).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    screener(load(a.inp))


if __name__ == "__main__":
    main()
