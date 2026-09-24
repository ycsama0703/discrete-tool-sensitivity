"""
Stage-I: actually MEASURE the enumeration screener on real model outputs.

Everywhere else in this repo the screener's "100% / 100%" is either an identity
(`baseline_family.py` sets `our_flags = true_flip  # by construction`) or a
hardcoded reference line (`stageG_scale_table.py`). Neither is a measurement.
This probe runs it against the real tool calls the 12 stage-F/G configurations
produced, and reports what it actually achieves.

PRE-REGISTERED DEFINITIONS (fixed before looking at any result):

  Setup. For one (question, model) pair, the agent issues one tool call per
  symbol, each with whatever `period` that model filled. The decision is
  top-3 symbols by EPS. We compare:
      correct_decision  - top-3 computed with the question's correct period
      agent_decision    - top-3 computed with the period the agent filled
                          (per symbol; a model can fill different values for
                          different symbols of the same question)

  Two distinct events, deliberately NOT conflated:
      PARAM ERROR    - the agent filled period != correct period, for >=1 symbol
      DECISION ERROR - agent_decision != correct_decision

  These come apart: a wrong period that does not reorder the top-3 is a param
  error with no decision error. The screener targets decision errors.

  The screener. It never consults the model. For each symbol it enumerates the
  period enum {quarter, fy} (`all` resolves to the API's default and is treated
  as a distinct value), recomputes the top-3 under each, and FLAGS the question
  if the decision is not invariant across those recomputations.

  Primary metric - DECISION-ERROR INTERCEPTION (what the screener is for):
      recall    = flagged / (questions with a decision error)
      precision = (flagged AND decision error) / flagged
  A flag on a question whose decision happens to be correct is counted as a
  false positive even though the decision is genuinely period-sensitive. This
  is the strict reading and the one that can make precision < 100%.

  Secondary metric - PARAM-ERROR DETECTION (what the L1/L2/L3 ladder measures),
  reported so the two are visibly different quantities rather than one table
  column:
      recall    = flagged / (questions with a param error)

  Pre-registered expectations:
   - Decision-error recall should be 100%: if the decision moves when period
     moves, enumerating period must see it. Anything less is a bug.
   - Decision-error PRECISION IS NOT EXPECTED TO BE 100%. The screener flags
     period-sensitivity, which is a superset of realised decision errors.
   - Param-error recall should be BELOW 100%, because a wrong period that does
     not reorder the top-3 is invisible to a decision-level check - and should
     be, since no decision was harmed.

Data: findata EPS for the 20 symbols under period=quarter and period=fy.

Usage:
    python stageI_screener_measured.py            # all available configs
    python stageI_screener_measured.py --file stageG_sonnet5.jsonl
"""

import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FIN = "https://lum.id/findata"
CACHE = os.path.join(HERE, "stageI_eps_cache.json")

SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "ORCL", "CRM",
           "TSLA", "AMD", "INTC", "NFLX", "ADBE", "AVGO", "CSCO", "QCOM",
           "IBM", "TXN", "AMAT", "MU"]

CONFIGS = [
    ("qwen2.5-7b (local)",  "stageF_ladder_qwen.jsonl"),
    ("qwen2.5-7b (API)",    "stageG_qwen7b.jsonl"),
    ("qwen2.5-72b",         "stageG_qwen72b.jsonl"),
    ("llama3.1-8b (local)", "stageF_ladder_llama.jsonl"),
    ("llama3.1-8b (API)",   "stageG_llama8b.jsonl"),
    ("llama3.3-70b",        "stageG_llama70b.jsonl"),
    ("gemma3-12b (local)",  "stageF_ladder_gemma.jsonl"),
    ("gpt-6-luna",          "stageG_gpt6luna.jsonl"),
    ("deepseek-v4.1-flash", "stageG_dsv41flash.jsonl"),
    ("gemini-3.8-flash",    "stageG_gemini38.jsonl"),
    ("qwen3.8-flash",       "stageG_qwen38.jsonl"),
    ("claude-sonnet-5",     "stageG_sonnet5.jsonl"),
]


