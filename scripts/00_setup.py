#!/usr/bin/env python3
"""
00_setup.py — Environment setup and dependency installation.

Installs Python packages from requirements.txt and verifies that all
critical imports succeed. Works on Windows (py launcher) and Linux.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and print output."""
    print(f"  -> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines()[-20:]:
            print(f"    {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().splitlines()[-10:]:
            print(f"    {line}")
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed (rc={result.returncode})")
    return result


def main():
    print("=" * 60)
    print("STEP 0: Environment Setup")
    print("=" * 60)

    # 1. Install Python dependencies
    print("\n[1/3] Installing Python packages ...")
    req_file = ROOT / "requirements.txt"
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)])

    # 2. Verify critical imports
    print("\n[2/3] Verifying imports ...")
    imports = [
        "geopandas", "rasterio", "rasterstats", "numpy", "pandas",
        "matplotlib", "contextily", "mapclassify", "shapely", "pyproj",
        "fiona", "requests", "scipy",
    ]
    ok = 0
    for mod in imports:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "?")
            print(f"  [OK] {mod:20s} {ver}")
            ok += 1
        except ImportError as e:
            print(f"  [FAIL] {mod:20s} {e}")

    if ok < len(imports):
        print(f"\n  WARNING: {len(imports) - ok} package(s) failed to import")
    else:
        print(f"\n  All {ok} packages OK")

    # 3. Ensure output directories exist
    print("\n[3/3] Creating output directories ...")
    from config import (
        UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR, PROCESSED_DIR,
        BLOCKS_DIR, MAPS_DIR, FIGURES_DIR,
    )
    for d in [UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR, PROCESSED_DIR,
              BLOCKS_DIR, MAPS_DIR, FIGURES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {d}")

    print("\n" + "=" * 60)
    print("Setup complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
