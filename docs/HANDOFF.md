# 交接文档（2026-09-30）：研究进度、结果、规则与远程工作配置

> 在新机器上打开项目时**先读这一份**。它汇总了截至 2026-09-30 的全部进度、所有实验结论、我们定下的工作规则、
> 怎么复现与继续跑实验、踩过的坑，以及笔记本需要手动配置的东西。
> 更细的内容以这些文档为准：
> - `docs/EXPERIMENT_REGISTRY.md` —— **实验总表（唯一权威）**：编号、结果、状态、论文位置
> - `docs/paper_storyline.md` —— **论文主线（第 2 版）**：数学符号 + LLM 机制 + 经典锚点 + 证据
> - `docs/theory_narrative.md` —— 同一叙事的对照表版本，带文献验证标记和预测清单
> - `docs/theory_problem_roots.md` —— 问题根源的文献精读（两轮共 8 路）与预测检验记录
> - `docs/theory_screener_guarantees.md` —— 方法保证：哪些归属前人、哪些是我们的
> - `docs/METHOD_EVAL_PROTOCOL.md` —— S7 / S7-B 协议；`docs/S10_ADJUSTMENT_PROTOCOL.md` —— S10 协议

---

## 1. 研究是什么（一句话）

LLM agent 替用户填写了一个**用户没指定、也不知道存在的离散工具参数**（如金融数据接口的 `period`、价格复权 `adjustment`）。
调用合法、执行成功、数字看起来正常，但下游决策（前 k 名、阈值判断）会悄悄改变。我们刻画了这类失败的根源（生成 / 检测 / 后果三层），
证明任何不查询其他取值下数据的检查都不可能可靠，给出决定"何时会翻"的决策几何 (ρ, κ)，并说明"在所有合法取值上决策一致才放行"
（选择性分类里 El-Yaniv & Wiener 的 CSS 的实例）是唯一可靠、放行最多、且代价与模型无关的规则。领域：金融。

## 2. 当前阶段

**实验主体已完成，理论叙事已成形，下一步是写论文。** 主线六步每一步都有实验支撑（见第 3 节）。

---

## 3. 主要结论与数字（按论文主线顺序）

| 主线步骤 | 结论 | 关键数字 | 来源 |
|---|---|---|---|
| 二 生成 | 用户没写参数时，模型静默填自己的默认值；写明时几乎不错 | 写明 ≈ 0%，未写 56–98%（S7）；I1 写明 0/240；错误集中于一个值 77–99%；选错时 5 次采样全同 42–87% | S7、I1、P2/P3/L1 |
| 三 检测 | 不查其他取值下数据的检查（自查、强模型裁判、自一致性、投票、连续认证）都不可能可靠 | S7 真实场景强模型裁判最多漏 18；裁判 balanced acc 0.51–0.58；S10 合计：裁判放行 98 错 46，投票放行 18 错 17 | S7、S10、定理 1 |
| 四 后果 | 翻不翻由决策几何决定：排序看 ρ，阈值看 κ；LLM 亲自决策时同样服从 | corr(ρ,flip) +0.79，corr(κ,flip) +0.91；流量穿越 40% vs 存量 8–13%；LLM 决策翻转与代码逐题一致 98–99%（luna、deepseek） | G6–G8、P1、S7-B |
| 五 方法 | ENUM 零漏错 | S7 真实场景：6 模型 × 2 读法漏错 0；S7-B：3 模型参数导致错误 0；S10：6 模型漏错 0 | S7、S7-B、S10 |
| 六 代价 | 放行与模型无关，由 (ρ, κ) 可预测 | 187/192 放行决定跨模型一致（余下 5 个均为混用口径）；AUC 0.83–0.87（S7），0.945（S10） | L2、H3、S10 |
| 六½ 泛化 | 第二个金融参数（价格复权，ρ 型）上结论重现 | 决策错误 45–51%；ENUM 放行 20–27%、漏错 0 | S10 |

**事先写死但未通过的预测（如实记录）**：P3 前半（写明后仍错——实际几乎不错，推翻了"绑定失败为主"）；P4 部分（3/6 模型自查有信号）；
L3（自查信号来自"×4 先验"——反方向）；S7 投票强（真实场景下投票放行仅 0–4%）；S7-B 中 qwen2.5 的 B-G1（推理噪声）；
S10 的 E1（单一默认值 ≥ 70% 仅 2/6 模型）与 E3 后半（每组样本太少）。

**已退出主线**：绑定分解 ℓ = a + bu + cv + duv（移入讨论）；"用问题文本缩小版本空间"作为改进（真实场景用户不写参数）；
审计步骤的概率界（写错，已作废，只保留经验证据 640 单元 0 违反）。

---

## 4. 工作规则（用户定下的，新会话务必遵守）

