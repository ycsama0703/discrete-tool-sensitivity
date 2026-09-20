"""
Multi-decision probe: is decision-flip specific to EPS ranking, or general?

Variant A tested ONE decision (rank by EPS, pick top-3 most expensive). This
probe asks: does the decision-flip generalize across MANY decision tasks on the
SAME data? If multiple decisions flip under period=quarter->fy, the phenomenon
is not an artifact of one decision task.

Decision tasks (all on fundamentals, 20 symbols, quarter vs fy):
  D1 rank-by-field, pick top-3 most expensive  (EPS, revenue, net_income, op_income)
  D2 rank-by-field, pick top-3 cheapest
  D3 threshold: "which symbols have field > median?" (set membership)
  D4 growth: "rank by field growth (fy/quarter ratio), pick top-3"
  D5 pairwise: "fraction of 'A > B' comparisons that flip"

For each task we measure the flip rate between quarter and fy. If most tasks
flip substantially, decision-flip is general.

Usage:
    python multi_decision.py --in mixed_scale.jsonl
"""

import argparse
import json
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def vals_by_field(rows):
    """field -> {symbol: {quarter: v, fy: v}} for fundamentals period subs."""
    out = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period":
            out[r["field"]][r["symbol"]][r["from_val"]] = r["v1"]
            out[r["field"]][r["symbol"]][r["to_val"]] = r["v2"]
    # keep fields with >=15 symbols having both
    clean = {}
    for f, syms in out.items():
        both = {s: v for s, v in syms.items()
                if "quarter" in v and "fy" in v}
        if len(both) >= 15:
            clean[f] = both
    return clean


def topk(syms, keyfn, k=3, reverse=True):
    return set(sorted(syms, key=keyfn, reverse=reverse)[:k])


def jaccard(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def run(rows):
    fields = vals_by_field(rows)
    print("=" * 70)
    print("MULTI-DECISION PROBE  (is decision-flip general?)")
    print("=" * 70)
    print(f"fields with quarter+fy data: {sorted(fields)}\n")

    for f, syms in fields.items():
        symlist = list(syms.keys())
        q = lambda s: syms[s]["quarter"]
        fy = lambda s: syms[s]["fy"]

        # D1: top-3 most expensive
        t3q = topk(symlist, q)
        t3f = topk(symlist, fy)
        j1 = jaccard(t3q, t3f)

        # D2: top-3 cheapest
        c3q = topk(symlist, q, reverse=False)
        c3f = topk(symlist, fy, reverse=False)
        j2 = jaccard(c3q, c3f)

        # D3: threshold (above median)
        med_q = sorted(q(s) for s in symlist)[len(symlist)//2]
        med_f = sorted(fy(s) for s in symlist)[len(symlist)//2]
        abq = {s for s in symlist if q(s) > med_q}
        abf = {s for s in symlist if fy(s) > med_f}
        j3 = jaccard(abq, abf)

        # D4: growth ranking (fy/quarter ratio)
        gr_q = {s: fy(s)/q(s) if q(s) else 0 for s in symlist}
        # growth is same in both periods (ratio), so no flip by construction;
        # instead rank by fy value as a second "selection" task
        j4 = jaccard(topk(symlist, fy), topk(symlist, q))

        # D5: pairwise flips
        n_pairs = n_flip = 0
        for i in range(len(symlist)):
            for j in range(i+1, len(symlist)):
                a, b = symlist[i], symlist[j]
                n_pairs += 1
                if (q(a) > q(b)) != (fy(a) > fy(b)):
                    n_flip += 1
        p5 = n_flip / n_pairs if n_pairs else 0

        print(f"--- {f} ---")
        print(f"  D1 top-3 expensive  overlap {j1:.0%} (flip {1-j1:.0%})")
        print(f"  D2 top-3 cheapest   overlap {j2:.0%} (flip {1-j2:.0%})")
        print(f"  D3 above-median     overlap {j3:.0%} (flip {1-j3:.0%})")
        print(f"  D4 top-3 (fy)       overlap {j4:.0%} (flip {1-j4:.0%})")
        print(f"  D5 pairwise flips   {p5:.1%}")
        print()

    # aggregate verdict
    print("=" * 70)
    print("VERDICT: is decision-flip general across tasks?")
    # count tasks with substantial flip (>20% set change or >10% pairwise)
    n_task = 0
    n_flip_task = 0
    for f, syms in fields.items():
        symlist = list(syms.keys())
        q = lambda s: syms[s]["quarter"]
        fy = lambda s: syms[s]["fy"]
        for name, j in [("expensive", jaccard(topk(symlist,q), topk(symlist,fy))),
                        ("cheapest", jaccard(topk(symlist,q,reverse=False), topk(symlist,fy,reverse=False))),
                        ("median", None)]:
            if j is None:
                med_q = sorted(q(s) for s in symlist)[len(symlist)//2]
                med_f = sorted(fy(s) for s in symlist)[len(symlist)//2]
                j = jaccard({s for s in symlist if q(s)>med_q},
                            {s for s in symlist if fy(s)>med_f})
            n_task += 1
            if 1 - j > 0.20:
                n_flip_task += 1
    print(f"  tasks with >20% set flip: {n_flip_task}/{n_task}")
    print(f"  -> decision-flip is {'GENERAL' if n_flip_task/n_task>=0.5 else 'task-specific'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    run(load(a.inp))


if __name__ == "__main__":
    main()
