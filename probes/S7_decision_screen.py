"""
S7 (registry: docs/EXPERIMENT_REGISTRY.md; protocol: docs/METHOD_EVAL_PROTOCOL.md)
Method evaluation: does the theory-driven screener release fewer wrong
decisions than the alternatives, on real agent calls and real findata data?

Three tools (protocol amendment 2026-09-27, after the smoke test showed that
flow-only fields make every threshold decision flip):
  get_fundamentals    revenue, operating_income, net_income, eps        (flows)
  get_enterprise_value market_cap, total_debt, cash_and_short_term      (stocks)
  get_key_metrics     current_ratio                                     (ratio)
Each has a `period` enum {all, fy, quarter}; get_fundamentals also has
`statement` {balance, cashflow, income}, which the endpoint ignores.

Sub-commands, run in order:
  fetch   cache findata for every symbol, endpoint and period
  build   D-DEC: 8 fields x 2 decisions x 3 intents x 4 universes = 192 instances
  calls   run one model, one tool call per (instance, symbol)
  eval    offline: decisions, every method, metrics

The screener under test (ENUM), fully automatic:
  step 1 type gate      enum-typed params of each tool are discrete
  step 2 jump audit     per tool and param, merge values whose outputs are
                        identical on AUDIT symbols (universes other than the test
                        one); params with a single class (no jump) are dropped
  step 3 decision gate  for each remaining value class, recompute the decision
                        with every call set to that value; release only if all
                        equal the agent's own decision
Release is safe because the correct period is one of the enum values and is the
same for every symbol. Covers errors in the enumerated parameter only; a wrong
TOOL (field not returned) is an explicit error and is reported separately.

Usage:
  python S7_decision_screen.py fetch
  python S7_decision_screen.py build
  python S7_decision_screen.py calls --universe TECH --backend transformers --out S7_calls_qwen_TECH.jsonl
  python S7_decision_screen.py eval  --calls S7_calls_qwen_TECH.jsonl
"""

import argparse
import json
import os
import random
import re
import statistics
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FIN = "https://lum.id/findata"
CACHE = os.path.join(HERE, "S7_findata_cache.json")
INST = os.path.join(HERE, "S7_ddec.jsonl")

QHIST = os.path.join(HERE, "S7_findata_qhist.json")

PERIODS = ["all", "fy", "quarter"]
STATEMENTS = ["balance", "cashflow", "income"]
# R-first   read the first record (findata's actual behaviour)
# R-annual  `all` reads its latest FY/TTM record (another API's convention)
# R-aligned like R-first, but `fy` is rebuilt from the quarterly series so that
#           "most recent fiscal year" is time-aligned with "most recent quarter"
#           (findata's own FY records lag the quarters by ~455 days, registry X4).
#           Offline sensitivity analysis only; needs `qhist`.
RULES = ["R-first", "R-annual", "R-aligned"]
DECISIONS = ["top3", "threshold"]
INTENTS = {"quarter": " in the most recent quarter",
           "fy": " in the most recent fiscal year",
           "ambiguous": ""}                       # ambiguous -> quarter by convention

# field -> (tool, endpoint, phrase, kind)
FIELDS = {
    "revenue":             ("get_fundamentals", "fundamentals", "revenue", "flow"),
    "operating_income":    ("get_fundamentals", "fundamentals", "operating income", "flow"),
    "net_income":          ("get_fundamentals", "fundamentals", "net income", "flow"),
    "eps":                 ("get_fundamentals", "fundamentals", "EPS", "flow"),
    "market_cap":          ("get_enterprise_value", "enterprise-value", "market capitalization", "stock"),
    "total_debt":          ("get_enterprise_value", "enterprise-value", "total debt", "stock"),
    "cash_and_short_term": ("get_enterprise_value", "enterprise-value", "cash and short-term investments", "stock"),
    "current_ratio":       ("get_key_metrics", "key-metrics", "current ratio", "ratio"),
}
TOOL_ENDPOINT = {"get_fundamentals": "fundamentals",
                 "get_enterprise_value": "enterprise-value",
                 "get_key_metrics": "key-metrics"}
ENDPOINT_FIELDS = {}
for _f, (_t, _e, _p, _k) in FIELDS.items():
    ENDPOINT_FIELDS.setdefault(_e, []).append(_f)

_PERIOD = {"type": "string", "enum": PERIODS,
           "description": "quarter = single quarter, fy = fiscal year, all = both"}
