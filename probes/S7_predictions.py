"""Test the four predictions locked in docs/theory_problem_roots.md section 7
(written 2026-09-29, before this script was run). Uses existing S7 data only.

P1  flow vs stock. Model quarter->fy as log r_s = mu_r + eps_s. Measurement
    theory: a threshold statement is not invariant to the common scaling mu_r.
    Prediction: flow fields have mu_r ~ log 4 and many per-symbol threshold
    crossings; stock fields under R-aligned (fy = Q4 value, time-aligned) have
    mu_r ~ 0 and few crossings; under R-first stock crossings are higher (the
    455-day FY lag adds drift). FALSIFIED if stock crossings under R-aligned are
    not clearly below flow crossings.
P2  default bias. Wrong calls are not spread uniformly over the wrong values:
    within each correct value, the dominant wrong value takes clearly more than
    half (threshold used: > 70%).
P3  two error classes. Explicit-intent requests (quarter / fy) have a parameter
    error rate > 0, and it differs from the ambiguous requests.
P4  self-verification is signal-free: balanced accuracy of "the call is wrong"
    against the actual parameter error is close to 0.5 (threshold: within
    0.5 +/- 0.1).
All instances are used (calibration and test split alike): these are claims
about the data and the models, not about a tuned screener.
"""
import collections
import json
import math
import os
import statistics

import S7_decision_screen as S

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["qwen", "gemma", "llama", "dsv41", "qwen38", "luna"]


def load(path):
    return [json.loads(l) for l in open(os.path.join(HERE, path), encoding="utf-8")]


def p1(cache, insts):
    print("=" * 70, "\nP1  quarter->fy: common scaling mu_r and threshold crossings")
    rules = [r for r in S.RULES if r != "R-annual"]   # R-annual only changes `all`
    for rule in rules:
        print(f"\n  [{rule}]  field               kind   n_sym  mu_r=mean log(fy/q)  sd   crossing rate")
        by_kind = collections.defaultdict(list)
        for f, (tool, _, _, kind) in S.FIELDS.items():
            logs, cross = [], []
            for inst in insts:
                if inst["field"] != f or inst["decision"] != "threshold":
                    continue
                for s in inst["symbols"]:
                    q = S.value(cache, s, tool, "quarter", f, rule)
                    y = S.value(cache, s, tool, "fy", f, rule)
                    if q is None or y is None:
                        continue
                    cross.append((q > inst["T"]) != (y > inst["T"]))
                    if q > 0 and y > 0:
                        logs.append(math.log(y / q))
            mu = statistics.mean(logs) if logs else float("nan")
            sd = statistics.pstdev(logs) if len(logs) > 1 else float("nan")
            rate = sum(cross) / len(cross) if cross else float("nan")
            by_kind[kind].append(rate)
            print(f"           {f:20s} {kind:6s} {len(logs):5d}  {mu:+8.3f}            {sd:5.2f}  {rate:6.1%}")
        print("           mean crossing rate by kind:",
              {k: f"{statistics.mean(v):.1%}" for k, v in by_kind.items()}, f"   (log 4 = {math.log(4):.3f})")


def p2_p3(insts_by_id):
    print("=" * 70, "\nP2  which wrong value do wrong calls pick?  (per correct value)")
    print("P3  parameter error rate by intent\n")
    for m in MODELS:
        calls = [c for c in load(f"S7_calls_{m}.jsonl") if not c.get("parse_failed") and c.get("period")]
        wrong = collections.defaultdict(collections.Counter)
        err = collections.defaultdict(lambda: [0, 0])
        for c in calls:
            inst = insts_by_id[c["id"]]
            e = c["period"] != inst["correct"]
            err[inst["intent"]][0] += e
            err[inst["intent"]][1] += 1
            if e:
                wrong[inst["correct"]][c["period"]] += 1
        p2s = []
        for corr, cnt in sorted(wrong.items()):
            tot = sum(cnt.values())
            top, k = cnt.most_common(1)[0]
            p2s.append(f"correct={corr}: {dict(cnt)} -> '{top}' {k / tot:.0%}")
        rates = {i: f"{e / n:.1%} ({e}/{n})" for i, (e, n) in err.items()}
        print(f"  {m:7s} P3 {rates}")
        print(f"          P2 {' | '.join(p2s)}")


def p4(insts_by_id):
    print("=" * 70, "\nP4  does 'the call is wrong' track the actual parameter error?  (rep. symbol)")
    print("          method        n   actual_err  TPR    TNR    balanced_acc")
    for m in MODELS:
        calls = {(c["id"], c["symbol"]): c for c in load(f"S7_calls_{m}.jsonl")}
        for mode, flag_word in (("verify", "no"), ("judge", "wrong")):
            tp = fn = tn = fp = 0
            for r in load(f"S7_base_{mode}_{m}.jsonl"):
                if r.get("verdict") is None or r.get("api_error"):
                    continue
                c = calls.get((r["id"], r["symbol"]))
                if not c or c.get("parse_failed"):
                    continue
                actual = c["period"] != insts_by_id[r["id"]]["correct"]
                flagged = r["verdict"] == flag_word
                tp += actual and flagged
                fn += actual and not flagged
                tn += (not actual) and (not flagged)
                fp += (not actual) and flagged
            n = tp + fn + tn + fp
            tpr = tp / (tp + fn) if tp + fn else float("nan")
            tnr = tn / (tn + fp) if tn + fp else float("nan")
            label = "self_verify" if mode == "verify" else "judge"
            print(f"  {m:7s} {label:12s} {n:4d}   {(tp + fn) / n:6.1%}    {tpr:5.1%}  {tnr:5.1%}  {(tpr + tnr) / 2:.3f}")


def main():
    cache = json.load(open(S.CACHE, encoding="utf-8"))
    S.add_aligned_fy(cache)
    insts = load("S7_ddec.jsonl")
    insts_by_id = {r["id"]: r for r in insts}
    p1(cache, insts)
    p2_p3(insts_by_id)
    p4(insts_by_id)


if __name__ == "__main__":
    main()
