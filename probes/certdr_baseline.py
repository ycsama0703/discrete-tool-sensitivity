"""
Stage-2r probe: prior ranking certificates under a COMMON-MODE perturbation.

CertDR (Wu et al., CIKM 2022, arXiv:2209.06691) certifies top-K robustness of
neural rankers under word substitution. Read from its method section:

  Def 3.1  S_d := {d' : ||d'-d||_0/||d|| <= delta}   -- indexed by a SINGLE
           document, built only from that document's own words' synonym sets.
  Def 3.2  "for all d in L_q[K+1:], and any d' in S_d"  -- each document
           separately, a universal quantifier over documents.
  Thm 4.1  applied to each document INDEPENDENTLY; o_d is a per-document
           quantity.
  Prop 4.2 DeltaL_q = f(d_K) - f(d_{K+1}) - max_d o_d > 0  =>  certified.

So the aggregation is union-bound style: every candidate is allowed to move by
its own budget, independently and in the worst direction.

Our perturbation is not like that. One discrete parameter substitution
(period=quarter -> fy) moves EVERY item at once, and the movements are highly
correlated: writing r_s = f_s/q_s, the common factor exp(mean(log r)) is
shared by all items and cancels in any comparison. Only the residual
dispersion can reorder anything.

The question this probe asks is therefore not "is CertDR loose?" but "does its
perturbation model match ours at all?", and the answer is falsifiable.

PREDICTIONS (written before running)
  B1 vacuous    -- a CertDR-style union bound certifies < 20% of cells, even
                   when handed the EXACT per-item deviation rather than an
                   upper bound (the most generous possible instantiation).
  B2 not severity -- the actual top-K flip rate is much lower than the union
                   bound's failure rate. The bound fails because the model is
                   wrong, not because the phenomenon is severe.
  B3 quotient helps -- factoring out the common mode (which is exactly
                   order-preserving, hence sound) certifies substantially more
                   cells than the union bound.
  B4 SOUND      -- the common-mode-quotient certificate must never certify a
                   cell whose top-K actually changed. Zero false certificates.
                   If B4 fails the whole construction is wrong and must be
                   reported as such.

B4 is the one that can kill this. B1 passing on its own proves nothing; a
vacuous bound plus an unsound replacement is worse than no result.

Usage:
    python certdr_baseline.py
"""

import json
import math
import statistics
from collections import defaultdict

from tau_expand import topk
from tau_universe import UNIVERSES

SRC = "tau_universe.jsonl"
K = 3


def cells():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    g = defaultdict(dict)
    for r in rows:
        g[(r["universe"], r["field"])][r["symbol"]] = (r["quarter"], r["fy"])
    out = []
    for (uni, field), syms in sorted(g.items()):
        pos = [s for s, (a, b) in syms.items() if a > 0 and b > 0]
        if len(pos) < 12:
            continue
        out.append((uni, field, pos,
                    {s: syms[s][0] for s in pos},
                    {s: syms[s][1] for s in pos}))
    return out


