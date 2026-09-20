"""
Stage-2o probe: does the tau relation survive a change of symbol universe?

Stage-2n (tau_expand.py) established corr(tau, flip) = -0.890 across 12 fields,
but on ONE symbol universe: 20 US large-cap tech names. Two weaknesses follow:
  (a) external validity — the relation may be a property of that sector;
  (b) effective n — the 12 fields are nested accounting aggregates, so n=12
      overstates the independent evidence.

This probe adds three more universes (60 new symbols). That gives 4 x 12 = 48
(universe, field) cells, and lets us test the relation WITHIN universe while
removing universe-level confounds.

Predictions, written down before the new data was analysed:

  P1 replication  — corr(tau, flip) < -0.5 holds INDEPENDENTLY in each of the
                    three new universes.
  P2 mechanism    — tau on flow fields is LOWER in a seasonally heterogeneous
                    universe (CONSUMER: Q4-heavy retail + flat staples + small
                    caps) than in a seasonally homogeneous one (TECH), and its
                    flip rate correspondingly HIGHER.
                    Rationale: fy is the sum of four quarters. If every firm
                    shared one seasonal shape, the quarter ranking would equal
                    the fy ranking and tau would be 1. tau falls only to the
                    extent that firms differ in seasonal shape. So the driver
                    of tau is dispersion in seasonality, and a heterogeneous
                    universe must sit lower.
  P3 same line    — the tau->flip slope is comparable across universes (max /
                    min within a factor of 2), i.e. one mechanism rather than
                    four unrelated negative correlations.
  P4 pooled       — after centering tau and flip within each universe (which
                    removes any universe-level confound), the pooled relation
                    over 48 cells stays < -0.5.

P2 is the one that can fail while P1 still passes. If P1 passes and P2 fails,
tau is a real predictor whose ORIGIN we have misdiagnosed, and the seasonality
story must come out of the paper.

Usage:
    python tau_universe.py --collect
    python tau_universe.py --analyze
"""

import argparse
import json
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from tau_expand import (ENDPOINTS, FLOW, SYMBOLS, fd, first, flip_rate,
                        kendall_tau, path_for, pearson, rel_jump, spearman)

UNIVERSES = {
    # baseline, collected in Stage-2n
    "TECH": SYMBOLS,
    # financials + healthcare + industrials: large caps, low seasonal dispersion
    "FIN_HEALTH": ["JPM", "BAC", "GS", "WFC", "MS", "C", "AXP", "BLK",
                   "JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "TMO", "CVS",
                   "CAT", "BA", "GE", "HON"],
    # energy + staples + industrials: commodity cycles, defensive names
    "ENERGY_STAPLES": ["XOM", "CVX", "COP", "SLB", "PG", "KO", "PEP", "CL",
                       "MO", "UPS", "LMT", "MCD", "SBUX", "NKE", "TGT", "HD",
                       "LOW", "COST", "WMT", "TMO"],
    # Q4-heavy retail + small/mid caps: HIGH seasonal dispersion (P2 target)
    "CONSUMER": ["WMT", "TGT", "COST", "HD", "LOW", "NKE", "SBUX", "MCD",
                 "PG", "KO", "PEP", "CL", "MO",
                 "ETSY", "YETI", "CROX", "DECK", "FIVE", "OLLI", "WING"],
}

OUT = "tau_universe.jsonl"


def collect_symbol(args):
    sym, universe = args
    rows = []
    for endpoint, fields in ENDPOINTS.items():
        dq = first(fd(path_for(endpoint, sym, "quarter")))
        df = first(fd(path_for(endpoint, sym, "fy")))
        if dq is None or df is None:
            continue
        for field in fields:
            v1, v2 = dq.get(field), df.get(field)
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                rows.append(dict(universe=universe, symbol=sym,
                                 endpoint=endpoint, field=field,
                                 quarter=v1, fy=v2))
    return rows


def collect():
    jobs = []
    for uni, syms in UNIVERSES.items():
        if uni == "TECH":
            continue  # reuse Stage-2n collection
        for s in syms:
            jobs.append((s, uni))
    rows = []
    with ThreadPoolExecutor(8) as ex:
        for got in ex.map(collect_symbol, jobs):
            rows.extend(got)
    # fold in the TECH universe already on disk
    for r in (json.loads(l) for l in open("tau_expand.jsonl", encoding="utf-8")):
        r["universe"] = "TECH"
        rows.append(r)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    for uni in UNIVERSES:
        n = len({r["symbol"] for r in rows if r["universe"] == uni})
        m = sum(1 for r in rows if r["universe"] == uni)
        print(f"  {uni:16s} {n} symbols, {m} observations")
    return rows


def ols_slope(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    if not vx:
        return 0.0
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs))) / vx


def cells_for(rows, universe):
    by_field = defaultdict(dict)
    for r in rows:
        if r["universe"] == universe:
            by_field[r["field"]][r["symbol"]] = (r["quarter"], r["fy"])
    out = []
    for field, syms in sorted(by_field.items()):
        if len(syms) < 15:
            continue
        symlist = list(syms.keys())
        q = {s: syms[s][0] for s in symlist}
        fy = {s: syms[s][1] for s in symlist}
        out.append(dict(universe=universe, field=field, n=len(symlist),
                        kind="flow" if field in FLOW else "stock",
                        tau=kendall_tau(q, fy),
                        flip=flip_rate(symlist, q, fy),
                        jump=rel_jump(q, fy, symlist)))
    return out


