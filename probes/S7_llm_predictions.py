"""Predictions from LLM theory, locked 2026-09-29 before running. Existing S7 data only.

L1  Sharpened (post-trained) output distributions: when the agent's call is wrong,
    its k=5 self-consistency samples are usually unanimous, i.e. the model is
    consistently wrong rather than uncertain. Prediction: unanimous in > 50% of
    wrong cases for at least 4 of 6 models.
L2  ENUM's release decision depends on the data, not on the model: it releases
    iff D is constant over all legal values AND the agent's own (possibly mixed
    per-symbol) decision equals that constant. Prediction: across models, the
    release decision differs on an instance ONLY when some model mixed periods
    across symbols on it (zero exceptions).
L3  Self-checks draw on a parametric prior ("annual ~ 4x quarterly"), which is
    informative for flow fields and not for stock fields. Prediction: for the
    models whose self-verification has signal overall (qwen, dsv41, luna),
    balanced accuracy is higher on flow fields than on stock fields.
Rule R-first, all instances.
"""
import collections
import json
import os

import S7_decision_screen as S

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["qwen", "gemma", "llama", "dsv41", "qwen38", "luna"]
RULE = "R-first"


def load(path):
    return [json.loads(l) for l in open(os.path.join(HERE, path), encoding="utf-8")]


def l1(insts):
    print("L1  wrong calls: are the 5 self-consistency samples unanimous?")
    for m in MODELS:
        calls = {(c["id"], c["symbol"]): c for c in load(f"S7_calls_{m}.jsonl")}
        n = unan = 0
        for r in load(f"S7_base_selfcons_{m}.jsonl"):
            c = calls.get((r["id"], r["symbol"]))
            if not c or c.get("parse_failed") or c["period"] == insts[r["id"]]["correct"]:
                continue
            n += 1
            unan += len(set(r["periods"])) == 1 and r["periods"][0] is not None
        print(f"    {m:7s} wrong={n:3d}  unanimous={unan:3d} ({unan / n:.0%})")


def l2(cache, insts):
    print("\nL2  is ENUM's release decision model-independent (except when the agent mixes periods)?")
    rel = collections.defaultdict(dict)     # iid -> model -> (released, mixed)
    for m in MODELS:
        by = collections.defaultdict(dict)
        for c in load(f"S7_calls_{m}.jsonl"):
            by[c["id"]][c["symbol"]] = c
        for iid, cs in by.items():
            inst = insts[iid]
            if len(cs) < len(inst["symbols"]) or any(c.get("parse_failed") or c["period"] not in S.PERIODS
                                                    for c in cs.values()):
                continue
            tool = S.FIELDS[inst["field"]][0]
            ds = set()
            for p in S.PERIODS:
                vals = {s: S.value(cache, s, tool, p, inst["field"], RULE) for s in inst["symbols"]}
                ds.add(S.decide(inst, vals) if None not in vals.values() else None)
            agent_vals = {s: S.value(cache, s, cs[s]["tool"], cs[s]["period"], inst["field"], RULE)
                          for s in inst["symbols"]}
            if None in agent_vals.values() or None in ds:
                continue
            released = len(ds) == 1 and S.decide(inst, agent_vals) in ds
            mixed = len({c["period"] for c in cs.values()}) > 1
            rel[iid][m] = (released, mixed)
    agree = disagree = explained = 0
    per_model = collections.Counter()
    for iid, d in rel.items():
        per_model.update(m for m, (r, _) in d.items() if r)
        if len({r for r, _ in d.values()}) <= 1:
            agree += 1
        else:
            disagree += 1
            explained += any(mx for _, mx in d.values())
    print(f"    instances with >=2 models evaluable: {sum(len(d) >= 2 for d in rel.values())}")
    print(f"    same release decision across models: {agree}; differs: {disagree} "
          f"(of which some model mixed periods: {explained}; unexplained: {disagree - explained})")
    print(f"    released instances per model: {dict(per_model)}")


def l3(insts):
    print("\nL3  self-verification balanced accuracy by field kind")
    for m in MODELS:
        calls = {(c["id"], c["symbol"]): c for c in load(f"S7_calls_{m}.jsonl")}
        cnt = collections.defaultdict(lambda: [0, 0, 0, 0])   # tp fn tn fp
        for r in load(f"S7_base_verify_{m}.jsonl"):
            c = calls.get((r["id"], r["symbol"]))
            if r.get("verdict") is None or not c or c.get("parse_failed"):
                continue
            inst = insts[r["id"]]
            actual, flagged = c["period"] != inst["correct"], r["verdict"] == "no"
            k = cnt[S.FIELDS[inst["field"]][3]]
            k[0] += actual and flagged; k[1] += actual and not flagged
            k[2] += (not actual) and (not flagged); k[3] += (not actual) and flagged
        out = []
        for kind in ("flow", "stock", "ratio"):
            tp, fn, tn, fp = cnt[kind]
            tpr = tp / (tp + fn) if tp + fn else float("nan")
            tnr = tn / (tn + fp) if tn + fp else float("nan")
            out.append(f"{kind} {(tpr + tnr) / 2:.2f} (err {tp + fn}/{tp + fn + tn + fp})")
        print(f"    {m:7s} " + "   ".join(out))


def main():
    cache = json.load(open(S.CACHE, encoding="utf-8"))
    insts = {r["id"]: r for r in load("S7_ddec.jsonl")}
    l1(insts)
    l2(cache, insts)
    l3(insts)


if __name__ == "__main__":
    main()
