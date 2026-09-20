"""
Stage-2n probe: expand the tau hypothesis from 4 fields to all available fields.

The Stage-2m probe (verify_tau.py) found corr(tau, flip_rate) = -0.98 across
4 fundamentals fields. n=4 is too small to distinguish a real mechanism from a
coincidence. This probe expands to every field the findata API exposes with
both quarter and fy data (21 fields across 3 endpoints).

Hypothesis (unchanged): a discrete substitution flips a decision iff it
reshuffles the RELATIVE ranking. High Kendall tau between quarter and fy ->
low decision-flip rate.

Prediction, written down BEFORE looking at the expanded data:
  H1  corr(tau, flip_rate) across all fields stays < -0.5
  H2  it survives within the fundamentals endpoint alone (removes the
      possibility that the relation is just an endpoint artifact)
  H3  it survives Spearman (removes the possibility that it is driven by
      two clusters at the extremes of the tau axis)

If H1 holds but H2/H3 fail, the -0.98 was a between-cluster artifact, not a
within-field mechanism, and the paper must say so.

Usage:
    python tau_expand.py --collect --out tau_expand.jsonl
    python tau_expand.py --analyze tau_expand.jsonl
"""

import argparse
import json
import statistics
import urllib.request
from collections import defaultdict

BASE = "https://lum.id/findata"

# endpoint -> fields that carry both quarter and fy values
ENDPOINTS = {
    "fundamentals": ["revenue", "gross_profit", "operating_income",
                     "ebitda", "net_income", "eps"],
    "enterprise-value": ["enterprise_value", "market_cap", "total_debt",
                         "cash_and_short_term"],
    "key-metrics": ["pe", "pb", "ps", "ev_ebitda", "ev_revenue",
                    "debt_to_equity", "current_ratio", "quick_ratio",
                    "roe", "roa", "fcf_yield"],
}

# flow fields accumulate over the period (a fy value spans 4 quarters);
# stock fields are point-in-time snapshots. The hypothesis does not depend on
# this split, but it is the obvious confounder, so we tag it and check within
# each group.
FLOW = {"revenue", "gross_profit", "operating_income", "ebitda",
        "net_income", "eps", "roe", "roa", "fcf_yield"}

SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "ORCL", "CRM",
           "TSLA", "AVGO", "AMD", "INTC", "QCOM", "TXN", "IBM", "CSCO",
           "ADBE", "NFLX", "PYPL", "MU"]


def fd(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=45) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:100]}


def first(d):
    if isinstance(d, list) and d:
        return d[0]
    if isinstance(d, dict) and "error" not in d:
        return d
    return None


def path_for(endpoint, sym, period):
    if endpoint == "fundamentals":
        return f"/fundamentals/{sym}/history?period={period}&limit=1"
    return f"/{endpoint}/{sym}?period={period}&limit=1"


def collect(out_path):
    rows = []
    for sym in SYMBOLS:
        got = 0
        for endpoint, fields in ENDPOINTS.items():
            dq = first(fd(path_for(endpoint, sym, "quarter")))
            df = first(fd(path_for(endpoint, sym, "fy")))
            if dq is None or df is None:
                continue
            for field in fields:
                v1, v2 = dq.get(field), df.get(field)
                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    rows.append(dict(symbol=sym, endpoint=endpoint,
                                     field=field, quarter=v1, fy=v2))
                    got += 1
        print(f"  {sym}: {got} field observations")
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


# ---------------------------------------------------------------- statistics

def kendall_tau(x, y):
    """Kendall tau between two dicts symbol->value over their shared keys."""
    syms = list(x.keys())
    n = len(syms)
    concord = discord = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = syms[i], syms[j]
            d = (x[a] - x[b]) * (y[a] - y[b])
            if d > 0:
                concord += 1
            elif d < 0:
                discord += 1
    total = concord + discord
    return (concord - discord) / total if total else 0.0


def pearson(xs, ys):
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / (vx ** 0.5 * vy ** 0.5) if vx * vy else 0.0


