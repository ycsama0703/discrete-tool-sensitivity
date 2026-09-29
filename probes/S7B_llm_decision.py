"""S7-B: the LLM itself makes the decision from the returned numbers.
Design and locked predictions: docs/METHOD_EVAL_PROTOCOL.md section 1b-rev.

  python S7B_llm_decision.py run  --backend openrouter --model openai/gpt-6-luna --tag luna
  python S7B_llm_decision.py run  --backend transformers --model Qwen/Qwen2.5-7B-Instruct --tag qwen
  python S7B_llm_decision.py eval --tag luna

For every instance the model answers once per distinct table: one uniform table
per period value, the agent's own table (from S7_calls_<tag>.jsonl), a repeat of
the quarter table (self-inconsistency) and a mixed table (alternate symbols
quarter / fy). Temperature 0. Rule R-first. Output S7B_<tag>.jsonl, resumable.
"""
import argparse
import collections
import concurrent.futures as cf
import hashlib
import json
import os
import re
import statistics

import S7_decision_screen as S

HERE = os.path.dirname(os.path.abspath(__file__))
RULE = "R-first"
SYSTEM = "You are a financial analysis assistant. Answer using only the data provided."


def table_text(inst, vals):
    return "\n".join(f"{s}: {vals[s]}" for s in inst["symbols"])


def prompt(inst, vals):
    shape = ("exactly 3 tickers" if inst["decision"] == "top3"
             else "every ticker that qualifies (an empty list if none)")
    user = (f"{inst['question']}\n\nData returned by the tool (one value per company):\n"
            f"{table_text(inst, vals)}\n\nAnswer with a JSON list of {shape}, and nothing else, "
            f'e.g. ["AAA", "BBB"].')
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_answer(inst, gen):
    """Last JSON list of strings in the reply, restricted to the instance's tickers.
    None if there is no list or it names a ticker outside the instance."""
    if not gen or gen.startswith("__API_ERROR__"):
        return None
    lists = re.findall(r"\[[^\[\]]*\]", gen)
    for raw in reversed(lists):
        try:
            xs = json.loads(raw.replace("'", '"'))
        except Exception:
            continue
        if isinstance(xs, list) and all(isinstance(x, str) for x in xs):
            xs = [x.strip().upper() for x in xs]
            if all(x in inst["symbols"] for x in xs):
                return sorted(set(xs))
            return None
    return None


class Decider:
    def __init__(self, a):
        self.backend = a.backend
        if a.backend == "openrouter":
            from stageG_openrouter_ladder import ORAgent, load_key
            self.client = ORAgent(a.model, load_key(), temperature=0.0)
        elif a.backend == "transformers":
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.torch = torch
            self.tok = AutoTokenizer.from_pretrained(a.model)
            self.model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map="auto")
            self.model.eval()
        else:
            self.model_name = a.model

    def __call__(self, messages):
        if self.backend == "openrouter":
            return self.client._chat(messages, max_new=1500)
        if self.backend == "transformers":
            text = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            ids = self.tok(text, return_tensors="pt").to(self.model.device)
            with self.torch.no_grad():
                out = self.model.generate(**ids, max_new_tokens=120, do_sample=False)
            return self.tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        import urllib.request
        body = json.dumps({"model": self.model_name, "messages": messages, "stream": False,
                           "options": {"temperature": 0, "num_predict": 200}}).encode()
        req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read()).get("message", {}).get("content", "")
        except Exception as e:
            return f"__API_ERROR__ ollama: {str(e)[:80]}"


def tables(cache, inst, agent_calls):
    """condition -> {symbol: value}. None if any value is missing."""
    tool, f = S.FIELDS[inst["field"]][0], inst["field"]
    out = {}
    for p in S.PERIODS:
        out[f"uni:{p}"] = {s: S.value(cache, s, tool, p, f, RULE) for s in inst["symbols"]}
    out["mixed"] = {s: S.value(cache, s, tool, "quarter" if i % 2 == 0 else "fy", f, RULE)
                    for i, s in enumerate(sorted(inst["symbols"]))}
    if agent_calls and all(s in agent_calls and not agent_calls[s].get("parse_failed")
                           and agent_calls[s]["period"] in S.PERIODS for s in inst["symbols"]):
        out["agent"] = {s: S.value(cache, s, agent_calls[s]["tool"], agent_calls[s]["period"], f, RULE)
                        for s in inst["symbols"]}
    if any(v is None for t in out.values() for v in t.values()):
        return None
    return out


