# Stage-2o probe — does the tau relation survive a change of symbol universe?

Stage-2n established corr(tau, flip) = −0.890 across 12 fields, but on **one**
symbol universe: 20 US large-cap tech names. Two weaknesses followed:
(a) external validity — the relation could be a property of that sector;
(b) effective n — the 12 fields are nested accounting aggregates, so n=12
overstates the independent evidence.

This probe adds three universes (60 new symbols, 704 new observations), giving
**4 × 12 = 48 (universe, field) cells**. P1–P4 were written into
`tau_universe.py` before the new data was analysed.

| universe | composition | rationale |
|---|---|---|
| TECH | 20 US large-cap tech | Stage-2n baseline |
| FIN_HEALTH | banks, insurers, pharma, industrials | different accounting regimes |
| ENERGY_STAPLES | oil, defensive staples, logistics | commodity cycles |
| CONSUMER | Q4-heavy retail + staples + small caps | high seasonal dispersion |

## Result

| test | result | verdict |
|---|---|---|
| P1 replication in each new universe | −0.916 / −0.922 / −0.777 | **PASS (3/3)** |
| P2 seasonal-dispersion mechanism | d(tau) = **+0.157**, predicted < 0 | **FAIL** |
| P3 same slope across universes | max/min = 1.66× | PASS |
| P4 pooled, within-universe centered (n=48) | r = **−0.852**, p < 0.0001 | PASS |

Per-universe:

| universe | corr(tau, flip) | slope | mean tau | mean flip |
|---|---|---|---|---|
| TECH | −0.890 | −0.76 | 0.612 | 43.5% |
| FIN_HEALTH | −0.916 | −0.72 | 0.561 | 40.6% |
| ENERGY_STAPLES | −0.922 | −1.20 | 0.770 | 30.0% |
| CONSUMER | −0.777 | −0.80 | 0.799 | 22.7% |

**P4 is the one that matters for the paper.** Centering tau and flip within
each universe removes every universe-level confound, and the relation survives
on 48 cells at −0.852. That answers the "effective n < 12" objection from
Stage-2n: the evidence is no longer four nested accounting aggregates on one
sector.

**P3 matters more than it looks.** Four negative correlations with four
unrelated slopes would be four coincidences. Slopes within 1.66× of each other
is one mechanism appearing four times.

## P2 failed, and failing was the useful part

We predicted the CONSUMER universe — Q4-heavy retailers mixed with flat
staples — would have **lower** tau, because fy is the sum of four quarters and
tau should fall as firms differ in seasonal shape.

The opposite happened: CONSUMER has **higher** tau (0.799 vs 0.612) and
**lower** flip (22.7% vs 43.5%) than TECH.

Looking at the universe says why. It spans WMT (~$680B revenue) to WING
(~$600M) — three orders of magnitude. When items are that far apart, no
substitution can reorder them. The driver is not seasonality but **how far
apart the items are relative to how differently the substitution rescales
them**.

That reframing is derivable rather than correlational, and it became Stage-2p
(`README_margin_model.md`), which confirmed it: CONSUMER has larger item
separation (σ_q 1.53 vs 1.30) and much smaller differential rescaling
(σ_r 0.55 vs 0.98), so ρ = σ_r/σ_q is 0.43 vs 0.75.

**Do not put the seasonality story in the paper.** It was our prediction, it
was wrong, and the mechanism that replaced it is better.

## Running it

```bash
python tau_universe.py --collect     # reuses tau_expand.jsonl for TECH
python tau_universe.py --analyze
```

## Known limits

- Still one API, one discrete parameter (`period`), all US-listed.
- Universes overlap slightly (TMO in two, several consumer names in two);
  cells are not fully independent across universes.
- CONSUMER conflates two changes (sector and market cap). Fine for external
  validity, but it cannot attribute the effect to either one — Stage-2p
  resolves this by measuring σ_q directly instead of proxying it by sector.
