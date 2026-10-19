"""Operational, embodied (new and replacement), and end-of-life GHG accounting."""
from __future__ import annotations
import pandas as pd


def calculate_emissions(rows: pd.DataFrame) -> pd.DataFrame:
    """Append kgCO2e; includes no avoided emissions or monetized externalities."""
    df = rows.copy()
    df["operational_kgco2e"] = df.energy_kwh * df.grid_kgco2e_per_kwh
    df["embodied_kgco2e"] = (
        df.new_sites * df.embodied_kgco2e_per_new_site
        + df.replacement_sites * df.embodied_kgco2e_per_replacement_site
    )
    df["eol_kgco2e"] = (df.retired_sites + df.replacement_sites) * df.eol_kgco2e_per_removed_site
    df["total_kgco2e"] = df.operational_kgco2e + df.embodied_kgco2e + df.eol_kgco2e
    return df
