# Stage-2h probe — mixed sensitivity S_mix vs continuous bound (card 3)

The core contribution of card 3: continuous sensitivity certification (Lipschitz
bound L·ε) cannot cover DISCRETE tool-parameter errors, because a discrete
substitution (period=quarter → fy) has ε=0 in continuous space, so L·ε=0. The
mixed sensitivity S_mix(ε) = L_G·ε + D_G explicitly adds the discrete worst-case
jump D_G and covers them.

This probe compares, on findata's fundamentals endpoint:
- **continuous bound**: L·ε (ε=0 for discrete change) — should MISS discrete jumps
- **mixed bound**: L_G·ε + D_G — should COVER discrete jumps
- **empirical Monte Carlo**: random parameter perturbation — reference

Budget: **$0** (pure findata API calls, no LLM).

## The core quantities

For a tool call x = (c, z) with continuous part c and discrete part z:

- **continuous bound**: S_cont(ε) = sup_{||c'-c||≤ε} d_Y(f(c',z), f(c,z)) ≈ L·ε
- **discrete jump**: D_G = max_{z'∈N_G(z)} d_Y(f(c,z'), f(c,z))
- **mixed bound**: S_mix(ε) = L_G·ε + D_G

The claim: for a discrete substitution z→z', the continuous bound gives ε=0
(no continuous change), so S_cont(0)=0, but D_G can be large. The mixed bound
S_mix captures D_G.

## What we test

For findata's `/fundamentals/{symbol}/history` with discrete param `period`
(quarter/fy/all):

1. Construct canonical calls (period=quarter, correct).
2. Enumerate discrete neighbors (period=fy, period=all).
3. Compute output jump d_Y for each neighbor (relative diff in eps/revenue).
4. Compute:
   - continuous bound: L·ε with ε=0 → 0 (misses discrete jump)
   - mixed bound: D_G = max discrete jump → covers it
   - empirical: the actual observed jump
5. Compare coverage.

## Pre-registered decision rules

**M1 — continuous bound misses discrete jumps.** For discrete substitutions,
the continuous bound (ε=0) gives 0, which is < the observed jump. **Kill if
continuous bound covers the jumps** (i.e. observed jump ≤ L·ε for some
continuous ε) — then the "continuous misses discrete" claim fails.

**M2 — mixed bound covers them.** S_mix = D_G (at ε=0) ≥ observed jump for the
discrete neighbors. **Kill if D_G < observed jump** — then the mixed bound is
too loose/tight to be useful.

**M3 — mixed bound is tighter than naive.** The mixed bound (D_G) is tighter
than a naive "delete all docs" or "worst-case over everything" bound, i.e. it
doesn't just blow up to cover everything. **Kill if D_G is unboundedly large**
(no screening value).

All three pass → card 3's core claim holds: continuous bound misses discrete
jumps, mixed bound covers them tightly.

## Running it

```bash
python build_mixed_sensitivity.py --symbols AAPL,MSFT,NVDA,GOOGL,AMZN,META,ORCL,CRM
python build_mixed_sensitivity.py --analyze mixed_sensitivity.jsonl
```

No LLM, no API key. Pure findata REST calls.

## Known limits

- Tests period substitution on fundamentals. Other params (statement, ticker,
  unit) later.
- D_G is computed over the enumerated neighbors (quarter/fy/all), not a full
  semantic graph. A fuller graph is later work.
- Measures output jumps, not whether an LLM makes them (generator relevance
  was a separate probe).
