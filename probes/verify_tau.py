"""
Verify the tau hypothesis: does rank-correlation between periods predict
decision-flip?

Hypothesis (from multi_decision probe): a discrete substitution flips a
decision iff it reshuffles the RELATIVE ranking. If the ranking is preserved
(high Kendall tau between quarter and fy), decisions don't flip even with large
jumps; if the ranking reshuffles (low tau), decisions flip.

Test on fundamentals fields (eps, revenue, net_income, operating_income), 20
symbols, quarter vs fy:
  - tau = Kendall rank correlation between quarter and fy values
  - flip rate = fraction of decision tasks that flip (top-3 exp/cheap, median,
    pairwise)
  - predict: tau and flip rate are NEGATIVELY correlated across fields

We also test the stronger claim: tau predicts flip at the SYMBOL level (a
symbol whose rank is unstable across periods is more likely to be in a flipped
decision), and at the PAIR level (a pair whose relative order flips has low
local tau).

Usage:
    python verify_tau.py --in mixed_scale.jsonl
"""

import argparse
import json
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def vals_by_field(rows):
    out = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period":
            out[r["field"]][r["symbol"]][r["from_val"]] = r["v1"]
            out[r["field"]][r["symbol"]][r["to_val"]] = r["v2"]
    clean = {}
    for f, syms in out.items():
        both = {s: v for s, v in syms.items()
                if "quarter" in v and "fy" in v}
        if len(both) >= 15:
            clean[f] = both
    return clean


def kendall_tau(x, y):
    """Kendall tau between two dicts symbol->value (same keys)."""
    syms = list(x.keys())
    n = len(syms)
    concord = discord = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = syms[i], syms[j]
            dx = (x[a] - x[b]) * (y[a] - y[b])
            if dx > 0:
                concord += 1
            elif dx < 0:
                discord += 1
    total = concord + discord
    if total == 0:
        return 0.0
    return (concord - discord) / total


def topk(syms, keyfn, k=3, reverse=True):
    return set(sorted(syms, key=keyfn, reverse=reverse)[:k])


def jaccard(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def field_flip_rate(syms, q, fy):
    """Fraction of decision tasks that flip for this field.
    q, fy are dicts symbol->value."""
    symlist = list(syms.keys())
    qf = lambda s: q[s]
    fyf = lambda s: fy[s]
    tasks = []
    # top-3 expensive
    tasks.append(1 - jaccard(topk(symlist, qf), topk(symlist, fyf)))
    # top-3 cheapest
    tasks.append(1 - jaccard(topk(symlist, qf, reverse=False),
                             topk(symlist, fyf, reverse=False)))
    # median
    med_q = sorted(qf(s) for s in symlist)[len(symlist)//2]
    med_f = sorted(fyf(s) for s in symlist)[len(symlist)//2]
    tasks.append(1 - jaccard({s for s in symlist if qf(s) > med_q},
                             {s for s in symlist if fyf(s) > med_f}))
    # pairwise
    n_pairs = n_flip = 0
    for i in range(len(symlist)):
        for j in range(i + 1, len(symlist)):
            a, b = symlist[i], symlist[j]
            n_pairs += 1
            if (qf(a) > qf(b)) != (fyf(a) > fyf(b)):
                n_flip += 1
    tasks.append(n_flip / n_pairs)
    return sum(tasks) / len(tasks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    fields = vals_by_field(load(a.inp))

    print("=" * 70)
    print("VERIFY TAU HYPOTHESIS: does rank-correlation predict decision-flip?")
    print("=" * 70)
    print("prediction: high tau (ranking preserved) -> low flip rate\n")

    rows = []
    for f, syms in fields.items():
        symlist = list(syms.keys())
        q = {s: syms[s]["quarter"] for s in symlist}
        fy = {s: syms[s]["fy"] for s in symlist}
        tau = kendall_tau(q, fy)
        flip = field_flip_rate(syms, q, fy)
        rows.append((f, tau, flip))
        print(f"  {f:18s} tau={tau:+.3f}  flip_rate={flip:.1%}")

    # correlation between tau and flip rate across fields
    import statistics
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(len(xs)))
    varx = sum((x-mx)**2 for x in xs)
    vary = sum((y-my)**2 for y in ys)
    corr = cov/(varx**0.5*vary**0.5) if varx*vary else 0

    print("\n" + "=" * 70)
    print(f"corr(tau, flip_rate) across fields = {corr:+.3f}")
    print(f"prediction (negative corr): "
          f"{'CONFIRMED' if corr < -0.5 else 'WEAK' if corr < 0 else 'REJECTED'}")

    # symbol-level: does a symbol's rank instability predict being in a flipped
    # decision? (rank delta between periods)
    print("\n--- symbol-level: rank instability vs decision membership ---")
    all_rank_delta = []
    all_flip_member = []
    for f, syms in fields.items():
        symlist = list(syms.keys())
        rq = {s: i+1 for i, s in enumerate(sorted(symlist,
              key=lambda s: syms[s]["quarter"], reverse=True))}
        rf = {s: i+1 for i, s in enumerate(sorted(symlist,
              key=lambda s: syms[s]["fy"], reverse=True))}
        top3q = topk(symlist, lambda s: syms[s]["quarter"])
        top3f = topk(symlist, lambda s: syms[s]["fy"])
        for s in symlist:
            all_rank_delta.append(abs(rf[s] - rq[s]))
            # is this symbol in a flipped top-3? (in one but not the other)
            all_flip_member.append(int((s in top3q) != (s in top3f)))
    # correlation between rank delta and flip membership
    xs = all_rank_delta
    ys = all_flip_member
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(len(xs)))
    varx = sum((x-mx)**2 for x in xs)
    vary = sum((y-my)**2 for y in ys)
    corr2 = cov/(varx**0.5*vary**0.5) if varx*vary else 0
    print(f"corr(rank_delta, in_flipped_top3) = {corr2:+.3f} "
          f"({'CONFIRMED' if corr2 > 0.3 else 'WEAK'})")


if __name__ == "__main__":
    main()
