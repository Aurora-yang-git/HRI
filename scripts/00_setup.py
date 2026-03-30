#!/usr/bin/env python3
"""
00_setup.py — Environment setup and dependency installation.

Installs system-level GDAL libraries, Python packages from requirements.txt,
and verifies that all critical imports succeed.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(cmd: str, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a shell command and print output."""
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed (rc={result.returncode}): {cmd}")
    return result


def main():
    print("=" * 60)
    print("STEP 0: Environment Setup")
    print("=" * 60)

    # 1. Install system GDAL (needed by rasterio / fiona)
    print("\n[1/4] Installing system GDAL libraries...")
    run("sudo apt-get update -qq", check=False)
    run("sudo apt-get install -y -qq gdal-bin libgdal-dev", check=False)

    # 2. Install Python dependencies
    print("\n[2/4] Installing Python packages...")
    req_file = ROOT / "requirements.txt"
    run(f"{sys.executable} -m pip install -q -r {req_file}")

    # 3. Verify critical imports
    print("\n[3/4] Verifying imports...")
    imports = [
        "geopandas", "rasterio", "rasterstats", "numpy", "pandas",
        "matplotlib", "contextily", "mapclassify", "shapely", "pyproj",
        "fiona", "requests",
    ]
    for mod in imports:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", getattr(m, "gdal_version", "?"))
            print(f"  ✓ {mod:20s} {ver}")
        except ImportError as e:
            print(f"  ✗ {mod:20s} FAILED: {e}")
            sys.exit(1)

    # 4. Print GDAL version
    print("\n[4/4] GDAL CLI version:")
    run("gdalinfo --version", check=False)

    # 5. Ensure output directories exist
    from config import (
        UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR, PROCESSED_DIR,
        BLOCKS_DIR, MAPS_DIR, FIGURES_DIR,
    )
    for d in [UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR, PROCESSED_DIR,
              BLOCKS_DIR, MAPS_DIR, FIGURES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("Setup complete ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
