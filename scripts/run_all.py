#!/usr/bin/env python3
"""
run_all.py — Execute the full Shanghai heat-risk analysis pipeline.

Runs scripts 00 through 09 in sequence, with timing and error reporting.
"""

import importlib
import sys
import time
from pathlib import Path

# Ensure scripts directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

STEPS = [
    ("00_setup", "Environment Setup"),
    ("01_download_data", "Data Download"),
    ("02_preprocess", "Preprocessing"),
    ("03_create_blocks", "Road-Enclosed Blocks"),
    ("04_zonal_stats", "Zonal Statistics"),
    ("05_calculate_hri", "HRI Calculation"),
    ("06_calculate_shelters", "Shelter Indices"),
    ("07_priority_index", "Priority Indices"),
    ("08_visualize", "Visualization"),
    ("09_generate_qgis_project", "QGIS Project"),
]


def main():
    print("\n" + "#" * 60)
    print("  Shanghai Heat Risk Analysis — Full Pipeline")
    print("#" * 60 + "\n")

    results = []
    total_start = time.time()

    for module_name, description in STEPS:
        print(f"\n{'-' * 60}")
        print(f">> Running: {module_name} — {description}")
        print(f"{'-' * 60}")

        t0 = time.time()
        try:
            mod = importlib.import_module(module_name)
            mod.main()
            elapsed = time.time() - t0
            results.append((module_name, description, "[OK] OK", elapsed))
            print(f"\n  [time] {description}: {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results.append((module_name, description, f"[FAIL] FAILED: {e}", elapsed))
            print(f"\n  [FAIL] {description} FAILED after {elapsed:.1f}s: {e}")
            import traceback
            traceback.print_exc()
            # Continue to next step
            continue

    total_elapsed = time.time() - total_start

    # Summary
    print("\n\n" + "#" * 60)
    print("  Pipeline Summary")
    print("#" * 60)
    print(f"\n{'Module':<30s} {'Status':<20s} {'Time':>8s}")
    print("-" * 60)
    for module_name, description, status, elapsed in results:
        print(f"  {description:<28s} {status:<20s} {elapsed:7.1f}s")
    print("-" * 60)
    print(f"  {'TOTAL':<48s} {total_elapsed:7.1f}s")

    # Check outputs
    print("\n\nOutput files:")
    from config import BLOCKS_FILE, MAPS_DIR, QGIS_PROJECT
    for p in [BLOCKS_FILE, QGIS_PROJECT]:
        if p.exists():
            print(f"  [OK] {p} ({p.stat().st_size / 1e6:.1f} MB)")
        else:
            print(f"  [FAIL] {p} MISSING")

    if MAPS_DIR.exists():
        for f in sorted(MAPS_DIR.iterdir()):
            print(f"  [OK] {f} ({f.stat().st_size / 1e6:.1f} MB)")

    n_ok = sum(1 for _, _, s, _ in results if s.startswith("[OK]"))
    n_total = len(results)
    print(f"\n  {n_ok}/{n_total} steps completed successfully")

    if n_ok < n_total:
        sys.exit(1)


if __name__ == "__main__":
    main()
