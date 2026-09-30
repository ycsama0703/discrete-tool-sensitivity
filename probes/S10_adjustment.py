"""S10: a second financial discrete parameter -- price adjustment.
Protocol: docs/S10_ADJUSTMENT_PROTOCOL.md. Data: S10_snapshot.json (frozen yfinance closes,
validated as-traded reconstruction). Reuses the S7 harness (agent backends, parser pieces,
resumable runner).

  python S10_adjustment.py build
  python S10_adjustment.py calls    --backend openrouter --model openai/gpt-6-luna --out S10_calls_luna.jsonl --resume
  python S10_adjustment.py baseline --mode selfcons|verify|judge ... --calls S10_calls_luna.jsonl --out S10_base_<mode>_luna.jsonl
  python S10_adjustment.py eval     --tag luna --vote qwen gemma ...
  python S10_adjustment.py summary  --tags qwen gemma llama dsv41 qwen38 luna

PREDICTIONS (locked 2026-09-30, before any agent call):
  E1 generation : with the adjustment unstated, each model fills one dominant value in >= 70% of
                  its calls (omitted = the schema default), and at least two models' dominant values differ.
  E2 consequence: release (decision invariant over all adjustment values) is predicted by (rho, kappa)
                  alone with AUC >= 0.80, and better than the output-jump magnitude.
  E3 consequence: rho dose effect -- top-3 return flip rate vs the reference is higher for 'unadjusted'
                  than for 'splits_only' on windows that contain a split; across the 4 groups the
                  ordering by mean rho matches the ordering by top-3 flip rate (splits_only switch).
  E4 method     : ENUM releases 0 parameter-induced decision errors (every model); self-consistency,
                  self-verification, strong judge and voting each release >= 1 (pooled over models).
  E5 cost       : ENUM's release decision differs across models only on instances where some model
                  mixed adjustment values across symbols.
"""
import argparse
import collections
import json
import math
import os
import random
import re
import statistics

import S7_decision_screen as S

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "S10_snapshot.json")
INST = os.path.join(HERE, "S10_instances.jsonl")
MODES = ["splits_only", "splits_and_dividends", "unadjusted"]
DEFAULT = "splits_only"
WINDOWS = [("2025-01-02", "2025-12-31"), ("2023-01-03", "2025-12-31"), ("2021-01-04", "2025-12-31")]
DAYS = ["2021-06-30", "2023-06-30", "2025-06-30"]

TOOLS = [{
    "name": "get_price_history",
    "description": ("Historical daily closing prices for a US-listed stock. Returns the closing price on "
                    "start_date and on end_date."),
    "parameters": {"type": "object", "properties": {
        "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        # verbatim from OpenBB equity.price.historical (TMX provider), checked 2026-09-30
        "adjustment": {"type": "string", "enum": MODES, "default": DEFAULT,
                       "description": "The adjustment factor to apply. Only valid for daily data."}},
        "required": ["symbol", "start_date", "end_date"]}}]
SYSTEM = "You are a financial data assistant. Call the tool with the correct parameters."

_snap = None


def snap():
    global _snap
    if _snap is None:
        _snap = json.load(open(SNAP, encoding="utf-8"))
    return _snap


def close(s, mode, day):
    px = snap()["prices"][s]
    d = max(k for k in px if k <= day)                 # last trading day on or before `day`
    adj, so = px[d]
    if mode == "splits_and_dividends":
        return adj
    if mode == "splits_only":
        return so
    if mode == "unadjusted":
        v = so
        for sd, f in snap()["splits"][s]:
            if sd > d:
                v *= f
        return v
    return None


def value(inst, s, mode):
    """The number the decision uses: % return over the window, or the close on the day."""
    if mode not in MODES:
        return None
    if inst["measure"] == "return":
        return 100 * (close(s, mode, inst["end"]) / close(s, mode, inst["start"]) - 1)
    return close(s, mode, inst["end"])