**沟通**
- 一律用华语回复；解释要简单直白。提问前先写全背景、证据和权衡，不要只甩选项。
- 汇报只讲结果对主线的意义；**不要罗列审稿人可能追问的旁支**，不要抠细枝末节（篇幅有限，专注主线）。

**研究方法**
- **场景**：真实 agent 场景里用户只下达任务、不写参数；"用户写明了参数"只作对照组。
- **领域只做金融**（学院是金融背景）；扩容只找金融 dataset/benchmark，没有合适的不硬做。
- **理论先挖问题根源**，广泛借鉴别领域的建模，再建方法理论；已知结果写成"是 X 的实例"并引用，不写成自己的定理。
- 文献要**读方法节**，不凭摘要下结论；看到相似工作别退缩，找差异、把前人变 baseline。
- **预测先写死在代码里再看数据**；不从两三个点推广出机制。
- **先小窗探针 / 冒烟测试，再全量**。
- confound 不改变主线结论就记录并继续，**不为数字更干净反复重跑**。
- 标签歧义（没写期间时正确答案按约定）直接按约定算错误，不再讨论。
- "告知模型错误在哪"的对照档（如 I1 的 S2/S3）是加强主线的 bonus，不是判据。
- 新实验动手前**先在 `EXPERIMENT_REGISTRY.md` 登记编号**。

**资源与操作**
- **所有实验在 luyao4 服务器上跑**（conda 环境 `kolrl`）；API 模型可在本地跑。**绝不为跑实验改本机进程或系统设置。**
- 花钱（租 vast、API 大额调用）要先经用户同意；**sonnet 太贵，不作被测模型也不作裁判**；裁判用 `openai/gpt-6-luna`
  （给 gpt-6-luna 自己当裁判时用 `openai/gpt-6-luna-pro`）。
- commit / push 等用户说了再做；同步 luyao4 副本用 scp（服务器上的 git 副本落后于 GitHub）。

---

## 5. 代码与数据地图

```
probes/
  S7_decision_screen.py       S7 主实验（period）：fetch/qhist/build/calls/baseline/eval
                              eval 选项：--intent ambiguous（真实场景）、--split all（全字段）、95% 上限
  S7_predictions.py / .txt    P1–P4 预测检验
  S7_llm_predictions.py / .txt  L1–L3（LLM 理论预测）
  S7_H3_coverage.py / .txt    H3：(ρ, κ) 预测放行
  S7B_llm_decision.py         S7-B：LLM 亲自决策（run / eval）
  S10_adjustment.py           S10：价格复权（build/calls/baseline/eval/summary），预测 E1–E5 写在文件头
  S10_snapshot.json           S10 冻结数据（80 只股票，yfinance）
  expansion/                  扩容候选检查（A 复权、B EDGAR 财年/自然年）及其输出
  vast/                       vast.ai 租机脚本：onstart*.sh、launch_and_collect*.sh、collect_s10.sh
  S7_calls_{model}.jsonl, S7_base_{selfcons,verify,judge}_{model}.jsonl, S7_eval_*.txt
  S10_calls_{model}.jsonl, S10_base_*_{model}.jsonl, S10_eval_*.txt, S10_summary.txt
  S7B_{model}.jsonl, S7B_eval_*.txt
```

模型标签：`qwen`（Qwen2.5-7B，本地）、`gemma`（gemma3:12b，ollama，本地）、`llama`（Llama-3.1-8B，本地 / vast）、
`dsv41`（deepseek-v4.1-flash）、`qwen38`（qwen3.8-flash）、`luna`（gpt-6-luna），后三个走 OpenRouter。

---

## 6. 复现与继续实验

**评估（纯本地，不需要 GPU、不花钱）**：
```bash
cd probes
python S7_decision_screen.py eval --intent ambiguous --split all --calls S7_calls_qwen.jsonl \
   --base-selfcons S7_base_selfcons_qwen.jsonl --base-verify S7_base_verify_qwen.jsonl \
   --base-judge S7_base_judge_qwen.jsonl --vote S7_calls_gemma.jsonl S7_calls_llama.jsonl ...
python S7_H3_coverage.py
python S7B_llm_decision.py eval --tag luna
python S10_adjustment.py eval --tag luna --vote qwen gemma llama dsv41 qwen38 luna
python S10_adjustment.py summary --tags qwen gemma llama dsv41 qwen38 luna
```
Windows 上运行前设 `PYTHONUTF8=1`。

**新跑模型调用**：API 模型需要 `.env` 里的 `OPENROUTER_API_KEY`；本地模型在 luyao4 上跑（写成脚本 scp 过去，用 nohup 后台启动，
写 done 标记文件）；慢的模型（llama）租 vast：`bash probes/vast/launch_and_collect_s10.sh <offer_id> <已 push 的 commit>`，
开机脚本先在 luyao4 上用小模型演练过再租。

