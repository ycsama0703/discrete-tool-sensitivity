"""
Variant-B probe: interface sensitivity audit report (card 3).

Turns the existing mixed_scale.jsonl (420 discrete substitutions, 20 symbols,
4 endpoints, 2 discrete params) into the artifact variant B is about: an
AUTOMATED INTERFACE SENSITIVITY AUDIT — a report that tells a tool developer
"which parameter combinations of your API jump, and by how much".

This is the "interface QA" story: a tool owner runs this over their API's
discrete params and gets a danger list. No LLM, no new data collection —
it reorganizes the 420 substitutions already measured.

Usage:
    python audit_interface_sensitivity.py --in mixed_scale.jsonl
"""

import argparse
import json
from collections import defaultdict

# screening threshold: a substitution is "dangerous" if D_G > this
THRESHOLD = 0.10


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def audit(rows):
    print("=" * 70)
    print("INTERFACE SENSITIVITY AUDIT  (variant B)")
    print("=" * 70)
    print(f"inputs: {len(rows)} discrete substitutions, "
          f"{len(set(r['symbol'] for r in rows))} symbols, "
          f"{len(set(r['endpoint'] for r in rows))} endpoints, "
          f"{len(set(r['param'] for r in rows))} discrete params\n")

    # --- 1. DANGER LIST: per (endpoint, param, from->to) worst-case jump ---
    print("1. DANGER LIST — parameter combinations that jump")
    print("   (D_G = worst-case output jump for this substitution)\n")
    by_sub = defaultdict(list)
    for r in rows:
        key = (r["endpoint"], r["param"], r["from_val"], r["to_val"])
        by_sub[key].append(r["observed_jump"])

    danger = []
    for (ep, param, frm, to), jumps in sorted(by_sub.items()):
        dg = max(jumps)
        n = len(jumps)
        flag = "  <-- DANGEROUS" if dg > THRESHOLD else ""
        danger.append((dg, ep, param, frm, to, n))
        print(f"  {ep:18s} {param:9s} {frm:8s}->{to:8s} D_G={dg:6.1%} (n={n}){flag}")

    n_danger = sum(1 for d in danger if d[0] > THRESHOLD)
    print(f"\n  dangerous combinations: {n_danger}/{len(danger)} "
          f"(D_G > {THRESHOLD:.0%})")

    # --- 2. COVERAGE: how much of the interface was audited ---
    print("\n2. COVERAGE — how much of the interface the audit sees")
    print(f"   endpoints: {len(set(r['endpoint'] for r in rows))} "
          f"(fundamentals/enterprise-value/key-metrics/owner-earnings)")
    print(f"   discrete params: {len(set(r['param'] for r in rows))} "
          f"(period, statement)")
    print(f"   symbols: {len(set(r['symbol'] for r in rows))}")

    # --- 3. STRUCTURAL vs NUMERIC jumps ---
    print("\n3. JUMP TYPE — numeric vs structural")
    numeric = [r for r in rows if r["param"] == "period"]
    structural = [r for r in rows if r["param"] == "statement"]
    if numeric:
        dg_num = max(r["observed_jump"] for r in numeric)
        print(f"   period (numeric jump, e.g. quarter->fy): "
              f"max D_G = {dg_num:.1%}")
    if structural:
        dg_str = max(r["observed_jump"] for r in structural)
        print(f"   statement (structural jump, e.g. income->balance): "
              f"max D_G = {dg_str:.1%}")

    # --- 4. VERDICT for variant B ---
    print("\n4. VERDICT (variant B)")
    v1 = n_danger >= 1  # audit finds at least one dangerous combo
    v2 = n_danger / len(danger) >= 0.5 if danger else False  # most combos jump
    v3 = max(d[0] for d in danger) > 0.5  # at least one big jump
    print(f"   V1 audit finds dangerous combos ({n_danger} >= 1): "
          f"{'PASS' if v1 else 'FAIL'}")
    print(f"   V2 most combos jump ({n_danger}/{len(danger)} >= 50%): "
          f"{'PASS' if v2 else 'FAIL'}")
    print(f"   V3 at least one big jump (>50%): "
          f"{'PASS' if v3 else 'FAIL'}")
    print(f"\n   All PASS -> variant B works: the audit report surfaces")
    print(f"   which parameter combinations of the API are dangerous.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="mixed_scale.jsonl")
    a = ap.parse_args()
    audit(load(a.inp))


if __name__ == "__main__":
    main()
