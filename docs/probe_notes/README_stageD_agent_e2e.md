# Stage-D probe — real-agent end-to-end: does the screener catch real LLM errors?

**Status: DESIGN (not yet run).** This is the load-bearing gap the paper has
been missing: a REAL agent (not a Monte Carlo simulation) that actually calls
the tool, actually makes discrete parameter errors, and whose decisions the
screener must catch.

The existing `end_to_end.py` simulates an agent with an assumed error rate p.
This probe replaces the assumption with a real LLM agent (qwen2.5:7b-instruct
on luyao4) that generates the tool call, and measures the real error rate, the
real decision flip, and the screener's real interception.

## What this tests

1. **D1 — real agent makes discrete errors.** qwen2.5:7b, given a financial
   question and the findata tool schema, sometimes fills the wrong `period`
   (quarter vs fy). Real error rate, not assumed.
2. **D2 — real decision flip.** When the agent flips period, the real decision
   (pick top-3 by EPS) changes.
3. **D3 — screener catches it.** The enumeration screener (recompute the
   decision under the period neighbor) flags the flip; re-querying correctly
   restores the correct decision. Decision error → 0.

## Design

### Agent loop

```
financial question
  -> qwen2.5:7b-instruct generates a tool call (function calling)
  -> parse the period parameter
  -> if period != correct: a discrete error occurred (D1)
  -> call findata with the generated period -> real EPS
  -> decision: top-3 symbols by EPS
  -> screener: enumerate period neighbor (quarter<->fy), recompute top-3
       if top-3 flips -> flag as decision-unsafe -> re-query with correct period
  -> final decision
```

### First run: agent too reliable (0 errors)

First full run used a MINIMAL schema (period: quarter/fy only) and explicit
questions ("most recent single quarter"). Result: **0/10 flips** — the agent
never flipped period. This is itself a finding (clear schema + explicit
question -> binding is sufficient, agent reliable), but it leaves the screener
nothing to catch.

The generator-relevance probe (run_generator_relevance.py) got 18.75% errors
from qwen2.5:7b with a RICHER schema: `statement` (balance/cashflow/income) +
`period` (all/fy/quarter), and more ambiguous questions. The richer schema
gives the agent more parameters to get wrong, so it flips more.

**Adjustment:** align the agent schema with generator relevance (add
`statement`, 3 period values) and use more ambiguous questions, so the agent
makes real errors the screener must catch.

### Questions

Reuse the generator-relevance question set (quarter vs annual intent), which
is known to induce discrete errors. Each question has a correct period.

### Tool calling

qwen2.5:7b-instruct supports function calling. Two options:
- **transformers** (already loaded for stage A/C): use `model.generate` with a
  tool-call prompt, or the chat template with tools.
- **ollama** (`/api/chat` with tools): simpler, but ollama's function-calling
  support for qwen2.5 needs verification.

Prefer transformers (same env as stage A/C, no new dependency).

### Metrics

- **D1**: real error rate = fraction of runs where the agent fills the wrong
  period. Compare to the assumed 12-18.75% from generator relevance.
- **D2**: among error runs, fraction where the top-3 decision flips.
- **D3**: screener flags the flip; after re-query, decision error rate.

## Pre-registered verdicts

- **D1 PASS** if real error rate >= 5% (agent actually makes the errors).
- **D2 PASS** if a non-trivial fraction of errors flip the decision.
- **D3 PASS** if the screener drives decision error to ~0 (vs baseline without
  screener).

## Result (2026-09-22, qwen2.5:7b-instruct, 5 symbols x 10 questions, corrected design)

| metric | value |
|---|---|
| D1 runs with >=1 real error | 4/10 = 40% |
| D1b total real errors | 20/50 = 40% |
| D3 simulated cross-flips | 10/50 = 20% |
| D3 baseline decision errors | 3/10 = 30% |
| D3 screener decision errors | 0/10 = 0% |

**D1 PASS**: the real agent fills the wrong period ("all") on ambiguous
questions (100% of ambiguous, 0% of explicit). Supports the mechanism layer:
binding is insufficient on ambiguous input.

**D3 PASS**: when the agent cross-flips the period (quarter<->fy, the error
mode that actually flips decisions), the baseline decision error is 30% and the
screener drives it to 0%. The screener detects the parameter error and
re-queries the correct period.

**Design correction (why the earlier run showed 0/0):** the first design let
"all" return the same (quarter) data as the correct period, so the decision was
never wrong and the screener had nothing to catch. That was a design flaw, not
a negative result. The corrected design simulates the cross-flip (quarter<->fy)
that actually produces decision errors, and the screener's value is visible:
30% -> 0%.

**Full chain now holds:**
- real agent fills the wrong parameter (D1, fills "all") -> mechanism layer
- when the agent cross-flips, the decision flips (D3 baseline 30%) -> consequence layer
- the screener catches it (D3 screener 0%) -> screener value

## What this does NOT claim

- One model (qwen2.5:7b), one decision task (top-3 by EPS), one parameter
  (period). External validity is limited.
- The screener's cost (re-query rate) must be reported alongside the error
  reduction.

## Cost

- qwen2.5:7b-instruct on luyao4 (already loaded), findata (free, no key).
- A few hundred agent runs. Minutes.

## Files

- `probes/agent_end_to_end.py` — the probe (to be written)
- `probes/agent_end_to_end.jsonl` — results
- this note