def decide(inst, vals):
    if inst["decision"] == "top3":
        return frozenset(sorted(vals, key=lambda s: vals[s], reverse=True)[:3])
    return frozenset(s for s, v in vals.items() if v > inst["T"])


# --- build ---------------------------------------------------------------------

def cmd_build(a):
    out = []
    for g, syms in snap()["groups"].items():
        syms = sorted(syms)
        lst = ", ".join(syms)
        for start, end in WINDOWS:
            inst = dict(measure="return", start=start, end=end, correct="splits_and_dividends")
            T = round(statistics.median(value(inst, s, "splits_and_dividends") for s in syms), 1)
            span = f"from {start} to {end}"
            out.append(dict(inst, id=f"{g}|return|top3|{start[:4]}", group=g, decision="top3", T=None, symbols=syms,
                            question=f"Consider these companies: {lst}. Which 3 of them had the best stock performance {span}?"))
            out.append(dict(inst, id=f"{g}|return|threshold|{start[:4]}", group=g, decision="threshold", T=T, symbols=syms,
                            question=f"Consider these companies: {lst}. Which of them had a stock return above {T:.1f}% {span}?"))
        for day in DAYS:
            inst = dict(measure="price", start=day, end=day, correct="unadjusted")
            T = round(statistics.median(value(inst, s, "unadjusted") for s in syms), 2)
            out.append(dict(inst, id=f"{g}|price|top3|{day}", group=g, decision="top3", T=None, symbols=syms,
                            question=f"Consider these companies: {lst}. Which 3 of them had the highest share price on {day}?"))
            out.append(dict(inst, id=f"{g}|price|threshold|{day}", group=g, decision="threshold", T=T, symbols=syms,
                            question=f"Consider these companies: {lst}. Which of them closed above ${T:.2f} on {day}?"))
    with open(INST, "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(out)} instances -> {INST}")


# --- calls ---------------------------------------------------------------------

def build_messages(user):
    sys_prompt = (f"{SYSTEM}\n\nYou have these tools:\n{json.dumps(TOOLS)}\n\n"
                  f"Given a user request, call one tool by returning a JSON object of the form "
                  f"{{\"name\": \"<tool name>\", \"arguments\": {{...}}}}. "
                  f"Choose the arguments carefully based on what the user asks for.")
    return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]


def user_msg(r, s):
    return (f"{r['question']}\n\nTo answer, you will call a tool once per company. "
            f"Now call the tool for {s}.")


def parse_call(gen):
    """(tool, adjustment, start, end). adjustment '__OMITTED__' if the call has no such argument
    (the executor then applies the schema default, as a real API would)."""
    if not gen or S.api_error(gen):
        return None, None, None, None
    best = None
    for _, txt in S._objects(gen):
        o = S._load(txt)
        if isinstance(o, dict) and ("name" in o or "arguments" in o or "parameters" in o or "adjustment" in o):
            best = o
    if best is None:
        return None, None, None, None
    args = best.get("arguments") or best.get("parameters") or best
    if isinstance(args, str):
        args = S._load(args) or {}
    tool = best.get("name") or ("get_price_history" if "symbol" in args else None)
    adj = args.get("adjustment", "__OMITTED__")
    if isinstance(adj, str) and adj != "__OMITTED__":
        adj = adj.strip().lower()
    return tool, adj, args.get("start_date"), args.get("end_date")


def effective(adj):
    return DEFAULT if isinstance(adj, str) and adj.upper() == "__OMITTED__" else adj


def cmd_calls(a):
    agent = S.make_agent(a)
    insts = [json.loads(l) for l in open(INST, encoding="utf-8")]
    if a.group:
        insts = [r for r in insts if r["group"] == a.group]
    work = [dict(inst=r, symbol=s) for r in insts for s in r["symbols"]]

    def one(w):
        r, s = w["inst"], w["symbol"]
        gen = agent.generate(build_messages(user_msg(r, s)))
        tool, adj, st, en = parse_call(gen)
        return dict(id=r["id"], symbol=s, tool=tool, adjustment=adj, start_date=st, end_date=en,
                    api_error=S.api_error(gen), parse_failed=(tool is None), raw=gen[-200:])

    S.run_resumable(a, work, one, is_ok=lambda r: not S.api_row(r),
                    label=lambda r: (r["inst"]["id"], r["symbol"]) if "inst" in r else (r["id"], r["symbol"]))


