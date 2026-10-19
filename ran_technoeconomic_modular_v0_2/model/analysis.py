"""Scenario-level aggregation, targeted discount-rate sensitivity, CSV/PNG outputs."""
from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .cost import npv_factor

SUM_FIELDS = [
    "existing_sites", "new_sites", "retired_sites", "replacement_sites", "ending_sites", "average_active_sites",
    "energy_kwh", "operational_kgco2e", "embodied_kgco2e", "eol_kgco2e", "total_kgco2e",
    "new_capex_eur", "replacement_capex_eur", "fixed_opex_eur", "electricity_opex_eur",
    "eol_cost_eur", "total_annual_cost_eur", "discounted_annual_cost_eur",
]


def aggregate_results(detailed: pd.DataFrame, traffic: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sum into one row per scenario/year, then whole-horizon scenario totals."""
    annual = (
        detailed.groupby(["scenario", "year"], as_index=False)[SUM_FIELDS].sum()
        .merge(traffic, on="year", how="left", validate="many_to_one")
        .sort_values(["scenario", "year"])
        .reset_index(drop=True)
    )
    annual["cumulative_discounted_cost_eur"] = annual.groupby("scenario")["discounted_annual_cost_eur"].cumsum()
    summary = (
        annual.groupby("scenario", as_index=False)
        .agg(
            total_energy_kwh=("energy_kwh", "sum"),
            total_operational_kgco2e=("operational_kgco2e", "sum"),
            total_embodied_kgco2e=("embodied_kgco2e", "sum"),
            total_eol_kgco2e=("eol_kgco2e", "sum"),
            total_kgco2e=("total_kgco2e", "sum"),
            total_undiscounted_cost_eur=("total_annual_cost_eur", "sum"),
            npc_eur=("discounted_annual_cost_eur", "sum"),
        )
        .sort_values("scenario")
        .reset_index(drop=True)
    )
    return annual, summary


def discount_rate_sensitivity(annual: pd.DataFrame, start_year: int, rates: list[float]) -> pd.DataFrame:
    """Recompute NPC from unchanged undiscounted costs at each *illustrative* rate."""
    records = []
    for rate in rates:
        for name, block in annual.groupby("scenario"):
            npc = sum(
                float(row.total_annual_cost_eur) * npv_factor(int(row.year), start_year, float(rate))
                for row in block.itertuples(index=False)
            )
            records.append({"scenario": name, "discount_rate": float(rate), "npc_eur": npc})
    return pd.DataFrame.from_records(records, columns=["scenario", "discount_rate", "npc_eur"])


def write_outputs(detailed: pd.DataFrame, annual: pd.DataFrame, summary: pd.DataFrame,
                  output_dir: str | Path, sensitivity: pd.DataFrame | None = None) -> None:
    """Export intermediate accounting results to make the methodology auditable."""
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    for name, frame in [
        ("detailed_results.csv", detailed), ("annual_results.csv", annual),
        ("scenario_summary.csv", summary),
    ]:
        frame.to_csv(folder / name, index=False, float_format="%.8f")
    if sensitivity is not None:
        sensitivity.to_csv(folder / "discount_rate_sensitivity.csv", index=False, float_format="%.8f")

    # 1 GWh = 1e6 kWh; 1 ktCO2e = 1e6 kgCO2e; 1 million EUR = 1e6 EUR.
    for column, ylabel, filename in [
        ("energy_kwh", "Annual RAN electricity (GWh)", "energy_by_year.png"),
        ("total_kgco2e", "Annual lifecycle emissions (ktCO2e)", "emissions_by_year.png"),
        ("cumulative_discounted_cost_eur", "Cumulative discounted cost (million EUR)", "npc_by_year.png"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 5))
        for name, block in annual.groupby("scenario", sort=True):
            ax.plot(block.year, block[column] / 1e6, marker="o", markersize=2.8, label=name)
        ax.set(xlabel="Calendar year", ylabel=ylabel, title="SYNTHETIC DEMONSTRATION — NOT ORANGE RESULTS")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(folder / filename, dpi=150)
        plt.close(fig)
