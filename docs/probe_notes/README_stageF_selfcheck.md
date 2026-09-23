# Stage-F probe — active self-verification as a detector of discrete parameter errors

**Status: DESIGNED (script written, not yet run).** This is the "why not just
have the LLM check itself?" baseline — the first objection a reviewer raises
against the enumeration screener. We give the SAME agent that filled the wrong
`period` the chance to verify its own tool call, and measure whether it catches
the error.

## Why this is the most valuable baseline

1. **It is the obvious alternative.** "Why not just ask the LLM to check its
   own call?" is the first question a reviewer asks. Without this baseline the
   paper leaves it unanswered.
2. **It is likely to fail, and the failure is the point.** The agent fills the
   wrong `period` because of a *binding* defect (stage A: binding is
   insufficient on ambiguous input). Self-verification depends on the SAME
   binding capability — the agent must bind "quarter" to the question's intent
   to know its own `period=quarter` call was wrong. If binding is the failing
   step, the detector that depends on it fails too. **The internal detector
   cannot reliably diagnose a failure of the very capability the diagnosis
   depends on.**
3. **It is cheap.** Reuses the stage D agent framework; one extra generation
   per call.

## Literature grounding (verified before designing — per the "search before
simulate, judge by method section" rule)

- **SilentProbe** (2609.00035, method verified): measures silent failure in
  production APIs used as agent tools. **Detection is passive/spontaneous** —
  the agent is never asked to verify; detection = retrying after a zero-row
  response. Result: models detected the failure in **12%**, repaired **0%**,
  asserted a false negative **41%**, invented a figure **12%**. F6 is the
  *active* version of SilentProbe's passive detection, on our top-3 decision
  task.
- **SelfCheckGPT** (2303.08896, method verified): self-consistency — sample
  multiple responses, flag divergence. Detects *inconsistency*, not
  *incorrectness*: an agent that always fills the wrong period is consistent,
  so self-consistency misses it. (We chose active self-verification over
  self-consistency for this reason.)
- **Reflexion** (2303.11366, method verified): agent verbally reflects on its
  own outputs. F6's active self-verification is the tool-call-parameter
  instance of this family.

## Design

Reuse stage D's agent loop (20 symbols × 20 questions, 3 models). After the
agent generates a tool call, run **three self-verification ladder levels** on
the SAME call, so the three levels are compared on the same set of errors:

```
financial question
  -> agent generates a tool call (period = quarter/fy/all)     [D1, stage D]
  -> if period != correct: a discrete error occurred
  -> L1 VALUE COMPARISON: tell the agent the correct period, ask "is X right?"
       "Does period=X correctly answer the request? The request asks for the
        Y figure. Answer yes or no."  (X = filled, Y = correct)
  -> L2 SEMANTIC JUDGMENT: only replay what the agent filled, no correct answer
       "Review your call. Is period=X the correct period for this request?
        Answer yes or no."
  -> L3 ERROR LOCALIZATION: an external screener flagged the call but did NOT
       say which parameter is wrong
       "An external screener flagged your call as possibly wrong, but it did
        NOT tell you which parameter. Which parameter (symbol, statement,
        period) is wrong? Answer: symbol, statement, period, or none."
  -> record whether each level flags the error
  -> compare each level's detection vs enumeration screener (100%)
```

### Why a ladder (three difficulty levels)

Different self-verification forms are not equally hard for the model. Making
them a ladder isolates *which* capability fails:

- **L1 (value comparison)** is the easiest: the correct period is handed to the
  model, so it only compares values (`all` != `quarter`). High detection here
  proves nothing about real self-diagnosis.
- **L2 (semantic judgment)** is the "fair" version: no correct answer is given,
  so the model must judge from its own understanding whether its period matches
  the question — the same binding capability it used to fill the parameter.
- **L3 (error localization)** is the hardest and the most deployment-realistic:
  an external screener flags the call (as our enumeration screener would), but
  the model must identify *which* parameter is wrong. This tests whether the
  model can localize an error it is told exists — "even if the model knows
  something is wrong, it may not identify what is wrong."

L3 mirrors the paper's screener scenario: the screener flags, the agent
localizes. If the model cannot localize the period error, the internal detector
is not a substitute for external enumeration.

### Metrics (recall + precision per level)

For each ladder level, report both — a detector that flags everything is
trivially high-recall but useless:

- **Recall (detection rate)** = of real-error calls, how many the level flags.
  Compare to enumeration screener = 100%.
- **Precision** = of calls the level flags, how many are real errors (1 −
  false-alarm rate). A good detector should be ~100% (few false alarms).

### Pre-registered verdicts

- **F6 PASS (paper's claim strengthened)** if the harder levels (L2, L3) have
  recall well below the screener's 100% — e.g. < 50%. The internal detector
  (dependent on the failing binding capability) is not a reliable substitute
  for external enumeration.
- **F6 FAIL (paper's claim weakened)** if L2/L3 recall is high (≥ 90%): then
  the LLM can self-diagnose, and the screener's advantage is only convenience,
  not necessity.
- Report precision regardless — a detector that flags everything is trivially
  "high recall" but useless.
  then the LLM can self-diagnose, and the screener's advantage is only
  convenience, not necessity.
- Report false-alarm rate regardless — a detector that flags everything is
  trivially "high recall" but useless.

## Expected result (to be measured)

Detection rate low (binding defect present at check time), enumeration
screener 100%. A clean contrast: **internal detection (depends on the failing
binding) vs external enumeration (does not depend on binding)**.

## What this does NOT claim

- One decision task (top-3 by EPS), one parameter (period), 3 models. External
  validity limited.
- Self-verification might do better with a different prompt, a stronger model,
  or chain-of-thought. We report the leading-prompt result; the point is the
  *contrast* with the screener, not an absolute "self-check never works".

## Files

- `probes/stageF_selfcheck.py` — the probe (script written, not yet run)
- `probes/stageF_selfcheck.jsonl` — results (to be produced)
- this note
