# References

Every work touched during the three literature sweeps (2026-09-20/21), grouped
by the role it plays in the paper.

**Verification marks — treat these as binding:**

- ✅ **I read the method section / definitions myself.** Safe to characterise.
- ◐ **I read the intro or §1 myself**, not the method section.
- ○ **From a search summary only.** May be mischaracterised, and the venue or
  year may be wrong. **Verify before citing.**
- ⛔ **Do not cite.** Could not be verified at all, or the claim attributed to
  it could not be found.

---

## 1. Direct baseline — ranking certificates

| | ref | why it matters |
|---|---|---|
| ✅ | **CertDR** — Wu, Zhang, Guo, Chen, Fan, de Rijke, Cheng. *Certified Robustness to Word Substitution Ranking Attack for Neural Ranking Models.* CIKM 2022. [arXiv:2209.06691](https://arxiv.org/abs/2209.06691) | **The baseline.** Def 3.1 `S_d := {d' : ‖d'−d‖₀/‖d‖ ≤ δ}` is per-document; Def 3.2 quantifies over documents separately; Thm 4.1 applies per-document; Prop 4.2 is a **union bound**; threat model **exempts incumbents** ("documents already ranked 1..K are excluded from attack"). Run as a baseline in probe `certdr_baseline.py`. Its conclusion flags **top-K internal ordering** as open. |
| ✅ | Liang, Soloff, Barber, Willett. *Assumption-free stability for ranking problems.* [arXiv:2506.02257](https://arxiv.org/abs/2506.02257) | Perturbs the **dataset**, treats margin as an assumption to **escape**, output is **set-valued** (inflated top-k). No closed-form flip probability. Not a competitor; cite for why we pay a distributional assumption. |
| ○ | Jia, Cao, Wang, Gong. *Certified Robustness for Top-k Predictions.* ICLR 2020. [arXiv:1912.09899](https://arxiv.org/abs/1912.09899) | top-k certification, but ℓ₂ / continuous radius. |
| ○ | *Almost Tight L0-norm Certified Robustness of Top-k Predictions.* [arXiv:2011.07633](https://arxiv.org/abs/2011.07633) | **discrete (ℓ₀) × top-k closed the loop in 2020.** Refutes any "ranking under discrete perturbation is unexplored" claim. |
| ○ | Jia, Liu, Hu, Gong. *PORE: Provably Robust Recommender Systems against Data Poisoning.* USENIX Security 2023 | top-k recommendation certification. |
| ○ | **RobustMask.** [arXiv:2512.23307](https://arxiv.org/abs/2512.23307) | CertDR follow-up; drops the synonym-table assumption; still **membership**, not internal order. |
| ○ | Soloff, Barber, Willett. *Building a stable classifier with the inflated argmax.* [arXiv:2405.14064](https://arxiv.org/abs/2405.14064) | explicit margin selection rule, assumption-free. |
| ○ | Oyarhoseini, Lin, Karimi. *A Unified Perturbation Framework for Leaderboard Stability and Manipulation.* [arXiv:2605.15761](https://arxiv.org/abs/2605.15761) | Bradley–Terry leaderboards, influence functions, Kendall τ. Empirical baseline on the ranking side. |
| ○ | Dede, Kamalakis, Sphicopoulos. *Theoretical estimation of the probability of weight rank reversal in pairwise comparisons.* EJOR 252(2), 2016 | **closed-form rank-reversal probability** (multivariate normal, AHP). The precedent for a closed-form flip rate. Not citing it would look like we do not know the MCDM literature. |

## 2. Foundations we stand on (cite as inheritance, never as ours)

| | ref | what we inherit |
|---|---|---|
| ○ | **Cronbach, Gleser, Nanda, Rajaratnam.** *The Dependability of Behavioral Measurements.* 1972. / **Brennan.** *Generalizability Theory.* 2001 | **σ²δ (relative decisions) vs σ²Δ (absolute decisions), differing exactly by facet MAIN EFFECTS.** This is §2.4b's decision geometry, 54 years early. **Not citing it risks a desk-reject-level objection.** Write "we transfer", never "we show". |
| ○ | Demmel & Veselić 1992; **Ipsen.** *Relative perturbation results for matrix eigenvalues and singular values.* Acta Numerica 7 (1998); Ren-Cang Li, *Relative Perturbation Theory I–IV* | **Multiplicative perturbation ⇒ RELATIVE gap governs stability**, established 1992–2000. Our log-scale margin condition is this. |
| ○ | Pham-Gia et al. (2006), ratio distributions; Fieller's theorem | The arctan closed form needs the ratio's components **centred and uncorrelated**. **Our own data violates this** (mean \|corr(log q, log r)\| = 0.399; 12/48 cells > 0.5). Cite when scoping the closed form. |
| ○ | Kim et al. *The Lipschitz Constant of Self-Attention.* ICML 2021. [arXiv:2006.04710](https://arxiv.org/abs/2006.04710) | where the continuous machinery comes from |
| ○ | Castin, Ablin, Peyré. *How Smooth Is Attention?* ICML 2024. [arXiv:2312.14820](https://arxiv.org/abs/2312.14820) | same; theory on compact subsets of ℝᵈ |

## 3. Discrete-substitution certification (mature — cite as known premise)

| | ref | note |
|---|---|---|
| ✅ | Jia, Raghunathan, Göksel, Liang. *Certified Robustness to Adversarial Word Substitutions.* EMNLP 2019. [arXiv:1909.00986](https://arxiv.org/abs/1909.00986) | IBP. Median **10³¹** perturbations per IMDB example — the canonical "enumeration does not scale". **Our inversion: schema enums give \|S\| ≈ 3.** |
| ○ | Huang, Stanforth, Welbl, Dyer, Yogatama, Gowal, Dvijotham, Kohli. *Achieving Verified Robustness to Symbol Substitutions via IBP.* EMNLP 2019. [arXiv:1909.01492](https://arxiv.org/abs/1909.01492) | Argues **interval boxes are too loose for text** — i.e. our layer-1 critique, 2019. |
| ◐ | Ye, Gong, Liu. **SAFER.** ACL 2020. [arXiv:2005.14424](https://arxiv.org/abs/2005.14424) | Randomized smoothing. **Thm 1 bounds output deviation, Prop 1 converts it to a decision-flip criterion** — the standard two-step our S_mix reproduces. |
| ○ | Zeng et al. **RanMASK.** Computational Linguistics 49(2), 2023. [arXiv:2105.03743](https://arxiv.org/abs/2105.03743) | Drops the "defender knows the attacker's synonym table" assumption. **The critique our schema-exhaustive neighbourhood is immune to** — say so explicitly. |
| ○ | Zhang et al. **Text-CRS.** IEEE S&P 2024. [arXiv:2307.16630](https://arxiv.org/abs/2307.16630) | unified certification of discrete text operations |
| ◐ | Kumar, Agarwal, Srinivas, Li, Feizi, Lakkaraju. *Certifying LLM Safety against Adversarial Prompting.* COLM 2024. [arXiv:2309.02705](https://arxiv.org/abs/2309.02705) | erase-and-check, genuinely enumerative. **Its intro has the best three-step objection-handling passage in the corpus** (admit → argue it shouldn't be done → give empirical evidence anyway). |
| ◐ | Xiang, Wu et al. *Certifiably Robust RAG.* [arXiv:2405.15556](https://arxiv.org/abs/2405.15556) | isolate-then-aggregate; **entirely discrete** budget (integer k′), no metric-space argument. Best example of concrete deployment stakes via product names + sourced incidents. |
| ○ | **LipsLev** — Abad Rocamora, Chrysos, Cevher. *Certified Robustness Under Bounded Levenshtein Distance.* ICLR 2025. [arXiv:2501.13676](https://arxiv.org/abs/2501.13676) | **⚠️ THE COUNTER-EXAMPLE.** Defines Lipschitz constants w.r.t. **Levenshtein distance**. Forbids us from ever writing "Lipschitz presupposes continuity". |
| ○ | *Hybrid Randomized Smoothing.* ICML 2026. [arXiv:2605.12876](https://arxiv.org/abs/2605.12876) | unifies mixed discrete–continuous inputs; same caution as above |
| ○ | Casadio, Dinkar, Komendantskaya et al. *NLP Verification: Towards a General Methodology for Certifying Robustness.* Eur. J. Applied Mathematics, 2026. [arXiv:2403.10144](https://arxiv.org/abs/2403.10144) | names the **"embedding gap"**. The canonical citation for layer 1 as a known premise. |
| ○ | *The King is Naked.* [arXiv:2112.07605](https://arxiv.org/abs/2112.07605) | ε-ball robustness is "linguistically inconsistent" for discrete input |
| ○ | *CluCERT.* AAAI 2026. [arXiv:2512.08967](https://arxiv.org/abs/2512.08967) | clustering-denoised smoothing |
| ○ | Li, Xie, Li. *SoK: Certified Robustness for Deep Neural Networks.* IEEE S&P 2023 | the field has an SoK — evidence of maturity |

## 4. Agent-side certification

| | ref | note |
|---|---|---|
| ◐ | **LLMCert-T / CATS** — Yeon, Chaudhary, Singh (UIUC). *Quantitative Certification of Agentic Tool Selection.* [arXiv:2510.03992](https://arxiv.org/abs/2510.03992) | **The paper to continue, not attack.** Certifies **tool selection**, not argument values; tools are metadata-only. Clopper–Pearson, not norm balls. **⚠️ self-verify these two quotes before citing**: "tool metadata is discrete text and JSON schemas with **no natural perturbation radius**" and "**has no ℓp analogue**". Its §"why a certificate" paragraph is our B4 template. |
| ○ | Rahman et al. *Beyond Aggregate Risk: Role-Stratified Conformal Risk Control for LLM Tool Calls.* [arXiv:2607.24343](https://arxiv.org/abs/2607.24343) | Stratifies by **consequence severity**; we stratify by **decision geometry**. Owe the reader one example where the two disagree. |
| ○ | Ghitu & Wicker. *Towards Poisoning Robustness Certification for NLG.* [arXiv:2602.09757](https://arxiv.org/abs/2602.09757) | certifies tool-calling validity but against **training-time poisoning** |
| ○ | Winston, Winston, Just. *Solver-Aided Verification of Policy Compliance in Tool-Augmented LLM Agents.* [arXiv:2603.20449](https://arxiv.org/abs/2603.20449) | SMT constraints over tool arguments — a **precondition check**, not a robustness certificate |
| ○ | *Gecko.* [arXiv:2602.19218](https://arxiv.org/abs/2602.19218) | OpenAPI schema as source of truth; deterministic rule checks incl. **enum**. Empirical, **no certificate**. Closest "schema-aware" baseline. |
| ○ | *Agent-Sentry.* [arXiv:2603.22868](https://arxiv.org/abs/2603.22868) | allowlists only "groundable" parameters from finite pools; free text excluded. **Someone has already drawn this boundary.** |
| ✅ | **SelfCheckGPT.** Manakul, Liusie, Gales. [arXiv:2303.08896](https://arxiv.org/abs/2303.08896) | **Verified (method).** Self-consistency: sample multiple responses, flag divergence. The canonical "internal consistency" detector. **Limitation for us**: detects *inconsistency*, not *incorrectness* — an agent that always fills the wrong period is consistent, so self-consistency misses it. F6's contrast. |
| ✅ | **Reflexion.** Shinn et al. [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) | **Verified (method).** Agent verbally reflects on its own outputs (external or internally simulated feedback). The "self-reflection" family. F6's active self-verification is the tool-call-parameter instance of this. |
| ○ | *Self-Verification.* Weng et al. [arXiv:2302.06692](https://arxiv.org/abs/2302.06692) | self-verification improves reasoning by re-checking; candidate F6 anchor — **verify method section before citing** |

## 5. Layer-1 targets — continuous machinery transplanted onto discrete fields

All three were verified at the method-section level by a search agent. **I have
not opened them myself. Verify before citing.**

| | ref | the transplant |
|---|---|---|
| ○ | *Self-Adaptive Multi-Agent LLM-Based Security Pattern Selection for IoT.* [arXiv:2605.00741](https://arxiv.org/abs/2605.00741) | Eq.(1) `S̃ₜ = Sₜ + δₜ, ‖δₜ‖ ≤ Δ` over a 7-tuple whose **four fields are discrete**. The norm is **never specified**, Δ is **never assigned a value**, and addition is **undefined** on those fields. The cleanest instance. |
| ○ | **HalluGuard.** ICLR 2026. [arXiv:2601.18753](https://arxiv.org/abs/2601.18753) | Assumption A2 declares an edit-distance → ℓ2 `L_Φ`-Lipschitz bridge; **`L_Φ` never appears again** in Prop 3.1, Thm 3.2, or the scoring equation. The bridge is **assumed, not established**. |
| ○ | *Harnessing non-adversarial robustness in LLMs.* [arXiv:2605.29816](https://arxiv.org/abs/2605.29816) | Theory needs a continuous density-domination condition; experiments feed **discrete text edits** (Unicode confusables, typos). |
| ⛔ | Du, Chan. *LLMs in the Loop: A Stability- and Network-Aware Survey.* eess.SY, 2026-09-15. [arXiv:2609.16599](https://arxiv.org/abs/2609.16599) | Source of "**hallucinations as bounded disturbances**" and the best framing citation — **but only abstract-level evidence exists; no HTML, PDF unreadable. Verify the quote before using it.** |

## 6. Agent empirical benchmarks (nearest neighbours — treat as baselines)

| | ref | note |
|---|---|---|
| ◐ | **ToolRobustBench.** [arXiv:2608.23635](https://arxiv.org/abs/2608.23635) | **Nearest neighbour.** Already has `argument binding` as its own stage plus cascade-aware attribution separating self-generated argument errors from upstream contamination. 15,456 instances × 7 models. Finds **tool-output perturbation is the main bottleneck**. Its Limitations section is the model for ours (separates transferable *principles* from environment-specific *numbers*). |
| ◐ | *More Vulnerable than You Think.* [arXiv:2506.21967](https://arxiv.org/abs/2506.21967) | **Parameter-level numbers already published**: parameter hallucinations drop success **>12%**, tool-selection **<8%**; "agents tend to **blindly trust** the erroneous response … parameter hallucinations **derail the entire tool-using process**". **Also the confound**: missing *parameter* descriptions hurt more than missing *tool* descriptions — we must control schema-description quality or a reviewer will say we measured schema quality, not discreteness. |
| ○ | *AgentDojo.* [arXiv:2406.13352](https://arxiv.org/abs/2406.13352) | |
| ○ | *AgentProp-Bench.* [arXiv:2604.16706](https://arxiv.org/abs/2604.16706) | parameter-level injection propagates to a wrong final answer with prob ≈ 0.62 |
| ✅ | *SilentProbe.* [arXiv:2609.00035](https://arxiv.org/abs/2609.00035) | **Verified (method section).** Measures silent failure in production APIs used as agent tools. **Detection is passive/spontaneous, not self-check**: the agent is never asked to verify; detection = retrying with a different value after a zero-row response. Result: models detected the failure in **12%**, repaired **0%**, asserted a false negative **41%**, invented a figure **12%**. This is our F6's *passive* cousin — F6 is the *active* self-verification version. **Avoid "silent" in our naming**, it collides. |
| ✅ | *Butterfly Effects in Toolchains.* [arXiv:2507.15296](https://arxiv.org/abs/2507.15296) | **Verified (abstract).** Taxonomy of failed parameter filling in tool-agent chains: 5 failure categories derived from the invocation chain (e.g. parameter name hallucination), 15 input perturbation methods. A **classification**, not a detector — cite for failure attribution, not for a detection mechanism. |
| ○ | *From Allies to Adversaries.* [arXiv:2412.10198](https://arxiv.org/abs/2412.10198) | adversarial injection into tool calls |
| ○ | *ReliabilityBench.* [arXiv:2601.06112](https://arxiv.org/abs/2601.06112) | |

## 7. Finance agent reliability (B1 material and the de-trading playbook)

| | ref | how it establishes stakes |
|---|---|---|
| ◐ | *Standard Benchmarks Fail — Auditing LLM Agents in Finance Must Prioritize Risk.* [arXiv:2502.15865](https://arxiv.org/abs/2502.15865) | Two **small, sourced, verifiable** incidents (Freysa **$47,000**; a user **$2,500**) — credibility over shock. Explicitly files Sharpe/ARR/MDD under "fails to account for higher-order risk". Slogan: "**from what LLM agents can do to what they must not do**". |
| ◐ | **CAIA.** *When Hallucination Costs Millions.* [arXiv:2510.00332](https://arxiv.org/abs/2510.00332) | "They measure **competence, not resilience**." Big number anchored to **irreversibility** ("losses cannot be recovered"). Argues **domain-as-instrument** in three numbered properties. |
| ◐ | *Finance Agent Benchmark.* [arXiv:2508.00828](https://arxiv.org/abs/2508.00828) | **Most restrained.** No losses at all — labour and trust instead. Causal chain **stops at the decision**. Self-deprecating headline (best model **46.8%**). SEC EDGAR + 7 expert annotators. |
| ◐ | *CryptoAnalystBench.* [arXiv:2602.11304](https://arxiv.org/abs/2602.11304) | **The sentence pattern to copy**: three parallel clauses, three different modals, zero dollar amounts, each ending in a *named analytical error*. |
| ◐ | **FinMCP-Bench.** ICASSP 2026. [arXiv:2603.24943](https://arxiv.org/abs/2603.24943) | **Our B1 citation**: "production financial agents … deployed in **33 real-world scenarios**", **65 financial tools via MCP**. |
| ○ | *Profit Mirage.* [arXiv:2510.07920](https://arxiv.org/abs/2510.07920) | backtest gains vanish after the knowledge cutoff. **Cite pre-emptively if asked "are you doing alpha?"** |
| ○ | *FinRetrieval.* [arXiv:2603.04403](https://arxiv.org/abs/2603.04403) | 500 structured-retrieval questions with full tool-call traces; structured API **90.8%** vs web search **19.8%**. Closest to our Daloopa data. |
| ○ | FailSafeQA [2502.06329](https://arxiv.org/abs/2502.06329) · FinTrust [2510.15232](https://arxiv.org/abs/2510.15232) · FinSafetyBench [2605.00706](https://arxiv.org/abs/2605.00706) · BankerToolBench [2604.11304](https://arxiv.org/abs/2604.11304) · ToolFailBench [2607.04686](https://arxiv.org/abs/2607.04686) · BigFinanceBench [2606.03829](https://arxiv.org/abs/2606.03829) | unread candidates |
| ○ | FinArena [2503.02692](https://arxiv.org/abs/2503.02692) · FinRobot [2405.14767](https://arxiv.org/abs/2405.14767) · InvestorBench [2412.18174](https://arxiv.org/abs/2412.18174) · FinCon [2407.06567](https://arxiv.org/abs/2407.06567) · FLAG-Trader [2502.11433](https://arxiv.org/abs/2502.11433) | **trading-performance framing — cite only as what we are not doing** |

## 8. Decision-aware uncertainty

| | ref | note |
|---|---|---|
| ◐ | Messing. *Hidden Measurement Error in LLM Pipelines.* [arXiv:2604.11581](https://arxiv.org/abs/2604.11581) | **Useful to us**: its main D-study formula is **absolute-style** (retains facet main effects) and it analyses **Chatbot Arena, a ranking task, with that same formula** — a concrete published instance of the conflation §2.4b identifies. **⚠️ Appendix D "G-Theory Connection and EMS Tables" was truncated in both fetches. If it contains the σ²δ/σ²Δ split for LLMs, our §2.4b transfer is narrower than claimed. Must be checked.** |
| ○ | *PEAR: Decision-Focused Learning via Tangent-Space Projection.* ICML 2026. [arXiv:2605.01361](https://arxiv.org/abs/2605.01361) | filters decision-irrelevant error components out of the gradient |
| ○ | *UQ for LLM Agents: Taxonomy, Protocol, Empirical Study.* [arXiv:2609.07395](https://arxiv.org/abs/2609.07395) | "the quantity reported is not the quantity deployment needs" — same spirit, trajectory axis |
| ○ | *SCOPE.* [arXiv:2602.13110](https://arxiv.org/abs/2602.13110) | selective conformal guarantees for LLM-as-judge |
| ○ | Ren et al. **KnowNo** (2023); CROQ / Prune 'n Predict (ICLR 2025); SafePath [arXiv:2505.09427](https://arxiv.org/abs/2505.09427) | conformal prediction for LLM planners/agents |
| ○ | *No Certificate No Execution.* [arXiv:2605.24462](https://arxiv.org/abs/2605.24462) | agent certification trajectories |

## 9. ⛔ Do not cite — unverified

- [arXiv:2507.20150](https://arxiv.org/abs/2507.20150) *The Policy Cliff* — a search layer claimed it argues "any metric on a finite set induces the discrete topology, so continuity assumptions hold trivially", which **would partially collide with our layer 1**. The abstract does not contain this and the HTML 404s. **Download the PDF and settle this** before layer 1 goes in writing.
- arXiv:2604.17384 ("Defense Trilemma"), arXiv:2604.24579 (Neumann-series perturbation bound), arXiv:2602.02427 (gradient-norm equivalence) — surfaced by search, never verified. **Do not cite.**

---

## Verification round, 2026-09-21 — all five tasks closed

PDFs downloaded and read directly (`probes/fetch_papers.py`, text under
`_papers/`, untracked). Outcomes, including the ones that went against us:

**1. 2604.11581 Appendix D — OCCUPIED. Our §2.4b claim must narrow.** ⚠️
Appendix D states the distinction explicitly, for LLM evaluation:
> "The D-study formulas above give the **absolute** error variance, appropriate for **threshold decisions**… For **relative** decisions (comparing two models or ranking items), **shared main effects such as prompt and judge shift all items equally and cancel**… Applying the absolute formula mechanically will overstate some shared sources and understate object-specific interactions."

Consequences: (a) cite it, write §2.4b as "we instantiate", never claim to bring
the distinction to LLMs; (b) **retract** the earlier note that it analyses
Chatbot Arena with the absolute formula as an unwitting conflation — it states
the caveat itself. Remaining increment: they give a variance decomposition and
SE advice for **evaluation design**; we give a per-query computable criterion ρ
and **measure** its predictive power under **tool-call substitution**.

**2. 2510.03992 — CONFIRMED verbatim.** ✅ Both sentences exist:
> "tool metadata is discrete text and JSON schemas with **no natural perturbation radius**, ruling out standard continuous-input certification" (§1)
> "Certified robustness is well developed for continuous classifiers under bounded perturbation sets, but **tool metadata has no ℓp analogue**: the input space is discrete and combinatorial, perturbations are semantic, and the pipeline is non-differentiable." (§5)

**3. 2609.16599 — CONFIRMED verbatim, and it is a better layer-1 target than
the three candidates.** ✅ Beyond the framing sentence ("hallucinations as
bounded disturbances"), §2.3 models the applied tool/control parameter as
**quantization**:
> "The parameter actually in force represents a **delayed, quantized**, and potentially dropped version of the LLM's raw output… θ̂(t) = q(θ(tₖ)), where q(·) **decodes discrete token sequences onto the valid parameter set Θ**… correspond directly to the time delay, packet dropout, and **signal quantization**"

Θ is said to encode "constraints, triggering thresholds… **mode indices**" — enum
parameters. Quantization is a *bounded small-error* model presuming the grid
finely approximates a continuum. A semantic enum is not such a grid. **This is
now layer 1.**

**4. 2507.20150 (The Policy Cliff) — CONFIRMED, and it kills our old layer-1
phrasing while supplying a better one.** ⚠️✅
> "**Any metric on a finite set induces the discrete topology**… any function from a space with the discrete topology to any other metric space is **necessarily continuous**."
> "the source of policy instability… **does not stem from a formal 'discontinuity' of the reward function itself**"
> "…as **a consequence of the inherent discontinuity of optimization over a discrete action set**"

On a finite space continuity is vacuous, so "discreteness breaks continuity" is
empty — and with the *discrete* metric, d(quarter,fy)=1 and L·ε = D_G, an
informative bound. The problem is the **choice of metric**, not continuity.
**Never write "the continuous bound fails because the input is discrete" again.**
Its argmax conclusion is the upstream statement of our decision-flip mechanism —
cite as foundation, not as an opponent.

**5. CertDR — CONFIRMED, plus the best positioning find of the round.** ✅
Open problem confirmed verbatim: *"In future work, it is worth to strengthen the
notion of Certified Top-K Robustness to guarantee that the order of top-K ranking
results remains unchanged."* And §4:
> "Here, we **leave the query q free from attack**. In the future work, we would like to explore the defense against **query attacks** by focusing on q in this formulation."

CertDR perturbs the **ranked objects** and explicitly defers **query-side**
attacks. A query-side perturbation is the natural source of a **common mode** —
one change moves every candidate at once. Our discrete parameter substitution
acts on the call, i.e. the query side. So the positioning is not "we differ from
CertDR" but "**we occupy the cell CertDR flagged as open, and show its
perturbation geometry is common-mode — which is exactly why a union bound goes
vacuous there**" (2/48 certified vs 14/48 genuinely stable).

**Bonus: 2601.18753 upgraded ○ → ✅.** A2 assumes
‖Φ(y)−Φ(y′)‖ ≤ L_Φ·d_Y(y,y′) over edit distance while A3 places the perturbation
ball in ℝ^r. `L_Φ` appears only in A2 and the notation recap — never in a theorem
or the scoring equation — and no quantitative relation between the two spaces is
ever given. The bridge is declared, never crossed.

### Still open

- **2605.00741** ○ — PDF download truncated. **Verify or delete; do not cite.**
- **2605.29816** — first pass did not surface the claimed contradiction.
  Downgraded, not in use.
- Whether anyone solved CertDR's top-K *internal ordering* problem in 2023–2026.
  RobustMask still certifies membership only. Hedge as "we are not aware of".
