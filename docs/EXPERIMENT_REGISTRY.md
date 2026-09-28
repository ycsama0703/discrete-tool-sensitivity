# 实验登记表（唯一权威清单）

> **规则**：新实验动手之前先在这里登记编号和论文位置；做完之后回填结果和状态。别的文档引用实验时，
> 一律用本表的编号（P3、G6、S4……）。旧名（Stage-2f、Stage-D、paper_framework 的 §3.x）只作为别名保留。
> 数字以本表和对应的 probe note 为准；`experiment_summary.md` 已停用。
>
> 建立于 2026-09-26：把 2026-09-16 至 09-25 做过的全部 27 个实验逐份核对后整理而成。

## 状态标记
- ✅ **有效**：可以在论文中引用
- ⚠️ **有效但有已知缺陷**：引用时必须同时写明缺陷
- ⛔ **作废 / 被取代**：**不得引用**（原因写在表里）
- 🔜 **计划中 / 未解决**

## 论文目标结构（论文位置列所指，尚未成稿）

| 节 | 内容 |
|---|---|
| §1 Intro | B3 的支点数字用 P1；B7 的数字用 G6 |
| §2 Setup & theory | S_cont / D_G / S_mix；margin model 推导（理论本身，不是实验） |
| §3 Phenomenon | §3.1 离散跃迁与连续界报零 · §3.2 agent 确实会犯 · §3.3 外部效度 |
| §4 Decision geometry | §4.1 输出幅度 ≠ 决策风险 · §4.2 从 τ 到 ρ · §4.3 序关系 vs 阈值决策 · §4.4 共模扰动下的最坏情况证书 |
| §5 Detection | §5.1 枚举筛查器（实测）· §5.2 baseline family · §5.3 自我检查阶梯 · §5.4 多模型投票 |
| §6 Why not fix the schema? | 接口 vs 模型缺陷；筛查器是写好描述的前提 |
| §7 Mechanism | 语义绑定（附录候选） |
| §8 Limitations | |
| App. | 接口审计、工具路由、历史版本 |

---

## P — 现象：离散错误存在，agent 会犯，连续界测不到

| 编号 | 旧名 / 框架 § | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| **P1** | Stage-2f / §3.1 | findata 的离散参数会产生输出跃迁吗？ | 96 次替换，62.5% 跳变 >10%；schema-valid 96/96；AAPL eps 2.04→6.11（66.6%），revenue 109B→391B（72%） | ✅ | **§1（B3 支点）**, §3.1 |
| **P2** | Stage-2h / §3.3 | 连续界漏、混合界盖？ | M1–M3 PASS；连续界 = 0，S_mix = D_G 能覆盖，D_G 有界（最大 72%） | ✅ | §2 例子, §3.1 |
| **P3** | Stage-2i / §3.4 | 放大后还成立吗，增量来自哪里？ | 20 symbol、4 端点、2 参数、420 次跃迁，S1–S3 PASS；period 是数值跃迁，statement 是结构跃迁 | ✅ | §3.1 |
| **P4** | Stage-2g / §3.2 | 真实 LLM 会犯这类错吗？ | 弱模型高影响错误 12–18.75%（llama/qwen） | ⚠️ 题目是为诱发错误而构造的；"强模型 0%"已被 P6 推翻，**不得引用** | §3.2（历史） |
| **P5** | Stage-D（D1 部分）/ §3.15 | 真实 agent 端到端的参数错误率？ | 3 个本地模型各 400 次调用：24.5% / 27.5% / 28.0%；错误集中在模糊的 quarter 问题上 | ✅ | §3.2 |
| **P6** | Stage-G（错误率部分） | 换规模、代际、厂商能降低错误率吗？ | 12 个配置（7B→前沿、5 个厂商）全部落在 **25.9–38.2%**；claude-sonnet-5 为 36.5%；gemini-3.8-flash 有 100/400 次**省略 period**；本地与 API 的 sanity check 通过 | ✅ 这是**参数错误率**。错误类型的构成（2026-09-26 拆分）：绝大多数是"问季度填了 `all`"；quarter→fy 互换出现在 llama3.1-8b（43–44/400）、qwen3.8-flash（43）、sonnet-5（17）、deepseek-v4.1（10）、gemini（3，另有 100 次省略）；fy 题目 0 错。**`all` 是真实的参数错误**：它在 findata 上造成的伤害较小，只是因为该 API 恰好把季度记录排在第一条；换一个 API 或换一种下游读法就会出错。**不得写成"`all` 无害"**。论文正文报参数错误率，按错误类型拆分；findata 上的实际伤害只作为特定 API 的补充 | **§3.2** |
| **P7** | Daloopa 外部效度 / §3.18 | 商用模型在真实题目上也犯吗？ | 5 个商用产品 5–9%，接地版 1.0%；170 个真实错误**全部跳变 >1%**，73% >10%；99.4% 是相邻 period | ✅ 是检索任务，不是工具 agent，只能作为外部效度 | §3.3 |
| **P8** | Daloopa binding | 问题写明 period 时，模型还会绑错吗？ | 写明时本地模型 0–0.2% 错；写得模糊时（P5）24–28% → **失败只出现在模糊输入上** | ✅ 任务是有引导的二选一分类 | §3.3 |
| C1 | FinRetrieval（**只引用，不做实验**） | — | 作者原文：地区差距 "stem from fiscal year naming conventions" | 仅引用 | §3.3 |

