"""Run: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from model.data_loader import load_inputs
from model.cost import npv_factor
from model.pipeline import run_model
from model.analysis import write_outputs

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.details, self.annual, self.summary, self.sensitivity, self.cfg = run_model(DEMO)

    def test_full_demo_pipeline(self):
        self.assertEqual((self.cfg["start_year"], self.cfg["end_year"]), (2026, 2040))
        self.assertEqual(self.annual.shape[0], 60)
        self.assertEqual(set(self.summary.scenario), {"BAU", "SOBRIETY", "DENSIFICATION", "CONSTRAINED"})
        self.assertTrue((self.summary.npc_eur > 0).all())

    def test_s0_stock_is_same_for_all_scenarios(self):
        _, dim, _, _, _ = load_inputs(DEMO)
        first = dim[dim.year == 2026]
        total = first.groupby("scenario").existing_sites.sum()
        self.assertEqual(total.nunique(), 1)
        self.assertEqual(int(total.iloc[0]), 360)

    def test_common_traffic_is_exogenous(self):
        self.assertEqual(self.annual.groupby("year").traffic_demand_pb_per_year.nunique().max(), 1)

    def test_stock_balance_and_replacements(self):
        self.assertTrue((self.details.ending_sites == (
            self.details.existing_sites + self.details.new_sites - self.details.retired_sites
        )).all())
        self.assertTrue((self.details.average_active_sites >= 0).all())
        replaced = self.details.loc[self.details.replacement_sites.gt(0)].iloc[0]
        self.assertGreater(replaced.replacement_capex_eur, 0)
        self.assertAlmostEqual(replaced.eol_cost_eur,
                               (replaced.retired_sites + replaced.replacement_sites) * replaced.eol_eur_per_removed_site)

    def test_zero_new_sites_means_zero_new_build_capex(self):
        rows = self.details.loc[self.details.new_sites.eq(0)]
        self.assertFalse(rows.empty)
        self.assertTrue(rows.new_capex_eur.eq(0).all())

    def test_energy_formula_and_leap_year(self):
        row = self.details.iloc[0]
        self.assertAlmostEqual(row.energy_kwh, row.average_active_sites * row.average_power_kw_per_site * row.hours_per_year)
        self.assertEqual(set(self.details.loc[self.details.year.eq(2028), "hours_per_year"]), {8784})

    def test_ghg_breakdown(self):
        parts = self.summary[["total_operational_kgco2e", "total_embodied_kgco2e", "total_eol_kgco2e"]].sum(axis=1)
        self.assertTrue(((self.summary.total_kgco2e - parts).abs() < 1e-5).all())

    def test_electricity_cost_not_double_counted(self):
        row = self.details.iloc[0]
        self.assertAlmostEqual(row.fixed_opex_eur, row.average_active_sites * row.fixed_opex_eur_per_active_site_year_excl_energy)
        self.assertAlmostEqual(row.electricity_opex_eur, row.energy_kwh * row.electricity_price_eur_per_kwh)
        self.assertAlmostEqual(row.total_annual_cost_eur, sum([
            row.new_capex_eur, row.replacement_capex_eur, row.fixed_opex_eur,
            row.electricity_opex_eur, row.eol_cost_eur,
        ]))

    def test_npc_discount_formula(self):
        self.assertEqual(sum(100 * npv_factor(y, 2026, 0) for y in [2026, 2027, 2028]), 300)
        self.assertAlmostEqual(100 * npv_factor(2027, 2026, .04), 100 / 1.04)

    def test_sensitivity_same_npc_at_base_rate(self):
        rates = self.sensitivity[self.sensitivity.discount_rate.eq(self.cfg["discount_rate"])]
        joined = rates.merge(self.summary[["scenario", "npc_eur"]], on="scenario", suffixes=("_sense", "_base"))
        self.assertEqual(len(joined), len(self.summary))
        for row in joined.itertuples(index=False):
            self.assertAlmostEqual(row.npc_eur_sense, row.npc_eur_base, delta=1e-5)

    def test_zero_discount_rate_equals_undiscounted(self):
        zero = self.sensitivity[self.sensitivity.discount_rate.eq(0.0)]
        joined = zero.merge(self.summary, on="scenario")
        for row in joined.itertuples(index=False):
            self.assertAlmostEqual(row.npc_eur_x, row.total_undiscounted_cost_eur, delta=1e-5)

    def test_outputs_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_outputs(self.details, self.annual, self.summary, tmp, self.sensitivity)
            for filename in ["detailed_results.csv", "annual_results.csv", "scenario_summary.csv",
                             "discount_rate_sensitivity.csv", "energy_by_year.png",
                             "emissions_by_year.png", "npc_by_year.png"]:
                self.assertGreater((Path(tmp) / filename).stat().st_size, 0)


class InvalidInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        for file in DEMO.iterdir():
            shutil.copy2(file, self.folder / file.name)

    def tearDown(self):
        self.tmp.cleanup()

    def rewrite_csv(self, filename, fn):
        path = self.folder / filename
        df = pd.read_csv(path)
        df = fn(df)
        df.to_csv(path, index=False)

    def test_missing_replacement_column_is_explicit_zero(self):
        self.rewrite_csv("dimensioning.csv", lambda df: df.drop(columns="replacement_sites"))
        _, dim, _, _, _ = load_inputs(self.folder)
        self.assertTrue(dim.replacement_sites.eq(0).all())

    def test_stock_discontinuity_rejected(self):
        def mutate(df):
            cond = (df.scenario == "BAU") & (df.year == 2028) & (df.site_type == "macro")
            df.loc[cond, "existing_sites"] += 1
            return df
        self.rewrite_csv("dimensioning.csv", mutate)
        with self.assertRaisesRegex(ValueError, "stock discontinuity"):
            load_inputs(self.folder)

    def test_baseline_mismatch_rejected(self):
        def mutate(df):
            cond = (df.scenario == "BAU") & (df.site_type == "macro")
            df.loc[cond, "existing_sites"] += 1
            return df
        self.rewrite_csv("dimensioning.csv", mutate)
        with self.assertRaisesRegex(ValueError, "same baseline stock"):
            run_model(self.folder)

    def test_wrong_scenario_ids_rejected(self):
        path = self.folder / "scenarios.json"
        obj = json.loads(path.read_text())
        obj["scenarios"][0]["id"] = "BAU_TYPO"
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "mismatched IDs"):
            run_model(self.folder)

    def test_unknown_technology_rejected(self):
        def mutate(df):
            df.loc[df.site_type.eq("macro"), "technology"] = "not_a_technology"
            return df
        self.rewrite_csv("dimensioning.csv", mutate)
        with self.assertRaisesRegex(ValueError, "technology_parameters.csv: missing categories"):
            load_inputs(self.folder)

    def test_negative_price_rejected(self):
        def mutate(df):
            df.loc[df.index[0], "electricity_price_eur_per_kwh"] = -1
            return df
        self.rewrite_csv("annual_parameters.csv", mutate)
        with self.assertRaisesRegex(ValueError, "finite nonnegative"):
            load_inputs(self.folder)

    def test_infinite_power_rejected(self):
        def mutate(df):
            df.loc[df.index[0], "average_power_kw_per_site"] = float("inf")
            return df
        self.rewrite_csv("technology_parameters.csv", mutate)
        with self.assertRaisesRegex(ValueError, "finite nonnegative"):
            load_inputs(self.folder)

    def test_duplicate_network_row_rejected(self):
        self.rewrite_csv("dimensioning.csv", lambda df: pd.concat([df, df.iloc[[0]]], ignore_index=True))
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            load_inputs(self.folder)

    def test_missing_traffic_year_rejected(self):
        self.rewrite_csv("traffic.csv", lambda df: df.loc[df.year.ne(2030)])
        with self.assertRaisesRegex(ValueError, "cover every year"):
            load_inputs(self.folder)

    def test_retirement_exceeding_stock_rejected(self):
        def mutate(df):
            df.loc[df.index[0], "retired_sites"] = 1000
            return df
        self.rewrite_csv("dimensioning.csv", mutate)
        with self.assertRaisesRegex(ValueError, "exceeds starting stock"):
            load_inputs(self.folder)


if __name__ == "__main__":
    unittest.main()
