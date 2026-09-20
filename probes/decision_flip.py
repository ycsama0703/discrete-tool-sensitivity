"""
Variant-A probe: decision-flip under discrete tool error (card 3).

Variant A is the "pre-decision trust-boundary screener": an agent uses a tool
output to make a downstream decision. The claim is that a discrete parameter
error (period=quarter -> fy) not only jumps the OUTPUT, it can FLIP the DECISION.

This probe tests the decision-flip directly, using only the EPS data already in
mixed_scale.jsonl (no external prices needed):

  Decision task: "rank the 20 symbols by EPS and pick the 3 most expensive"
  (a real investment-style selection decision).

  If the agent queries period=quarter, it ranks by quarter EPS.
  If it queries period=fy, it ranks by fy EPS.
  The two rankings differ -> the selected "top-3 most expensive" set may flip.

We measure:
  - D1: how many of the 20 symbols change RANK between quarter and fy EPS
  - D2: how much the selected top-3 set changes (Jaccard overlap)
  - D3: how many pairwise "A more expensive than B" comparisons flip
  - D4: does the screener (flag D_G large) predict the decision flip?

Usage:
    python decision_flip.py --in mixed_scale.jsonl
"""

import argparse
import json
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def eps_by_period(rows):
    """symbol -> {quarter: eps, fy: eps} from fundamentals period substitutions."""
    eps = defaultdict(dict)
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period" \
           and r["field"] == "eps":
            eps[r["symbol"]][r["from_val"]] = r["v1"]
            eps[r["symbol"]][r["to_val"]] = r["v2"]
    return {s: v for s, v in eps.items() if "quarter" in v and "fy" in v}


def rank(symbols, keyfn):
    """Return dict symbol->rank (1 = highest EPS = most expensive)."""
    ordered = sorted(symbols, key=keyfn, reverse=True)
    return {s: i + 1 for i, s in enumerate(ordered)}


def decision_flip(rows):
    eps = eps_by_period(rows)
    syms = list(eps.keys())
    print("=" * 70)
    print("DECISION-FLIP PROBE  (variant A)")
    print("=" * 70)
    print(f"symbols with both quarter & fy EPS: {len(syms)}\n")

    rq = rank(syms, lambda s: eps[s]["quarter"])
    rf = rank(syms, lambda s: eps[s]["fy"])

    # D1: rank changes
    n_changed = sum(1 for s in syms if rq[s] != rf[s])
    print("1. RANK CHANGES (quarter vs fy EPS)")
    print(f"   symbols whose rank changed: {n_changed}/{len(syms)} "
          f"= {n_changed/len(syms):.0%}")
    for s in sorted(syms, key=lambda s: abs(rq[s]-rf[s]), reverse=True)[:8]:
        print(f"     {s:6s} rank {rq[s]:2d} -> {rf[s]:2d} "
              f"(delta {rf[s]-rq[s]:+d})")

    # D2: top-3 selection flip (most expensive = highest EPS)
    top3_q = set(sorted(syms, key=lambda s: eps[s]["quarter"], reverse=True)[:3])
    top3_f = set(sorted(syms, key=lambda s: eps[s]["fy"], reverse=True)[:3])
    overlap = len(top3_q & top3_f)
    print("\n2. TOP-3 SELECTION (most expensive by EPS)")
    print(f"   quarter top-3: {sorted(top3_q)}")
    print(f"   fy      top-3: {sorted(top3_f)}")
    print(f"   overlap: {overlap}/3  -> {overlap/3:.0%} kept, "
          f"{3-overlap} flipped")

    # D3: pairwise comparison flips
    n_pairs = 0
    n_flip = 0
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            a, b = syms[i], syms[j]
            n_pairs += 1
            q_ab = eps[a]["quarter"] > eps[b]["quarter"]
            f_ab = eps[a]["fy"] > eps[b]["fy"]
            if q_ab != f_ab:
                n_flip += 1
    print("\n3. PAIRWISE COMPARISON FLIPS")
    print(f"   'A more expensive than B' flips: {n_flip}/{n_pairs} "
          f"= {n_flip/n_pairs:.1%}")

    # D4: does D_G predict the flip? (screener value)
    # A symbol whose EPS jumps a lot is more likely to change rank.
    jumps = {s: abs(eps[s]["fy"] - eps[s]["quarter"]) /
             max(abs(eps[s]["fy"]), abs(eps[s]["quarter"]), 1e-9)
             for s in syms}
    rank_delta = {s: abs(rf[s] - rq[s]) for s in syms}
    # correlation between jump and rank change
    import statistics
    xs = [jumps[s] for s in syms]
    ys = [rank_delta[s] for s in syms]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(len(xs)))
    varx = sum((x-mx)**2 for x in xs)
    vary = sum((y-my)**2 for y in ys)
    corr = cov/(varx**0.5*vary**0.5) if varx*vary else 0
    print("\n4. SCREENER VALUE (does D_G predict rank change?)")
    print(f"   corr(EPS jump, rank change) = {corr:+.2f}")

    # verdict
    print("\n5. VERDICT (variant A)")
    d1 = n_changed / len(syms) >= 0.3
    d2 = overlap < 3  # top-3 set is not identical
    d3 = n_flip / n_pairs >= 0.05
    d4 = corr > 0.3
    print(f"   D1 many ranks change ({n_changed}/{len(syms)} >= 30%): "
          f"{'PASS' if d1 else 'FAIL'}")
    print(f"   D2 top-3 selection flips (overlap {overlap}/3 < 3): "
          f"{'PASS' if d2 else 'FAIL'}")
    print(f"   D3 pairwise comparisons flip ({n_flip/n_pairs:.1%} >= 5%): "
          f"{'PASS' if d3 else 'FAIL'}")
    print(f"   D4 D_G predicts flip (corr {corr:+.2f} > 0.3): "
          f"{'PASS' if d4 else 'FAIL'}")
    print(f"\n   D1-D3 PASS -> discrete error flips real decisions.")
    print(f"   D4 PASS -> the screener (D_G) predicts which decisions flip.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    decision_flip(load(a.inp))


if __name__ == "__main__":
    main()
