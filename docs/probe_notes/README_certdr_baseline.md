# Stage-2r probe — prior ranking certificates under a common-mode perturbation

CertDR (Wu et al., CIKM 2022, arXiv:2209.06691) certifies top-K robustness of
neural rankers under word substitution, and at first reading it occupies our
claim: it is a margin condition for ranking under discrete substitution. This
probe checks whether its **perturbation model** matches ours, by running it as
a baseline on our 48 cells.

## What its method section actually says

- **Def 3.1** `S_d := {d' : ||d'-d||_0/||d|| <= delta}` — indexed by a
  **single document**, built only from that document's own words' synonym sets.
- **Def 3.2** *"for all d in L_q[K+1:], and any d' in S_d"* — each document
  **separately**; a universal quantifier over documents, not a joint
  perturbation of the list.
- **Thm 4.1** applied to each document **independently**; `o_d` is a
  per-document quantity.
- **Prop 4.2** `gap(d_K, d_{K+1}) - max_d o_d > 0`, a **union bound**: every
  candidate may move by its own budget, independently, in the worst direction.
- Threat model: an adversary promoting one target document. **Documents
  already ranked 1..K are excluded from attack.**

Our perturbation is not of that shape. One parameter substitution
(`period=quarter -> fy`) moves **every** item at once, including the
incumbents, and the movements are strongly correlated: with `r_s = f_s/q_s`,
the common factor `exp(mean(log r))` is shared by all items and cancels in
every comparison.

## Results (48 cells, K=3, per-item budgets set to the EXACT deviation)

| | certified | of the 14 genuinely-stable cells |
|---|---|---|
| CertDR criterion, literal | 1/48 (2.1%) | — |
| union bound, repaired for moving incumbents | **2/48 (4.2%)** | 2/14 (14.3%) |
| same bound on the common-mode quotient | 3/48 (6.2%) | 3/14 (21.4%) |
| *actual* top-3 flips | 34/48 changed, **14 stable** | |

| test | verdict |
|---|---|
| B1 union bound is vacuous (<20%) | PASS (4.2%) |
| B2 vacuity is model mismatch, not severity | PASS (+25.0pp) |
| B3 quotient recovers cells | PASS **but by one cell only** |
| B4 quotient certificate is sound | PASS (0 false certificates) |

### B1/B2 are the real findings

The union bound certifies **2 of 48** cells. That is not because the decisions
are fragile: **14 cells are genuinely stable** and the bound proves it for 2 of
them. It fails on the other 12 not because they flip — they do not — but
because it charges every item its full movement independently while the
movement is mostly common mode. The median `o_quot/o_union` is 0.518, so about
**half** of the budget the union bound charges cannot reorder anything.

### B0 — a precise statement about validity, not a gotcha

CertDR's criterion exempts the incumbents from attack. Our substitution moves
them, so its guarantee **does not transfer** to this setting. But on this data
it produced **zero** false certificates, simply because it certifies almost
nothing (1/48). This is an **assumption mismatch**, and must be reported as
such — not as an empirical demonstration of unsoundness.

### B3 is weak and should not be leaned on

Quotienting the common mode out is exactly order-preserving, hence sound
(B4: zero false certificates), but it recovers **one** additional cell
(2 -> 3). Honest reading: a worst-case bound is the wrong instrument here
whatever we do to it, because the worst case over a correlated perturbation is
dominated by the single most-rescaled item, and one such item is enough to
destroy the bound even when the ranking is untouched. The right object is the
**rate**, which is what rho gives (Stage-2p: corr(rho, flip) = +0.851).

**Do not write "we fix CertDR."** The defensible claim is narrower and more
interesting: *worst-case ranking certificates are near-vacuous under
common-mode perturbation, for a structural reason, and a distributional
predictor is the appropriate replacement.*

## What this settles about positioning

CertDR is a **baseline**, not an occupier. The difference is not framing, it is
the perturbation geometry:

| | CertDR | ours |
|---|---|---|
| what is perturbed | each document's text | one call parameter |
| across candidates | independent, per-document `o_d` | common-mode, correlated |
| incumbents | exempt from attack | moved too |
| neighbourhood | guessed synonym set | schema enum, exhaustive, tiny |
| threat | adversary promoting a document | the agent's own wrong enum |
| output | worst-case certificate | flip **rate** |

The per-document independence in Def 3.1/3.2 is precisely what makes their
aggregation a union bound, and precisely what our setting violates.

## Running it

```bash
python certdr_baseline.py     # reads tau_universe.jsonl
```

## Known limits

- Our instantiation normalises scores to [0,1] by `max(q)`. CertDR's `f̄` is a
  smoothed relevance score already in [0,1]; the mapping is a choice and a
  different normalisation changes the absolute certification rate (though not
  the union-vs-quotient ordering).
- We hand the bound the **exact** per-item deviation. Real CertDR computes an
  upper bound from synonym overlap, so a faithful port would certify even less.
  This is deliberately generous.
- K=3 only; 16/48 cells drop non-positive items for the quotient's logarithm.
- We did not re-implement randomized smoothing. This compares the certificate's
  **aggregation structure**, which is what the mismatch is about, not its
  base-ranker machinery.
