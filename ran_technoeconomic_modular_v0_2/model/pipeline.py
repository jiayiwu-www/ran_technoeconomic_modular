"""One transparent pipeline; no physics, cost formulas, or scenario rules here."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

from .data_loader import load_inputs, attach_parameters
from .scenario import load_scenarios
from .energy import calculate_energy
from .emissions import calculate_emissions
from .cost import calculate_costs
from .analysis import aggregate_results, discount_rate_sensitivity


def run_model(input_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Returns detailed, annual, summary, sensitivity, configuration."""
    config, dimensioning, tech, annual_params, traffic = load_inputs(input_dir)
    load_scenarios(input_dir, dimensioning, config["start_year"])
    detailed = attach_parameters(dimensioning, tech, annual_params)
    detailed = calculate_energy(detailed, config)
    detailed = calculate_emissions(detailed)
    detailed = calculate_costs(detailed, config)
    annual, summary = aggregate_results(detailed, traffic)
    rates = config.get("sensitivity_discount_rates", [])
    sensitivity = discount_rate_sensitivity(annual, config["start_year"], rates)
    return detailed, annual, summary, sensitivity, config
