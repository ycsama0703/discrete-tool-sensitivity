"""
Stage-2q probe: decision geometry — which quantity is the right one depends on
what kind of decision the agent is making.

Stage-2p showed the flip condition for ORDER decisions contains no absolute
magnitude: a pair flips iff |dlog r| > |dlog q|, so the rate is governed by
rho = sigma_r / sigma_q. Taken alone that reads as though D_G (and hence the
mixed bound S_mix) is simply the wrong quantity.

That over-claims. Consider an ABSOLUTE THRESHOLD decision — "is revenue above
$10B?". There, what matters is whether the substitution pushes an item across
a fixed constant, which depends on the COMMON rescaling, not the differential
one. Absolute magnitude is exactly right there, and rho — being scale-free —
should be blind to it.

Decompose log r = mu_r + (deviation), where mu_r = mean(log r) is the common
rescaling every item receives and sigma_r = stdev(log r) is the differential
part. Then:

    ORDER decisions     depend on sigma_r / sigma_q  =: rho
                        (common rescaling cancels in a comparison)
    THRESHOLD decisions depend on |mu_r| / sigma_q   =: kappa
                        (common rescaling is the entire effect; it is what
                         the output jump measures)

So the two quantities are COMPLEMENTARY, not successive corrections, and the
continuous bound is wrong for both (it reports zero for a discrete swap).

PREDICTIONS (written before running)
  C1  corr(rho, order_flip) strong positive AND clearly beats corr(kappa, order_flip)
  C2  corr(kappa, threshold_flip) strong positive AND clearly beats corr(rho, threshold_flip)
  C3  the crossover holds: each predictor wins on its own decision family
  C4  diagnostic — rho and kappa are not collinear (|corr| < 0.7), otherwise
      C1/C2 cannot be separated and the test is uninformative

If C3 fails, the decision-geometry framing is wrong and S_mix stays a weak
link that our own margin result supersedes. Report that outcome.

Usage:
    python decision_geometry.py
"""

import json
import math
import statistics
from collections import defaultdict

from tau_expand import jaccard, pearson, spearman, topk
from tau_universe import UNIVERSES

SRC = "tau_universe.jsonl"


