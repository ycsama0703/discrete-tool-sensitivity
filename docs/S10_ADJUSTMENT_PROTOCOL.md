# S10 协议：第二个金融离散参数——价格复权（adjustment）

> 状态：**已完成**（2026-09-30 批准并运行；结果见 `EXPERIMENT_REGISTRY.md` S10 行）。目的：证明"agent 静默填写未指定的离散参数"不是 `period` 一个参数特有的现象，
> 并在一个以**实体特异变化（ρ 型）**为主的真实参数上检验理论与方法。领域限定金融（用户 2026-09-30 决定）。
> 检查脚本与快照：`probes/expansion/`（在 luyao4 上运行）。

---

## 0. 候选检查记录（实际下载后的结论）

| 候选 | 实际检查 | 结论 |
|---|---|---|
| **A. 价格复权**（yfinance 数据 + OpenBB 原生参数 schema） | `A1_inspect_adjust.py`、`A2_adjust_geometry.py`：34 只股票 2020–2025 全部下载 | **采用。** 见第 1 节 |
| B. 财年 / 自然年（SEC EDGAR companyfacts） | `B1`、`B2`：47 家公司、2022–2024 | **不采用。** 只有 9–11 家（财年 1–5 月结束）受影响；ρ = 0.04–0.10，前 3 名排序翻转仅 0.5–2%；还混入了与口径无关的差异（JNJ、PFE、MCD、HON：SEC 把 CY 标签挂在重述值上），会污染实验 |
| C. Finance Agent v2（vals-ai） | 克隆仓库，读 `tools.py`、`prompt.py`、`public.csv` | **不作平台，作动机证据。** 27 道公开题多为 DCF/LBO 等分析任务，多公司价格比较仅 2 道；需平台审批与 Tavily / sec-api / Tiingo 付费 key。其价格工具同时返回复权与不复权列，作者在 system prompt 中写死 "always use the raw, unadjusted price … unless the question specifically asks"——一流金融 agent benchmark 也只能用指令回避这个选择 |
| findata 其他参数 | 解析 openapi（174 个 endpoint） | 除 `period` 外无合适参数：`statement` 不影响返回值；`/ohlc` 无复权开关（返回全复权价）；预测市场排行榜 `window` 换的是另一批实体，不是同一批实体的数值变化 |
| FinRetrieval、Daloopa | 读论文与数据（Daloopa 已在本地，P7/P8） | 题目都写明期间、单值检索，无排序/阈值决策。**作动机引用**：FinRetrieval 中期间口径混淆占全部错误 43%（最强配置 63%） |
| BFCL `get_stock_history`、FinMCP-Bench、FinToolBench | 读原始 JSON / 论文 | 参数均写明或不评参数；BFCL 仅 2 题且已弃用、参数描述含糊 |

---

## 1. 为什么选复权

1. **参数是原生的**：OpenBB（常用金融 agent 工具库）`equity.price.historical` 的 TMX provider 定义为
   `adjustment: Literal["splits_only", "splits_and_dividends", "unadjusted"] = "splits_only"`，
   描述 "The adjustment factor to apply. Only valid for daily data."（2026-09-30 从 OpenBB develop 分支核实）。工具 schema 原样照搬，
   不是我们为实验造的参数。
2. **变化是实体特异的（ρ 型）**，与 `period`（主要是共同缩放，κ 型）互补。实测 2020-01-02 收盘价，全复权相对只调拆股：
   MO −41%、T −37%、VZ −32%、XOM −26%、KO −18%、AAPL −4%、NVDA −0.7%、AMZN/TSLA/AMD 0%。
3. **提供了 ρ 的剂量梯度**（`A2_adjust_geometry.py`，200 个随机 20 股子集）：

| 替换（以全复权为参照） | 平均 ρ | 前 3 名收益率题翻转 | 阈值题翻转 |
|---|---|---|---|
| → splits_only（不计分红） | 0.03–0.18 | 13–24% | 55–89% |
| → unadjusted（按当时成交价） | 0.39–1.88 | 窗口含拆股时 98–100%；1 年窗口 24% | 80–100% |

4. **真实场景下用户不会说**："这 20 只股票 2023 年以来谁表现最好"——用户不会说要不要算分红、要不要调拆股。
5. **免费、可复现**：数据冻结为本地快照。

---

## 2. 工具与执行器

**给 agent 的工具**（与 S7 相同的调用格式，每个标的调用一次）：

```
get_price_history(symbol: str, start_date: str, end_date: str,
                  adjustment: "splits_only" | "splits_and_dividends" | "unadjusted" = "splits_only")
  description: OpenBB 原文 + 返回说明（返回 start_date 与 end_date 两个交易日的收盘价）
```