# --- LLM-based baselines (representative symbol, as in S7) ------------------------

VERIFY_Q = ("Review your call. Is adjustment={p} the correct adjustment for this request? "
            "Answer with exactly one word: yes or no.")
JUDGE_SYS = ("You are auditing a financial agent's tool call. Decide whether the value of the "
             "'adjustment' argument correctly matches what the user asked for. "
             "Answer with exactly one word: correct or wrong.")


def cmd_baseline(a):
    agent = S.make_agent(a)
    insts = [json.loads(l) for l in open(INST, encoding="utf-8")]
    calls = {}
    if a.calls:
        for l in open(os.path.join(HERE, a.calls), encoding="utf-8"):
            c = json.loads(l)
            calls[(c["id"], c["symbol"])] = c

    def one(r):
        s = r["symbols"][0]
        out = dict(id=r["id"], symbol=s, mode=a.mode, api_error=False)
        if a.mode == "selfcons":
            gens = [agent.generate(build_messages(user_msg(r, s))) for _ in range(a.k)]
            out["api_error"] = any(S.api_error(g) for g in gens)
            out["adjustments"] = [effective(parse_call(g)[1]) if parse_call(g)[0] else None for g in gens]
            return out
        c = calls.get((r["id"], s))
        if not c or c["parse_failed"]:
            out["verdict"] = None
            return out
        call_txt = json.dumps({"name": c["tool"], "arguments": {"symbol": s, "start_date": r["start"], "end_date": r["end"],
                                                                "adjustment": effective(c["adjustment"])}})
        if a.mode == "verify":
            msgs = build_messages(user_msg(r, s)) + [{"role": "assistant", "content": call_txt},
                                                     {"role": "user", "content": VERIFY_Q.format(p=effective(c["adjustment"]))}]
            g = agent.generate(msgs); low = g.strip().lower()
            out["verdict"] = "no" if re.search(r"\bno\b", low) else ("yes" if re.search(r"\byes\b", low) else None)
        else:
            msgs = [{"role": "system", "content": JUDGE_SYS},
                    {"role": "user", "content": f"Tools available:\n{json.dumps(TOOLS)}\n\nUser request:\n{user_msg(r, s)}"
                                                f"\n\nAgent's tool call:\n{call_txt}\n\nIs the adjustment correct?"}]
            g = agent.generate(msgs); low = g.strip().lower()
            out["verdict"] = "wrong" if re.search(r"\bwrong\b", low) else ("correct" if re.search(r"\bcorrect\b", low) else None)
        out["api_error"] = S.api_error(g)
        if out["api_error"]:
            out["verdict"] = None
        out["raw"] = g[-120:]
        return out

    S.run_resumable(a, [dict(inst=r) for r in insts], lambda w: one(w["inst"]),
                    is_ok=lambda r: not S.api_row(r),
                    label=lambda r: r["inst"]["id"] if "inst" in r else r["id"])


# --- evaluation ----------------------------------------------------------------

def load(path):
    p = os.path.join(HERE, path)
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def audit_classes(group, inst):
    """Leave-one-group-out: merge adjustment values whose numbers are identical on every symbol of
    the OTHER groups for this instance's dates and measure."""
    others = [s for g, ss in snap()["groups"].items() if g != group for s in ss]
    sig = {m: tuple(round(value(inst, s, m), 6) for s in others) for m in MODES}
    cls = {}
    for m in MODES:
        cls.setdefault(sig[m], []).append(m)
    return list(cls.values())


