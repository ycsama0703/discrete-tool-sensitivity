"""H3: ENUM's coverage is predictable from the decision geometry (rho, kappa).
Locked 2026-09-29 before running. Existing S7 data only; no model calls.

Release label (model-free, L2): the decision is identical under every legal
period value. Reference = the instance's correct period (T is the median of the
correct-period values). For each other period p' whose data differ, write
    log y_s(p') = log y_s(ref) + mu + eps_s,   sd(eps) = sigma_r,
    sigma_q = sd over symbols of log y_s(ref),
    rho = sigma_r / sigma_q,   kappa = mu / sigma_q (signed).
Prediction uses ONLY (rho, kappa, n, k) -- no per-symbol values:
    top-k:     x ~ N(0,1)^n, x' = x + rho*e;          P(top-k(x) == top-k(x'))
    threshold: x ~ N(0,1),   x' = x + kappa + rho*e;  P(no crossing)^n
(both by Monte Carlo), multiplied over the substitutions p' (independence).
Symbols with non-positive values are left out of the log statistics.

H3a  stratum level (decision x kind x rule): mean predicted coverage matches the
     actual coverage; pass if MAE over strata <= 10 percentage points.
H3b  instance level: predicted release probability discriminates released from
     flagged instances with AUC >= 0.80, and beats the output-jump magnitude
     (mean relative jump, a D_G-style quantity) as a predictor.
"""
import collections
import json
import math
import os
import random
import statistics

import S7_decision_screen as S

HERE = os.path.dirname(os.path.abspath(__file__))
N_MC = 4000
_cache = {}


def p_topk(rho, n, k=3):
    key = ("t", round(rho, 2), n, k)
    if key not in _cache:
        rng = random.Random(7)
        hit = 0
        for _ in range(N_MC):
            x = [rng.gauss(0, 1) for _ in range(n)]
            y = [xi + rho * rng.gauss(0, 1) for xi in x]
            top = lambda v: set(sorted(range(n), key=lambda i: v[i], reverse=True)[:k])
            hit += top(x) == top(y)
        _cache[key] = hit / N_MC
    return _cache[key]


def p_threshold(kappa, rho, n):
    key = ("h", round(kappa, 2), round(rho, 2), n)
    if key not in _cache:
        rng = random.Random(11)
        m = 20 * N_MC
        keep = 0
        for _ in range(m):
            x = rng.gauss(0, 1)
            keep += (x > 0) == (x + kappa + rho * rng.gauss(0, 1) > 0)
        _cache[key] = (keep / m) ** n
    return _cache[key]


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def main():
    cache = json.load(open(S.CACHE, encoding="utf-8"))
    S.add_aligned_fy(cache)
    insts = [json.loads(l) for l in open(os.path.join(HERE, "S7_ddec.jsonl"), encoding="utf-8")]
    for rule in ("R-first", "R-aligned"):
        rows = []
        for inst in insts:
            tool, f = S.FIELDS[inst["field"]][0], inst["field"]
            vals = {p: {s: S.value(cache, s, tool, p, f, rule) for s in inst["symbols"]} for p in S.PERIODS}
            if any(v is None for d in vals.values() for v in d.values()):
                continue
            released = len({S.decide(inst, vals[p]) for p in S.PERIODS}) == 1
            ref = vals[inst["correct"]]
            pos = [s for s in inst["symbols"] if ref[s] > 0]
            if len(pos) < 4:
                continue
            sq = statistics.pstdev(math.log(ref[s]) for s in pos)
            pred, jump = 1.0, []
            for p in S.PERIODS:
                alt = vals[p]
                if alt == ref:
                    continue
                pp = [s for s in pos if alt[s] > 0]
                logs = [math.log(alt[s] / ref[s]) for s in pp]
                mu, sr = statistics.mean(logs), statistics.pstdev(logs)
                rho, kappa = sr / sq, mu / sq
                n = len(inst["symbols"])
                pred *= p_topk(rho, n) if inst["decision"] == "top3" else p_threshold(kappa, rho, n)
                jump += [abs(alt[s] - ref[s]) / max(abs(alt[s]), abs(ref[s]), 1e-9) for s in inst["symbols"]]
            rows.append(dict(inst=inst, released=released, pred=pred,
                             jump=statistics.mean(jump) if jump else 0.0))

        print(f"\n===== {rule}: {len(rows)} instances, actual coverage {sum(r['released'] for r in rows) / len(rows):.1%}")
        print("  stratum                 n   actual   predicted")
        strata = collections.defaultdict(list)
        for r in rows:
            strata[(r["inst"]["decision"], r["inst"]["kind"])].append(r)
        errs = []
        for k, rs in sorted(strata.items()):
            act = sum(r["released"] for r in rs) / len(rs)
            pr = statistics.mean(r["pred"] for r in rs)
            errs.append(abs(act - pr))
            print(f"  {k[0]:9} {k[1]:6}   {len(rs):4}   {act:6.1%}   {pr:8.1%}")
        mae = statistics.mean(errs)
        print(f"  H3a stratum MAE = {mae * 100:.1f} pp  -> {'PASS' if mae <= 0.10 else 'FAIL'} (<= 10 pp)")
        lab = [r["released"] for r in rows]
        a_geo = auc([r["pred"] for r in rows], lab)
        a_jump = auc([-r["jump"] for r in rows], lab)
        print(f"  H3b AUC geometry = {a_geo:.3f}   AUC output-jump = {a_jump:.3f}  -> "
              f"{'PASS' if a_geo >= 0.80 and a_geo > a_jump else 'FAIL'}")
        tk = [r for r in rows if r["inst"]["decision"] == "top3"]
        print(f"      within top-3 only: AUC geometry = {auc([r['pred'] for r in tk], [r['released'] for r in tk]):.3f}"
              f"   AUC output-jump = {auc([-r['jump'] for r in tk], [r['released'] for r in tk]):.3f}")


if __name__ == "__main__":
    main()
