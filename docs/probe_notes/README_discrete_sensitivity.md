# Stage-2f probe — discrete tool-call sensitivity (card 3, 09-16-MECH-AI-3)

Minimal test of card 3's Phase-0 precondition: **does findata's discrete tool
parameters (period, unit, ticker) produce output jumps that a continuous
sensitivity bound (Lipschitz) cannot cover?**

Card 3's claim: financial agent tool parameters are DISCRETE (ticker, period,
accounting basis, unit). A one-token change can jump from a correct call to
another schema-valid call. Continuous sensitivity certification (Lipschitz
bound L·ε) assumes the error lies in a continuous neighborhood — but a discrete
parameter substitution has ε=0 in the continuous space, so L·ε=0 and the bound
cannot cover the output jump.

Budget: **$0** (no LLM; pure API calls + schema analysis).

## The core quantity

For a tool call x = (c, z) where c is continuous (dates, thresholds) and z is
discrete (ticker, period, unit):

- **continuous bound**: S_cont(ε) = sup_{||c'-c||≤ε} d_Y(f(c',z), f(c,z)) ≈ L·ε
- **discrete jump**: D_G = max_{z'∈N_G(z)} d_Y(f(c,z'), f(c,z))

The claim: for a discrete substitution z→z', the continuous bound gives ε=0
(no continuous change), so S_cont(0)=0, but D_G can be large. The continuous
bound MISSES the discrete error.

## What we test

For findata's fundamentals/earnings endpoints, construct canonical calls and
enumerate discrete neighbors:

| substitution | example | expected output jump |
|---|---|---|
| **period** | Q1 → Q2 (same year) | large (different quarter's EPS) |
| **period** | single-quarter → YTD | large (YTD vs single quarter) |
| **unit** | dollars → millions | large (scale difference) |
| **ticker** | AAPL → MSFT | large (different company) |

For each, execute the original and the neighbor, compute d_Y (relative
difference in the returned value). Check whether a continuous bound (ε=0 for
discrete change) could cover the jump.

## Pre-registered decision rules

**D1 — discrete jumps exist.** A non-trivial fraction of discrete substitutions
produce large output jumps (d_Y > threshold). **Kill if < 50%** — then discrete
parameters don't cause meaningful output changes.

**D2 — continuous bound misses them.** For discrete substitutions, the
continuous bound (ε=0) gives S_cont(0)=0, which cannot cover the observed jump.
This is structural (discrete change has no continuous representation), but we
verify the jump is real (not a schema error). **Kill if jumps are explained by
schema/type errors** (i.e. the "discrete error" is just a malformed call).

**D3 — schema-valid.** The discrete neighbors are schema-valid (the API accepts
them without error). **Kill if < 80% are schema-valid** — then the "legal
discrete substitution" premise fails.

All three pass → card 3's Phase-0 precondition holds: findata's discrete
parameters produce output jumps that continuous sensitivity misses.

## Running it

```bash
python build_discrete_sensitivity.py --symbols AAPL,MSFT,NVDA,GOOGL,AMZN,META,ORCL,CRM
python build_discrete_sensitivity.py --analyze discrete_sensitivity.jsonl
```

No LLM, no API key. Pure findata REST calls.

## Known limits

- Tests period/unit/ticker substitutions on fundamentals/earnings. Other
  endpoints and parameter types (accounting basis) are later.
- Measures output jumps, not whether an LLM actually makes these errors
  (generator relevance is a later step).
- The "continuous bound misses it" is partly structural (discrete change has
  ε=0); we verify the jump is real and schema-valid.