def analyze():
    rows = [json.loads(l) for l in open(OUT, encoding="utf-8")]
    cells = {u: cells_for(rows, u) for u in UNIVERSES}

    print("=" * 76)
    print("TAU ACROSS SYMBOL UNIVERSES — external validity of the tau relation")
    print("=" * 76)

    print("\nP1 — does the relation replicate inside each universe?")
    print(f"  {'universe':16s} {'fields':>6s} {'corr(tau,flip)':>15s} "
          f"{'slope':>8s} {'mean tau':>9s} {'mean flip':>10s}")
    slopes = {}
    p1 = {}
    for uni in UNIVERSES:
        c = cells[uni]
        taus = [x["tau"] for x in c]
        flips = [x["flip"] for x in c]
        r = pearson(taus, flips)
        sl = ols_slope(taus, flips)
        slopes[uni] = sl
        p1[uni] = r < -0.5
        print(f"  {uni:16s} {len(c):6d} {r:+15.3f} {sl:8.2f} "
              f"{statistics.mean(taus):9.3f} {statistics.mean(flips):9.1%}")
    new_ok = sum(1 for u in UNIVERSES if u != "TECH" and p1[u])
    print(f"  replicated in {new_ok}/3 new universes: "
          f"{'PASS' if new_ok == 3 else 'PARTIAL' if new_ok else 'FAIL'}")

    print("\nP2 — is tau driven by seasonal dispersion? "
          "(flow fields, CONSUMER vs TECH)")
    for uni in ["TECH", "FIN_HEALTH", "ENERGY_STAPLES", "CONSUMER"]:
        fl = [x for x in cells[uni] if x["kind"] == "flow"]
        if not fl:
            continue
        print(f"  {uni:16s} flow: mean tau = "
              f"{statistics.mean(x['tau'] for x in fl):+.3f}   "
              f"mean flip = {statistics.mean(x['flip'] for x in fl):.1%}")
    tech_fl = [x for x in cells["TECH"] if x["kind"] == "flow"]
    cons_fl = [x for x in cells["CONSUMER"] if x["kind"] == "flow"]
    d_tau = statistics.mean(x["tau"] for x in cons_fl) - \
        statistics.mean(x["tau"] for x in tech_fl)
    d_flip = statistics.mean(x["flip"] for x in cons_fl) - \
        statistics.mean(x["flip"] for x in tech_fl)
    p2 = d_tau < 0 and d_flip > 0
    print(f"  CONSUMER - TECH: d(tau) = {d_tau:+.3f} (predicted < 0), "
          f"d(flip) = {d_flip:+.1%} (predicted > 0)")
    print(f"  P2 {'PASS' if p2 else 'FAIL'}"
          + ("" if p2 else "  -> the seasonality explanation of tau is wrong"))

    print("\nP3 — same line, or merely the same sign?")
    sl_vals = [abs(s) for s in slopes.values() if s]
    ratio = max(sl_vals) / min(sl_vals) if sl_vals else 0
    p3 = ratio < 2.0
    print(f"  slopes: " + ", ".join(f"{u}={slopes[u]:.2f}" for u in UNIVERSES))
    print(f"  max/min = {ratio:.2f}x  (< 2 means one mechanism)  "
          f"{'PASS' if p3 else 'FAIL'}")

    print("\nP4 — pooled over 48 cells, centered within universe")
    allc = [x for u in UNIVERSES for x in cells[u]]
    raw_r = pearson([x["tau"] for x in allc], [x["flip"] for x in allc])
    ct, cf = [], []
    for uni in UNIVERSES:
        c = cells[uni]
        mt = statistics.mean(x["tau"] for x in c)
        mf = statistics.mean(x["flip"] for x in c)
        ct += [x["tau"] - mt for x in c]
        cf += [x["flip"] - mf for x in c]
    cen_r = pearson(ct, cf)
    p4 = cen_r < -0.5
    print(f"  raw pooled      n={len(allc)}  r = {raw_r:+.3f}")
    print(f"  within-universe n={len(ct)}  r = {cen_r:+.3f}   "
          f"{'PASS' if p4 else 'FAIL'}")
    print(f"  spearman(centered) = {spearman(ct, cf):+.3f}")

    import random
    random.seed(0)
    hits = 0
    sh = list(cf)
    for _ in range(20000):
        random.shuffle(sh)
        if pearson(ct, sh) <= cen_r:
            hits += 1
    pval = (hits + 1) / 20001
    print(f"  permutation p = {pval:.4f}  "
          f"{'SIGNIFICANT' if pval < 0.05 else 'NOT SIGNIFICANT'}")

    print("\n" + "=" * 76)
    print("VERDICT")
    print(f"  P1 replicates in 3 new universes : "
          f"{'PASS' if new_ok == 3 else f'PARTIAL ({new_ok}/3)'}")
    print(f"  P2 seasonal-dispersion mechanism : {'PASS' if p2 else 'FAIL'}")
    print(f"  P3 same slope across universes   : {'PASS' if p3 else 'FAIL'}")
    print(f"  P4 pooled, universe-controlled   : {'PASS' if p4 else 'FAIL'}")
    if new_ok == 3 and p4:
        print("\n  The relation is not a property of US large-cap tech. With")
        print("  universe held fixed it survives on 48 cells, which answers the")
        print("  'effective n < 12' objection from Stage-2n.")
        if not p2:
            print("  But P2 FAILED: tau predicts flip for a reason other than")
            print("  seasonal dispersion. Drop that explanation from the paper")
            print("  and report tau as an empirical regularity we cannot yet")
            print("  derive from firm fundamentals.")
    else:
        print("\n  Replication is incomplete — tau is at least partly a")
        print("  property of the universe, and the paper must scope it.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    a = ap.parse_args()
    if a.collect:
        collect()
        print(f"\nwrote {OUT}\nrun: python tau_universe.py --analyze")
    else:
        analyze()


if __name__ == "__main__":
    main()
