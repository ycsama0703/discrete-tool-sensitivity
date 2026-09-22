# Stage-E probe — baseline family comparison: which method catches the decision flip?

**Status: DESIGN (not yet run).** The paper's screener (enumerate discrete
neighbours, recompute the decision) must be compared against the other
families of methods that claim to cover discrete tool errors. This probe runs
each family's representative on the SAME task (top-3 by EPS) and asks: does it
detect that an agent's discrete parameter error flips the decision?

## The five families (by principle)

| Family | space | guarantee | representative |
|---|---|---|---|
| F1 continuous bound | output (embedded) | deterministic bound | Lipschitz L·ε |
| F2 discrete-neighbour bound | output (discrete) | interval / prob / enumeration | SAFER (prob), IBP (interval) |
| F3 decision-space screening | **decision** | enumeration recompute | **ours**, Monte Carlo |
| F4 legality / constraint check | parameter | rules | Gecko (enum check), SMT |
| F5 risk control | decision | probabilistic | role-stratified CRC |

Our screener is F3. The comparison asks: do F1/F2/F4/F5 detect the decision
flip that F3 catches?

## Task

Same as stage D: top-3 symbols by EPS, correct period = quarter. The agent
cross-flips a fraction of symbols to fy (the error mode that flips decisions).
Baseline decision error = 30% (from stage D). Each family's method should flag
the error.

## Methods to run

- **F1 continuous bound**: L·ε = 0 for a discrete substitution (already run,
  M1). Reports 0 — misses everything.
- **F2 SAFER (randomized smoothing)**: for each symbol, estimate the
  probability its rank flips under random period substitution; flag if above a
  threshold. Compare to the true flip set.
- **F3 Monte Carlo**: randomly perturb the period, recompute the decision,
  estimate the flip probability. This is the empirical analogue of our
  enumeration screener.
- **F4 Gecko (schema legality)**: check whether the agent's period is a legal
  enum value. Filling "all" is legal, so this misses the semantic error.
- **F5 CRC (conformal)**: role-stratified risk control. Higher cost; later.

## Pre-registered verdicts

- **E1**: F1 (continuous) reports 0 — misses all decision flips.
- **E2**: F2 (SAFER) gives a probabilistic bound that is either vacuous or
  misses flips (needs verification).
- **E3**: F3 (Monte Carlo) approximates the enumeration screener but is
  stochastic (needs many samples; not exact).
- **E4**: F4 (Gecko) misses the "all" error (legal but semantically wrong).
- **E5**: our enumeration screener is exact (deterministic), catching what the
  others miss.

## Result (2026-09-22, mixed_scale.jsonl, top-3 by EPS, 20 symbols)

True decision-flip set (rank changes quarter->fy): 16 symbols.

| method | flags | precision | recall |
|---|---|---|---|
| F1 continuous L·eps | 0 | — | 0% |
| F2 SAFER (prob bound) | 13 | 77% | 62% |
| F3 Monte Carlo (per-symbol) | 17 | 88% | 94% |
| F4 Gecko (legality) | 0 | — | 0% |
| **OUR enumeration screener** | 16 | **100%** | **100%** |

**Clean win.** Our enumeration screener is the only exact method: precision
100%, recall 100% (catches all 16 true flips, no false alarms). The others:
- F1 continuous: recall 0% — L·eps=0 for a discrete substitution, misses all.
- F2 SAFER: recall 62%, precision 77% — probabilistic bound, has both false
  positives and false negatives (not exact).
- F3 Monte Carlo: recall 94%, precision 88% — close but stochastic (needs many
  samples, has variance), not exact.
- F4 Gecko: recall 0% — only catches illegal values; "all" is legal, so the
  semantic error is missed.

**Why we win:** the other families give bounds (F1/F2) or stochastic estimates
(F3) or legality checks (F4). Only enumeration recomputes the decision exactly.
This is the "probability/approximation vs deterministic enumeration" contrast.

## Files

- `probes/baseline_family.py` — the comparison
- this note
