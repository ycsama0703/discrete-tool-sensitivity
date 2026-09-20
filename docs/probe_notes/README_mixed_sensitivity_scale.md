# Stage-2i probe — scale up + ablation of mixed sensitivity (card 3)

The Stage-2h probe (README_mixed_sensitivity.md) showed the core claim holds on
8 symbols, 1 endpoint (fundamentals), 1 discrete param (period): continuous
bound misses discrete jumps (M1/M2/M3 PASS). This probe SCALES UP and runs
ABLATIONS to find WHERE the increment comes from.

## What we scale

1. **More endpoints**: fundamentals, enterprise-value, key-metrics, owner-earnings
   (all have `period` enum: all/fy/quarter).
2. **More discrete params**: `period` (quarter/fy/all) AND `statement`
   (balance/cashflow/income) on fundamentals.
3. **Larger symbol pool**: 8 -> 20 symbols (add more large caps).

## What we ablate (increment source)

The core quantity is D_G (discrete worst-case jump) that the continuous bound
misses. We ablate to find where it comes from:

**A1 — by endpoint**: does D_G appear in fundamentals only, or across
enterprise-value / key-metrics / owner-earnings too? If only one endpoint, the
increment is endpoint-specific.

**A2 — by discrete param**: does D_G come from `period` (quarter→fy) or
`statement` (balance→cashflow)? If only period, the increment is
period-specific.

**A3 — by field**: does D_G appear in eps, revenue, net_income, operating_income
uniformly, or concentrated in some fields? If concentrated, the increment is
field-specific.

**A4 — by symbol**: is D_G present for all symbols or only some? If only some,
the increment is symbol-specific.

## Pre-registered decision rules

**S1 — increment generalizes across endpoints.** D_G (period=quarter→fy) is
non-trivial (>10%) in at least 3 of the 4 endpoints. **Kill if < 3** — the
increment is endpoint-specific.

**S2 — increment generalizes across discrete params.** Both `period` and
`statement` produce non-trivial D_G. **Kill if only one does** — the increment
is param-specific.

**S3 — increment generalizes across symbols.** D_G (period=quarter→fy) is
non-trivial (>10%) in ≥ 80% of symbols. **Kill if < 80%** — the increment is
symbol-specific.

**S4 — ablation localizes the source.** The ablation shows which endpoint/param/
field/symbol drives D_G, so the paper can claim the increment is structural
(discrete params produce jumps) not an artifact of one endpoint.

All four pass → the increment is structural and generalizes; the ablation
localizes its source.

## Running it

```bash
python build_mixed_sensitivity_scale.py --symbols <20 symbols> --out mixed_scale.jsonl
python build_mixed_sensitivity_scale.py --analyze mixed_scale.jsonl
```

No LLM, no API key. Pure findata REST calls.

## Known limits

- Tests period/statement on 4 endpoints. Other params (ticker, unit) later.
- D_G computed over enumerated neighbors, not a full semantic graph.
- Measures output jumps, not LLM behavior (generator relevance was separate).