## G — 决策几何：哪些决策会翻转

| 编号 | 旧名 / 框架 § | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| **G1** | Stage-2j 变体 A v1 / §6 | period 替换会让决策翻转吗？输出跳变能预测吗？ | 80% 的 symbol 排名变化，top-3 换掉 2/3；**D4：逐实例 corr(jump, flip) = −0.12** | ✅ | §4.1 |
| **G2** | Stage-2l / §3.6 | 其他决策任务也会翻转吗？ | 10/12 个任务翻转 >20%；revenue 跳 66% 但 top-3 不变 | ✅ | §4.1 |
| G3 | Stage-2m / §3.7 | τ 能预测翻转吗？ | corr(τ, flip) = −0.98，**n=4** | ✅ 但样本小，作为中间步骤；数字以 G4/G5 为准 | §4.2（过程） |
| **G4** | Stage-2n / §3.8 | τ 在 12 个字段上还成立吗？ | −0.890；H1–H5 PASS；控制 jump 后的偏相关 −0.881；对照：revenue 跳 63.5% 只翻 24.7%，current_ratio 跳 9.9% 却翻 32.8% | ✅ | §4.2 |
| **G5** | Stage-2o / §3.9 | 换 symbol 宇宙还成立吗？ | 3 个新宇宙 −0.916 / −0.922 / −0.777；pooled 宇宙内中心化后 −0.852（n=48）；**季节性解释（P2）预测失败** | ✅；**季节性的说法不得写进论文** | §4.2 |
| **G6** | Stage-2p / §3.10 | 为什么 τ 能预测？ | 翻转当且仅当 \|Δlog r\| > \|Δlog q\|；flip = (1/π)arctan ρ，MAE 3.16pp；**corr(ρ, flip) +0.851 vs corr(jump, flip) +0.110**（n=48） | ✅ 有 16/48 个格子丢弃了非正值；闭式解在重尾处偏激进 | **§1（B7 数字）**, §4.2 |
| **G7** | Stage-2q / §3.11 | ρ 管哪类决策，D_G/κ 管哪类？ | 序关系决策：ρ +0.791、κ −0.028；阈值决策：κ +0.908、jump +0.861；C1–C4 PASS | ✅ | §4.3 |
| **G8** | Stage-2r / §3.12 | CertDR 式的最坏情况证书在这里好用吗？ | union bound 只认证 **2/48**，而实际稳定的有 14/48；共模商化后也只到 3/48 | ✅ 措辞是"假设错配"，**不得写成"we fix CertDR"** | §4.4 |
| G9 | Stage-K | ρ 在真实数据上成立吗？ | +0.539 | ⛔ **和 G6/G7 用的是同一份 tau_universe 真实数据、同样的整组替换，只是换成更粗的二值指标，属于重复实验**。当时误以为 G6/G7 是合成数据 | 不引用 |