TOOLS = [
    {"name": "get_fundamentals",
     "description": ("Quarterly or annual income statement, balance sheet, or cash flow "
                     "summary for a US-listed company. Use 'statement' to choose the "
                     "statement type, and 'period' to choose quarter vs annual."),
     "parameters": {"type": "object", "properties": {
         "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
         "statement": {"type": "string", "enum": STATEMENTS,
                       "description": "Which statement: balance sheet, cash flow, or income"},
         "period": _PERIOD}, "required": ["symbol"]}},
    {"name": "get_enterprise_value",
     "description": ("Market capitalization, total debt, cash and short-term investments, "
                     "and enterprise value for a US-listed company."),
     "parameters": {"type": "object", "properties": {
         "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
         "period": _PERIOD}, "required": ["symbol"]}},
    {"name": "get_key_metrics",
     "description": "Valuation and liquidity ratios (e.g. current ratio) for a US-listed company.",
     "parameters": {"type": "object", "properties": {
         "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
         "period": _PERIOD}, "required": ["symbol"]}},
]
SYSTEM = "You are a financial data assistant. Call the tool with the correct parameters."


def universes():
    from tau_universe import UNIVERSES
    return UNIVERSES


# --- fetch ------------------------------------------------------------------

def _get(endpoint, sym, period):
    q = f"?period={period}" if period else ""
    path = f"/fundamentals/{sym}/history{q}" if endpoint == "fundamentals" else f"/{endpoint}/{sym}{q}"
    req = urllib.request.Request(FIN + path, headers={"User-Agent": "research"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    return d if isinstance(d, list) else []


def cmd_fetch(a):
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    syms = sorted({s for v in universes().values() for s in v})
    for s in syms:
        if s in cache and all(e in cache[s] for e in ENDPOINT_FIELDS):
            continue
        cache[s] = {}
        for ep, fields in ENDPOINT_FIELDS.items():
            rec = {}
            for p in ("quarter", "fy", "all", None):
                d = _get(ep, s, p)
                key = p or "default"
                rec[key] = {f: (d[0].get(f) if d else None) for f in fields}
                rec[key]["_type"] = d[0].get("period_type") if d else None
                if p == "all":
                    # R-annual: latest FY/TTM record of the `all` series; if the
                    # series has none (enterprise-value), the first record.
                    ann = next((x for x in d if x.get("period_type") in ("FY", "TTM")),
                               d[0] if d else None)
                    rec["all_annual"] = {f: (ann.get(f) if ann else None) for f in fields}
                    rec["all_annual"]["_type"] = ann.get("period_type") if ann else None
            cache[s][ep] = rec
        print(f"  {s}: " + "  ".join(f"{ep}[all_annual={cache[s][ep]['all_annual']['_type']}]"
                                     for ep in ENDPOINT_FIELDS), flush=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1)
    print(f"cached {len(cache)} symbols -> {CACHE}")


def cmd_qhist(a):
    """Quarterly histories, for the R-aligned fiscal year. Written to a separate
    file so the cache used by `build` (and hence the instances) never changes."""
    out = json.load(open(QHIST, encoding="utf-8")) if os.path.exists(QHIST) else {}
    syms = sorted({s for v in universes().values() for s in v})
    for s in syms:
        if s in out:
            continue
        out[s] = {}
        for ep, fields in ENDPOINT_FIELDS.items():
            d = _get(ep, s, "quarter")[:12]
            out[s][ep] = [dict(t=x.get("period_type"), d=x.get("period_end_date"),
                               **{f: x.get(f) for f in fields}) for x in d]
        print(f"  {s}", flush=True)
    json.dump(out, open(QHIST, "w", encoding="utf-8"), indent=1)
    print(f"wrote {QHIST}")


def add_aligned_fy(cache):
    """cache[s][ep]['fy_aligned'][field]: the latest completed fiscal year built
    from quarters — flows: sum of that year's Q1..Q4; stocks/ratios: the Q4 value.
    None when the four quarters are not all present."""
    if not os.path.exists(QHIST):
        return False
    qh = json.load(open(QHIST, encoding="utf-8"))
    for s, eps in qh.items():
        if s not in cache:
            continue
        for ep, recs in eps.items():
            aligned = {}
            i = next((k for k, x in enumerate(recs) if x["t"] == "Q4"), None)
            for f in ENDPOINT_FIELDS[ep]:
                kind = FIELDS[f][3]
                if i is None:
                    aligned[f] = None
                elif kind == "flow":
                    yr = recs[i:i + 4]
                    ok = [x["t"] for x in yr] == ["Q4", "Q3", "Q2", "Q1"] and \
                        all(x[f] is not None for x in yr)
                    aligned[f] = sum(x[f] for x in yr) if ok else None
                else:
                    aligned[f] = recs[i][f]
            cache[s][ep]["fy_aligned"] = aligned
    return True


# --- executor ---------------------------------------------------------------

def value(cache, sym, tool, period, field, rule, statement=None):
    """What the agent gets back for this call. `statement` is accepted and, like
    the real endpoint, has no effect — the audit has to discover that.
    None = explicit failure (wrong tool for the field, or a value outside the enum)."""
    ep = TOOL_ENDPOINT.get(tool)
    if ep is None or field not in ENDPOINT_FIELDS[ep]:
        return None
    r = cache[sym][ep]
    if period == "fy" and rule == "R-aligned":
        return r.get("fy_aligned", {}).get(field)
    if period in ("quarter", "fy"):
        return r[period][field]
    if period == "all":
        return r["all_annual" if rule == "R-annual" else "all"][field]
    if period == "__OMITTED__":
        return r["default"][field]
    return None


# --- build ------------------------------------------------------------------

def fmt_T(field, t):
    if field == "eps":
        return f"${t:.2f} per share"
    if field == "current_ratio":
        return f"{t:.2f}"
    if abs(t) >= 1e9:
        return f"${t / 1e9:.2f} billion"
    return f"${t / 1e6:.0f} million"


def cmd_build(a):
    cache = json.load(open(CACHE, encoding="utf-8"))
    out = []
    for uni, syms in universes().items():
        for field, (tool, ep, phrase, kind) in FIELDS.items():
            ok = [s for s in sorted(syms)
                  if all(cache[s][ep][k][field] is not None
                         for k in ("quarter", "fy", "all", "all_annual", "default"))]
            for dec in DECISIONS:
                for intent, pp in INTENTS.items():
                    cp = "fy" if intent == "fy" else "quarter"
                    T = statistics.median(cache[s][ep][cp][field] for s in ok)
                    lst = ", ".join(ok)
                    if dec == "top3":
                        q = (f"Consider these companies: {lst}. Which 3 of them had the "
                             f"highest {phrase}{pp}?")
                    else:
                        q = (f"Consider these companies: {lst}. Which of them had "
                             f"{phrase}{pp} above {fmt_T(field, T)}?")
                    out.append(dict(id=f"{uni}|{field}|{dec}|{intent}", universe=uni,
                                    field=field, tool=tool, kind=kind, decision=dec,
                                    intent=intent, correct=cp, T=T, symbols=ok, question=q))
    with open(INST, "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(out)} instances -> {INST}")


# --- calls ------------------------------------------------------------------

def build_messages(user):
    sys_prompt = (
        f"{SYSTEM}\n\nYou have these tools:\n{json.dumps(TOOLS)}\n\n"
        f"Given a user request, call one tool by returning a JSON object of the form "
        f"{{\"name\": \"<tool name>\", \"arguments\": {{...}}}}. "
        f"Choose 'period' carefully based on what the user asks for.")
    return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]


def _objects(text):
    """Every balanced {...} span in text, in order (quote-aware)."""
    out, depth, start, quote, esc = [], 0, None, None, False
    for i, ch in enumerate(text):
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'" and depth:
            quote = ch
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                out.append((start, text[start:i + 1]))
    return out


def _load(s):
    try:
        return json.loads(s)
    except Exception:
        import ast
        try:                                   # llama writes {'name': ..., ...}
            v = ast.literal_eval(s)
            return v if isinstance(v, dict) else None
        except Exception:
            return None


def parse_call(gen):
    """Returns (tool, period, statement).

    2026-09-28 fix: the stageJ-style extraction took the greedy span from the
    FIRST '{' to the LAST '}', so any brace in a model's preamble made the call
    unparseable, and single-quoted (Python-dict) calls failed json.loads. On
    llama this misread 114/960 well-formed calls as failures (44/48 TECH
    decisions would have been excluded). Now: scan every balanced object and
    take the LAST one that looks like a tool call."""
    if gen.startswith("__API_ERROR__"):
        return None, None, None
    m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", gen, re.DOTALL)
    raw = m.group(1) if m else gen
    found = None
    for start, s in _objects(raw):
        c = _load(s)
        if isinstance(c, dict) and ("name" in c or "arguments" in c or "parameters" in c or "period" in c):
            found = (start, c)
    if found is None:
        return None, None, None
    start, call = found
    tool = call.get("name") if isinstance(call.get("name"), str) else None
    if tool is None:
        # e.g. sonnet: 'get_fundamentals\n{"symbol": ..., "period": ...}' — the
        # name is written before a bare argument object; take the last tool name
        # mentioned before the JSON
        names = re.findall(r"get_(?:fundamentals|enterprise_value|key_metrics)", raw[:start])
        tool = names[-1] if names else None
    args = call.get("arguments") or call.get("parameters") or call
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    if not isinstance(args, dict):
        return tool, None, None
    un = lambda v: v.get("value") if isinstance(v, dict) else v
    p, st = un(args.get("period")), un(args.get("statement"))
    if p is None and tool:
        p = "__OMITTED__"
    return tool, p, st


def make_agent(a):
    import stageJ_schema_ablation as J
    if a.backend == "ollama":
        ag = J.OllamaAgent(a.model)
    elif a.backend == "openrouter":
        ag = J.ORAgentJ(a.model)
        ag.generate = lambda m: ag.client._chat(m, max_new=a.max_new)
    else:
        ag = J.Agent(a.model)
    return ag


def api_error(gen):
    return (gen or "").startswith("__API_ERROR__")


def api_row(r):
    """A stored row that failed at the API (older files have no api_error flag)."""
    return bool(r.get("api_error")) or api_error(r.get("raw", ""))


def payment_error(r):
    return api_row(r) and "402" in r.get("raw", "")


class Abort(Exception):
    pass


def run_resumable(a, keys, fn, is_ok, label):
    """Run fn over keys, appending to a.out. With --resume, rows already in the
    file that are OK are kept and not re-run; failed/API-error rows are redone.
    Aborts (without writing further rows) as soon as the API reports 402 —
    after 2026-09-27, when a credit-exhausted run kept going and recorded
    thousands of 402s as model behaviour."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    path = os.path.join(HERE, a.out)
    keep = {}
    if a.resume and os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            r = json.loads(l)
            if is_ok(r):
                keep[label(r)] = r
    todo = [k for k in keys if label(k) not in keep]
    if getattr(a, "limit", None):
        todo = todo[:a.limit]           # dry runs only (vast rehearsal)
    print(f"{len(keys)} items, {len(keep)} kept from previous run, {len(todo)} to run", flush=True)
    stop = threading.Event()

    def guarded(k):
        if stop.is_set():
            return None
        o = fn(k)
        if payment_error(o):
            stop.set()
        return o

    workers = a.concurrency if a.backend == "openrouter" else 1
    n = 0
    # kept rows were read above, so rewriting the file in place is safe; new rows
    # are appended as they finish, so a crash loses nothing and progress is visible
    with open(path, "w", encoding="utf-8") as fh:
        for r in keep.values():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()
        with ThreadPoolExecutor(workers) as ex:
            for o in ex.map(guarded, todo):
                if o is None or payment_error(o):
                    continue
                fh.write(json.dumps(o, ensure_ascii=False) + "\n"); fh.flush()
                n += 1
                if n % 40 == 0:
                    print(f"  {n}/{len(todo)}", flush=True)
    if stop.is_set():
        raise SystemExit(f"ABORTED: API returned 402 (payment required). {n} new rows written; "
                         f"re-run with --resume after topping up.")
    print(f"wrote {a.out}")


def cmd_calls(a):
    agent = make_agent(a)
    insts = [json.loads(l) for l in open(INST, encoding="utf-8")]
    if a.universe:
        insts = [r for r in insts if r["universe"] == a.universe]
    work = [dict(inst=r, symbol=s) for r in insts for s in r["symbols"]]

    def one(w):
        r, s = w["inst"], w["symbol"]
        user = (f"{r['question']}\n\nTo answer, you will call a tool once per company. "
                f"Now call the tool for {s}.")
        gen = agent.generate(build_messages(user))
        tool, p, st = parse_call(gen)
        return dict(id=r["id"], symbol=s, tool=tool, period=p, statement=st,
                    api_error=api_error(gen),
                    parse_failed=(tool is None or p is None), raw=gen[-200:])

    # Only API errors are redone on --resume. A call the model genuinely failed
    # to format is its behaviour; retrying it until it parses would bias the
    # error rate. --redo-parse opts in (e.g. after raising --max-new because
    # reasoning models were cut off mid-thought).
    run_resumable(a, work, one,
                  is_ok=lambda r: not api_row(r) and not (a.redo_parse and r["parse_failed"]),
                  label=lambda r: (r["inst"]["id"], r["symbol"]) if "inst" in r else (r["id"], r["symbol"]))


# --- LLM-based baselines ----------------------------------------------------
# Each instance is probed through ONE representative symbol (the first in its
# list), because the period choice is driven by the question: in the smoke run
# qwen filled the same period for all 20 symbols of every question. Probing all
# 20 would multiply the cost by 20 (self-consistency alone: 19,200 generations
# per model) for no information. Protocol change log, 2026-09-27.

VERIFY_Q = ("Review your call. Is period={p} the correct period for this request? "
            "Answer with exactly one word: yes or no.")
JUDGE_SYS = ("You are auditing a financial agent's tool call. Decide whether the value "
             "of the 'period' argument correctly matches what the user asked for. "
             "Answer with exactly one word: correct or wrong.")


def cmd_baseline(a):
    """--mode selfcons: k fresh calls per instance (same prompt, sampling)
       --mode verify  : the agent reviews its own call (ladder L2 prompt)
       --mode judge   : a separate (stronger) model judges the agent's call;
                        --calls gives the agent's calls, --model the judge"""
    agent = make_agent(a)
    insts = [json.loads(l) for l in open(INST, encoding="utf-8")]
    if a.universe:
        insts = [r for r in insts if r["universe"] == a.universe]
    calls = {}
    if a.calls:
        for l in open(os.path.join(HERE, a.calls), encoding="utf-8"):
            c = json.loads(l)
            calls[(c["id"], c["symbol"])] = c

    def user_msg(r, s):
        return (f"{r['question']}\n\nTo answer, you will call a tool once per company. "
                f"Now call the tool for {s}.")

    def one(r):
        s = r["symbols"][0]
        out = dict(id=r["id"], symbol=s, mode=a.mode, api_error=False)
        if a.mode == "selfcons":
            gens = [agent.generate(build_messages(user_msg(r, s))) for _ in range(a.k)]
            out["api_error"] = any(api_error(g) for g in gens)
            out["periods"] = [parse_call(g)[1] for g in gens]
            if out["api_error"]:
                out["raw"] = next(g for g in gens if api_error(g))[:120]
        else:
            c = calls.get((r["id"], s))
            if not c or c["parse_failed"]:
                out["verdict"] = None              # nothing to verify: unavailable
                return out
            call_txt = json.dumps({"name": c["tool"], "arguments": {"symbol": s, "period": c["period"]}})
            if a.mode == "verify":
                msgs = build_messages(user_msg(r, s)) + [
                    {"role": "assistant", "content": call_txt},
                    {"role": "user", "content": VERIFY_Q.format(p=c["period"])}]
                g = agent.generate(msgs)
                low = g.strip().lower()
                out["verdict"] = "no" if re.search(r"\bno\b", low) else ("yes" if re.search(r"\byes\b", low) else None)
            else:  # judge
                msgs = [{"role": "system", "content": JUDGE_SYS},
                        {"role": "user", "content":
                            f"Tools available:\n{json.dumps(TOOLS)}\n\nUser request:\n{user_msg(r, s)}"
                            f"\n\nAgent's tool call:\n{call_txt}\n\nIs the period correct?"}]
                g = agent.generate(msgs)
                low = g.strip().lower()
                out["verdict"] = "wrong" if re.search(r"\bwrong\b", low) else ("correct" if re.search(r"\bcorrect\b", low) else None)
            out["api_error"] = api_error(g)
            if out["api_error"]:
                out["verdict"] = None
            out["raw"] = g[-120:]
        return out

    run_resumable(a, [dict(inst=r) for r in insts], lambda w: one(w["inst"]),
                  is_ok=lambda r: not api_row(r),
                  label=lambda r: r["inst"]["id"] if "inst" in r else r["id"])


def load_baselines(a):
    """Map instance id -> {method: (flag, score)} from optional baseline files."""
    res = {}
    def rows(path):
        return [json.loads(l) for l in open(os.path.join(HERE, path), encoding="utf-8")] if path else []
    # An API error or an unparseable verdict makes the method UNAVAILABLE for
    # that instance; it is never counted as "did not flag". (Counting it as
    # "no flag" makes the baseline look worse than it is — a bias in our favour.)
    for r in rows(a.base_selfcons):
        if r.get("api_error") or "api_error" not in r:
            continue   # files written before 2026-09-27 cannot tell 402s from unparsed samples
        ps = [p for p in r["periods"] if p]
        # disagreement among the k samples (SelfCheckGPT: flag inconsistency);
        # an unparseable sample counts as its own distinct answer
        answers = [p if p else f"<unparsed{i}>" for i, p in enumerate(r["periods"])]
        score = 1 - max(answers.count(p) for p in set(answers)) / len(answers)
        res.setdefault(r["id"], {})["selfcons"] = (score > 0, score)
    for r in rows(a.base_verify):
        if api_row(r) or r.get("verdict") is None:
            continue
        res.setdefault(r["id"], {})["self_verify"] = (r["verdict"] == "no", float(r["verdict"] == "no"))
    for r in rows(a.base_judge):
        if api_row(r) or r.get("verdict") is None:
            continue
        res.setdefault(r["id"], {})["strong_judge"] = (r["verdict"] == "wrong", float(r["verdict"] == "wrong"))
    # voting across models: fraction of OTHER models' calls (rep symbol) whose
    # period differs from this model's
    votes = {}
    for path in (a.vote or []):
        for l in open(os.path.join(HERE, path), encoding="utf-8"):
            c = json.loads(l)
            votes.setdefault((c["id"], c["symbol"]), []).append(c["period"])
    return res, votes


# --- screener pieces ----------------------------------------------------------

def decide(inst, vals):
    if inst["decision"] == "top3":
        return frozenset(sorted(vals, key=lambda s: vals[s], reverse=True)[:3])
    return frozenset(s for s, v in vals.items() if v > inst["T"])


def audit_classes(cache, audit_syms, rule):
    """Step 2, generic: for each tool and each of its enum params, merge values
    whose outputs are identical on every audit symbol and field of that tool."""
    def classes_of(values, sig):
        c = {}
        for v in values:
            c.setdefault(sig(v), []).append(v)
        return list(c.values())
    out = {}
    for tool in TOOLS:
        name, ep = tool["name"], TOOL_ENDPOINT[tool["name"]]
        fields = ENDPOINT_FIELDS[ep]
        params = {}
        for pname, spec in tool["parameters"]["properties"].items():
            if "enum" not in spec:
                continue                                   # step 1: only enum params
            if pname == "period":
                sig = lambda v: tuple(value(cache, s, name, v, f, rule) for s in audit_syms for f in fields)
            else:
                sig = lambda v, pn=pname: tuple(value(cache, s, name, "quarter", f, rule, **{pn: v})
                                                for s in audit_syms for f in fields)
            params[pname] = classes_of(spec["enum"], sig)
        out[name] = params
    return out


def audit_violations(cache, syms, classes, rule):
    bad = 0
    for tool, params in classes.items():
        ep = TOOL_ENDPOINT[tool]
        for cl in params.get("period", []):
            for s in syms:
                for f in ENDPOINT_FIELDS[ep]:
                    if len({value(cache, s, tool, p, f, rule) for p in cl}) > 1:
                        bad += 1
    return bad


# --- eval -------------------------------------------------------------------

def cmd_eval(a):
    cache = json.load(open(CACHE, encoding="utf-8"))
    rules = RULES if add_aligned_fy(cache) else [r for r in RULES if r != "R-aligned"]
    insts = {r["id"]: r for r in (json.loads(l) for l in open(INST, encoding="utf-8"))}
    calls = [json.loads(l) for l in open(os.path.join(HERE, a.calls), encoding="utf-8")]
    by = {}
    for c in calls:
        by.setdefault(c["id"], {})[c["symbol"]] = c
    test_unis = sorted({insts[i]["universe"] for i in by})
    U = universes()
    # Leave-one-universe-out audit: the audit for universe u uses only symbols
    # that are not in u. (A single audit set over "universes not under test"
    # is EMPTY when all four are tested, which silently merges every value into
    # one class and turns the screener off — caught in the 2026-09-27 dry run.)
    audit_syms = {u: sorted({s for v, ss in U.items() if v != u for s in ss} - set(U[u]))
                  for u in test_unis}
    for u, a_s in audit_syms.items():
        if not a_s:
            raise SystemExit(f"empty audit set for {u}: the screener would be vacuous")
    rng = random.Random(0)
    base, votes = load_baselines(a)
    # calibration / test split by field (protocol section 1), fixed seed
    fl = sorted(FIELDS); random.Random(2026).shuffle(fl)
    calib_fields = set(fl[:len(fl) // 2])
    print(f"calibration fields: {sorted(calib_fields)}  (all numbers below: TEST split only)")

    for rule in rules:
        cls_by_u = {u: audit_classes(cache, audit_syms[u], rule) for u in test_unis}
        rows = []
        for iid, cs in by.items():
            inst = insts[iid]
            cls = cls_by_u[inst["universe"]]
            syms, f = inst["symbols"], inst["field"]
            if len(cs) < len(syms) or any(api_row(cs[s]) for s in syms):
                rows.append(dict(inst=inst, failed="api_error")); continue
            if any(cs[s]["parse_failed"] for s in syms):
                rows.append(dict(inst=inst, failed="parse")); continue
            agent_vals = {s: value(cache, s, cs[s]["tool"], cs[s]["period"], f, rule) for s in syms}
            if any(v is None for v in agent_vals.values()):
                rows.append(dict(inst=inst, failed="tool_or_value")); continue
            true_vals = {s: value(cache, s, inst["tool"], inst["correct"], f, rule) for s in syms}
            d_agent, d_true = decide(inst, agent_vals), decide(inst, true_vals)
            param_err = any(cs[s]["period"] != inst["correct"] for s in syms)
            tools_used = {cs[s]["tool"] for s in syms}

            # ENUM step 3: per value class of `period` (the only param that survives
            # the audit), set every call to that class's representative
            def uniform(p):
                return decide(inst, {s: value(cache, s, cs[s]["tool"], p, f, rule) for s in syms})
            period_classes = set()
            for t in tools_used:
                for cl in cls[t].get("period", []):
                    period_classes.add(cl[0])
            kept_params = {pn for t in tools_used for pn, c in cls[t].items() if len(c) > 1}
            enum_flag = any(uniform(p) != d_agent for p in period_classes) if "period" in kept_params else False
            all_uni = {p: uniform(p) for p in PERIODS}

            jumps = []
            for s in syms:
                x = agent_vals[s]
                for p in PERIODS:
                    y = value(cache, s, cs[s]["tool"], p, f, rule)
                    jumps.append(abs(y - x) / max(abs(x), abs(y), 1e-9))
            flags = {"none": False, "lipschitz": False, "legality": False,
                     "output_jump@0.10": max(jumps) > 0.10,
                     "safer_m1": all_uni[rng.choice(PERIODS)] != d_agent,
                     "certdr_union": not certdr_certified(cache, inst, cs, agent_vals, rule),
                     "ENUM": enum_flag}
            scores = {"output_jump": max(jumps),
                      "safer": sum(all_uni[p] != d_agent for p in PERIODS) / len(PERIODS)}
            b = base.get(iid, {})
            for m in ("selfcons", "self_verify", "strong_judge"):
                if m in b:
                    flags[m], scores[m] = b[m]
            if votes:
                s0 = syms[0]
                others = list(votes.get((iid, s0), []))
                if cs[s0]["period"] in others:
                    others.remove(cs[s0]["period"])        # drop this model's own vote
                v = sum(p != cs[s0]["period"] for p in others) / len(others) if others else 0.0
                flags["vote_disagree"], scores["vote_disagree"] = v > 0, v
            rows.append(dict(
                inst=inst, failed=None, param_err=param_err, dec_err=d_agent != d_true,
                flags=flags, scores=scores,
                enum_calls=len(period_classes) * len(syms),
                noaudit_calls=sum(len(c) for t in tools_used for pn, cl in cls[t].items()
                                  for c in cl) * len(syms)))
        calib = [r for r in rows if r["failed"] is None and r["inst"]["field"] in calib_fields]
        test = [r for r in rows if r["inst"]["field"] not in calib_fields]
        for key in ("selfcons", "vote_disagree", "output_jump"):
            t = crc_threshold(calib, key, alpha=0.05)
            for r in test:
                if r["failed"] is None and key in r["scores"]:
                    r["flags"][f"CRC[{key}]"] = t is None or r["scores"][key] > t
        report(rule, test, cls_by_u)
        for u in test_unis:
            print(f"  audit generalisation [{u}]: "
                  f"{audit_violations(cache, sorted(U[u]), cls_by_u[u], rule)} (symbol, field) "
                  f"pairs where a merged period class disagrees on this universe's symbols")


def certdr_certified(cache, inst, cs, agent_vals, rule):
    """CertDR-style worst-case certificate (union bound, repaired so that
    incumbents may move too — as in G8). Each item may move by its own largest
    deviation over the period enum, independently, in the worst direction."""
    syms, f = inst["symbols"], inst["field"]
    dev = {s: max(abs(value(cache, s, cs[s]["tool"], p, f, rule) - agent_vals[s]) for p in PERIODS)
           for s in syms}
    if inst["decision"] == "top3":
        order = sorted(syms, key=lambda s: agent_vals[s], reverse=True)
        gap = agent_vals[order[2]] - agent_vals[order[3]]
        return gap > 2 * max(dev.values())
    return all(abs(agent_vals[s] - inst["T"]) > dev[s] for s in syms)


def crc_threshold(calib, key, alpha):
    """Conformal risk control on the calibration split: the largest threshold t
    (release score <= t) with (n*R_hat + 1)/(n + 1) <= alpha, where R_hat is the
    empirical selective risk. None if no threshold qualifies (-> flag all)."""
    pts = sorted({r["scores"][key] for r in calib if key in r["scores"]})
    n = len(calib)
    best = None
    for t in pts:
        rel = [r for r in calib if key in r["scores"] and r["scores"][key] <= t]
        if not rel:
            continue
        risk = sum(r["dec_err"] for r in rel) / n
        if (n * risk + 1) / (n + 1) <= alpha:
            best = t
    return best


def aurc(rows, key):
    ok = sorted(rows, key=lambda r: r["scores"][key])
    risks, err = [], 0
    for i, r in enumerate(ok, 1):
        err += r["dec_err"]
        risks.append(err / i)
    return sum(risks) / len(risks) if risks else float("nan")


def report(rule, rows, cls_by_u):
    ok = [r for r in rows if r["failed"] is None]
    n = len(ok)
    fails = {k: sum(1 for r in rows if r["failed"] == k) for k in ("api_error", "parse", "tool_or_value")}
    if fails["api_error"]:
        print(f"  !! {fails['api_error']} instances have API errors — this run is incomplete; "
              f"re-run the calls with --resume before reading these numbers")
    pe = sum(r["param_err"] for r in ok); de = sum(r["dec_err"] for r in ok)
    print(f"\n==================== read rule {rule} ====================")
    print("step 2 audit (value classes per tool and enum param, leave-one-universe-out):")
    for u, cls in cls_by_u.items():
        for t, params in cls.items():
            print(f"    [{u:14}] {t:22} " + "  ".join(f"{pn}={c}" for pn, c in params.items()))
    print(f"instances evaluated {n}; excluded: {fails}; param error {pe}/{n} = {pe/max(n,1):.1%}; "
          f"decision error {de}/{n} = {de/max(n,1):.1%}")
    print(f"\n  {'method':18} {'coverage':>9} {'sel.risk':>9} {'released_err':>13} "
          f"{'dec.recall':>11} {'precision':>10}")
    methods = []
    for r in ok:
        for m in r["flags"]:
            if m not in methods:
                methods.append(m)
    missing = {m: n - sum(1 for r in ok if m in r["flags"]) for m in methods}
    for m in methods:
        if missing[m]:
            print(f"  {m:18} (unavailable on {missing[m]}/{n} instances — not reported)")
            continue
        rel = [r for r in ok if not r["flags"][m]]
        fl = [r for r in ok if r["flags"][m]]
        rel_err = sum(r["dec_err"] for r in rel)
        risk = rel_err / len(rel) if rel else float("nan")
        rec = (de - rel_err) / de if de else float("nan")
        prec = sum(r["dec_err"] for r in fl) / len(fl) if fl else float("nan")
        print(f"  {m:18} {len(rel)/n:9.1%} {risk:9.1%} {rel_err:13} {rec:11.1%} {prec:10.1%}")
    for key in ("output_jump", "safer", "selfcons", "vote_disagree"):
        if ok and all(key in r["scores"] for r in ok):
            print(f"  AURC {key:13} {aurc(ok, key):.4f}")
    if ok:
        print(f"  cost: ENUM {statistics.mean(r['enum_calls'] for r in ok):.0f} extra calls/decision "
              f"(no audit: {statistics.mean(r['noaudit_calls'] for r in ok):.0f})")
    print("\n  by stratum: universe x kind x decision -> n, decision errors, ENUM coverage, ENUM released errors")
    strata = {}
    for r in ok:
        k = (r["inst"]["universe"], r["inst"]["kind"], r["inst"]["decision"])
        strata.setdefault(k, []).append(r)
    for k, rs in sorted(strata.items()):
        rel = [r for r in rs if not r["flags"]["ENUM"]]
        print(f"    {k[0]:14} {k[1]:5} {k[2]:9} n={len(rs):2}  dec_err={sum(r['dec_err'] for r in rs):2}  "
              f"coverage={len(rel)/len(rs):5.1%}  released_err={sum(r['dec_err'] for r in rel)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "qhist", "build", "calls", "baseline", "eval"])
    ap.add_argument("--mode", choices=["selfcons", "verify", "judge"])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--base-selfcons")
    ap.add_argument("--base-verify")
    ap.add_argument("--base-judge")
    ap.add_argument("--vote", nargs="*", help="other models' call files, for vote disagreement")
    ap.add_argument("--resume", action="store_true",
                    help="keep finished rows of --out; redo only API errors")
    ap.add_argument("--redo-parse", action="store_true",
                    help="with --resume, also redo rows the model failed to format")
    ap.add_argument("--max-new", type=int, default=2000, help="openrouter max_tokens")
    ap.add_argument("--limit", type=int, help="run at most N new items (dry runs only)")
    ap.add_argument("--universe")
    ap.add_argument("--backend", choices=["transformers", "ollama", "openrouter"],
                    default="transformers")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", default="S7_calls.jsonl")
    ap.add_argument("--calls")
    a = ap.parse_args()
    {"fetch": cmd_fetch, "qhist": cmd_qhist, "build": cmd_build, "calls": cmd_calls,
     "baseline": cmd_baseline, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