---

## 7. 踩过的坑（操作）

- **远程命令一律写成脚本文件 scp 过去再执行**，不要在 PowerShell 里内联长命令（引号会被改坏）。
- **`pgrep -f` / `pkill -f` 会匹配到执行它的那个 shell 本身**（命令文本里含同样的字符串），会把自己杀掉；要停进程先查 PID 再 `kill <PID>`。
- Git Bash 调 Windows 的 `scp.exe`：本地路径要用 Windows 形式（`D:/...` 或 `cygpath -w`）；远程路径里的 `~` 会被 MSYS 改写，
  设 `MSYS_NO_PATHCONV=1` 并写 `luyao4:workspace/...`。
- 后台命令有约 10 分钟的时间上限，长任务用可续期的 Monitor（每 30 分钟重挂）盯完成标记；**租机的收尾（拷回、核对、销毁）不要依赖一个长时间后台进程**，
  必要时用 `probes/vast/collect_s10.sh` 手动收尾。
- vast 租机：有的机器 docker 拉镜像会卡死或报错，启动器会自动放弃并销毁；`vastai destroy` 需要 `echo y |` 确认。
- luyao4 的 16GB 显卡放不下 bf16 的 Qwen2.5-7B，会有部分参数放到 CPU（日志 "offloaded to the cpu"），所以慢，但结果正确。
- **yfinance**：`auto_adjust=False` 的收盘价已经做了拆股调整，且对**分拆事件也做了调整**（GE 的 GEHC/GEV）；还原当时成交价要乘回全部因子。
- **SEC EDGAR frames**：CY 标签有时挂在重述后的数值上（JNJ、PFE、MCD、HON），会混入与口径无关的差异。
- **findata**：年度数据比最新季度滞后约 455 天（X4）；R-first 下 `all` 碰巧返回季度数据——**不得写"all 无害"**。
- OpenRouter 余额耗尽会返回 402：脚本遇 402 立即中止，不把 402 当模型行为记录；`--resume` 只重做 API 错误，不重采模型的格式失败。

---

## 8. 笔记本配置清单（这些**不在仓库里**，仓库是公开的，需从台式机私下拷贝）

1. **luyao4 的 SSH**：两把私钥（跳板机那把带口令、luyao4 本身那把）+ `~/.ssh/config` 里 luyao4 的 Host 配置（经跳板机 ProxyJump）。
   配置细节见台式机上的私人笔记 `D:\luyao4\luyao4-ssh-setup.md` 和运维笔记（都不在仓库里）。Windows 上要用系统自带的
   `C:\Windows\System32\OpenSSH\ssh.exe` 并把带口令的钥匙加入 ssh-agent 服务。
2. **OpenRouter key**：在仓库根目录建 `.env`，写入 `OPENROUTER_API_KEY=...`（`.env` 已在 `.gitignore`）。余额 2026-09-30 约 **$4.51**。
3. **vast.ai**：`pip install vastai`，把 API key 放到 `~/.config/vastai/vast_api_key`；本机 SSH 公钥需已登记在 vast 账户。
4. **Python**：本地评估只需 `pandas`、`requests`、`yfinance`、`pyarrow`；GPU 模型只在 luyao4 / vast 上跑。
5. 克隆：`git clone https://github.com/ycsama0703/discrete-tool-sensitivity`。

---

## 9. 下一步（待办，按主线优先级）

1. **写论文**：按 `paper_storyline.md` 第 2 版的六步结构（含六½ 泛化）起草正文；理论部分按"已知结果的实例 + 我们的推广"表述。
2. **把两轮文献精读并入 `references.md`**（目前文献在各 theory 文档里，带 ✅/◐/○ 标记）；待补读：Miao et al. 2026
   *The Agentic Garden of Forking Paths*（全文，确认差异）、Raiffa & Schlaifer（EVPI 与决策不变性是否为教科书结论）、二元正态象限概率的原始出处。
3. **可选实验**（需 luyao4 GPU，未排期）：开源模型 token 概率检验生成层机制——默认值是否等于"只给 schema"时的 argmax、
   instruct 相对 base 是否 γ > 1、默认值跟语义走还是跟枚举位置走（`theory_narrative.md` 第 9 节）。
4. **暂缓**：S8 / S9（登记表中；旧的 S8 方向已不成立）；旗舰模型（sonnet）对照等预算。

---

## 10. 资源状态（2026-09-30）

- vast.ai：本研究租的机器都已销毁（账户里的 RTX 3060 Ti 48007284 处于 exited，不是本研究的）。
- luyao4：显卡空闲，无后台任务；服务器副本已同步到本文档所述状态。
- OpenRouter：约 $4.51。