## S — 筛查器与应用

| 编号 | 旧名 / 框架 § | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| S1 | Stage-2j 变体 A v2 / §6 | 应该枚举，还是用输出跳变来筛查？ | 输出跳变筛查：召回 69%、精度 73%；枚举"按定义"100% | ⚠️ 枚举那一行是恒等式，实测看 S4 | §5.1（设计动机） |
| S2 | Stage-2k / §3.5 | 端到端 Monte Carlo | 枚举把错误从 12% 降到 0% | ⛔ 枚举的精度和召回是**假设成 100%**，0% 是按定义得出的；只有输出跳变筛查那一列（约 69%）算有信息量 | 不引用 0% |
| S3 | Stage-D（D3 部分）/ §3.15 | 真实 agent 的筛查拦截 | 100% → 0% | ⛔ 翻转集合由随机种子**模拟**，筛查器两个分支都查正确 period，是 **oracle**（Stage-I 已指出） | 不引用 |
| **S4** | Stage-I | 筛查器在真实调用上实测表现如何？ | 决策错误**召回 100%**（凡是有定义的配置）；**精度 5–20%**；flag 率随宇宙变化 50–92%（CONSUMER 50%、TECH 92%）；真实决策错误每个配置只有 0–4/20 | ✅ **权威数字**；任务是我们造的（缺口 X1） | **§5.1** |
| **S5** | Stage-2j 变体 B / §6 | 枚举能找出"哪里危险"吗？ | 危险清单：quarter→fy、statement 互换是危险的；多数端点上 quarter→all 是安全的 → **能区分危险与安全，不是全报** | ✅ | **§6**（筛查器能揭示"哪里会错"）, App. |
| S6 | Stage-2j 变体 C / §6 | 能按敏感度选工具吗？ | key-metrics 53.1% < enterprise-value 86.7% < fundamentals 97.3%；20/20 个 symbol 排序一致 | ✅ | App. |
| **S7** | 方法测试 T1 | **风险–覆盖率**：在真实 agent 调用 + 真实决策上，同样的放行率下，谁放行出去的决策错误最少？和前人方法同台比较 | **主结果（2026-09-28，5 个模型全齐，测试集，R-first；格式 = 放行率 / 放行出去的错误决策数）**：<br>• 不筛查时的决策错误：qwen 6/96、gemma 11/96、llama 25/81、deepseek 17/90、qwen3.8 14/84<br>• **ENUM：放行 7–10%，放行的错误决策在 5 个模型 × 3 种读取规则下全部 = 0（H1 ✓）**<br>• 投票分歧（用另外 4 个模型的调用）：放行 67–74%，漏 0–4 个，是最强的对手（H2 相对投票不成立 → 卖点是保证，不是全面占优）<br>• 自一致性（k=5）漏 4–13 个；gpt-6-luna 裁判漏 4–18 个；自我验证漏 5–13 个，且**退化**：gemma 189/192 说"没问题"，llama 192/192 说"有问题"（放行率 0，和 I2 的过度纠错一致）<br>• SAFER 式：R-first 下漏 1–5 个，**R-annual 下 qwen 漏 16 个**（依赖读取规则，ENUM 不依赖）<br>• CRC[投票] 在部分模型上违反自身 5% 目标（按字段划分，不满足可交换性）<br>• llama 有 15 个实例因格式解析失败被排除（23/3840 次调用）。结果文件 `probes/S7_eval_{model}.txt`。样本小，置信区间、同放行率比较（H2）、H3（拦截率 vs ρ/κ）待补 | ⚠️ **主实验数据已齐**（2026-09-28）。llama 在 vast.ai RTX 3090 上续跑完成。**API 第一轮作废**：OpenRouter 余额耗尽，5,480 次调用返回 402，已用 `--resume` 续跑（见协议变更记录第 8 条）。sonnet 因预算暂缓。协议见 `METHOD_EVAL_PROTOCOL.md`。被测方法是**三步理论驱动流水线**（按类型分流 → 用 D_G 找跳变点 → 决策门）。主实验中决策由代码完成；**S7-B 子实验**：决策由模型完成（CONSUMER 宇宙，llama + sonnet） | **§5（主结果）** |
| **S8** | 方法测试 T2 | **降低误报**：几种报警规则（全枚举 / 用历史数据估 ρκ 预判 / 枚举 × 模型自身的不确定性），能否在几乎不漏报的前提下提高精度？ | — | 🔜 已登记，同上 | §5 |
| **S9** | 方法测试 T3 | **成本**：每个决策额外需要多少次工具调用和 LLM 调用、多少延迟；缓存能省下多少 | — | 🔜 已登记，同上 | §5 / App. |

