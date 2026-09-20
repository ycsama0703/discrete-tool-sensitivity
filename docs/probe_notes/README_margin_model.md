# Stage-2p probe — the margin model: why tau predicts decision flip

Stage-2o killed our seasonality explanation of tau (P2 failed, in the opposite
direction). The universe that broke it — CONSUMER, spanning WMT at ~$680B
revenue to WING at ~$600M — suggested the real driver: when items are three
orders of magnitude apart, no substitution can reorder them.

That reframing is **derivable**, not correlational.

## Derivation

Let `q_s` be the value under the base parameter, `f_s` under the discrete
neighbour, and `r_s = f_s / q_s` the per-item rescaling the substitution
induces. For an ordered pair (a, b) with `q_a > q_b`:

```
f_a > f_b  <=>  r_a·q_a > r_b·q_b
           <=>  log r_a − log r_b  >  −(log q_a − log q_b)
```

Writing `U = Δlog q` (item separation) and `V = Δlog r` (differential
rescaling), the pair **flips iff |V| > |U| with opposite sign**:

> A discrete substitution flips a decision exactly when its **differential**
> effect exceeds the **decision margin**.

The absolute jump size never enters the condition — only its dispersion
relative to item separation. This is the precise sense in which the quantity
the continuous bound measures is the wrong one.

If `U ~ N(0, 2σ_q²)` and `V ~ N(0, 2σ_r²)` independent, then
`P(|V| > |U|) = (2/π)·arctan(σ_r/σ_q)`, so with **ρ = σ_r / σ_q**:

```
pairwise flip rate = (1/π)·arctan(ρ)
Kendall tau        = 1 − (2/π)·arctan(ρ)
```

**tau and flip are two projections of the same quantity ρ.** That is why tau
predicts flip at −0.89: an identity plus noise, not an empirical accident.

## Result (48 cells = 4 universes × 12 fields)

| test | result | verdict |
|---|---|---|
| M1 identity `tau = 1 − 2·pflip` | mean err **0.0000**, max 0.0010 | PASS |
| M2 closed form `(1/π)arctan(ρ)` | MAE **3.16pp**, corr(pred, obs) +0.877 | PASS |
| M3 ρ beats output jump | corr(ρ, flip) **+0.851** vs corr(jump, flip) **+0.110** | PASS |
| M4 explains the P2 reversal | d(ρ) = **−0.323** for CONSUMER−TECH | PASS |

M1 is near-definitional and only checks the pipeline. M2 is the substantive
test — it could have failed if log-ratios were heavy-tailed, and largely did
not.

### M4 — ρ explains what seasonality could not

| universe (flow fields) | σ_q (separation) | σ_r (rescaling) | ρ | flip |
|---|---|---|---|---|
| TECH | 1.30 | 0.98 | **0.75** | 46.8% |
| FIN_HEALTH | 0.81 | 0.48 | 0.58 | 41.9% |
| ENERGY_STAPLES | 0.80 | 0.36 | 0.46 | 29.3% |
| CONSUMER | 1.53 | 0.55 | **0.43** | 21.5% |

CONSUMER items are *more* separated (σ_q 1.53 vs 1.30) and rescaled *far more
uniformly* (σ_r 0.55 vs 0.98), so the same class of substitution reorders
fewer of them. Monotone in ρ across all four universes.

## What changes in the paper

The tau extension was an empirical regularity: "flip rate is monotone
decreasing in tau, corr −0.89." It is now a **mechanism with a closed form**:

- **Condition (exact)**: a decision flips iff `|Δlog r| > |Δlog q|` — the
  substitution's differential rescaling exceeds the decision margin.
- **Rate (under a Gaussian approximation)**: `flip = (1/π)·arctan(ρ)`,
  `ρ = σ_r/σ_q`, fitting to 3.16pp MAE across 48 cells.
- **tau is a corollary**, not a separate finding: `tau = 1 − 2·flip`.
- **Why the continuous bound is the wrong instrument**: it measures |Δ| in
  output space. The flip condition contains no absolute magnitude at all —
  only a ratio of dispersions. A bound on output magnitude is not merely loose
  here, it is measuring a quantity that does not appear in the condition.

## The D4 claim, resolved

Three numbers for `corr(jump, flip)` now exist, and the paper must use the
right one:

| scope | corr(jump, flip) |
|---|---|
| D4, per-instance, TECH | −0.12 |
| Stage-2n, per-field, TECH only (n=12) | +0.43 |
| Stage-2p, per-cell, 4 universes (n=48) | **+0.11** |

The +0.43 was a single-universe artifact. Across four universes output jump is
essentially uninformative (+0.11) while ρ reaches +0.851. The original D4
intuition was right; Stage-2n's caveat was over-cautious. **Report the n=48
number and show all three** — the spread across scopes is itself evidence that
output magnitude is an unstable predictor.

## Running it

```bash
python margin_model.py     # reads tau_universe.jsonl
```

## Known limits

- The margin model is multiplicative, so it needs positive values: **16/48
  cells drop some non-positive items** (loss-making quarters, negative
  fcf_yield). tau on the full item set differs from tau on the positive subset
  by 0.031 on average. Fields with many negatives (net_income in downturns)
  are under-represented.
- The Gaussian closed form is an approximation. Worst cells are CONSUMER
  fcf_yield (−17.7pp) and TECH eps (−10.7pp), both heavy-tailed — observed
  flip exceeds predicted, so the formula is *anti-conservative* exactly where
  decisions are most fragile. A screener should use the exact condition, not
  the arctan formula.
- `σ_q` is a property of the item set the agent happens to be comparing, so ρ
  is query-dependent — a feature for screening (it is computable per query),
  but it means there is no single ρ per tool or per field.
- Still one API, one discrete parameter, US-listed equities only.
