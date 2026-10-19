"""Read normalized network outputs and exogenous parameters. No calculations."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from .schema import validate_config, validate_tables


def load_inputs(input_dir: str | Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (config, dimensioning, technology, annual_parameters, common_traffic)."""
    folder = Path(input_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input directory not found: {folder}")
    with (folder / "config.json").open(encoding="utf-8") as file:
        cfg = json.load(file)
    validate_config(cfg)
    dimensioning = pd.read_csv(folder / "dimensioning.csv")
    technology = pd.read_csv(folder / "technology_parameters.csv")
    annual_parameters = pd.read_csv(folder / "annual_parameters.csv")
    traffic = pd.read_csv(folder / "traffic.csv")
    validate_tables(cfg, dimensioning, technology, annual_parameters, traffic)
    return cfg, dimensioning, technology, annual_parameters, traffic


def attach_parameters(dimensioning: pd.DataFrame, tech: pd.DataFrame,
                      annual: pd.DataFrame) -> pd.DataFrame:
    """Join validated inputs by category and year, preserving dimensioning rows."""
    return (
        dimensioning.merge(tech, on=["site_type", "technology"], how="left", validate="many_to_one")
        .merge(annual, on="year", how="left", validate="many_to_one")
        .sort_values(["scenario", "year", "site_type", "technology"])
        .reset_index(drop=True)
    )