## B — 替代方案（为什么别的方法不行）

| 编号 | 旧名 / 框架 § | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| **B1** | Stage-E / §3.16 | 5 个方法 family 的对比 | 连续界 0%；SAFER 精度 77% / 召回 62%；MC 88% / 94%；Gecko 0% | ⚠️ **"我们的筛查器 100/100"那一行是恒等式**（`our_flags = true_flip`），必须替换成 S4 | §5.2 |
| **B2** | Stage-F / §3.17 | 让模型自己检查（**阶梯 L1/L2/L3**） | qwen：L1 100/99、L2 100/65、**L3 4.6/8.9**；llama L3 60.6/24；gemma L3 22.7/73 | ✅ | §5.3 |
| **B3** | Stage-G（阶梯部分） | 阶梯实验扩到 12 个配置 | **L3 召回从 0.0%（gpt-6-luna）到 89.8%（qwen3.8-flash），不可预测**；同一家族放大 10 倍，可以变好（qwen 4.6→68.6），也可以变差（llama 63.8→6.8） | ✅ | §5.3 |
| **B4** | Stage-H | 多模型投票 | 投票错误率 30.0%，最好的单模型是 27.3%；错误相关 φ = +0.53~0.68；三个模型全错的频率是独立假设下的 7.4 倍 | ✅ 只有 3 个相近规模的模型 | §5.4 |

## I — 接口 / 描述

| 编号 | 旧名 | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| **I1** | Stage-J | 把 period 设为必填、改描述，能消除错误吗？ | S0 28.0% / S1（必填）27.3% / S2（事后知识写的描述）0.0% / S3（去掉点名字段）1.8%，错误值全是 `all` | ⚠️ **S0、S1 是主线证据；S2、S3 是 bonus**（告诉模型哪里会错，它能改对 → 排除"模型没能力"）；S2/S3 用了部署时拿不到的信息。**llama 补跑（2026-09-26，各 400 个 case）**：S0 29.6%（fy 45 / all 72）→ S1 25.6%（51/50）→ S2 14.8%（**46**/13）→ S3 23.3%（**64**/27）。**按原预注册判读，llama 在 S2 也没降到 10% 以下 → 对 llama 排除了"只是 schema 没写好"**；描述能消掉 `all`，但 **quarter→fy 在四档里从未下降**。所以"告诉它哪里会错就能改对"只对 `all` 这类错误成立。数据：`stageJ_llama_S{0..3}.jsonl`（只在 luyao4 上）。**API 三模型（2026-09-27）**：qwen3.8-flash 32.0 / 28.6 / 7.9 / **31.5**；deepseek-v4.1 36.0 / 34.1 / 4.3 / **31.3**；sonnet-5 36.5 / 33.8 / 0.0 / **34.5**（S0/S1/S2/S3）。S0 与 Stage-G 一致。**gemma3-12b（ollama，2026-09-27）**：28.5 / 29.2 / 0.8 / 16.8，错误全是 `all`（与 Stage-F 的 29.8% 一致）。**六个模型汇总**（gemma 加入后结论不变；S3 对 gemma 部分有效）：① 必填 5/5 无效；② **不含事后知识的通用描述 S3 只对 qwen2.5 有效，另外 4 个模型 ≈ S0**，此前"S3 证明通用描述就够"只是 qwen2.5 的特例；③ **只有用了事后知识的 S2 普遍有效**，但 llama（46）、qwen3.8（28）、deepseek（17）仍残留 quarter→fy。qwen3.8 的 S2 有 43 次 API 调用失败，已排除在外；即使全部算错，错误率也 ≤ 18%，不改变结论。数据：本地 `stageJ_{qwen38,dsv41,sonnet5}_S{0..3}.jsonl` | **§6** |
| I2 | — | **阶梯 L2.5**：把筛查器知道的信息（哪个参数敏感、各取值下工具返回什么）告诉模型，但不给答案，模型能不能**改对**？ | 主口径为预注册的**严格口径**（`all` 算错）。**qwen 小窗（100 个 case，错误全是 `all`）**：跑前 28.0% → R0 27.0% / R1 28.0% / **R2 2.0%**；R2 修复 92.9%、改错 0% → **H1–H4 全部通过**。**llama 全量（396 个 case，66 个 `all` + 43 个 quarter→fy）**：跑前 27.5% → R0 11.4% / R1 10.9% / R2 21.7%；R0 修复 95.4% / 改错 13.9%，R2 87.2% / **25.1%**；改错全是 fy 题被改成 quarter（R2 改了 70/160） | ⚠️ **结果因模型而异**：qwen 支持 C6；**llama 触发证伪条件**（R2 修复率 ≤ R0 + 10pp），它的错误率下降主要来自"再问一次"，筛查器信息没有额外帮助，R2 还把 fy 题推向 quarter（fy 日期停在 2024 年，跑前已列为注意事项；R1 不涉及日期，同样没有超过 R0）。宽松口径（findata 特有，`all` 算对）只作为敏感性分析。和 B3 的"L3 不可预测"是同一现象。设计见 `probes/I2_screener_rung.py`（2026-09-26）。脚本 `probes/I2_screener_rung.py`；重放 B2/B3 的同一批调用；三档：R0 只让模型重新考虑（对照）/ R1 告诉它 period 敏感 / R2 再加上各取值的真实返回。预注册：H1 R2 的错误率减半，且修复率比 R0 高 30pp 以上；H2 R0 修复率 ≤ 20%；H3 R2 比 R1 高 15pp 以上；H4 R2 把原本对的改错 ≤ 5%；**R2 修复率 ≤ R0 + 10pp 即证伪** | §6 |

