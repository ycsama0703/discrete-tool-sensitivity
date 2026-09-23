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
agent generates a tool call, add one active self-verification step:

```
financial question
  -> agent generates a tool call (period = quarter/fy/all)     [D1, stage D]
  -> if period != correct: a discrete error occurred
  -> ACTIVE self-verification: ask the agent
       "Does period=X correctly answer the request? The request asks for the
        Y figure. Answer yes or no."
     where X = the period the agent filled, Y = the correct period
  -> record whether the agent says "no" (detects its own error)
  -> compare: self-verification detection rate vs enumeration screener (100%)
```

The self-verification prompt is deliberately *leading*: it tells the agent the
correct period Y. This is the most favorable possible setup for the internal
detector — if it still fails with the answer handed to it, the failure is
robust. (A reviewer can't object "you didn't give the model enough info".)

### Metrics

- **Detection rate** = fraction of real-error calls where self-verification
  says "no" (flags the error). Compare to enumeration screener = 100%.
- **False-alarm rate** = fraction of correct calls where self-verification
  says "no" (spurious flag). A good detector should be ~0.

### Pre-registered verdicts

- **F6 PASS (paper's claim strengthened)** if detection rate is well below
  the screener's 100% — e.g. < 50%. The internal detector (dependent on the
  failing binding capability) is not a reliable substitute for external
  enumeration.
- **F6 FAIL (paper's claim weakened)** if detection rate is high (≥ 90%):
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
