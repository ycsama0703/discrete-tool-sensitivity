# Stage-2n probe — tau hypothesis at scale (card 3)

Stage-2m (`verify_tau.py`) found corr(tau, flip_rate) = −0.98 across **4**
fundamentals fields. n=4 cannot distinguish a mechanism from a coincidence.
This probe expands to every findata field carrying both quarter and fy values.

**Scope**: 12 fields × 20 symbols × 3 endpoints = 240 observations, $0, no
models (tau is a property of the data, not of model behaviour).

Predictions H1–H5 were written into `tau_expand.py` before the expanded data
was analysed, including what each failure mode would force the paper to say.

## Field table

| field | endpoint | kind | tau | flip | output jump |
|---|---|---|---|---|---|
| eps | fundamentals | flow | +0.305 | 64.1% | 59.9% |
| fcf_yield | key-metrics | flow | +0.526 | 55.0% | 78.9% |
| net_income | fundamentals | flow | +0.537 | 54.9% | 58.0% |
| market_cap | enterprise-value | stock | +0.568 | 42.9% | 39.7% |
| cash_and_short_term | enterprise-value | stock | +0.589 | 42.6% | 30.7% |
| enterprise_value | enterprise-value | stock | +0.589 | 42.6% | 38.2% |
| ebitda | fundamentals | flow | +0.663 | 41.7% | 63.4% |
| operating_income | fundamentals | flow | +0.663 | 41.7% | 63.1% |
| total_debt | enterprise-value | stock | +0.684 | 33.9% | 29.1% |
| gross_profit | fundamentals | flow | +0.695 | 45.4% | 65.5% |
| revenue | fundamentals | flow | +0.747 | 24.7% | 63.5% |
| current_ratio | key-metrics | stock | +0.779 | 32.8% | 9.9% |

## Result

| test | statistic | verdict |
|---|---|---|
| H1 corr(tau, flip), n=12 | **−0.890** | PASS |
| H2 within fundamentals (n=6) | −0.894 | PASS |
| H2 within enterprise-value (n=4) | −0.987 | PASS |
| H2 flow fields (n=7) / stock fields (n=5) | −0.896 / −0.950 | PASS |
| H3 Spearman(tau, flip) | −0.845 | PASS |
| H4 partial corr(tau, flip \| jump) | **−0.881** | PASS |
| H5 permutation test, 20k shuffles | p = 0.0001 | PASS |

The relation attenuated from −0.98 (n=4) to −0.890 (n=12), which is what an
honest expansion of a small-n estimate should do. It did not collapse.

**H2 is the load-bearing one.** The obvious confounder was that tau merely
separates field *families* — flow quantities (which accumulate over a period)
from stock quantities (point-in-time snapshots). If so, the correlation would
vanish inside each family. It does not: −0.896 within flow, −0.950 within
stock, −0.894 within a single endpoint. tau ranks fields *within* a family,
not just between families.

**H4 rules out the cheap explanation.** tau and output jump are only weakly
related (r = −0.313), and holding jump fixed leaves tau's relation with flip
essentially untouched (−0.890 → −0.881). tau is not a repackaged jump.

## The contrast pair

Two rows make the paper's point without any statistics:

- `revenue` — output jump **63.5%**, decision flip **24.7%**
- `current_ratio` — output jump **9.9%**, decision flip **32.8%**

A field whose value moves by two-thirds flips fewer decisions than a field
whose value barely moves. Output magnitude is the wrong quantity to watch;
rank stability is the right one.

## Honest correction to the D4 claim

D4 (variant A) reported corr(jump, flip) = **−0.12** and we described output
jump as not predicting decision flip. At the **field** level this probe finds
corr(jump, flip) = **+0.432**, and jump retains a weak independent
contribution after controlling for tau (partial +0.354).

These are different units of analysis — D4 correlated per-instance jumps,
this correlates per-field mean jumps — and both can be true. But the paper
must not claim jump carries *no* information. The defensible claim is the
comparative one: **tau predicts decision flip far better than output jump
does (−0.89 vs +0.43), and tau's predictive power survives controlling for
jump while the converse mostly does not.**

## Running it

```bash
python tau_expand.py --collect --out tau_expand.jsonl
python tau_expand.py --analyze tau_expand.jsonl
```

## Known limits

- 12 fields is the ceiling for this API: `key-metrics` returns `None` for
  pe/pb/ps/ev_ebitda/ev_revenue/debt_to_equity/quick_ratio/roe/roa, and
  `owner-earnings` returns an empty array for `period=fy`. Not a collection
  bug — verified against the raw endpoint.
- One API, one discrete parameter (`period`), one symbol universe (20 US
  large-cap tech). Cross-API external validity remains future work, and the
  symbol set is narrow enough that a different universe is the next check.
- The `statement` parameter is excluded: its neighbours expose disjoint field
  sets, so there is no common ranking to correlate.
- Field-level n=12 with 20k permutations gives p = 0.0001, but the 12 fields
  are not independent (revenue/gross_profit/operating_income/ebitda are
  nested accounting aggregates), so the effective n is smaller than 12 and
  the p-value is optimistic.