## M — 机制

| 编号 | 旧名 / 框架 § | 问题 | 关键结果 | 状态 | 论文位置 |
|---|---|---|---|---|---|
| **M1** | Stage-A / §3.13 | 绑定信号是否支配参数选择？ | qwen：V1 10%、V2 60%、V3 92%；llama：V1 32%、V2 38%、V3 60% | ⚠️ position 混淆（a 可能是"不愿在这个位置输出符号"）：**2026-09-22 已决定只记录、不重跑**（不影响主线结论，见记忆 feedback-dont-overpolish-confounds）。写论文时放进 limitations | §7 |
| M2 | Stage-C / §3.14 | 激活干预 | qwen：晚期层（19–25）real 是 random 的 2–3 倍，但方向不干净；**llama 没复现** | ⚠️ 只能算提示性证据 | §7 / App. |

## X — 已知缺口（尚无实验）

| 编号 | 缺口 | 现状 |
|---|---|---|
| X1 | 筛查器没在自然的决策负载上评估过（S4 用的是我们造的任务） | 候选核查见 `D:\luyao4\exp\gap1_candidates.md`：FAB 不适合；FinRetrieval 不带决策；**FinMCP-Bench 最合适，但卡在且慢 MCP 能否访问**。备选方案：放宽自建任务，并在 limitations 里说明 |
| X2 | 只测了 period 一个参数（statement 只在 P3 里测过跃迁） | 等 X1 或 I2 的时候一起考虑 |
| X3 | fiscal vs calendar 这个离散维度从没测过 | 线索来自 FAB（TJX/MU/ORCL）和 C1 |
| X4 | **findata 年度数据滞后**（2026-09-27 发现）：最新 FY 和最新季度之间间隔中位数 455 天，FY2025 普遍缺失 → **所有 quarter vs fy 的比较都混入了一年多的时间差** | 影响 P1–P3、G 系列、S4 中"跳变/翻转"的**大小和解释**（不全是口径差异）；**不影响翻转条件本身**（它对任何替换都精确成立）。写作时不能把全部效应归于季度/年度口径。S7 增加 R-aligned 离线敏感性分析 |