**执行器**（离线，读快照）：
- `splits_and_dividends` = yfinance `auto_adjust=True` 的 Close；
- `splits_only` = yfinance `auto_adjust=False` 的 Close（实测 yfinance 的不复权价已做拆股调整）；
- `unadjusted` = `splits_only` × 该日期之后所有拆股因子之积（按当时成交价）。只用真实拆股（比例 ≥ 1.5）；
  yfinance 把分拆事件也记成拆股（T 1.324、MMM 1.196、IBM 1.046 等），这些排除并在代码中列出。
- **上线前校验**：`unadjusted` 与已知成交价核对（例如 NVDA、AAPL、TSLA、CMG 在拆股前某日的历史收盘价），误差需 < 1%。

---

## 3. 数据与实例

- **股票池**：约 80 只美股大盘股，分 4 组各 20 只（高股息组、科技成长组〔多拆股〕、金融与工业组、消费与医药组），
  覆盖高股息 / 零股息 / 多次拆股。各组 ρ 不同，天然形成剂量梯度。
- **决策**（每组 12 个，共 48 个实例）：
  - 前 3 名收益率：窗口 {2025 全年, 2023–2025, 2021–2025}；
  - 收益率阈值（T = 参照口径下的中位数）：同三个窗口；
  - 某日收盘价前 3 名、某日收盘价阈值：日期 {2021-06-30, 2023-06-30, 2025-06-30}。
- **提问方式**：全部不提复权（真实场景）。例："Consider these companies: … Which 3 of them had the best stock performance
  from January 2, 2023 to December 31, 2025?"；"Which of them closed above $150 on June 30, 2021?"
- **参照口径（标注约定）**："表现 / 收益率"题 → `splits_and_dividends`（总收益，指数与基金业绩的通行口径）；
  "某日收盘价"题 → `unadjusted`（当日实际成交价）。按既定原则不再讨论标签歧义；ENUM 的保证不依赖这个约定。
- **规模**：48 实例 × 20 只 = 每个模型 960 次调用（S7 为 3,840）。

---

## 4. 模型与方法

- **模型**：沿用 S7 的 6 个——qwen2.5、gemma3、llama3.1（本地，luyao4；llama 慢时用 vast）、deepseek-v4.1、qwen3.8、gpt-6-luna（API）。
- **方法**：ENUM（三步流水线，审计按留一组做等价类合并）+ S7 的全部对比方法：SAFER 式扰动、CertDR 并集界、自一致性（k=5）、
  自我验证、强模型裁判（gpt-6-luna；对 gpt-6-luna 自身用 gpt-6-luna-pro）、多模型投票、CRC。评估沿用 `S7_decision_screen.py` 的指标
  （放行率、放出去的错误、错误率 95% 上限）。
- **成本估计**：API 调用（含对比方法）合计 < $0.5；本地模型在 luyao4 约数小时。

---

## 5. 预测（先写死在代码里，再看数据）

| 编号 | 对应叙事 | 预测 | 判据 |
|---|---|---|---|
| **E1** | 生成层 | 不提复权时，每个模型静默填一个固定默认值 | 每个模型主导取值占 ≥ 70% 调用；至少两个模型的主导取值不同 |
| **E2** | 后果层 | 放行与否可由 (ρ, κ) 预测 | 逐实例 AUC ≥ 0.80，且优于数值跳变幅度 |
| **E3** | 后果层 | ρ 剂量效应 | 前 3 名收益率题翻转率：unadjusted（含拆股窗口）> splits_only；按组 ρ 排序与按组翻转率排序一致 |
| **E4** | 方法 | ENUM 零漏错；不查数据的方法都漏 | ENUM 放出去的参数导致错误 = 0；自一致性、自我验证、裁判、投票合计各 ≥ 1 |
| **E5** | 代价 | 放行与模型无关 | 放行决定跨模型不同的实例，全部可由"agent 对不同标的混用口径"解释 |

---

## 6. 步骤

1. 建股票池、下载并冻结快照，校验 `unadjusted`（约 1 小时）。
2. 生成 48 个实例与题面；写 `S10_adjustment.py`（复用 S7 的调用、解析、对比方法与评估代码）；预测写入脚本头部。
3. 冒烟测试：1 组 × gpt-6-luna（几分钱），确认格式与流程。
4. 全量：6 个模型的调用 + 对比方法。
5. 评估、登记 `EXPERIMENT_REGISTRY.md`（编号 S10），更新论文叙事中"不只是 period"的证据。


## 7. 执行记录与偏离

- 快照校验：拆股还原需乘回 yfinance 记录的**全部**因子（含分拆，如 GE 的 GEHC/GEV），初版只乘真实拆股导致 GE 校验失败，已修正；8 个已知成交价全部精确吻合。
- CRC 未纳入（主线不需要）。
- llama 在 vast.ai 运行；本地启动器因后台时限被中止，改用 `vast/collect_s10.sh` 收尾（核对 960/48/48 后销毁）。
- 预测结果：E1 FAIL、E2 PASS、E3 半 FAIL、E4 PASS、E5 PASS（详见登记表）。
