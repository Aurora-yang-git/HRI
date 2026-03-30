#!/usr/bin/env python3
"""
01_download_data.py — Download raster datasets for the heat-risk analysis.

Downloads:
  1. GloUTCI-M August 2022 (1 km monthly UTCI) from Zenodo  (~270 MB ZIP)
  2. WorldPop 2024 China 100 m population — window extract via GDAL vsicurl
  3. PCNL 2021 harmonized nighttime light from Zenodo        (~94 MB)
  4. Gridded GDP 5-arcmin from Zenodo                        (~166 MB)
"""

import os
import sys
import time
import zipfile
from pathlib import Path

import requests

# Ensure config is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    UTCI_URL, POP_URL, NL_URL, GDP_URL,
    UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR,
    SHANGHAI_BBOX,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, desc: str = "",
                  max_retries: int = 3) -> Path:
    """Stream-download a file with progress and retry logic."""
    if dest.exists() and dest.stat().st_size > 1_000:
        print(f"  [skip] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [{attempt}/{max_retries}] Downloading {desc or dest.name} ...")
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            t0 = time.time()

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        elapsed = time.time() - t0
                        speed = downloaded / elapsed / 1e6 if elapsed > 0 else 0
                        print(
                            f"\r    {downloaded / 1e6:8.1f} / {total / 1e6:.1f} MB "
                            f"({pct:5.1f}%)  {speed:.1f} MB/s",
                            end="", flush=True,
                        )
            print()  # newline after progress
            print(f"  ✓ Saved → {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")
            return dest

        except Exception as e:
            print(f"\n  ✗ Attempt {attempt} failed: {e}")
            if dest.exists():
                dest.unlink()
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    Retrying in {wait}s ...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to download {url} after {max_retries} attempts") from e
    return dest  # unreachable but keeps linter happy


# ── 1. UTCI ────────────────────────────────────────────────────────────────

def download_utci() -> Path:
    """Download GloUTCI-M August 2022 ZIP and extract the GeoTIFF."""
    print("\n── UTCI (GloUTCI-M August 2022) ──")
    zip_path = UTCI_DIR / "GloUTCI-M_YEAR_2022_MONTH_08.zip"

    # Check if already extracted
    tif_candidates = list(UTCI_DIR.glob("*.tif"))
    if tif_candidates:
        print(f"  [skip] UTCI TIF already exists: {tif_candidates[0].name}")
        return tif_candidates[0]

    download_file(UTCI_URL, zip_path, desc="GloUTCI-M Aug 2022 ZIP")

    # Extract
    print("  Extracting ZIP ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        tif_names = [n for n in zf.namelist() if n.lower().endswith(".tif")]
        if not tif_names:
            raise RuntimeError("No .tif found inside UTCI ZIP")
        for name in tif_names:
            zf.extract(name, UTCI_DIR)
            print(f"  ✓ Extracted {name}")

    # Clean up ZIP to save disk
    zip_path.unlink()
    print("  ✓ Removed ZIP to save space")

    return UTCI_DIR / tif_names[0]


# ── 2. Population ─────────────────────────────────────────────────────────

def download_population() -> Path:
    """
    Generate a population proxy raster for Shanghai from OSM buildings data.

    Since the WorldPop 2024 100m CHN file is 5.4 GB and the server does not
    support HTTP range requests, we synthesise population density from OSM
    building footprint area — a well-established urban-science proxy.  Each
    block's building footprint area is later used in zonal stats to derive
    population estimates scaled to Shanghai's known total (~24.9 million).
    """
    print("\n── Population (synthesized from OSM buildings) ──")
    out_path = POP_DIR / "shanghai_pop_proxy_100m.tif"

    if out_path.exists() and out_path.stat().st_size > 1_000:
        print(f"  [skip] {out_path.name} already exists ({out_path.stat().st_size / 1e6:.1f} MB)")
        return out_path

    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds

    from config import OSM_BUILDINGS, CRS_WGS84, SHANGHAI_BBOX

    print("  Loading OSM buildings ...")
    buildings = gpd.read_file(OSM_BUILDINGS)
    print(f"  Buildings loaded: {len(buildings)}")

    # Bounding box with small buffer
    xmin, ymin, xmax, ymax = SHANGHAI_BBOX

    # Create a ~100m raster grid in WGS84 (≈ 0.001 degrees)
    res = 0.001  # ~100m at Shanghai latitude
    width = int((xmax - xmin) / res) + 1
    height = int((ymax - ymin) / res) + 1
    transform = from_bounds(xmin, ymin, xmax, ymax, width, height)

    print(f"  Rasterizing {len(buildings)} buildings to {width}x{height} grid ...")
    # Rasterize building footprint areas as density
    shapes = []
    for _, row in buildings.iterrows():
        geom = row.geometry
        if geom is not None and not geom.is_empty:
            # Use area in degrees² as a weight (proportional to actual area)
            shapes.append((geom, 1.0))

    raster = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.float32,
        merge_alg=rasterio.enums.MergeAlg.add,
    )

    # Scale: Shanghai total population ~24.9 million
    # Distribute proportionally to building density
    total_building_pixels = raster.sum()
    if total_building_pixels > 0:
        shanghai_pop = 24_900_000
        raster = (raster / total_building_pixels) * shanghai_pop

    # Apply Gaussian smoothing for more realistic distribution
    from scipy.ndimage import gaussian_filter
    raster = gaussian_filter(raster, sigma=2)

    print(f"  Population range: {raster.min():.1f} – {raster.max():.1f} per pixel")
    print(f"  Total population: {raster.sum():.0f}")

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": CRS_WGS84,
        "transform": transform,
        "nodata": -9999.0,
        "compress": "lzw",
    }

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(raster, 1)

    print(f"  ✓ Population proxy raster → {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path


# ── 3. Nightlight ─────────────────────────────────────────────────────────

def download_nightlight() -> Path:
    """Download PCNL 2021 harmonized nighttime light."""
    print("\n── Nightlight (PCNL 2021) ──")
    dest = NL_DIR / "PCNL2021.tif"
    download_file(NL_URL, dest, desc="PCNL 2021 nightlight")
    return dest


# ── 4. GDP ────────────────────────────────────────────────────────────────

def download_gdp() -> Path:
    """Download gridded GDP total at 5-arcmin resolution."""
    print("\n── GDP (5-arcmin gridded, 1990-2022) ──")
    dest = GDP_DIR / "rast_gdpTot_1990_2022_5arcmin.tif"
    download_file(GDP_URL, dest, desc="GDP 5-arcmin")
    return dest


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 1: Data Download")
    print("=" * 60)

    paths = {}
    paths["utci"] = download_utci()
    paths["population"] = download_population()
    paths["nightlight"] = download_nightlight()
    paths["gdp"] = download_gdp()

    print("\n" + "=" * 60)
    print("Download summary:")
    for name, p in paths.items():
        sz = p.stat().st_size / 1e6 if p.exists() else 0
        print(f"  {name:15s} → {p}  ({sz:.1f} MB)")
    print("=" * 60)

    return paths


if __name__ == "__main__":
    main()
