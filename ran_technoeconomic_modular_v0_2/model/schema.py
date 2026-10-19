"""Strict data-contract validation; no substantive modeling calculations."""
from __future__ import annotations

import math
import pandas as pd

DIM_KEYS = ["scenario", "year", "site_type", "technology"]
STOCK_KEYS = ["site_type", "technology"]
DIM_REQUIRED = DIM_KEYS + ["existing_sites", "new_sites", "retired_sites"]
TECH_PARAMS = [
    "average_power_kw_per_site",
    "capex_eur_per_new_site",
    "capex_eur_per_replacement_site",
    "fixed_opex_eur_per_active_site_year_excl_energy",
    "embodied_kgco2e_per_new_site",
    "embodied_kgco2e_per_replacement_site",
    "eol_eur_per_removed_site",
    "eol_kgco2e_per_removed_site",
]
ANNUAL_PARAMS = ["electricity_price_eur_per_kwh", "grid_kgco2e_per_kwh"]


def required(df: pd.DataFrame, fields: list[str], filename: str) -> None:
    missing = sorted(set(fields) - set(df.columns))
    if missing:
        raise ValueError(f"{filename}: missing required column(s): {missing}")
    if df.empty:
        raise ValueError(f"{filename}: cannot be empty")


def numeric_nonnegative(df: pd.DataFrame, fields: list[str], filename: str) -> None:
    for col in fields:
        try:
            df[col] = pd.to_numeric(df[col], errors="raise")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{filename}: {col} must be numeric") from exc
        if not df[col].notna().all() or not df[col].map(math.isfinite).all() or (df[col] < 0).any():
            raise ValueError(f"{filename}: {col} must contain finite nonnegative numbers")


def nonnegative_integers(df: pd.DataFrame, fields: list[str], filename: str) -> None:
    numeric_nonnegative(df, fields, filename)
    for col in fields:
        if (df[col] != df[col].round()).any():
            raise ValueError(f"{filename}: {col} must contain integers")
        df[col] = df[col].astype("int64")


def unique(df: pd.DataFrame, keys: list[str], filename: str) -> None:
    if df.duplicated(keys).any():
        row = df.loc[df.duplicated(keys), keys].iloc[0].to_dict()
        raise ValueError(f"{filename}: duplicate key {row}")


def text_fields(df: pd.DataFrame, fields: list[str], filename: str) -> None:
    for col in fields:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"{filename}: {col} must not be empty")
        df[col] = df[col].astype(str).str.strip()


def validate_config(cfg: dict) -> None:
    fields = ("start_year", "end_year", "discount_rate", "new_site_year_fraction", "retired_site_year_fraction")
    for field in fields:
        if field not in cfg:
            raise ValueError(f"config.json: missing '{field}'")
    for field in ("start_year", "end_year"):
        if type(cfg[field]) is not int:
            raise ValueError(f"config.json: {field} must be an integer year")
    if cfg["end_year"] < cfg["start_year"]:
        raise ValueError("config.json: end_year must be >= start_year")
    for field in ("discount_rate", "new_site_year_fraction", "retired_site_year_fraction"):
        value = cfg[field]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"config.json: {field} must be a finite number")
    if not (0 <= cfg["discount_rate"] < 1):
        raise ValueError("config.json: discount_rate must be in [0,1)")
    for f in ("new_site_year_fraction", "retired_site_year_fraction"):
        if not 0 <= cfg[f] <= 1:
            raise ValueError(f"config.json: {f} must be in [0,1]")
    if "sensitivity_discount_rates" in cfg:
        values = cfg["sensitivity_discount_rates"]
        if not isinstance(values, list) or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or
            not math.isfinite(v) or not 0 <= v < 1 for v in values
        ):
            raise ValueError("config.json: sensitivity_discount_rates must be a list of numbers in [0,1)")


def validate_tables(cfg: dict, dim: pd.DataFrame, tech: pd.DataFrame,
                    annual: pd.DataFrame, traffic: pd.DataFrame) -> None:
    """Validate input formats, units, yearly coverage, and physical stock continuity."""
    required(dim, DIM_REQUIRED, "dimensioning.csv")
    if "replacement_sites" not in dim:
        dim["replacement_sites"] = 0  # Explicitly zero, never inferred from site lifetime.
    nonnegative_integers(dim, ["year", "existing_sites", "new_sites", "retired_sites", "replacement_sites"], "dimensioning.csv")
    text_fields(dim, ["scenario", "site_type", "technology"], "dimensioning.csv")
    unique(dim, DIM_KEYS, "dimensioning.csv")

    required(tech, STOCK_KEYS + TECH_PARAMS, "technology_parameters.csv")
    text_fields(tech, STOCK_KEYS, "technology_parameters.csv")
    numeric_nonnegative(tech, TECH_PARAMS, "technology_parameters.csv")
    unique(tech, STOCK_KEYS, "technology_parameters.csv")

    required(annual, ["year"] + ANNUAL_PARAMS, "annual_parameters.csv")
    nonnegative_integers(annual, ["year"], "annual_parameters.csv")
    numeric_nonnegative(annual, ANNUAL_PARAMS, "annual_parameters.csv")
    unique(annual, ["year"], "annual_parameters.csv")

    required(traffic, ["year", "traffic_demand_pb_per_year"], "traffic.csv")
    nonnegative_integers(traffic, ["year"], "traffic.csv")
    numeric_nonnegative(traffic, ["traffic_demand_pb_per_year"], "traffic.csv")
    unique(traffic, ["year"], "traffic.csv")

    years = set(range(cfg["start_year"], cfg["end_year"] + 1))
    for name, frame in [("annual_parameters.csv", annual), ("traffic.csv", traffic)]:
        if set(frame["year"]) != years:
            raise ValueError(f"{name}: must cover every year {cfg['start_year']}–{cfg['end_year']}")
    if not set(dim.year).issubset(years):
        raise ValueError("dimensioning.csv: year outside the requested horizon")
    for scenario_id, block in dim.groupby("scenario"):
        if set(block.year) != years:
            raise ValueError(f"dimensioning.csv: scenario {scenario_id} lacks year(s)")
        check_stock_continuity(block, cfg, scenario_id)

    missing = dim[STOCK_KEYS].drop_duplicates().merge(
        tech[STOCK_KEYS], on=STOCK_KEYS, how="left", indicator=True
    )
    missing = missing.loc[missing._merge.eq("left_only")]
    if not missing.empty:
        raise ValueError(f"technology_parameters.csv: missing categories {missing[STOCK_KEYS].to_dict('records')}")


def check_stock_continuity(block: pd.DataFrame, cfg: dict, scenario: str) -> None:
    """Site replacement conserves count. Retirement lowers count; new build adds count."""
    previous: dict[tuple[str, str], int] | None = None
    for year in range(cfg["start_year"], cfg["end_year"] + 1):
        start, end = {}, {}
        for row in block.loc[block.year.eq(year)].itertuples(index=False):
            key = (row.site_type, row.technology)
            if row.retired_sites + row.replacement_sites > row.existing_sites:
                raise ValueError(f"dimensioning.csv: retirement/replacement exceeds starting stock: {scenario}/{year}/{key}")
            start[key] = int(row.existing_sites)
            end[key] = int(row.existing_sites + row.new_sites - row.retired_sites)
        if previous is not None:
            for key in set(previous) | set(start):
                if previous.get(key, 0) != start.get(key, 0):
                    raise ValueError(
                        f"dimensioning.csv: stock discontinuity {scenario}/{year}/{key}: "
                        f"expected {previous.get(key, 0)}, received {start.get(key, 0)}"
                    )
        previous = end
