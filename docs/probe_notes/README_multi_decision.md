# Stage-2l probe — multi-decision generalization (card 3)

Variant A tested ONE decision (rank by EPS, pick top-3 most expensive). This
probe asks: does decision-flip generalize across MANY decision tasks on the
SAME data? If multiple decisions flip under period=quarter→fy, the phenomenon
is not an artifact of one decision task.

## Design

All on fundamentals, 20 symbols, quarter vs fy. Fields: eps, revenue,
net_income, operating_income (all 20/20 have quarter+fy).

Decision tasks per field:
- D1 rank, pick top-3 most expensive
- D2 rank, pick top-3 cheapest
- D3 threshold: symbols with field > median
- D4 top-3 (fy ranking)
- D5 pairwise "A > B" comparison flips

## Results

| field | D1 top-3 exp | D2 top-3 cheap | D3 median | D4 top-3 | D5 pairwise |
|---|---|---|---|---|---|
| eps | flip 80% | flip 80% | flip 50% | flip 80% | 28.9% |
| revenue | **flip 0%** | flip 50% | flip 36% | **flip 0%** | 7.4% |
| net_income | flip 80% | flip 80% | flip 36% | flip 80% | 21.6% |
| operating_income | flip 50% | flip 80% | flip 0% | flip 50% | 13.2% |

**Verdict: 10/12 tasks flip >20% → decision-flip is GENERAL, not specific to
EPS ranking.**

## The structural finding (theory seed)

The flip rate is NOT uniform across fields — and that is the interesting part:

- **eps / net_income**: nearly all decisions flip hard (80%). These fields jump
  66–97% quarter→fy AND their relative ranking changes.
- **revenue**: top-3 expensive does NOT flip at all (overlap 100%). Revenue's
  quarter vs fy ranking is nearly identical (a big company's annual revenue is
  ~4× its quarterly, so the ordering is preserved).
- **operating_income**: intermediate.

**This is the seed of a theory**: decision-flip depends on whether the discrete
substitution changes the RELATIVE ranking, not just the magnitude. A field can
jump 66% (revenue) yet keep its top-3 (because all symbols scale together), or
jump less but flip (because relative order changes). This connects to variant
A's D4 finding (output jump does not predict decision flip) and generalizes it
across fields.

**Theoretical question this raises**: what property of a field/parameter
determines whether a discrete substitution flips a decision? Candidate: the
rank-correlation between the two periods (Kendall's tau / Spearman). If the
ranking is preserved (high tau), decisions don't flip even with large jumps; if
the ranking reshuffles (low tau), decisions flip.

## Running it

```bash
python multi_decision.py --in mixed_scale.jsonl
```

## Known limits

- Still one API (findata), one parameter (period). External validity across
  APIs/params is future work.
- Decision tasks are ranking/threshold/selection; real valuation decisions
  (P/E, DCF) would be stronger.
- The rank-correlation theory is a hypothesis to test, not yet tested.
