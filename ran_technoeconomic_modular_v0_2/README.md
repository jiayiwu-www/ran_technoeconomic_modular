# Modular RAN Techno-economic Model — v0.2 (Phase 1)

**可运行的 Python 研究框架，不是已经校准的 Orange/Ridha 计算结果。** 所有 `data/demo/` 中的流量、站点、价格、排放系数和情景路径均为 **synthetic demonstration data**。不能将示例输出用于论文中的实证结论或情景排序。

## 1. 如何运行（Mac / Terminal）

解压后打开 Terminal，进入解压出的目录（路径请根据实际位置修改）：

```bash
cd ~/Downloads/ran_technoeconomic_modular_v0_2
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py --input-dir data/demo --output-dir outputs/demo
python3 -m unittest discover -s tests -v
```

建议使用 Python 3.10 或更新版本。已配置好 pandas/matplotlib 的环境可跳过创建虚拟环境。命令应该在项目根目录执行。依赖主要是 pandas、matplotlib；没有调用 Orange 内部程序。

## 2. 项目结构 —— 按约定的六模块组织

```text
ran_technoeconomic_modular_v0_2/
├── main.py                   # 命令行入口
├── model/
│   ├── data_loader.py        # 1. CSV/JSON 读取与合并
│   ├── scenario.py           # 2. 情景目录、标签、S0 起始一致性
│   ├── energy.py             # 3. 年度 RAN 电耗
│   ├── emissions.py          # 4. Operational + embodied + EoL GHG
│   ├── cost.py               # 5. CAPEX + OPEX + EoL + NPC
│   ├── analysis.py           # 6. 情景比较/绘图/折现率敏感性分析
│   ├── schema.py             # 辅助：校验数据接口与站点存量
│   ├── pipeline.py           # 辅助：按既定顺序执行上述模块
│   └── __init__.py
├── data/
│   └── demo/
│       ├── config.json
│       ├── scenarios.json
│       ├── dimensioning.csv
│       ├── technology_parameters.csv
│       ├── annual_parameters.csv
│       └── traffic.csv
├── outputs/demo/             # 本次已跑出的示例文件
├── tests/test_model.py
├── INPUT_CONTRACT.md
└── requirements.txt
```

`schema.py` 和 `pipeline.py` **不是额外的研究计算模块**，分别负责输入验证和连接六个模块。每个研究计算功能保存在自己的文件里，便于以后独立调整。

## 3. Pipeline（当前简化版）

```text
traffic.csv  (common traffic demand, not served traffic)
     │ [used only for reference]
     ▼
Ridha's external dimensioning model  [NOT replicated here]
     │
     ▼
dimensioning.csv (scenario / year / site_type / technology)
     │
     ├── schema.py + scenario.py  -> validate stock, S0, scenario IDs
     ├── data_loader.py          -> merge annual/technology parameters
     ├── energy.py               -> annual energy (kWh)
     ├── emissions.py            -> operational / embodied / EoL CO2e (kg)
     ├── cost.py                 -> CAPEX / OPEX / EoL / discounted costs (EUR)
     └── analysis.py             -> annual tables / scenario summary / charts
                               -> discount-rate sensitivity (NPC only)
```

**保持“共同 traffic demand 不代表共同 served traffic”的区别。** 当前 `traffic.csv` 不用于估算站点数量、电耗或收入，只是进入结果表供核对。

## 4. 当前公式（必须理解的建模约定）

设 `s` 为场景、`t` 为年度、`k` 为站点/技术类别：

