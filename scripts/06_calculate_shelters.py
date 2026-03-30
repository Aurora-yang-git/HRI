#!/usr/bin/env python3
"""
06_calculate_shelters.py — Calculate heat shelter indices.

OHSI (Outdoor Heat Shelter Index):
  OHSI = normalize(green_area_m2 / pop_sum)

IHSI (Indoor Heat Shelter Index):
  IHSI = normalize((poi_density / pop_density) × mean_wt)
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BLOCKS_FILE, NORM_MAX, NORM_MIN


def normalize_positive(series: pd.Series) -> pd.Series:
    """Positive normalization to [0.1, 0.9]."""
    s_min, s_max = series.min(), series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)
    return NORM_MIN + (NORM_MAX - NORM_MIN) * (series - s_min) / (s_max - s_min)


def main():
    print("=" * 60)
    print("STEP 6: Calculate Shelter Indices")
    print("=" * 60)

    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    # ── OHSI ───────────────────────────────────────────────────────────
    print("\n[1/2] OHSI = normalize(green_area / population) ...")
    # Per-capita green space (m² per person)
    gspc = blocks["green_area_m2"] / blocks["pop_sum"].clip(lower=1)
    blocks["ohsi"] = normalize_positive(gspc)
    print(f"  Green space per capita: [{gspc.min():.2f}, {gspc.max():.2f}] m²/person")
    print(f"  OHSI: [{blocks['ohsi'].min():.3f}, {blocks['ohsi'].max():.3f}]")

    # ── IHSI ───────────────────────────────────────────────────────────
    print("\n[2/2] IHSI = normalize((poi_density / pop_density) × mean_wt) ...")
    ihsi_raw = (
        blocks["poi_density"]
        / blocks["pop_density"].clip(lower=0.001)
        * blocks["mean_wt"]
    )
    blocks["ihsi"] = normalize_positive(ihsi_raw)
    print(f"  IHSI raw: [{ihsi_raw.min():.4f}, {ihsi_raw.max():.4f}]")
    print(f"  IHSI: [{blocks['ihsi'].min():.3f}, {blocks['ihsi'].max():.3f}]")

    # Save
    blocks.to_file(BLOCKS_FILE, driver="GPKG")
    print(f"\n  ✓ Saved with shelter indices → {BLOCKS_FILE}")

    print("\n" + "=" * 60)
    print("Shelter indices complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
