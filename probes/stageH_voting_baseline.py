"""
Stage-H: multi-model majority voting as a baseline, and why it fails.

"Why not just run three models and take the majority vote?" is, next to
self-verification, the most natural objection to the enumeration screener.
This probe answers it using the stage-F data directly — qwen2.5:7b,
llama3.1:8b and gemma3:12b were run on the SAME 400 (symbol, question) cases,
so a 3-model vote can be computed with no extra inference.

The finding: voting does not help, and the reason is structural. Voting
assumes errors are independent; here they are strongly correlated (pairwise
phi = +0.53 to +0.68), because all three models fail for the same reason —
binding is insufficient on ambiguous input. All three are wrong together on
16.2% of cases, against 2.2% expected under independence.

This completes a three-way argument, all pointing the same way:
  - self-verification fails: it depends on the very binding that failed
  - majority voting fails:   all models share the same binding defect
  - enumeration succeeds:    it does not depend on any model

Usage:
    python stageH_voting_baseline.py
"""

import itertools
import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "qwen": "stageF_ladder_qwen.jsonl",
    "llama": "stageF_ladder_llama.jsonl",
    "gemma": "stageF_ladder_gemma.jsonl",
}


def load():
    data = {}
    for k, f in FILES.items():
        path = os.path.join(HERE, f)
        data[k] = [json.loads(l) for l in open(path, encoding="utf-8")]
    keys = {k: [(r["symbol"], r["idx"]) for r in v] for k, v in data.items()}
    ref = keys["qwen"]
    for k, v in keys.items():
        assert v == ref, f"{k} is not aligned with qwen — voting would be invalid"
    return data


def main():
    data = load()
    names = list(FILES)
    n = len(data["qwen"])
    err = {k: [1 if r["real_error"] else 0 for r in v] for k, v in data.items()}

    print(f"cases: {n} (identical (symbol, question) set across all three models)\n")

    print("=== single-model period error rate ===")
    for k in names:
        e = sum(err[k])
        print(f"  {k:6} {e}/{n} = {e/n:.1%}")

    print("\n=== pairwise error correlation ===")
    for a, b in itertools.combinations(names, 2):
        ea, eb = err[a], err[b]
        n11 = sum(1 for x, y in zip(ea, eb) if x and y)
        n10 = sum(1 for x, y in zip(ea, eb) if x and not y)
        n01 = sum(1 for x, y in zip(ea, eb) if not x and y)
        n00 = sum(1 for x, y in zip(ea, eb) if not x and not y)
        den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        phi = (n11 * n00 - n10 * n01) / den if den else float("nan")
        jac = n11 / (n11 + n10 + n01) if (n11 + n10 + n01) else 0.0
        print(f"  {a:6} vs {b:6}  phi={phi:+.3f}  both-wrong={n11:3}  jaccard={jac:.2f}")

    print("\n=== how many models are wrong per case: actual vs independent ===")
    cnt = Counter(sum(err[k][i] for k in names) for i in range(n))
    p = [sum(err[k]) / n for k in names]
    exp = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
    for bits in itertools.product([0, 1], repeat=3):
        pr = 1.0
        for pi, b in zip(p, bits):
            pr *= pi if b else (1 - pi)
        exp[sum(bits)] += pr
    print(f"  {'k wrong':>8}  {'actual':>16}  {'if independent':>16}")
    for k in sorted(exp):
        print(f"  {k:>8}  {cnt.get(k,0):5} ({cnt.get(k,0)/n:5.1%})  "
              f"{exp[k]*n:8.1f} ({exp[k]:5.1%})")
    ratio = (cnt.get(3, 0) / n) / exp[3] if exp[3] else float("inf")
    print(f"\n  all three wrong: {ratio:.1f}x more often than independence predicts")

    print("\n=== 3-model majority vote ===")
    ok = wrong = tie = 0
    for i in range(n):
        rows = [data[k][i] for k in names]
        truth = rows[0]["correct"]
        votes = [r["filled_period"] for r in rows if r["filled_period"] is not None]
        if not votes:
            tie += 1
            continue
        top, ct = Counter(votes).most_common(1)[0]
        if ct <= len(votes) / 2:
            tie += 1
        elif top == truth:
            ok += 1
        else:
            wrong += 1
    print(f"  correct                 : {ok}/{n} = {ok/n:.1%}")
    print(f"  majority agreed & wrong : {wrong}/{n} = {wrong/n:.1%}")
    print(f"  no majority (tie)       : {tie}/{n} = {tie/n:.1%}")
    print(f"  VOTE FAILS (wrong+tie)  : {wrong+tie}/{n} = {(wrong+tie)/n:.1%}")

    best = min(sum(err[k]) for k in names) / n
    print(f"\n  best single model       : {best:.1%}")
    print(f"  enumeration screener    : 0.0%")
    print("\n  Voting does not beat the best single model. Its premise -")
    print("  independent errors - does not hold: the models share one binding defect.")


if __name__ == "__main__":
    main()
