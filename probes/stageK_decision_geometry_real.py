"""
Stage-K: does decision geometry (rho) predict which real (universe, field)
decisions are period-sensitive -- i.e. where a wrong period flips the top-k?

Stage-2q showed rho = sigma_r / sigma_q predicts flips on synthetic 48 cells
(+0.791 for order decisions). The paper's theory claim is that rho predicts
which REAL decisions are period-sensitive, where the enumeration screener flags.
This probe checks it on the real tau_universe data (4 universes x multiple
fields, quarter vs fy values per symbol).

Why this framing: the screener's job is to flag period-SENSITIVITY (where a
period substitution flips the decision), not realised agent errors (which are
rare and mostly harmless `all`). So the right test is: does rho predict which
(universe, field) decisions are sensitive to a quarter<->fy substitution?

Setup. For each (universe, field), the decision is top-3 symbols by that field's
value. Enumerate the period substitution: recompute top-3 under quarter and
under fy. If they differ, the decision is period-sensitive (screener flags).
The predictor is rho = sigma_r / sigma_q over that universe's symbols.

Pre-registered reading:
  - If rho predicts period-sensitivity (corr(rho, sensitive) clearly positive),
    decision geometry transfers to real decisions and explains WHERE the
    screener flags.
  - If rho does not predict (~0), the decision-geometry theory does not explain
    the screener's flag pattern on real data.

Data: tau_universe.jsonl (4 universes, quarter/fy per symbol per field).

Usage:
    python stageK_decision_geometry_real.py
"""

import json
import math
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = [json.loads(l) for l in open(
    os.path.join(HERE, "tau_universe.jsonl"), encoding="utf-8")]


def top3(vals):
    ok = {s: v for s, v in vals.items() if v is not None}
    return frozenset(sorted(ok, key=lambda s: ok[s], reverse=True)[:3])


def rho_for(vals_q, vals_f):
    """rho = sigma_r / sigma_q over symbols with both values present."""
    logs_r, logs_q = [], []
    for s in vals_q:
        q, f = vals_q[s], vals_f[s]
        if q and f and q > 0 and f > 0:
            logs_r.append(math.log(f / q))
            logs_q.append(math.log(q))
    if len(logs_r) < 4:
        return None
    mu_r = sum(logs_r) / len(logs_r)
    mu_q = sum(logs_q) / len(logs_q)
    var_r = sum((x - mu_r) ** 2 for x in logs_r) / len(logs_r)
    var_q = sum((x - mu_q) ** 2 for x in logs_q) / len(logs_q)
    if var_q == 0:
        return None
    return math.sqrt(var_r) / math.sqrt(var_q)


def main():
    # group by (universe, field)
    cells = defaultdict(lambda: defaultdict(dict))
    for r in DATA:
        cells[(r["universe"], r["field"])][r["symbol"]] = {
            "quarter": r["quarter"], "fy": r["fy"]}

    rows = []
    for (uni, field), syms in sorted(cells.items()):
        vals_q = {s: v["quarter"] for s, v in syms.items()}
        vals_f = {s: v["fy"] for s, v in syms.items()}
        d_q = top3(vals_q)
        d_f = top3(vals_f)
        sensitive = d_q != d_f
        rho = rho_for(vals_q, vals_f)
        if rho is not None:
            rows.append(dict(universe=uni, field=field, rho=rho,
                             sensitive=sensitive))

    n = len(rows)
    n_sens = sum(1 for r in rows if r["sensitive"])
    print(f"(universe, field) decisions: {n}, period-sensitive: {n_sens}/{n} = {n_sens/n:.0%}")
    print()

    rho = [r["rho"] for r in rows]
    sens = [1 if r["sensitive"] else 0 for r in rows]
    mx = sum(rho) / len(rho)
    my = sum(sens) / len(sens)
    num = sum((a - mx) * (b - my) for a, b in zip(rho, sens))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rho))
    dy = math.sqrt(sum((b - my) ** 2 for b in sens))
    corr = num / (dx * dy) if dx * dy else float("nan")

    rho_s = [r["rho"] for r in rows if r["sensitive"]]
    rho_n = [r["rho"] for r in rows if not r["sensitive"]]
    ms = sum(rho_s) / len(rho_s) if rho_s else float("nan")
    mn = sum(rho_n) / len(rho_n) if rho_n else float("nan")

    print(f"corr(rho, period-sensitive) = {corr:+.3f}  (n={n})")
    print(f"mean rho (sensitive)   = {ms:.3f}  (n={len(rho_s)})")
    print(f"mean rho (not sens)    = {mn:.3f}  (n={len(rho_n)})")
    print()

    # per-universe breakdown
    print(f"{'universe':>14} {'cells':>5} {'sens':>5} {'corr':>7} {'rho_s':>7} {'rho_n':>7}")
    print("-" * 55)
    for uni in sorted(set(r["universe"] for r in rows)):
        sub = [r for r in rows if r["universe"] == uni]
        ss = sum(1 for r in sub if r["sensitive"])
        rs = [r["rho"] for r in sub]
        ss_ = [1 if r["sensitive"] else 0 for r in sub]
        mxs = sum(rs) / len(rs)
        mys = sum(ss_) / len(ss_)
        num = sum((a - mxs) * (b - mys) for a, b in zip(rs, ss_))
        dx = math.sqrt(sum((a - mxs) ** 2 for a in rs))
        dy = math.sqrt(sum((b - mys) ** 2 for b in ss_))
        c = num / (dx * dy) if dx * dy else float("nan")
        rho_s_ = [r["rho"] for r in sub if r["sensitive"]]
        rho_n_ = [r["rho"] for r in sub if not r["sensitive"]]
        ms_ = sum(rho_s_) / len(rho_s_) if rho_s_ else float("nan")
        mn_ = sum(rho_n_) / len(rho_n_) if rho_n_ else float("nan")
        print(f"{uni:>14} {len(sub):5} {ss:5} {c:7.3f} {ms_:7.3f} {mn_:7.3f}")

    print("\nReading: if corr(rho, sensitive) is clearly positive, decision geometry")
    print("explains WHERE the screener flags on real data. If ~0, it does not.")


if __name__ == "__main__":
    main()
