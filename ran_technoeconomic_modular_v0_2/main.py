"""Usage: python3 main.py --input-dir data/demo --output-dir outputs/demo"""
from __future__ import annotations

import argparse
from pathlib import Path
from model.pipeline import run_model
from model.analysis import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Modular RAN techno-economic demonstration")
    parser.add_argument("--input-dir", default="data/demo", help="A normalized scenario dataset directory")
    parser.add_argument("--output-dir", default="outputs/demo", help="Where results will be written")
    args = parser.parse_args()
    detailed, annual, summary, sensitivity, config = run_model(args.input_dir)
    write_outputs(detailed, annual, summary, args.output_dir, sensitivity)
    print("\nSYNTHETIC DEMO ONLY — NOT ORANGE DATA OR A RESEARCH RESULT")
    print(f"Period: {config['start_year']}–{config['end_year']}; base real discount rate: {config['discount_rate']:.1%}")
    print(summary[["scenario", "npc_eur", "total_energy_kwh", "total_kgco2e"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    print(f"\nSaved model outputs to {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
