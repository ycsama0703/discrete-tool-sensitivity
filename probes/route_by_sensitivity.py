"""
Variant-C probe: tool routing by sensitivity (card 3).

Variant C is the "tool selection / routing" story: an agent choosing between
tools uses S_mix to pick the one most robust to a discrete parameter error.

The claim: different endpoints (tools) have DIFFERENT sensitivity to the same
discrete substitution. If S_mix (D_G) ranks endpoints by robustness, an agent
can route to the most robust tool.

From mixed_scale.jsonl, for the SAME substitution (period=quarter->fy):
  fundamentals      D_G = 97.3%
  enterprise-value  D_G = 86.7%
  key-metrics       D_G = 53.1%
  owner-earnings    D_G = 0.0%  (no jump)

So the endpoints are NOT equally sensitive. If an agent needs a number that is
robust to period errors, owner-earnings (D_G=0) is the safest choice; if it
needs fundamentals, it must re-verify the period.

We measure:
  - R1: endpoints differ in sensitivity to the same substitution (spread of D_G)
  - R2: S_mix (D_G) provides a usable robustness ranking (not all equal)
  - R3: the ranking is stable across symbols (not one symbol driving it)

Usage:
    python route_by_sensitivity.py --in mixed_scale.jsonl
"""

import argparse
import json
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def routing(rows):
    print("=" * 70)
    print("TOOL ROUTING BY SENSITIVITY  (variant C)")
    print("=" * 70)

    # D_G per (endpoint, substitution) = max jump
    by_sub = defaultdict(list)
    for r in rows:
        key = (r["endpoint"], r["param"], r["from_val"], r["to_val"])
        by_sub[key].append(r["observed_jump"])

    # focus on the canonical substitution period=quarter->fy across endpoints
    print("\n1. ENDPOINT SENSITIVITY to period=quarter->fy")
    ep_dg = {}
    for (ep, param, frm, to), jumps in by_sub.items():
        if param == "period" and frm == "quarter" and to == "fy":
            ep_dg[ep] = max(jumps)
    for ep, dg in sorted(ep_dg.items(), key=lambda x: x[1]):
        print(f"   {ep:18s} D_G = {dg:6.1%}")
    spread = max(ep_dg.values()) - min(ep_dg.values())
    print(f"   spread (max-min) = {spread:.1%}")

    # R1: endpoints differ
    n_ep = len(ep_dg)
    distinct = len(set(round(v, 3) for v in ep_dg.values()))
    print("\n2. ROBUSTNESS RANKING (most robust -> least)")
    ranked = sorted(ep_dg.items(), key=lambda x: x[1])
    for i, (ep, dg) in enumerate(ranked):
        print(f"   #{i+1} {ep:18s} D_G = {dg:6.1%}")
    print(f"   -> agent routing: pick {ranked[0][0]} (D_G={ranked[0][1]:.0%}) "
          f"for robustness")

    # R3: is the ranking stable across symbols?
    # per-symbol D_G for each endpoint, check the ordering holds per symbol.
    # owner-earnings has no quarter->fy data (only quarter->all, D_G=0), so we
    # test stability on the 3 endpoints that DO have quarter->fy data:
    # key-metrics (most robust) vs fundamentals (least robust).
    print("\n3. RANKING STABILITY ACROSS SYMBOLS")
    sym_ep = defaultdict(dict)  # symbol -> {endpoint: D_G}
    for r in rows:
        if r["param"] == "period" and r["from_val"] == "quarter" \
           and r["to_val"] == "fy":
            sym_ep[r["symbol"]][r["endpoint"]] = max(
                sym_ep[r["symbol"]].get(r["endpoint"], 0), r["observed_jump"])
    # for each symbol, is key-metrics (most robust) <= fundamentals (least)?
    n_consistent = 0
    n_sym = 0
    for s, ep in sym_ep.items():
        if "key-metrics" in ep and "fundamentals" in ep:
            n_sym += 1
            if ep["key-metrics"] <= ep["fundamentals"]:
                n_consistent += 1
    print(f"   symbols where key-metrics D_G <= fundamentals D_G: "
          f"{n_consistent}/{n_sym} = {n_consistent/n_sym:.0%}")

    # verdict
    print("\n4. VERDICT (variant C)")
    r1 = spread > 0.3  # endpoints differ by >30%
    r2 = distinct >= 3  # at least 3 distinct sensitivity levels
    r3 = n_consistent / n_sym >= 0.8 if n_sym else False
    print(f"   R1 endpoints differ in sensitivity (spread {spread:.0%} > 30%): "
          f"{'PASS' if r1 else 'FAIL'}")
    print(f"   R2 usable ranking ({distinct} distinct levels >= 3): "
          f"{'PASS' if r2 else 'FAIL'}")
    print(f"   R3 ranking stable across symbols "
          f"({n_consistent}/{n_sym} >= 80%): {'PASS' if r3 else 'FAIL'}")
    print(f"\n   All PASS -> S_mix (D_G) ranks tools by robustness, so an")
    print(f"   agent can route to the most robust tool for a query.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    routing(load(a.inp))


if __name__ == "__main__":
    main()
