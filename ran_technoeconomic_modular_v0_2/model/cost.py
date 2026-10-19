"""Operator-only private costs, in constant EUR, and net present cost (NPC)."""
from __future__ import annotations
import pandas as pd


def npv_factor(year: int, base_year: int, discount_rate: float) -> float:
    """Within-year costs treated at calendar-year start: base_year exponent zero."""
    return 1.0 / (1.0 + discount_rate) ** (year - base_year)


def calculate_costs(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    """New CAPEX, replacement, fixed and electricity OPEX, EoL, discounted cost."""
    df = rows.copy()
    df["new_capex_eur"] = df.new_sites * df.capex_eur_per_new_site
    df["replacement_capex_eur"] = df.replacement_sites * df.capex_eur_per_replacement_site
    df["fixed_opex_eur"] = (
        df.average_active_sites * df.fixed_opex_eur_per_active_site_year_excl_energy
    )
    df["electricity_opex_eur"] = df.energy_kwh * df.electricity_price_eur_per_kwh
    df["eol_cost_eur"] = (df.retired_sites + df.replacement_sites) * df.eol_eur_per_removed_site
    components = ["new_capex_eur", "replacement_capex_eur", "fixed_opex_eur", "electricity_opex_eur", "eol_cost_eur"]
    df["total_annual_cost_eur"] = df[components].sum(axis=1)
    df["discount_factor"] = df.year.map(
        lambda year: npv_factor(int(year), config["start_year"], config["discount_rate"])
    )
    df["discounted_annual_cost_eur"] = df.total_annual_cost_eur * df.discount_factor
    return df