def certdr(inst, agent_vals):
    dev = {s: max(abs(value(inst, s, m) - agent_vals[s]) for m in MODES) for s in agent_vals}
    if inst["decision"] == "top3":
        o = sorted(agent_vals, key=agent_vals.get, reverse=True)
        return agent_vals[o[2]] - agent_vals[o[3]] > 2 * max(dev.values())
    return all(abs(agent_vals[s] - inst["T"]) > dev[s] for s in agent_vals)


def rows_for(tag, vote_tags):
    insts = {r["id"]: r for r in load("S10_instances.jsonl")}
    by = collections.defaultdict(dict)
    for c in load(f"S10_calls_{tag}.jsonl"):
        by[c["id"]][c["symbol"]] = c
    base = collections.defaultdict(dict)
    for r in load(f"S10_base_selfcons_{tag}.jsonl"):
        if r.get("api_error"):
            continue
        ans = [p if p else f"<unparsed{i}>" for i, p in enumerate(r["adjustments"])]
        sc = 1 - max(ans.count(p) for p in set(ans)) / len(ans)
        base[r["id"]]["selfcons"] = sc > 0
    for r in load(f"S10_base_verify_{tag}.jsonl"):
        if r.get("verdict") is not None and not r.get("api_error"):
            base[r["id"]]["self_verify"] = r["verdict"] == "no"
    for r in load(f"S10_base_judge_{tag}.jsonl"):
        if r.get("verdict") is not None and not r.get("api_error"):
            base[r["id"]]["strong_judge"] = r["verdict"] == "wrong"
    votes = collections.defaultdict(list)
    for vt in vote_tags:
        if vt == tag:
            continue
        for c in load(f"S10_calls_{vt}.jsonl"):
            if not c.get("parse_failed"):
                votes[(c["id"], c["symbol"])].append(effective(c["adjustment"]))
    rng = random.Random(0)
    rows = []
    for iid, inst in insts.items():
        cs = by.get(iid, {})
        syms = inst["symbols"]
        if len(cs) < len(syms) or any(S.api_row(cs[s]) for s in syms):
            rows.append(dict(inst=inst, failed="api_or_missing")); continue
        if any(cs[s]["parse_failed"] or cs[s]["tool"] != "get_price_history" or effective(cs[s]["adjustment"]) not in MODES
               for s in syms):
            rows.append(dict(inst=inst, failed="parse_or_invalid")); continue
        adj = {s: effective(cs[s]["adjustment"]) for s in syms}
        agent_vals = {s: value(inst, s, adj[s]) for s in syms}
        d_agent = decide(inst, agent_vals)
        uni = {m: decide(inst, {s: value(inst, s, m) for s in syms}) for m in MODES}
        d_true = uni[inst["correct"]]
        classes = audit_classes(inst["group"], inst)
        flags = {"none": False,
                 "ENUM": any(uni[c[0]] != d_agent for c in classes),
                 "safer_m1": uni[rng.choice(MODES)] != d_agent,
                 "certdr_union": not certdr(inst, agent_vals)}
        flags.update(base.get(iid, {}))
        if vote_tags:
            s0 = syms[0]
            others = votes.get((iid, s0), [])
            flags["vote_disagree"] = any(p != adj[s0] for p in others)
        rows.append(dict(inst=inst, failed=None, adj=adj, mixed=len(set(adj.values())) > 1,
                         param_err=any(adj[s] != inst["correct"] for s in syms),
                         dec_err=d_agent != d_true, flags=flags, released_enum=not flags["ENUM"]))
    return rows, by


