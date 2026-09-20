"""
Stage-2p probe: the margin model — why tau predicts decision flip.

Stage-2o killed the seasonality explanation of tau (P2 failed, and in the
opposite direction: the CONSUMER universe has HIGHER tau than TECH). Looking
at that universe suggests the real driver: it spans WMT (~$680B revenue) to
WING (~$600M), a spread of three orders of magnitude. When items are that far
apart, no substitution can reorder them.

That suggests a margin condition, which is derivable rather than correlational.

DERIVATION
Let q_s be the value under the base parameter and f_s under the discrete
neighbour, and let r_s = f_s / q_s be the per-item rescaling the substitution
induces. For an ordered pair (a, b) with q_a > q_b:

    f_a > f_b  <=>  r_a q_a > r_b q_b
               <=>  log r_a - log r_b > -(log q_a - log q_b)

Writing U = dlog q (item separation) and V = dlog r (differential rescaling),
the pair FLIPS iff |V| > |U| with opposite sign. So a decision flips exactly
when the substitution's differential rescaling exceeds the decision margin.
Absolute jump size never enters — only its dispersion relative to separation.

If U ~ N(0, 2 sigma_q^2) and V ~ N(0, 2 sigma_r^2) independent, then
P(|V| > |U|) = (2/pi) arctan(sigma_r / sigma_q), so with rho = sigma_r/sigma_q:

    pairwise flip rate = (1/pi) arctan(rho)
    kendall tau        = 1 - (2/pi) arctan(rho)

tau and flip are two projections of the SAME quantity rho. That is why tau
predicts flip at r = -0.89: not an empirical accident, an identity plus noise.

PREDICTIONS (written before running)
  M1 identity   — tau = 1 - 2 * pairwise_flip holds to within 0.02.
                  This is near-definitional and only checks the pipeline; if it
                  fails, something is wrong with the code, not the theory.
  M2 closed form— predicted flip (1/pi)arctan(rho) matches observed pairwise
                  flip, MAE < 0.05 over the 48 cells. This is the real test:
                  it can fail if log-ratios are heavy-tailed or correlated
                  with size.
  M3 rho beats jump — corr(rho, flip) is strongly POSITIVE and beats
                  corr(jump, flip) by a wide margin.
  M4 explains the universe effect — rho, computed per universe on flow fields,
                  is LOWER for CONSUMER than TECH, i.e. rho accounts for the
                  P2 reversal that seasonality could not.

Usage:
    python margin_model.py
"""

import json
import math
import statistics
from collections import defaultdict

from tau_expand import FLOW, flip_rate, kendall_tau, pearson, rel_jump, spearman
from tau_universe import UNIVERSES

OUT = "tau_universe.jsonl"


def pairwise_flip(symlist, q, fy):
    n_pairs = n_flip = 0
    for i in range(len(symlist)):
        for j in range(i + 1, len(symlist)):
            a, b = symlist[i], symlist[j]
            n_pairs += 1
            if (q[a] > q[b]) != (fy[a] > fy[b]):
                n_flip += 1
    return n_flip / n_pairs if n_pairs else 0.0


def build_cells():
    rows = [json.loads(l) for l in open(OUT, encoding="utf-8")]
    grouped = defaultdict(dict)
    for r in rows:
        grouped[(r["universe"], r["field"])][r["symbol"]] = (r["quarter"], r["fy"])

    cells = []
    for (uni, field), syms in sorted(grouped.items()):
        if len(syms) < 15:
            continue
        symlist = list(syms.keys())
        q = {s: syms[s][0] for s in symlist}
        fy = {s: syms[s][1] for s in symlist}

        # the margin model is multiplicative, so it needs positive values.
        pos = [s for s in symlist if q[s] > 0 and fy[s] > 0]
        if len(pos) < 12:
            continue
        lq = [math.log(q[s]) for s in pos]
        lr = [math.log(fy[s] / q[s]) for s in pos]
        sig_q = statistics.stdev(lq)
        sig_r = statistics.stdev(lr)
        rho = sig_r / sig_q if sig_q else float("inf")

        # tau on the SAME positive subset the margin model uses, otherwise the
        # M1 identity compares two different symbol sets.
        qp = {s: q[s] for s in pos}
        fyp = {s: fy[s] for s in pos}

        cells.append(dict(
            universe=uni, field=field, n=len(symlist), n_pos=len(pos),
            kind="flow" if field in FLOW else "stock",
            tau=kendall_tau(q, fy), tau_pos=kendall_tau(qp, fyp),
            flip=flip_rate(symlist, q, fy),
            pflip=pairwise_flip(pos, q, fy),
            jump=rel_jump(q, fy, symlist),
            sig_q=sig_q, sig_r=sig_r, rho=rho,
            pred_flip=math.atan(rho) / math.pi,
            pred_tau=1 - 2 * math.atan(rho) / math.pi))
    return cells