def analyze():
    print("=" * 78)
    print("CertDR-STYLE CERTIFICATE UNDER A COMMON-MODE PERTURBATION")
    print("=" * 78)
    print(f"instantiation: scores normalised to [0,1] by max(q); top-K, K={K};")
    print("per-item budget o_s = EXACT |f_s - q_s| (most generous to the bound)\n")

    res = []
    for uni, field, pos, q, fy in cells():
        scale = max(q.values())
        nq = {s: q[s] / scale for s in pos}
        nf = {s: fy[s] / scale for s in pos}

        ranked = sorted(pos, key=lambda s: nq[s], reverse=True)
        top, below = ranked[:K], ranked[K:]
        gap = nq[ranked[K - 1]] - nq[ranked[K]]          # f(d_K) - f(d_{K+1})

        # per-item deviations, exact (the most generous instantiation)
        o = {s: abs(nf[s] - nq[s]) for s in pos}

        # common-mode quotient: f_s = g * q_s * (r_s/g) with
        # g = exp(mean log r). Scaling every item by the constant g cannot
        # change any pairwise order, so certifying the quotient perturbation
        # q_s -> q_s * (r_s/g) certifies the real one.
        gmean = math.exp(statistics.mean(math.log(fy[s] / q[s]) for s in pos))
        oq = {s: abs(nq[s] * (fy[s] / q[s]) / gmean - nq[s]) for s in pos}

        # (a) CertDR's criterion as literally stated. Its threat model exempts
        # the incumbents ("documents already ranked 1..K are excluded from
        # attack"), so only below-K items are charged a budget.
        cert_literal = gap - max(o[s] for s in below) > 0

        # (b) the same union bound repaired for a perturbation that also moves
        # the incumbents: every top-K item may fall, every other may rise.
        cert_union = (min(nq[s] - o[s] for s in top)
                      - max(nq[s] + o[s] for s in below)) > 0

        # (c) the repaired bound on the quotient perturbation
        cert_quot = (min(nq[s] - oq[s] for s in top)
                     - max(nq[s] + oq[s] for s in below)) > 0

        flipped = topk(pos, lambda s: nq[s], k=K) != topk(pos, lambda s: nf[s], k=K)

        res.append(dict(uni=uni, field=field, gap=gap,
                        o_union=max(o[s] for s in pos),
                        o_quot=max(oq[s] for s in pos),
                        cert_literal=cert_literal, cert_union=cert_union,
                        cert_quot=cert_quot, flipped=flipped))

    print(f"  {'universe':15s} {'field':20s} {'gap':>7s} {'o_uni':>7s} "
          f"{'o_quot':>7s} {'lit':>4s} {'uni':>4s} {'quot':>5s} {'flip':>5s}")
    for c in res:
        print(f"  {c['uni']:15s} {c['field']:20s} {c['gap']:7.4f} "
              f"{c['o_union']:7.4f} {c['o_quot']:7.4f} "
              f"{'Y' if c['cert_literal'] else '-':>4s} "
              f"{'Y' if c['cert_union'] else '-':>4s} "
              f"{'Y' if c['cert_quot'] else '-':>5s} "
              f"{'FLIP' if c['flipped'] else '-':>5s}")

    n = len(res)
    n_lit = sum(c["cert_literal"] for c in res)
    n_union = sum(c["cert_union"] for c in res)
    n_quot = sum(c["cert_quot"] for c in res)
    n_flip = sum(c["flipped"] for c in res)
    n_stable = n - n_flip

    print("\n" + "=" * 78)
    print("B0 — is CertDR's criterion even VALID here?")
    bad_lit = [c for c in res if c["cert_literal"] and c["flipped"]]
    print(f"  certified by the literal criterion: {n_lit}/{n}")
    print(f"  of which the top-{K} actually changed: {len(bad_lit)}")
    for c in bad_lit:
        print(f"    !! {c['uni']} {c['field']}")
    print(f"  Its threat model exempts the incumbents ('documents already")
    print(f"  ranked 1..K are excluded from attack'); our substitution moves")
    print(f"  them too, so its GUARANTEE DOES NOT TRANSFER to this setting.")
    if not bad_lit:
        print(f"  Note: no false certificate actually occurred here. The")
        print(f"  assumption is violated in principle, but on this data the")
        print(f"  criterion certifies so little ({n_lit}/{n}) that it was never")
        print(f"  caught out. Report this as an assumption mismatch, NOT as an")
        print(f"  empirical demonstration of unsoundness.")
    print(f"  -> the fair baseline is the repaired symmetric bound below")

    print(f"\nB1 — is the (repaired, sound) union bound vacuous?")
    print(f"  union-bound certified: {n_union}/{n} = {n_union/n:.1%}")
    b1 = n_union / n < 0.20
    print(f"  {'PASS (vacuous)' if b1 else 'FAIL (not vacuous)'}")

    print(f"\nB2 — is that because the phenomenon is severe, or the model wrong?")
    print(f"  cells whose top-{K} ACTUALLY changed: {n_flip}/{n} = {n_flip/n:.1%}")
    print(f"  cells the union bound failed to certify: {n-n_union}/{n} = "
          f"{(n-n_union)/n:.1%}")
    b2 = (n - n_union) / n - n_flip / n > 0.2
    print(f"  gap between them: {((n-n_union)-n_flip)/n:+.1%}   "
          f"{'PASS' if b2 else 'FAIL'}")
    print(f"  ({n_stable} cells are genuinely stable; the union bound proves "
          f"{n_union} of them)")

    print(f"\nB3 — does quotienting out the common mode help?")
    print(f"  quotient certified: {n_quot}/{n} = {n_quot/n:.1%}   "
          f"(union: {n_union/n:.1%})")
    b3 = n_quot > n_union
    print(f"  recovered {n_quot - n_union} additional cells   "
          f"{'PASS' if b3 else 'FAIL'}")
    if n_stable:
        print(f"  coverage of the genuinely-stable cells: "
              f"union {n_union/n_stable:.1%} -> quotient {n_quot/n_stable:.1%}")

    print(f"\nB4 — SOUNDNESS: does the quotient certificate ever certify a "
          f"cell that flipped?")
    unsound = [c for c in res if c["cert_quot"] and c["flipped"]]
    b4 = not unsound
    print(f"  false certificates: {len(unsound)}   "
          f"{'PASS (sound)' if b4 else 'FAIL (UNSOUND)'}")
    for c in unsound:
        print(f"    !! {c['uni']} {c['field']}")

    # how much of the union budget is pure common mode
    ratios = [c["o_quot"] / c["o_union"] for c in res if c["o_union"] > 0]
    print(f"\n  median o_quot/o_union = {statistics.median(ratios):.3f}  "
          f"-> {1-statistics.median(ratios):.0%} of the per-item budget the")
    print(f"  union bound charges is common mode that cannot reorder anything")

    print("\n" + "=" * 78)
    print("VERDICT")
    print(f"  B1 union bound vacuous     : {'PASS' if b1 else 'FAIL'}")
    print(f"  B2 model wrong, not severe : {'PASS' if b2 else 'FAIL'}")
    print(f"  B3 quotient recovers cells : {'PASS' if b3 else 'FAIL'}")
    print(f"  B4 quotient is SOUND       : {'PASS' if b4 else 'FAIL'}")
    if b1 and b2 and b3 and b4:
        print("\n  A union-bound ranking certificate is near-vacuous here, and")
        print("  not because decisions are fragile — most cells are stable and")
        print("  it cannot prove it. It charges every item its full movement")
        print("  independently, while the movement is mostly common mode that")
        print("  cancels in every comparison. Quotienting the common mode out")
        print("  is order-preserving, hence sound, and recovers the cells.")
        print("  Prior ranking certificates are a BASELINE we beat for a")
        print("  structural reason, not a competitor that occupies the idea.")
    elif not b4:
        print("\n  The quotient certificate is UNSOUND. Do not report B1-B3;")
        print("  a vacuous baseline plus a broken replacement is not a result.")


if __name__ == "__main__":
    analyze()
