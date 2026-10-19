"""RAN operational energy module. Presently a simple average-power approach."""
from __future__ import annotations

import calendar
import pandas as pd


def calculate_energy(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Append physical site balances and annual energy (kWh).

    Average power by site type/technology is illustrative and fixed here.
    This is NOT yet a utilization, load, RER, sleep-mode, or capacity model.
    """
    df = rows.copy()
    df["ending_sites"] = df.existing_sites + df.new_sites - df.retired_sites
    df["average_active_sites"] = (
        df.existing_sites
        + config["new_site_year_fraction"] * df.new_sites
        - (1 - config["retired_site_year_fraction"]) * df.retired_sites
    )
    df["hours_per_year"] = df.year.map(lambda y: 24 * (366 if calendar.isleap(int(y)) else 365))
    df["energy_kwh"] = df.average_active_sites * df.average_power_kw_per_site * df.hours_per_year
    return df