def ranks(vals):
    """Average ranks, ties shared."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


def topk(syms, keyfn, k=3, reverse=True):
    return set(sorted(syms, key=keyfn, reverse=reverse)[:k])


def jaccard(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def flip_rate(symlist, q, fy):
    """Mean flip rate over 4 decision tasks (same battery as verify_tau.py)."""
    qf, ff = (lambda s: q[s]), (lambda s: fy[s])
    tasks = []
    tasks.append(1 - jaccard(topk(symlist, qf), topk(symlist, ff)))
    tasks.append(1 - jaccard(topk(symlist, qf, reverse=False),
                             topk(symlist, ff, reverse=False)))
    med_q = sorted(qf(s) for s in symlist)[len(symlist) // 2]
    med_f = sorted(ff(s) for s in symlist)[len(symlist) // 2]
    tasks.append(1 - jaccard({s for s in symlist if qf(s) > med_q},
                             {s for s in symlist if ff(s) > med_f}))
    n_pairs = n_flip = 0
    for i in range(len(symlist)):
        for j in range(i + 1, len(symlist)):
            a, b = symlist[i], symlist[j]
            n_pairs += 1
            if (qf(a) > qf(b)) != (ff(a) > ff(b)):
                n_flip += 1
    tasks.append(n_flip / n_pairs if n_pairs else 0.0)
    return sum(tasks) / len(tasks)


def rel_jump(q, fy, symlist):
    """Mean relative output jump — the screener signal D4 showed does NOT
    predict decision flip. Recomputed here on the expanded set."""
    js = []
    for s in symlist:
        scale = max(abs(q[s]), abs(fy[s]), 1e-9)
        js.append(abs(q[s] - fy[s]) / scale)
    return sum(js) / len(js)


# ------------------------------------------------------------------ analysis

def analyze(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    by_field = defaultdict(dict)
    endpoint_of = {}
    for r in rows:
        by_field[r["field"]][r["symbol"]] = (r["quarter"], r["fy"])
        endpoint_of[r["field"]] = r["endpoint"]

    results = []
    for field, syms in sorted(by_field.items()):
        if len(syms) < 15:
            continue
        symlist = list(syms.keys())
        q = {s: syms[s][0] for s in symlist}
        fy = {s: syms[s][1] for s in symlist}
        results.append(dict(
            field=field, endpoint=endpoint_of[field], n=len(symlist),
            kind="flow" if field in FLOW else "stock",
            tau=kendall_tau(q, fy), flip=flip_rate(symlist, q, fy),
            jump=rel_jump(q, fy, symlist)))

    print("=" * 74)
    print("TAU EXPANSION — does rank stability predict decision flip at scale?")
    print("=" * 74)
    print(f"fields: {len(results)}  symbols per field: "
          f"{min(r['n'] for r in results)}-{max(r['n'] for r in results)}\n")
    print(f"  {'field':22s} {'endpoint':17s} {'kind':6s} {'tau':>7s} "
          f"{'flip':>7s} {'jump':>8s}")
    for r in sorted(results, key=lambda r: r["tau"]):
        print(f"  {r['field']:22s} {r['endpoint']:17s} {r['kind']:6s} "
              f"{r['tau']:+7.3f} {r['flip']:6.1%} {r['jump']:8.1%}")

    taus = [r["tau"] for r in results]
    flips = [r["flip"] for r in results]
    jumps = [r["jump"] for r in results]

    print("\n" + "=" * 74)
    print("H1 — main relation across all fields")
    c1 = pearson(taus, flips)
    print(f"  corr(tau, flip_rate)  n={len(results)}  r = {c1:+.3f}   "
          f"{'HOLDS' if c1 < -0.5 else 'WEAK' if c1 < 0 else 'REJECTED'}")
    cj = pearson(jumps, flips)
    print(f"  corr(jump, flip_rate) n={len(results)}  r = {cj:+.3f}   "
          f"(D4 control: output jump should NOT predict flip)")

    print("\nH3 — Spearman robustness (guards against cluster-driven r)")
    s1 = spearman(taus, flips)
    print(f"  spearman(tau, flip_rate) = {s1:+.3f}   "
          f"{'HOLDS' if s1 < -0.5 else 'WEAK' if s1 < 0 else 'REJECTED'}")

    print("\nH2 — within-stratum (guards against endpoint / flow-stock artifact)")
    for label, subset in [
        ("fundamentals", [r for r in results if r["endpoint"] == "fundamentals"]),
        ("enterprise-value", [r for r in results if r["endpoint"] == "enterprise-value"]),
        ("key-metrics", [r for r in results if r["endpoint"] == "key-metrics"]),
        ("flow fields", [r for r in results if r["kind"] == "flow"]),
        ("stock fields", [r for r in results if r["kind"] == "stock"]),
    ]:
        if len(subset) < 3:
            print(f"  {label:18s} n={len(subset)}  (too few to correlate)")
            continue
        r_in = pearson([r["tau"] for r in subset], [r["flip"] for r in subset])
        print(f"  {label:18s} n={len(subset)}  r = {r_in:+.3f}   "
              f"{'HOLDS' if r_in < -0.5 else 'WEAK' if r_in < 0 else 'REJECTED'}")

    print("\nH4 — is tau just a proxy for the output jump?")
    ctj = pearson(taus, jumps)
    print(f"  corr(tau, jump) = {ctj:+.3f}")
    denom = ((1 - ctj ** 2) * (1 - cj ** 2)) ** 0.5
    partial = (c1 - ctj * cj) / denom if denom else 0.0
    print(f"  partial corr(tau, flip | jump) = {partial:+.3f}   "
          f"{'HOLDS' if partial < -0.5 else 'WEAK' if partial < 0 else 'REJECTED'}")
    denom2 = ((1 - ctj ** 2) * (1 - c1 ** 2)) ** 0.5
    partial_j = (cj - ctj * c1) / denom2 if denom2 else 0.0
    print(f"  partial corr(jump, flip | tau) = {partial_j:+.3f}   "
          f"(jump's own contribution once tau is held fixed)")

    print("\nH5 — permutation test (n=12 is small; is r = "
          f"{c1:+.3f} beyond chance?)")
    import random
    random.seed(0)
    n_perm = 20000
    hits = 0
    shuffled = list(flips)
    for _ in range(n_perm):
        random.shuffle(shuffled)
        if pearson(taus, shuffled) <= c1:
            hits += 1
    p = (hits + 1) / (n_perm + 1)
    print(f"  permutations with r <= observed: {hits}/{n_perm}   p = {p:.4f}   "
          f"{'SIGNIFICANT' if p < 0.05 else 'NOT SIGNIFICANT'}")

    print("\n" + "=" * 74)
    print("VERDICT")
    h1 = c1 < -0.5
    h3 = s1 < -0.5
    fund = [r for r in results if r["endpoint"] == "fundamentals"]
    h2 = pearson([r["tau"] for r in fund], [r["flip"] for r in fund]) < -0.5 \
        if len(fund) >= 3 else False
    print(f"  H1 all-field relation     : {'PASS' if h1 else 'FAIL'}")
    print(f"  H2 within fundamentals    : {'PASS' if h2 else 'FAIL'}")
    print(f"  H3 Spearman robustness    : {'PASS' if h3 else 'FAIL'}")
    print(f"  H4 not a jump proxy       : {'PASS' if partial < -0.5 else 'FAIL'}")
    print(f"  H5 permutation p < 0.05   : {'PASS' if p < 0.05 else 'FAIL'}")
    if h1 and h2 and h3:
        print("\n  All PASS -> tau is a field-level mechanism, not an n=4 accident.")
    elif h1 and h3 and not h2:
        print("\n  H2 FAIL -> the relation lives BETWEEN strata, not within one.")
        print("  tau separates field families (flow vs stock) but does not rank")
        print("  fields inside a family. Report as a coarse screener only.")
    elif h1 and not h3:
        print("\n  H3 FAIL -> the Pearson r is driven by clustering at the tau")
        print("  extremes. The -0.98 does not survive a rank-based test.")
    else:
        print("\n  H1 FAIL -> the 4-field result did not replicate at scale.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--out", default="tau_expand.jsonl")
    ap.add_argument("--analyze", metavar="PATH")
    a = ap.parse_args()
    if a.analyze:
        analyze(a.analyze)
    else:
        print(f"collecting {len(SYMBOLS)} symbols x "
              f"{sum(len(v) for v in ENDPOINTS.values())} fields ...")
        rows = collect(a.out)
        print(f"\nwrote {a.out} ({len(rows)} observations)")
        print(f"run: python tau_expand.py --analyze {a.out}")


if __name__ == "__main__":
    main()
