# Stage-2m probe — verify the tau hypothesis (card 3)

The multi-decision probe (Stage-2l) found decision-flip is general but uneven
across fields: eps/net_income flip hard, revenue barely flips. This probe tests
the hypothesis that explains the unevenness:

**Hypothesis**: a discrete substitution flips a decision iff it reshuffles the
RELATIVE ranking. If the ranking is preserved (high Kendall tau between quarter
and fy), decisions don't flip even with large jumps; if the ranking reshuffles
(low tau), decisions flip.

## Result

| field | tau (quarter vs fy) | flip rate |
|---|---|---|
| eps | +0.421 | 59.7% |
| net_income | +0.568 | 54.5% |
| operating_income | +0.737 | 35.8% |
| revenue | +0.853 | 23.4% |

**corr(tau, flip_rate) across fields = −0.980 → CONFIRMED.**

A near-perfect monotone relation: higher tau (more stable ranking) → lower flip
rate. revenue has the highest tau (0.853) and lowest flip (23.4%); eps the
lowest tau (0.421) and highest flip (59.7%).

Symbol-level is weaker: corr(rank_delta, in_flipped_top3) = +0.25. A single
symbol's rank instability does not strongly predict whether it lands in a
flipped top-3. The field-level relation is the strong one.

## What this means

This upgrades the story from "observe that decisions flip" to "predict which
decisions flip":

- Variant A's D4 was a NEGATIVE result: output jump does NOT predict decision
  flip (corr −0.12).
- Tau is a POSITIVE result: rank-correlation DOES predict decision flip
  (corr −0.98).

This gives the screener a cheaper signal than enumeration: instead of
enumerating all neighbors (expensive), compute tau (cheap); low tau → the
decision is fragile → flag it.

## The theoretical claim (now testable)

**Decision-flip rate ≈ monotone decreasing in the rank-correlation (Kendall
tau) between the discrete neighbors.** A tool/parameter/field with high tau
across its discrete options is decision-robust; low tau is decision-fragile.

This connects to the core thesis: the continuous bound certifies output
stability (L·ε), but decision safety is governed by rank stability (tau), which
the continuous bound does not measure. The mixed bound S_mix covers the output
jump D_G; tau governs whether that jump reaches a decision.

## Running it

```bash
python verify_tau.py --in mixed_scale.jsonl
```

## Known limits

- 4 fields, 1 API (findata), 1 parameter (period). External validity across
  APIs/params is future work.
- Field-level n=4 is small; the −0.98 is suggestive, not powered.
- Symbol-level tau→flip is weak; the mechanism is at the field/ranking level.