- **Stock:** `N_end = N_start + N_new - N_retired`。`replacement_sites` 是 like-for-like 更新，不改变净存量。更新和永久退役不允许超过年初存量。
- **Average active sites:** `N_avg = N_start + f_new N_new - (1-f_retired)N_retired`。示例的 `f_new=f_retired=0.5` 是暂定年中安装/退役假设。
- **Electricity:** `Energy_kWh = N_avg × average_power_kW × calendar_year_hours`；闰年是 8784 小时。
- **Operational CO₂e:** `Energy_kWh × grid_kgco2e_per_kWh`。
- **Embodied CO₂e:** `N_new × embodied_new + N_replacement × embodied_replacement`。
- **EoL CO₂e:** `(N_retired + N_replacement) × eol_emissions`。
- **CAPEX:** `N_new × capex_new + N_replacement × capex_replacement`。
- **OPEX:** `N_avg × fixed_opex_excluding_electricity + Energy_kWh × electricity_price`。
- **EoL cost:** `(N_retired + N_replacement) × eol_unit_cost`。
- **NPC:** `Σ_{t=start}^{end} annual_cost(t)/(1+r)^(t-start)`，以 start year 为 exponent 0，适用于常价 EUR 和与之匹配的 real discount rate。

注意 **private cost-only**：没有 revenue、carbon pricing、positive enabled benefits 或 social LCA。排放量是物理 CO₂e，并没有再额外纳入 operator private costs。参考年以前已经存在的网络资产视为 sunk stock，其历史建设成本不进入未来 CAPEX。尚未处理期末 residual value、设备寿命自动更新及使用寿命范围外的排放。

## 5. 当前能修改什么？

- **改变 horizon / 折现率 / 投运年比例**：编辑 `data/demo/config.json`（建议先复制 demo 再编辑）。
- **改变 scenarios 的标识和说明**：编辑 `scenarios.json`，同时保证 `dimensioning.csv` 的 scenario IDs 一一对应。情景说明**不会**偷偷改变模型结果。
- **改变 scenario 部署路径**：编辑 `dimensioning.csv` 中的站点、新建、永久退役、替换数量，注意跨年存量衔接与四场景共同 S0。
- **改变设备功率/固定 OPEX/CAPEX/排放因子**：编辑 `technology_parameters.csv`；与 category `(site_type, technology)` 对应。
- **改变每年电价与 grid emissions**：编辑 `annual_parameters.csv`。
- **替换需求预测**：编辑 `traffic.csv`。目前只做跟踪，不改变 dimensioning 结果。
- **敏感性分析**：`config.json` 的 `sensitivity_discount_rates` 是 *演示用* 折现率，`analysis.py` 根据不变的逐年成本重算 NPC，不模拟情景路径随折现率变化。

## 6. 输出文件

`outputs/demo/` 中包括 `detailed_results.csv`（技术类别级）、`annual_results.csv`（scenario-year）、`scenario_summary.csv`（15 年汇总）、`discount_rate_sensitivity.csv`，以及 `energy_by_year.png`、`emissions_by_year.png`、`npc_by_year.png`。

原始 synthetic 输入可以轻易造成一个情景看似更“优”，但该排序没有科学意义。

## 7. 后续和 Ridha 的对接

将 `data/demo/` **完整复制** 为 `data/orange_normalized/`，把 Orange 原始数据经过 *adapter* 映射到同样的字段（详情参见 `INPUT_CONTRACT.md`），然后执行：

```bash
python3 main.py --input-dir data/orange_normalized --output-dir outputs/orange_normalized
```

注意 adapter 需要区分 net new installations、permanent retirements 和 one-for-one replacements；如果 Ridha 只给净增站点，而不给 gross flows，**不能直接把净增量当 new_sites**。这会错误低估 CAPEX、replacement 和 embodied impacts。此时需要额外数据或确认简化假设。

## 8. 当前局限与下一步

下一阶段需要讨论以下问题，再扩写对应文件：

1. `energy.py`：utilization、sleep-mode、RER、技术配置是否由 dimensioning 给出？平均功率能否用情景/年份/站点/技术相关 profile 替换？
2. `cost.py`：是 annual exogenous replacements 还是通过 asset lifetime + cohort model 自动生成？如何处理升级改造与期末残值？
3. `emissions.py`：device-specific embodied factors 是否有统一的边界？power mix 是否应加入不同情景？
4. `analysis.py`：更一般的敏感性/不确定性传播，避免仅观察折现率。
5. 更远期独立扩展 social LCA / attribution / indirect positive benefits；**不会**把它们当成已实现的方法。