def main():
    cells = build_cells()
    print("=" * 78)
    print("MARGIN MODEL — flip happens when differential rescaling exceeds")
    print("               the decision margin")
    print("=" * 78)
    print(f"cells: {len(cells)} (universe x field), "
          f"positive-value items per cell: "
          f"{min(c['n_pos'] for c in cells)}-{max(c['n_pos'] for c in cells)}\n")

    print(f"  {'universe':15s} {'field':20s} {'sig_q':>6s} {'sig_r':>6s} "
          f"{'rho':>6s} {'pflip':>7s} {'pred':>7s} {'err':>7s}")
    for c in sorted(cells, key=lambda c: c["rho"]):
        print(f"  {c['universe']:15s} {c['field']:20s} {c['sig_q']:6.2f} "
              f"{c['sig_r']:6.2f} {c['rho']:6.2f} {c['pflip']:6.1%} "
              f"{c['pred_flip']:6.1%} {c['pred_flip']-c['pflip']:+6.1%}")

    taus = [c["tau"] for c in cells]
    flips = [c["flip"] for c in cells]
    pflips = [c["pflip"] for c in cells]
    rhos = [c["rho"] for c in cells]
    jumps = [c["jump"] for c in cells]
    preds = [c["pred_flip"] for c in cells]

    print("\n" + "=" * 78)
    n_trunc = sum(1 for c in cells if c["n_pos"] < c["n"])
    print("M1 — identity check: tau = 1 - 2 * pairwise_flip")
    errs = [abs(c["tau_pos"] - (1 - 2 * c["pflip"])) for c in cells]
    m1 = statistics.mean(errs) < 0.02
    print(f"  mean |err| = {statistics.mean(errs):.4f}  "
          f"max = {max(errs):.4f}   {'PASS' if m1 else 'FAIL'}")
    print("  (near-definitional — this checks the pipeline, not the theory)")
    print(f"  note: {n_trunc}/{len(cells)} cells drop non-positive items "
          f"(log-space model); tau on the full set differs by "
          f"{statistics.mean(abs(c['tau']-c['tau_pos']) for c in cells):.3f} "
          f"on average")

    print("\nM2 — closed form: pairwise flip = (1/pi) arctan(rho)")
    mae = statistics.mean(abs(preds[i] - pflips[i]) for i in range(len(cells)))
    m2 = mae < 0.05
    print(f"  MAE = {mae:.4f}   corr(pred, observed) = "
          f"{pearson(preds, pflips):+.3f}   {'PASS' if m2 else 'FAIL'}")
    print("  (the substantive test: fails if log-ratios are heavy-tailed)")

    print("\nM3 — does rho beat the output jump as a predictor?")
    r_rho = pearson(rhos, flips)
    r_jump = pearson(jumps, flips)
    r_tau = pearson(taus, flips)
    m3 = r_rho > 0.5 and abs(r_rho) > abs(r_jump)
    print(f"  corr(rho,  flip) = {r_rho:+.3f}   "
          f"spearman = {spearman(rhos, flips):+.3f}")
    print(f"  corr(tau,  flip) = {r_tau:+.3f}")
    print(f"  corr(jump, flip) = {r_jump:+.3f}")
    print(f"  {'PASS' if m3 else 'FAIL'}")

    print("\nM4 — does rho explain the universe reversal that seasonality could not?")
    for uni in UNIVERSES:
        fl = [c for c in cells if c["universe"] == uni and c["kind"] == "flow"]
        if not fl:
            continue
        print(f"  {uni:16s} flow: sig_q={statistics.mean(c['sig_q'] for c in fl):5.2f} "
              f"sig_r={statistics.mean(c['sig_r'] for c in fl):5.2f} "
              f"rho={statistics.mean(c['rho'] for c in fl):5.2f} "
              f"flip={statistics.mean(c['flip'] for c in fl):5.1%}")
    tech = [c for c in cells if c["universe"] == "TECH" and c["kind"] == "flow"]
    cons = [c for c in cells if c["universe"] == "CONSUMER" and c["kind"] == "flow"]
    d_rho = statistics.mean(c["rho"] for c in cons) - \
        statistics.mean(c["rho"] for c in tech)
    d_sq = statistics.mean(c["sig_q"] for c in cons) - \
        statistics.mean(c["sig_q"] for c in tech)
    m4 = d_rho < 0
    print(f"  CONSUMER - TECH: d(rho) = {d_rho:+.3f} (predicted < 0), "
          f"d(sig_q) = {d_sq:+.2f}")
    print(f"  {'PASS' if m4 else 'FAIL'}  -> CONSUMER items are "
          f"{'more' if d_sq > 0 else 'less'} separated, so the same "
          f"rescaling reorders {'fewer' if d_rho < 0 else 'more'} of them")

    print("\n" + "=" * 78)
    print("VERDICT")
    print(f"  M1 identity              : {'PASS' if m1 else 'FAIL'}")
    print(f"  M2 closed form           : {'PASS' if m2 else 'FAIL'}")
    print(f"  M3 rho beats output jump : {'PASS' if m3 else 'FAIL'}")
    print(f"  M4 explains P2 reversal  : {'PASS' if m4 else 'FAIL'}")
    if m2 and m3 and m4:
        print("\n  tau is not a standalone empirical regularity. Both tau and")
        print("  the flip rate are projections of rho = sigma_r / sigma_q, the")
        print("  ratio of substitution-induced rescaling dispersion to item")
        print("  separation. The paper can state a mechanism, not a correlation:")
        print("  a discrete substitution flips a decision when its DIFFERENTIAL")
        print("  effect exceeds the decision margin. Absolute jump size (what")
        print("  the continuous bound measures) does not appear in the condition.")
    elif m3 and not m2:
        print("\n  rho predicts, but the Gaussian closed form does not fit.")
        print("  Keep the margin condition |dlog r| > |dlog q| (exact) and drop")
        print("  the arctan formula (distributional assumption too strong).")


if __name__ == "__main__":
    main()
