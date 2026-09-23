"""
Stage-D mechanism: why D3 baseline decision error is 100% at 20 symbols.

Reproduces the mechanism argument in
docs/paper_framework.md §3.15 and docs/probe_notes/README_stageD_agent_e2e.md.

The D3 cross-flip set is deterministic (random.Random(0) inside each run_agent),
so every question uses the same flip set for a given symbol pool. At 20 symbols
the flip set is {GOOGL, CRM, ADBE, QCOM}, which hits a top-3 member of BOTH
periods (QCOM in quarter top-3, ADBE in fy top-3) — so every question's top-3
breaks, giving 100%. This script verifies that, and shows the expectation view
(flip rate rises with pool size over many seeds).

EPS data is hardcoded from the findata snapshot (2026-09-23) so this runs
offline with no API call.
"""

import random

# findata EPS snapshot, 2026-09-23 (period=quarter / period=fy)
Q = {"AAPL": 2.04, "MSFT": 4.28, "NVDA": 2.4, "GOOGL": 5.17, "AMZN": 5.82,
     "META": 10.57, "ORCL": 1.28, "CRM": 2.08, "TSLA": 0.15, "AMD": 1.4,
     "INTC": -0.73, "NFLX": 1.25, "ADBE": 4.26, "AVGO": 2.75, "CSCO": 0.85,
     "QCOM": 6.92, "IBM": 1.3, "TXN": 1.7, "AMAT": 3.2, "MU": 12.25}
F = {"AAPL": 6.11, "MSFT": 11.86, "NVDA": 2.97, "GOOGL": 8.04, "AMZN": 5.66,
     "META": 24.61, "ORCL": 3.81, "CRM": 6.44, "TSLA": 2.23, "AMD": 1.01,
     "INTC": -4.38, "NFLX": 20.28, "ADBE": 12.44, "AVGO": 1.33, "CSCO": 2.55,
     "QCOM": 9.09, "IBM": 6.53, "TXN": 5.24, "AMAT": 8.68, "MU": 0.7}
SYMBOLS = list(Q.keys())

# 20 questions, correct period per the full run
QUESTIONS = [("quarter", 0), ("fy", 1), ("quarter", 2), ("quarter", 3),
             ("quarter", 4), ("fy", 5), ("quarter", 6), ("quarter", 7),
             ("quarter", 8), ("fy", 9), ("quarter", 10), ("fy", 11),
             ("quarter", 12), ("fy", 13), ("quarter", 14), ("fy", 15),
             ("quarter", 16), ("fy", 17), ("quarter", 18), ("fy", 19)]


def top3(eps):
    return set(sorted(eps, key=lambda s: eps[s], reverse=True)[:3])


def cross_flip_set(symbols, seed=0, rate=0.4):
    rng = random.Random(seed)
    return {s for s in symbols if rng.random() < rate}


def base_flips(correct_period, symbols, seed=0):
    """D3 baseline: does the cross-flip change the top-3? (no screener)"""
    flipped = cross_flip_set(symbols, seed)
    base, correct = {}, {}
    for s in symbols:
        wrong = "fy" if correct_period == "quarter" else "quarter"
        base[s] = (F if wrong == "fy" else Q)[s] if s in flipped \
            else (Q if correct_period == "quarter" else F)[s]
        correct[s] = (Q if correct_period == "quarter" else F)[s]
    return top3(base) != top3(correct)


def main():
    print("=== 1. flip set at 20 symbols (seed=0) ===")
    flip20 = cross_flip_set(SYMBOLS)
    print(f"  flip set: {sorted(flip20)}  ({len(flip20)}/{len(SYMBOLS)})")

    print("\n=== 2. top-3 membership of flipped symbols ===")
    q3, f3 = top3(Q), top3(F)
    print(f"  quarter top-3: {sorted(q3)}  fy top-3: {sorted(f3)}")
    print(f"  flipped & in quarter top-3: {sorted(flip20 & q3)}")
    print(f"  flipped & in fy top-3:      {sorted(flip20 & f3)}")

    print("\n=== 3. D3 baseline decision errors, seed=0 ===")
    for n in [5, 20]:
        syms = SYMBOLS[:n]
        errs = sum(1 for cp, _ in QUESTIONS if base_flips(cp, syms))
        print(f"  n={n:2}: {errs}/{len(QUESTIONS)} questions flip")

    print("\n=== 4. expectation over 200 seeds (boundary tightness) ===")
    for n in [5, 10, 15, 20]:
        syms = SYMBOLS[:n]
        tot = sum(1 for seed in range(200)
                  for cp, _ in QUESTIONS if base_flips(cp, syms, seed))
        print(f"  n={n:2}: expected flip rate = {tot/(200*len(QUESTIONS)):.1%}")

    print("\n=== 5. seed sensitivity at 20 symbols ===")
    for seed in range(10):
        errs = sum(1 for cp, _ in QUESTIONS if base_flips(cp, SYMBOLS, seed))
        print(f"  seed={seed}: {errs}/20")


if __name__ == "__main__":
    main()