def cmd_eval(a):
    rows, by = rows_for(a.tag, a.vote or [])
    ok = [r for r in rows if r["failed"] is None]
    n = len(ok)
    fails = collections.Counter(r["failed"] for r in rows if r["failed"])
    lit = collections.Counter(c["adjustment"] for cs in by.values() for c in cs.values() if not c["parse_failed"])
    eff = collections.Counter(effective(c["adjustment"]) for cs in by.values() for c in cs.values() if not c["parse_failed"])
    tot = sum(eff.values())
    top, k = eff.most_common(1)[0] if eff else ("-", 0)
    print(f"[{a.tag}] instances evaluated {n}/{len(rows)}; excluded {dict(fails)}")
    print(f"  E1 filled values (literal): {dict(lit)}")
    print(f"     effective (omitted -> {DEFAULT}): {dict(eff)} -> dominant '{top}' {k / max(tot, 1):.1%} (>= 70%)")
    pe = sum(r["param_err"] for r in ok); de = sum(r["dec_err"] for r in ok)
    print(f"  param error {pe}/{n} = {pe / max(n, 1):.1%}; decision error {de}/{n} = {de / max(n, 1):.1%}")
    print(f"\n  {'method':14} {'coverage':>9} {'released':>9} {'rel_err':>8} {'risk.95UB':>10} {'dec.recall':>11}")
    methods = [m for m in ["none", "ENUM", "safer_m1", "certdr_union", "selfcons", "self_verify", "strong_judge", "vote_disagree"]
               if all(m in r["flags"] for r in ok)]
    for m in methods:
        rel = [r for r in ok if not r["flags"][m]]
        re_ = sum(r["dec_err"] for r in rel)
        rec = (de - re_) / de if de else float("nan")
        print(f"  {m:14} {len(rel) / max(n, 1):9.1%} {len(rel):9} {re_:8} {S.risk_upper(re_, len(rel)):10.1%} {rec:11.1%}")
    print("\n  by stratum (measure x decision): n, dec_err, ENUM coverage, ENUM released errors")
    st = collections.defaultdict(list)
    for r in ok:
        st[(r["inst"]["measure"], r["inst"]["decision"])].append(r)
    for k2, rs in sorted(st.items()):
        rel = [r for r in rs if r["released_enum"]]
        print(f"    {k2[0]:6} {k2[1]:9} n={len(rs):2} dec_err={sum(r['dec_err'] for r in rs):2} "
              f"coverage={len(rel) / len(rs):5.1%} released_err={sum(r['dec_err'] for r in rel)}")