---

## 文件索引

| 编号 | probe note（`docs/probe_notes/`） | 脚本（`probes/`） | 数据 |
|---|---|---|---|
| P1 | README_discrete_sensitivity | build_discrete_sensitivity.py | discrete_sensitivity.jsonl |
| P2 | README_mixed_sensitivity | build_mixed_sensitivity.py | mixed_sensitivity.jsonl |
| P3 | README_mixed_sensitivity_scale | build_mixed_sensitivity_scale.py | mixed_scale.jsonl |
| P4 | README_generator_relevance | run_generator_relevance.py | gen_relevance_results.jsonl |
| P5, S3 | README_stageD_agent_e2e | agent_end_to_end.py, stageD_mechanism.py | agent_end_to_end*_full.jsonl |
| P6, B3 | README_stageG_openrouter | stageG_openrouter_ladder.py, stageG_scale_table.py | stageG_*.jsonl, stageF_ladder_*.jsonl |
| P7 | README_daloopa_external_validity | `D:\luyao4\exp\daloopa\analyze_*.py` | `D:\luyao4\exp\daloopa\train.csv` |
| P8 | README_daloopa_period_binding | daloopa_period_binding.py | daloopa_period_*.jsonl |
| G1, S1, S5, S6 | README_variants | decision_flip.py, decision_screener.py, audit_interface_sensitivity.py, route_by_sensitivity.py | mixed_scale.jsonl |
| G2 | README_multi_decision | multi_decision.py | mixed_scale.jsonl |
| G3 | README_verify_tau | verify_tau.py | mixed_scale.jsonl |
| G4 | README_tau_expand | tau_expand.py | tau_expand.jsonl |
| G5 | README_tau_universe | tau_universe.py | tau_universe.jsonl |
| G6 | README_margin_model | margin_model.py | tau_universe.jsonl |
| G7 | README_decision_geometry | decision_geometry.py | tau_universe.jsonl |
| G8 | README_certdr_baseline | certdr_baseline.py | tau_universe.jsonl |
| G9 ⛔ | README_stageK_decision_geometry_real | stageK_decision_geometry_real.py | tau_universe.jsonl |
| S2 ⛔ | README_end_to_end | end_to_end.py | mixed_scale.jsonl |
| S4 | README_stageI_screener_measured | stageI_screener_measured.py | stageI_eps_cache.json + stageF/G 的调用 |
| B1 | README_stageE_baseline_family | baseline_family.py | mixed_scale.jsonl |
| B2 | README_stageF_selfcheck | stageF_selfcheck.py | stageF_ladder_{qwen,llama,gemma}.jsonl |
| B4 | README_stageH_voting | stageH_voting_baseline.py | stageF_ladder_*.jsonl |
| I1 | README_stageJ_schema_ablation | stageJ_schema_ablation.py | stageJ_qwen_S{0,1,2,3}.jsonl（**只在 luyao4 上**） |
| M1 | README_stageA_binding | stageA_binding.py | stageA_binding*.jsonl |
| M2 | README_stageC_patch | stageC_patch.py | stageC_patch*.jsonl |

## 别名对照（旧名 → 编号）

Stage-2f→P1 · 2g→P4 · 2h→P2 · 2i→P3 · 2j→G1/S1/S5/S6 · 2k→S2 · 2l→G2 · 2m→G3 · 2n→G4 · 2o→G5 · 2p→G6 · 2q→G7 · 2r→G8 ·
Stage-A→M1 · C→M2 · D→P5/S3 · E→B1 · F→B2 · G→P6/B3 · H→B4 · I→S4 · J→I1 · K→G9 · Daloopa→P7/P8

框架 §3.1→P1 · 3.2→P4 · 3.3→P2 · 3.4→P3 · 3.5→S2 · 3.6→G2 · 3.7→G3 · 3.8→G4 · 3.9→G5 · 3.10→G6 · 3.11→G7 · 3.12→G8 ·
3.13→M1 · 3.14→M2 · 3.15→P5/S3 · 3.16→B1 · 3.17→B2 · 3.18→P7
