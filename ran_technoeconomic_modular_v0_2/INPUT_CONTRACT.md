# Proposed normalized interface: Ridha → RAN Techno-economic Model v0.2

**工作提议，不代表 Ridha 的实际数据输出。** 你未来可以写单独 adapter 转换其输出，保证下面模型接口稳定。所有 CSV 均 UTF-8，第一行列名，`.` 作为小数点，数值非负且有限。`scenario` / `site_type` / `technology` 不允许为空。

## 1. `dimensioning.csv` （最核心）

主键 `(scenario, year, site_type, technology)`，不允许重复。

| 字段 | 类型 | 释义 |
|---|---|---|
| `scenario` | string | 情景 ID，须出现在 scenarios.json |
| `year` | integer | 年份，含首尾年份 |
| `site_type` | string | macro / micro / indoor 等，可扩展 |
| `technology` | string | 与 technology_parameters.csv 的 category 匹配 |
| `existing_sites` | integer ≥ 0 | **当年年初**在网数量 |
| `new_sites` | integer ≥ 0 | 使存量增加的新增建设数量（gross additional installations），不是 net stock difference |
| `retired_sites` | integer ≥ 0 | 永久移除，未被 one-for-one 替换的数量 |
| `replacement_sites` | integer ≥ 0 | 原设备等量更新数量；可选，缺失默认为 **0** |

`ending_sites = existing_sites + new_sites - retired_sites`，下年同类 `existing_sites` 必须等于本年 `ending_sites`。`retired_sites + replacement_sites <= existing_sites`。缺席的某个类别只允许以前一年 ending stock 为零开始/结束。一个 scenario 的全部年份必须被覆盖。各情景在参考年开始时具有完全一致的各类别 S0 stock，不仅是总和相同。

**特别注意：** `replacement_sites` 的现阶段定义是同类别设备的等量更新。如果从旧技术迁移到新技术，不能简单地在同类别下填写 replacement；可能需要分别表现旧类别的 retirement 与新类别的 addition，或者未来拓展专用 tech-upgrade flow / adapter。实现之前需与 Ridha 核对。

## 2. `technology_parameters.csv`

主键 `(site_type, technology)`。所有字段是 synthetic 演示；将来需真实来源和不确定性范围。

| 字段 | 单位 | 含义 |
|---|---|---|
| `average_power_kw_per_site` | kW/site | 年内平均功率的简化常数，未包含 sleep/load 自适应 |
| `capex_eur_per_new_site` | EUR/site | 新增建设 CAPEX |
| `capex_eur_per_replacement_site` | EUR/site | 替换 CAPEX |
| `fixed_opex_eur_per_active_site_year_excl_energy` | EUR/site-year | 固定 OPEX，**不含电费** |
| `embodied_kgco2e_per_new_site` | kg CO₂e/site | 新建设备制造/部署影响，边界须一致 |
| `embodied_kgco2e_per_replacement_site` | kg CO₂e/site | 替换制造影响 |
| `eol_eur_per_removed_site` | EUR/removed site | 移除及 EoL 私人成本 |
| `eol_kgco2e_per_removed_site` | kg CO₂e/removed site | 退役与替换产生的 EoL 排放 |

同一技术类别参数目前对不同年份/情景是共同的。这是 Phase 1 的接口限制，不意味着未来各 scenario 的设备效率应该相同。你以后可以按照 `(scenario, year, site_type, technology)` 拓展 parameter table，或者把负载/运行小时 profile 单列为独立参数。

## 3. `annual_parameters.csv`

主键 `year`，每一年必须有一条。

- `electricity_price_eur_per_kwh`：constant EUR/kWh
- `grid_kgco2e_per_kwh`：kg CO₂e/kWh

两个参数目前所有情景公用，可在后续需要时进行情景特异化。

## 4. `traffic.csv`

主键 `year`，一列 `traffic_demand_pb_per_year`，PB/year，**共享外生 demand**。当前 Phase 1 将其并入 `annual_results.csv` 仅供比对，不通过 demand 直接推导网络容量/站点/功耗。不假设所有情景的 served traffic 都相同。

## 5. `scenarios.json`

```json
{
  "scenarios": [
    {"id": "BAU", "description": "Business-as-usual"},
    {"id": "SOBRIETY", "description": "Illustrative sobriety pathway"}
  ]
}
```

这是字段示例，不是要求情景只存在两种。必须恰好列出 `dimensioning.csv` 包含的全部 scenario ID。这里的文字只提供识别和解释；**scenario 数值是由 dimensioning.csv 数据体现**。

## 6. `config.json`

- `start_year`, `end_year`：研究时间范围，含首尾。
- `discount_rate`：real discount rate，默认规则为 `start_year` 现金流指数 0。
- `new_site_year_fraction`：新建在首次当年运作时间比例，位于 [0,1]。
- `retired_site_year_fraction`：退役在最后一年运作时间比例，位于 [0,1]。
- `sensitivity_discount_rates`（可选）：不同折现率下 NPC reweighting；不会改变 yearly site, energy, GHG or cost flows。
- `currency_price_basis`：仅说明价格基期，不做价格转换。

## 7. Explicit exclusions in v0.2

不模拟 traffic → network dimensioning、不模拟负载或 sleep mode、不生成 equipment-replacement schedule、不考虑 terminal salvage value、不包括 transport/core/spectrum/handsets、不计 revenue、不做 social LCA/positive enabled benefits/attribution，也不暗示 demo 结果具有现实标定精度。
