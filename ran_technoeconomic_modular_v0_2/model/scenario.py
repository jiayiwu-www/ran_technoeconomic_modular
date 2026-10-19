"""Explicit scenario IDs and metadata; S0 baseline consistency validation.

A scenario's actual network choices reside in dimensioning.csv, not its label.
No ungrounded quantitative 'sobriety' or 'densification' rule is inferred.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from .schema import STOCK_KEYS


def load_scenarios(input_dir: str | Path, dim: pd.DataFrame, start_year: int) -> pd.DataFrame:
    """Read scenario IDs/descriptions and verify normalized dimensioning matches."""
    with (Path(input_dir) / "scenarios.json").open(encoding="utf-8") as file:
        obj = json.load(file)
    items = obj.get("scenarios")
    if not isinstance(items, list) or not items:
        raise ValueError("scenarios.json: 'scenarios' must be a nonempty list")
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("scenarios.json: each scenario must be an object")
    frame = pd.DataFrame(items)
    required = {"id", "description"}
    if not required.issubset(frame.columns):
        raise ValueError(f"scenarios.json: missing {required - set(frame.columns)}")
    if frame[["id", "description"]].isna().any().any() or any(
        frame[key].astype(str).str.strip().eq("").any() for key in ["id", "description"]
    ):
        raise ValueError("scenarios.json: IDs and descriptions must not be blank")
    if frame["id"].duplicated().any():
        raise ValueError("scenarios.json: duplicate scenario ID")
    given = set(frame["id"])
    observed = set(dim["scenario"])
    if given != observed:
        raise ValueError(f"scenarios.json: mismatched IDs: configured={sorted(given)}, dimensioning={sorted(observed)}")

    # All scenario paths begin from the same disaggregated equipment/site stock.
    snapshots = {}
    for name, block in dim.loc[dim.year.eq(start_year)].groupby("scenario"):
        snapshots[name] = {
            tuple(row[c] for c in STOCK_KEYS): int(row.existing_sites)
            for _, row in block.iterrows() if row.existing_sites > 0
        }
    if len({tuple(sorted(s.items())) for s in snapshots.values()}) != 1:
        raise ValueError("dimensioning.csv: scenarios must share the same baseline stock (S0)")
    return frame[["id", "description"]].copy()
