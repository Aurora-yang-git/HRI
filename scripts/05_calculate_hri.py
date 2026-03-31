#!/usr/bin/env python3
"""
05_calculate_hri.py — Calculate Heat Risk Index (HRI).

HRI = Hazard × Exposure × Vulnerability

Where:
  - Hazard    = normalize_positive(UTCI mean)
  - Exposure  = normalize_positive(population density)
  - Vulnerability = mean(
        normalize_negative(nightlight),   # higher NL -> lower vulnerability
        normalize_negative(GDP),          # higher GDP -> lower vulnerability
        normalize_positive(pop_density),  # proxy for age-sensitive population
    )

All normalization maps to [0.1, 0.9] range.
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BLOCKS_FILE, NORM_MAX, NORM_MIN


def normalize_positive(series: pd.Series) -> pd.Series:
    """Positive normalization: higher value -> higher risk.
    I_norm = 0.1 + 0.8 × (I − Min) / (Max − Min)
    """
    s_min, s_max = series.min(), series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)
    return NORM_MIN + (NORM_MAX - NORM_MIN) * (series - s_min) / (s_max - s_min)


def normalize_negative(series: pd.Series) -> pd.Series:
    """Negative normalization: higher value -> lower risk.
    I_norm = 0.1 + 0.8 × (Max − I) / (Max − Min)
    """
    s_min, s_max = series.min(), series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)
    return NORM_MIN + (NORM_MAX - NORM_MIN) * (s_max - series) / (s_max - s_min)


def main():
    print("=" * 60)
    print("STEP 5: Calculate HRI")
    print("=" * 60)

    # Load blocks
    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")
    print(f"  Columns: {list(blocks.columns)}")

    # -- Hazard ---------------------------------------------------------
    print("\n[1/4] Hazard = normalize_positive(UTCI) ...")
    blocks["hazard"] = normalize_positive(blocks["utci_mean"])
    print(f"  hazard: [{blocks['hazard'].min():.3f}, {blocks['hazard'].max():.3f}]")

    # -- Exposure -------------------------------------------------------
    print("\n[2/4] Exposure = normalize_positive(pop_density) ...")
    blocks["exposure"] = normalize_positive(blocks["pop_density"])
    print(f"  exposure: [{blocks['exposure'].min():.3f}, {blocks['exposure'].max():.3f}]")

    # -- Vulnerability --------------------------------------------------
    print("\n[3/4] Vulnerability = mean(NL_neg, GDP_neg, PD_pos) ...")
    nl_norm = normalize_negative(blocks["nl_mean"])
    gdp_norm = normalize_negative(blocks["gdp_mean"])
    pd_norm = normalize_positive(blocks["pop_density"])

    blocks["vulnerability"] = (nl_norm + gdp_norm + pd_norm) / 3.0
    print(f"  vulnerability: [{blocks['vulnerability'].min():.3f}, {blocks['vulnerability'].max():.3f}]")

    # -- HRI ------------------------------------------------------------
    print("\n[4/4] HRI = Hazard × Exposure × Vulnerability ...")
    blocks["hri"] = blocks["hazard"] * blocks["exposure"] * blocks["vulnerability"]
    blocks["hri_norm"] = normalize_positive(blocks["hri"])

    print(f"  hri:      [{blocks['hri'].min():.4f}, {blocks['hri'].max():.4f}]")
    print(f"  hri_norm: [{blocks['hri_norm'].min():.3f}, {blocks['hri_norm'].max():.3f}]")

    # Save
    blocks.to_file(BLOCKS_FILE, driver="GPKG")
    print(f"\n  [OK] Saved with HRI -> {BLOCKS_FILE}")

    print("\n" + "=" * 60)
    print("HRI calculation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