def key_of(inst, vals):
    return hashlib.md5((inst["id"] + table_text(inst, vals)).encode()).hexdigest()


def cmd_run(a):
    cache = json.load(open(S.CACHE, encoding="utf-8"))
    insts = [json.loads(l) for l in open(S.INST, encoding="utf-8")]
    if a.limit:
        insts = insts[:a.limit]
    agent = collections.defaultdict(dict)
    for l in open(os.path.join(HERE, f"S7_calls_{a.tag}.jsonl"), encoding="utf-8"):
        c = json.loads(l)
        agent[c["id"]][c["symbol"]] = c
    out_path = os.path.join(HERE, f"S7B_{a.tag}.jsonl")
    done = {}
    if os.path.exists(out_path):
        for l in open(out_path, encoding="utf-8"):
            r = json.loads(l)
            if not (r["raw"] or "").startswith("__API_ERROR__"):
                done[(r["key"], r["repeat"])] = r
    jobs = []
    for inst in insts:
        ts = tables(cache, inst, agent.get(inst["id"]))
        if ts is None:
            continue
        seen = set()
        for cond, vals in ts.items():
            k = key_of(inst, vals)
            if k not in seen:
                seen.add(k)
                jobs.append((inst, k, 0, vals))
        jobs.append((inst, key_of(inst, ts["uni:quarter"]), 1, ts["uni:quarter"]))
    todo = [j for j in jobs if (j[1], j[2]) not in done]
    print(f"{len(jobs)} distinct questions, {len(done)} kept, {len(todo)} to run", flush=True)
    if not todo:
        return
    decider = Decider(a)

    def one(job):
        inst, k, rep, vals = job
        g = decider(prompt(inst, vals))
        return dict(id=inst["id"], key=k, repeat=rep, raw=g, answer=parse_answer(inst, g))

    with open(out_path, "a", encoding="utf-8") as fo:
        if a.backend == "openrouter":
            with cf.ThreadPoolExecutor(a.concurrency) as ex:
                for i, r in enumerate(ex.map(one, todo), 1):
                    fo.write(json.dumps(r) + "\n"); fo.flush()
                    if "402" in (r["raw"] or "")[:200] and r["raw"].startswith("__API_ERROR__"):
                        raise SystemExit("payment error (402) - stopping")
                    if i % 50 == 0:
                        print(f"  {i}/{len(todo)}", flush=True)
        else:
            for i, job in enumerate(todo, 1):
                fo.write(json.dumps(one(job)) + "\n"); fo.flush()
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
    print(f"wrote {out_path}")


