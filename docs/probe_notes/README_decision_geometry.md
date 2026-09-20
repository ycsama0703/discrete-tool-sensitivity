# Stage-2q probe — decision geometry: which quantity is right depends on the decision

Stage-2p showed the flip condition for ORDER decisions contains no absolute
magnitude, which read as though D_G — and hence the mixed bound S_mix — is
simply the wrong quantity, superseded by our own second result.

That over-claimed. An absolute-threshold decision ("is revenue above $10B?")
turns on whether the substitution pushes an item across a fixed constant,
which depends on the **common** rescaling. Absolute magnitude is exactly right
there, and ρ — being scale-free — should be blind to it.

## The decomposition

Write `log r = μ_r + deviation`, where `r_s = f_s / q_s`:

- **μ_r = mean(log r)** — the common rescaling every item receives. This is
  what the output jump measures.
- **σ_r = stdev(log r)** — the differential rescaling.

Then, with σ_q the item separation:

| decision family | governing quantity | why |
|---|---|---|
| order (top-k, pairwise, rank-median) | **ρ = σ_r / σ_q** | common rescaling cancels in a comparison |
| absolute threshold ("> T") | **κ = \|μ_r\| / σ_q** | common rescaling is the entire effect |

C1–C4 were written into `decision_geometry.py` before running, including what
a failed crossover would force the paper to concede.

## Result — the crossover (48 cells)

| predictor | order decisions | threshold decisions |
|---|---|---|
| **ρ = σ_r/σ_q** | **+0.791** | +0.377 |
| **κ = \|μ_r\|/σ_q** | **−0.028** | **+0.908** |
| jump (output magnitude, ≈ D_G) | −0.050 | **+0.861** |

Spearman agrees (ρ: +0.837 / +0.385; κ: +0.026 / +0.917), and the crossover
survives within-universe centering (ρ→order +0.755, κ→threshold +0.922,
κ→order +0.038).

| test | result | verdict |
|---|---|---|
| C4 ρ and κ separable | corr(ρ, κ) = +0.169 | PASS |
| C1 ρ owns order | +0.791 vs κ's −0.028 | PASS |
| C2 κ owns threshold | +0.908 vs ρ's +0.377 | PASS |
| C3 crossover | both directions | **PASS** |

κ is essentially **zero** on order decisions (−0.028). That is not a weak
predictor, it is the correct prediction: a common rescaling cannot reorder
anything, so the quantity that measures it must carry no signal about
reordering.

## What this does to the paper

The two results stop competing and become one taxonomy. The continuous bound
is wrong for **both** families — a discrete swap has ε=0, so it reports zero
whatever the agent is deciding — while each of the other two quantities is
right for exactly one:

| | order decision | threshold decision |
|---|---|---|
| continuous Lipschitz bound (L·ε) | **0 — false safety** | **0 — false safety** |
| mixed bound S_mix / D_G | wrong quantity (−0.05) | **right (+0.86)** |
| margin ratio ρ | **right (+0.79)** | wrong quantity (+0.38) |

S_mix is no longer a middle step we supersede ourselves. It is the correct
instrument for threshold decisions, and ρ is the correct instrument for order
decisions. The contribution is knowing **which one the agent needs**, and that
the certification in use today supplies neither.

## Known limits

- Both quantities are multiplicative, so 16/48 cells drop non-positive items.
- The thresholds T are set at the 25/50/75th percentile of the **base**
  (quarter) distribution and then held fixed across the substitution. They are
  constants once chosen, which is the point — but they are calibrated from the
  item set rather than drawn from a real agent's rulebook. A rule like
  "revenue > $10B" that sits far outside the item range would give a flip rate
  near 0 and carry no signal; our thresholds sit where decisions are live.
- ρ's +0.377 on threshold decisions is not zero. σ_r and μ_r are not fully
  independent in this data (corr(ρ, κ) = +0.169), and fields with large
  differential rescaling also tend to have some common drift.
- Order family here is four ranking tasks on 12–20 items. Decisions with a
  different shape again — budget allocation, set selection under a constraint
  — are untested and may need a third quantity.