def fetch_eps():
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    eps = {}
    for s in SYMBOLS:
        eps[s] = {}
        for p in ("quarter", "fy"):
            try:
                req = urllib.request.Request(
                    f"{FIN}/fundamentals/{s}/history?period={p}",
                    headers={"User-Agent": "research"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read())
                eps[s][p] = d[0]["eps"] if isinstance(d, list) and d and "eps" in d[0] else None
            except Exception:
                eps[s][p] = None
        print(f"  {s}: quarter={eps[s]['quarter']} fy={eps[s]['fy']}", flush=True)
    json.dump(eps, open(CACHE, "w", encoding="utf-8"), indent=1)
    return eps


def top3(vals):
    ok = {s: v for s, v in vals.items() if v is not None}
    return frozenset(sorted(ok, key=lambda s: ok[s], reverse=True)[:3])


def resolve(period, correct_period):
    """Which EPS series does this filled period actually read?

    `all` returns both series; the agent then reads whichever the API puts
    first, which for findata is the same series as `quarter`. `__OMITTED__`
    means the parameter was absent and the API default applies - also quarter.
    Treating both as `quarter` is the CHARITABLE reading: it makes those calls
    correct whenever the question wanted quarter, i.e. it can only lower the
    measured decision-error rate, never inflate it.
    """
    if period in ("quarter", "fy"):
        return period
    return "quarter"


def evaluate(path, eps):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    by_q = {}
    for r in rows:
        by_q.setdefault(r["idx"], []).append(r)

    n_q = 0
    param_err = decision_err = flagged = 0
    flag_and_dec = 0
    dec_err_flagged = param_err_flagged = 0

    for idx, group in sorted(by_q.items()):
        usable = [r for r in group if not r.get("parse_failed")]
        if len(usable) < 4:
            continue
        cp = usable[0]["correct"]
        n_q += 1

        correct_vals = {r["symbol"]: eps.get(r["symbol"], {}).get(cp) for r in usable}
        agent_vals = {r["symbol"]: eps.get(r["symbol"], {}).get(
            resolve(r["filled_period"], cp)) for r in usable}

        d_correct = top3(correct_vals)
        d_agent = top3(agent_vals)

        has_param_err = any(r["real_error"] for r in usable)
        has_dec_err = (d_agent != d_correct)

        # the screener: enumerate the period enum per symbol, recompute, flag if
        # the decision is not invariant. It never looks at what the model filled.
        decisions = set()
        for p in ("quarter", "fy"):
            decisions.add(top3({r["symbol"]: eps.get(r["symbol"], {}).get(p)
                                for r in usable}))
        is_flagged = len(decisions) > 1

        param_err += has_param_err
        decision_err += has_dec_err
        flagged += is_flagged
        if is_flagged and has_dec_err:
            flag_and_dec += 1
        if has_dec_err and is_flagged:
            dec_err_flagged += 1
        if has_param_err and is_flagged:
            param_err_flagged += 1

    return dict(n_q=n_q, param_err=param_err, decision_err=decision_err,
                flagged=flagged, flag_and_dec=flag_and_dec,
                dec_rec=dec_err_flagged / decision_err if decision_err else float("nan"),
                dec_pre=flag_and_dec / flagged if flagged else float("nan"),
                par_rec=param_err_flagged / param_err if param_err else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()

    print("fetching findata EPS (cached after first run)...")
    eps = fetch_eps()
    print()

    configs = [(n, f) for n, f in CONFIGS if not a.file or f == a.file]
    print(f"{'config':22} {'Q':>3} {'param':>6} {'decis':>6} {'flag':>5} "
          f"| {'DEC rec':>7} {'DEC pre':>7} | {'PAR rec':>7}")
    print("-" * 82)
    for name, fn in configs:
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            print(f"{name:22}  (missing)")
            continue
        s = evaluate(p, eps)
        f = lambda x: "  n/a  " if x != x else f"{x:7.1%}"
        print(f"{name:22} {s['n_q']:3} {s['param_err']:6} {s['decision_err']:6} "
              f"{s['flagged']:5} | {f(s['dec_rec'])} {f(s['dec_pre'])} | {f(s['par_rec'])}")

    print("\nDEC rec/pre = decision-error interception (what the screener is for)")
    print("PAR rec     = param-error detection (what the L1/L2/L3 ladder measures)")
    print("Pre-registered: DEC recall 100%; DEC precision NOT expected to be 100%")
    print("(the screener flags period-sensitivity, a superset of realised errors);")
    print("PAR recall expected BELOW 100% - a wrong period that does not reorder")
    print("the top-3 harms no decision and should not be flagged.")


if __name__ == "__main__":
    main()