def cmd_eval(a):
    cache = json.load(open(S.CACHE, encoding="utf-8"))
    insts = {r["id"]: r for r in (json.loads(l) for l in open(S.INST, encoding="utf-8"))}
    agent = collections.defaultdict(dict)
    for l in open(os.path.join(HERE, f"S7_calls_{a.tag}.jsonl"), encoding="utf-8"):
        c = json.loads(l)
        agent[c["id"]][c["symbol"]] = c
    ans = {}
    for l in open(os.path.join(HERE, f"S7B_{a.tag}.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        ans[(r["key"], r["repeat"])] = None if r["answer"] is None else frozenset(r["answer"])
    rows, not_run = [], 0
    for iid, inst in insts.items():
        ts = tables(cache, inst, agent.get(iid))
        if ts is None:
            continue
        if any((key_of(inst, v), 0) not in ans for v in ts.values()):
            not_run += 1            # not (fully) run yet: skip, do not count as unparsed
            continue
        L = {c: ans.get((key_of(inst, v), 0)) for c, v in ts.items()}
        rep = ans.get((key_of(inst, ts["uni:quarter"]), 1))
        C = {c: S.decide(inst, v) for c, v in ts.items()}
        rows.append(dict(inst=inst, L=L, C=C, rep=rep, correct=f"uni:{inst['correct']}"))
    print(f"[{a.tag}] instances answered: {len(rows)}  (not yet run: {not_run})")
    unparsed = sum(v is None for r in rows for v in r["L"].values())
    print(f"  unparsed answers: {unparsed}/{sum(len(r['L']) for r in rows)}")
    ok = [r for r in rows if r["L"]["uni:quarter"] is not None and r["L"]["uni:fy"] is not None]

    # reasoning accuracy on the same table
    same = [r["L"]["uni:quarter"] == r["C"]["uni:quarter"] for r in ok]
    print(f"  LLM decision == code decision on the quarter table: {sum(same)}/{len(ok)} = {statistics.mean(same):.1%}")
    reps = [r for r in ok if r["rep"] is not None]
    print(f"  self-inconsistency (quarter table asked twice, temp 0): "
          f"{sum(r['rep'] != r['L']['uni:quarter'] for r in reps)}/{len(reps)}")

    print("\n  B-G1  flip quarter->fy:  stratum   n   code_flip  LLM_flip  |diff|")
    strata = collections.defaultdict(list)
    for r in ok:
        strata[(r["inst"]["decision"], r["inst"]["kind"])].append(r)
    agree, worst = [], 0.0
    for k, rs in sorted(strata.items()):
        cf_ = statistics.mean(r["C"]["uni:quarter"] != r["C"]["uni:fy"] for r in rs)
        lf = statistics.mean(r["L"]["uni:quarter"] != r["L"]["uni:fy"] for r in rs)
        worst = max(worst, abs(cf_ - lf))
        agree += [(r["C"]["uni:quarter"] != r["C"]["uni:fy"]) == (r["L"]["uni:quarter"] != r["L"]["uni:fy"]) for r in rs]
        print(f"        {k[0]:9} {k[1]:6} {len(rs):4}   {cf_:7.1%}   {lf:7.1%}   {abs(cf_ - lf) * 100:5.1f}")
    thr_flow = strata.get(("threshold", "flow"), [])
    tf = statistics.mean(r["L"]["uni:quarter"] != r["L"]["uni:fy"] for r in thr_flow) if thr_flow else float("nan")
    print(f"        max |diff| = {worst * 100:.1f} pp (<= 15), per-instance agreement = {statistics.mean(agree):.1%} (>= 80%), "
          f"threshold-flow LLM flip = {tf:.1%} (>= 80%)  -> "
          f"{'PASS' if worst <= 0.15 and statistics.mean(agree) >= 0.8 and tf >= 0.8 else 'FAIL'}")

    tk = [r for r in ok if r["inst"]["decision"] == "top3" and r["inst"]["kind"] == "flow" and r["L"]["mixed"] is not None]
    if tk:
        f = lambda src, c: statistics.mean(r[src][c] != r[src]["uni:quarter"] for r in tk)
        print(f"\n  B-G2  top-3 flow (n={len(tk)}): flip vs quarter table -- "
              f"code: fy {f('C', 'uni:fy'):.1%}, mixed {f('C', 'mixed'):.1%};  "
              f"LLM: fy {f('L', 'uni:fy'):.1%}, mixed {f('L', 'mixed'):.1%}  -> "
              f"{'PASS' if f('C', 'mixed') > f('C', 'uni:fy') and f('L', 'mixed') > f('L', 'uni:fy') else 'FAIL'}")

    # ENUM-B: re-ask the model on every class table (uniform tables), release iff all equal the agent-table answer
    print("\n  ENUM-B (H-B1, H-B3):")
    for label, subset in (("all intents", ok), ("period unstated", [r for r in ok if r["inst"]["intent"] == "ambiguous"])):
        ev = [r for r in subset if "agent" in r["L"] and all(r["L"][c] is not None for c in r["L"])]
        rel = [r for r in ev if len({r["L"][f"uni:{p}"] for p in S.PERIODS} | {r["L"]["agent"]}) == 1]
        param_err = [r for r in rel if r["L"]["agent"] != r["L"][r["correct"]]]
        reason_err = [r for r in rel if r["L"][r["correct"]] != r["C"][r["correct"]]]
        all_param = sum(r["L"]["agent"] != r["L"][r["correct"]] for r in ev)
        print(f"    {label:16} evaluable {len(ev):3}  released {len(rel):3} ({len(rel) / max(len(ev), 1):.1%})  "
              f"param-induced errors released {len(param_err)} (of {all_param} overall) -> "
              f"{'PASS' if not param_err else 'FAIL'};  reasoning errors among released {len(reason_err)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "eval"])
    ap.add_argument("--backend", choices=["openrouter", "transformers", "ollama"], default="openrouter")
    ap.add_argument("--model")
    ap.add_argument("--tag", required=True, help="S7 call file tag: S7_calls_<tag>.jsonl")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, help="first N instances only (smoke test)")
    a = ap.parse_args()
    cmd_run(a) if a.cmd == "run" else cmd_eval(a)


if __name__ == "__main__":
    main()