def order_flip(pos, q, fy):
    """Order-family decisions: top-3 expensive, top-3 cheapest, rank-median
    split, pairwise. All are invariant to a common rescaling."""
    qf, ff = (lambda s: q[s]), (lambda s: fy[s])
    tasks = []
    tasks.append(1 - jaccard(topk(pos, qf), topk(pos, ff)))
    tasks.append(1 - jaccard(topk(pos, qf, reverse=False),
                             topk(pos, ff, reverse=False)))
    mq = sorted(qf(s) for s in pos)[len(pos) // 2]
    mf = sorted(ff(s) for s in pos)[len(pos) // 2]
    tasks.append(1 - jaccard({s for s in pos if qf(s) > mq},
                             {s for s in pos if ff(s) > mf}))
    npair = nflip = 0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            a, b = pos[i], pos[j]
            npair += 1
            if (qf(a) > qf(b)) != (ff(a) > ff(b)):
                nflip += 1
    tasks.append(nflip / npair if npair else 0.0)
    return sum(tasks) / len(tasks)


def threshold_flip(pos, q, fy):
    """Absolute-threshold decisions: 'is the value above T?' for fixed
    constants T. The constants are set from the BASE (quarter) distribution
    and then held fixed while the substitution is applied — an agent's rule
    'flag firms above $X' does not move when the tool parameter changes.

    Flip = the item's side of T changes."""
    vals = sorted(q[s] for s in pos)
    rates = []
    for frac in (0.25, 0.50, 0.75):
        T = vals[int(frac * (len(vals) - 1))]
        crossed = sum(1 for s in pos if (q[s] > T) != (fy[s] > T))
        rates.append(crossed / len(pos))
    return sum(rates) / len(rates)


def build():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    grouped = defaultdict(dict)
    for r in rows:
        grouped[(r["universe"], r["field"])][r["symbol"]] = (r["quarter"], r["fy"])

    cells = []
    for (uni, field), syms in sorted(grouped.items()):
        pos = [s for s, (a, b) in syms.items() if a > 0 and b > 0]
        if len(pos) < 12:
            continue
        q = {s: syms[s][0] for s in pos}
        fy = {s: syms[s][1] for s in pos}
        lq = [math.log(q[s]) for s in pos]
        lr = [math.log(fy[s] / q[s]) for s in pos]
        sig_q = statistics.stdev(lq)
        if not sig_q:
            continue
        mu_r = statistics.mean(lr)
        sig_r = statistics.stdev(lr)
        cells.append(dict(
            universe=uni, field=field, n=len(pos),
            mu_r=mu_r, sig_r=sig_r, sig_q=sig_q,
            rho=sig_r / sig_q, kappa=abs(mu_r) / sig_q,
            jump=statistics.mean(abs(fy[s] - q[s]) / max(abs(q[s]), abs(fy[s]), 1e-9)
                                 for s in pos),
            order=order_flip(pos, q, fy),
            thresh=threshold_flip(pos, q, fy)))
    return cells


def main():
    cells = build()
    print("=" * 78)
    print("DECISION GEOMETRY — the right quantity depends on the decision type")
    print("=" * 78)
    print(f"cells: {len(cells)}\n")

    print(f"  {'universe':15s} {'field':20s} {'rho':>6s} {'kappa':>6s} "
          f"{'order':>7s} {'thresh':>7s}")
    for c in sorted(cells, key=lambda c: c["kappa"]):
        print(f"  {c['universe']:15s} {c['field']:20s} {c['rho']:6.2f} "
              f"{c['kappa']:6.2f} {c['order']:6.1%} {c['thresh']:6.1%}")

    rho = [c["rho"] for c in cells]
    kap = [c["kappa"] for c in cells]
    jmp = [c["jump"] for c in cells]
    ordr = [c["order"] for c in cells]
    thr = [c["thresh"] for c in cells]

    print("\n" + "=" * 78)
    print("C4 — diagnostic: are rho and kappa separable?")
    ck = pearson(rho, kap)
    c4 = abs(ck) < 0.7
    print(f"  corr(rho, kappa) = {ck:+.3f}   "
          f"{'PASS (separable)' if c4 else 'FAIL (collinear — test uninformative)'}")

    print("\nTHE CROSSOVER")
    print(f"  {'':22s} {'order decisions':>17s} {'threshold decisions':>21s}")
    r_ro, r_rt = pearson(rho, ordr), pearson(rho, thr)
    r_ko, r_kt = pearson(kap, ordr), pearson(kap, thr)
    r_jo, r_jt = pearson(jmp, ordr), pearson(jmp, thr)
    print(f"  {'rho   = sig_r/sig_q':22s} {r_ro:+17.3f} {r_rt:+21.3f}")
    print(f"  {'kappa = |mu_r|/sig_q':22s} {r_ko:+17.3f} {r_kt:+21.3f}")
    print(f"  {'jump  (output magn.)':22s} {r_jo:+17.3f} {r_jt:+21.3f}")
    print(f"\n  spearman check      rho: order {spearman(rho, ordr):+.3f} / "
          f"thresh {spearman(rho, thr):+.3f}")
    print(f"                    kappa: order {spearman(kap, ordr):+.3f} / "
          f"thresh {spearman(kap, thr):+.3f}")

    print("\nC1 — rho owns order decisions")
    c1 = r_ro > 0.5 and abs(r_ro) > abs(r_ko)
    print(f"  corr(rho, order) = {r_ro:+.3f} vs corr(kappa, order) = "
          f"{r_ko:+.3f}   {'PASS' if c1 else 'FAIL'}")

    print("\nC2 — kappa owns threshold decisions")
    c2 = r_kt > 0.5 and abs(r_kt) > abs(r_rt)
    print(f"  corr(kappa, thresh) = {r_kt:+.3f} vs corr(rho, thresh) = "
          f"{r_rt:+.3f}   {'PASS' if c2 else 'FAIL'}")

    print("\nC3 — crossover: each predictor wins on its own family")
    c3 = c1 and c2
    print(f"  {'PASS' if c3 else 'FAIL'}")

    # within-universe centering, to make sure the crossover is not a
    # universe-level artifact
    print("\nrobustness — within-universe centered")
    cr, ck2, co, ct = [], [], [], []
    for uni in UNIVERSES:
        sub = [c for c in cells if c["universe"] == uni]
        if len(sub) < 3:
            continue
        for key, acc in (("rho", cr), ("kappa", ck2),
                         ("order", co), ("thresh", ct)):
            m = statistics.mean(c[key] for c in sub)
            acc.extend(c[key] - m for c in sub)
    print(f"  corr(rho, order)    = {pearson(cr, co):+.3f}   "
          f"corr(rho, thresh)  = {pearson(cr, ct):+.3f}")
    print(f"  corr(kappa, thresh) = {pearson(ck2, ct):+.3f}   "
          f"corr(kappa, order) = {pearson(ck2, co):+.3f}")

    print("\n" + "=" * 78)
    print("VERDICT")
    print(f"  C4 rho/kappa separable : {'PASS' if c4 else 'FAIL'}")
    print(f"  C1 rho -> order        : {'PASS' if c1 else 'FAIL'}")
    print(f"  C2 kappa -> threshold  : {'PASS' if c2 else 'FAIL'}")
    print(f"  C3 crossover           : {'PASS' if c3 else 'FAIL'}")
    if c3 and c4:
        print("\n  The two quantities are complementary, not successive")
        print("  corrections. S_mix / D_G is the RIGHT bound for absolute-")
        print("  threshold decisions; rho is the right one for order decisions.")
        print("  The continuous bound is wrong for both, because a discrete")
        print("  swap has eps = 0 and it reports zero for either family.")
        print("  The paper keeps both legs, split by decision geometry.")
    else:
        print("\n  Crossover not established. Do NOT claim decision geometry.")
        print("  S_mix remains the weak link superseded by the margin result,")
        print("  and the paper should lead with rho alone.")


if __name__ == "__main__":
    main()
