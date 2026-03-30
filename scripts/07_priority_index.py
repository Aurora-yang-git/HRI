#!/usr/bin/env python3
"""
07_priority_index.py — Calculate intervention priority indices and Jenks classes.

OHSPI = HRI_norm − OHSI   (outdoor heat shelter priority)
IHSPI = HRI_norm − IHSI   (indoor heat shelter priority)

Positive values → high risk + low shelter → needs intervention.
Negative values → risk adequately covered by existing shelters.

Also applies 7-class Natural Breaks (Jenks) to HRI, OHSPI, and IHSPI.
"""

import sys
from pathlib import Path

import geopandas as gpd
import mapclassify
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BLOCKS_FILE, JENKS_CLASSES


def classify_jenks(series, k: int = JENKS_CLASSES) -> np.ndarray:
    """Apply Natural Breaks classification, return class labels 1..k."""
    values = series.dropna().values
    if len(np.unique(values)) < k:
        # Not enough unique values for requested classes
        k = max(2, len(np.unique(values)))
    classifier = mapclassify.NaturalBreaks(values, k=k)
    # Map back to full series (including NaN positions)
    labels = np.full(len(series), np.nan)
    mask = series.notna()
    labels[mask] = classifier.yb + 1  # 1-based
    return labels.astype(int)


def main():
    print("=" * 60)
    print("STEP 7: Priority Indices")
    print("=" * 60)

    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    # ── Priority indices ───────────────────────────────────────────────
    print("\n[1/2] Computing OHSPI and IHSPI ...")
    blocks["ohspi"] = blocks["hri_norm"] - blocks["ohsi"]
    blocks["ihspi"] = blocks["hri_norm"] - blocks["ihsi"]

    print(f"  OHSPI: [{blocks['ohspi'].min():.3f}, {blocks['ohspi'].max():.3f}]")
    print(f"  IHSPI: [{blocks['ihspi'].min():.3f}, {blocks['ihspi'].max():.3f}]")

    # ── Jenks classification ──────────────────────────────────────────
    print(f"\n[2/2] Jenks {JENKS_CLASSES}-class classification ...")
    blocks["hri_class"] = classify_jenks(blocks["hri_norm"])
    blocks["ohspi_class"] = classify_jenks(blocks["ohspi"])
    blocks["ihspi_class"] = classify_jenks(blocks["ihspi"])

    for col in ["hri_class", "ohspi_class", "ihspi_class"]:
        print(f"  {col}: {dict(blocks[col].value_counts().sort_index())}")

    # Save
    blocks.to_file(BLOCKS_FILE, driver="GPKG")
    print(f"\n  ✓ Saved with priority indices → {BLOCKS_FILE}")
    print(f"    Final columns: {list(blocks.columns)}")

    print("\n" + "=" * 60)
    print("Priority index calculation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