def cmd_summary(a):
    """E2, E3 (model-free), E4, E5 (across models)."""
    import S7_H3_coverage as H
    insts = load("S10_instances.jsonl")
    # E2 / E3: geometry, model-free
    lab, pred, jump, grp = [], [], [], collections.defaultdict(lambda: [[], []])
    for inst in insts:
        syms = inst["symbols"]
        vals = {m: {s: value(inst, s, m) for s in syms} for m in MODES}
        lab.append(len({decide(inst, vals[m]) for m in MODES}) == 1)
        ref = vals[inst["correct"]]
        p, js = 1.0, []
        pos = [s for s in syms if ref[s] > 0] if inst["measure"] == "price" else syms
        for m in MODES:
            if m == inst["correct"]:
                continue
            alt = vals[m]
            if inst["measure"] == "return":      # work on gross returns so logs are defined
                lr = [math.log((1 + alt[s] / 100) / (1 + ref[s] / 100)) for s in syms]
                lq = [math.log(1 + ref[s] / 100) for s in syms]
            else:
                lr = [math.log(alt[s] / ref[s]) for s in pos]; lq = [math.log(ref[s]) for s in pos]
            sq = statistics.pstdev(lq)
            rho, kappa = statistics.pstdev(lr) / sq, statistics.mean(lr) / sq
            p *= H.p_topk(rho, len(syms)) if inst["decision"] == "top3" else H.p_threshold(kappa, rho, len(syms))
            js += [abs(alt[s] - ref[s]) / max(abs(alt[s]), abs(ref[s]), 1e-9) for s in syms]
            if inst["measure"] == "return" and inst["decision"] == "top3" and m == "splits_only":
                grp[inst["group"]][0].append(rho)
                grp[inst["group"]][1].append(decide(inst, alt) != decide(inst, ref))
        pred.append(p); jump.append(-statistics.mean(js))
    a_geo, a_jump = H.auc(pred, lab), H.auc(jump, lab)
    print(f"E2 release predicted by (rho, kappa): AUC {a_geo:.3f} vs output-jump {a_jump:.3f}  (release rate {statistics.mean(lab):.1%}) -> "
          f"{'PASS' if a_geo >= 0.8 and a_geo > a_jump else 'FAIL'}")
    fl = {m: [] for m in ("splits_only", "unadjusted")}
    for inst in insts:
        if inst["measure"] == "return" and inst["decision"] == "top3":
            has_split = any(inst["start"] < d <= inst["end"] for s in inst["symbols"] for d, f in snap()["splits"][s])
            if has_split:
                ref = decide(inst, {s: value(inst, s, inst["correct"]) for s in inst["symbols"]})
                for m in fl:
                    fl[m].append(decide(inst, {s: value(inst, s, m) for s in inst["symbols"]}) != ref)
    o_rho = sorted(grp, key=lambda g: statistics.mean(grp[g][0]))
    o_flip = sorted(grp, key=lambda g: statistics.mean(grp[g][1]))
    print(f"E3 top-3 return flips on split windows: splits_only {statistics.mean(fl['splits_only']):.1%}, "
          f"unadjusted {statistics.mean(fl['unadjusted']):.1%} (n={len(fl['unadjusted'])})")
    print(f"   groups by mean rho (splits_only): {[(g, round(statistics.mean(grp[g][0]), 3)) for g in o_rho]}")
    print(f"   groups by flip rate            : {[(g, round(statistics.mean(grp[g][1]), 2)) for g in o_flip]}")
    print(f"   -> {'PASS' if statistics.mean(fl['unadjusted']) > statistics.mean(fl['splits_only']) and o_rho == o_flip else 'FAIL'}")
    if not a.tags:
        return
    # E4 / E5
    pooled = collections.defaultdict(lambda: [0, 0])
    rel_by = collections.defaultdict(dict)
    enum_leak = {}
    for t in a.tags:
        rows, _ = rows_for(t, a.tags)
        ok = [r for r in rows if r["failed"] is None]
        enum_leak[t] = sum(r["dec_err"] for r in ok if r["released_enum"])
        for m in ["selfcons", "self_verify", "strong_judge", "vote_disagree", "safer_m1"]:
            rs = [r for r in ok if m in r["flags"] and not r["flags"][m]]
            pooled[m][0] += len(rs); pooled[m][1] += sum(r["dec_err"] for r in rs)
        for r in ok:
            rel_by[r["inst"]["id"]][t] = (r["released_enum"], r["mixed"])
    need = ["selfcons", "self_verify", "strong_judge", "vote_disagree"]
    print(f"E4 ENUM released errors per model: {enum_leak}")
    print(f"   pooled released / errors: " + ", ".join(f"{m} {v[0]}/{v[1]}" for m, v in pooled.items()))
    print(f"   -> {'PASS' if all(v == 0 for v in enum_leak.values()) and all(pooled[m][1] >= 1 for m in need) else 'FAIL'}")
    diff = [i for i, d in rel_by.items() if len({x[0] for x in d.values()}) > 1]
    unexpl = [i for i in diff if not any(x[1] for x in rel_by[i].values())]
    print(f"E5 release decision differs across models on {len(diff)}/{len(rel_by)} instances; unexplained by mixing: {len(unexpl)} "
          f"-> {'PASS' if not unexpl else 'FAIL'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "calls", "baseline", "eval", "summary"])
    ap.add_argument("--backend", choices=["transformers", "ollama", "openrouter"], default="openrouter")
    ap.add_argument("--model")
    ap.add_argument("--out")
    ap.add_argument("--calls")
    ap.add_argument("--mode", choices=["selfcons", "verify", "judge"])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--tag")
    ap.add_argument("--tags", nargs="*")
    ap.add_argument("--vote", nargs="*")
    ap.add_argument("--group")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-new", type=int, default=2000)
    a = ap.parse_args()
    {"build": cmd_build, "calls": cmd_calls, "baseline": cmd_baseline, "eval": cmd_eval, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
