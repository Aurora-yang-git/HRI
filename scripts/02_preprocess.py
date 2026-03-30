#!/usr/bin/env python3
"""
02_preprocess.py — Preprocess downloaded raster datasets.

Steps:
  1. Generate a Shanghai boundary polygon from OSM road extents.
  2. Clip each raster to Shanghai extent using gdal_translate (window-based).
  3. Reproject all rasters to EPSG:32651 (UTM Zone 51N) via gdalwarp.
  4. For UTCI: convert Int16 values to °C (divide by 100).
  5. For GDP: extract the most recent band (2022).
"""

import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    CRS_UTM51N,
    CRS_WGS84,
    SHANGHAI_BBOX,
    BOUNDARY_FILE,
    GDP_DIR,
    NL_DIR,
    POP_DIR,
    UTCI_DIR,
    PROCESSED_DIR,
    UTCI_PROCESSED,
    POP_PROCESSED,
    NL_PROCESSED,
    GDP_PROCESSED,
    OSM_ROADS,
)


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def make_boundary() -> gpd.GeoDataFrame:
    """Create a Shanghai boundary polygon from the OSM roads bounding box."""
    print("\n[1/5] Generating Shanghai boundary ...")

    if BOUNDARY_FILE.exists():
        print(f"  [skip] Boundary already exists: {BOUNDARY_FILE}")
        return gpd.read_file(BOUNDARY_FILE)

    roads = gpd.read_file(OSM_ROADS, columns=[])
    total_bounds = roads.total_bounds
    print(f"  OSM roads extent: {total_bounds}")

    xmin = max(total_bounds[0], SHANGHAI_BBOX[0])
    ymin = max(total_bounds[1], SHANGHAI_BBOX[1])
    xmax = min(total_bounds[2], SHANGHAI_BBOX[2])
    ymax = min(total_bounds[3], SHANGHAI_BBOX[3])

    boundary_geom = box(xmin, ymin, xmax, ymax)
    gdf = gpd.GeoDataFrame({"name": ["Shanghai"]}, geometry=[boundary_geom], crs=CRS_WGS84)

    ensure_dir(BOUNDARY_FILE.parent)
    gdf.to_file(BOUNDARY_FILE, driver="GPKG")
    print(f"  ✓ Boundary saved → {BOUNDARY_FILE}")
    return gdf


def clip_reproject_raster(
    src_path: Path,
    dst_path: Path,
    band_index: int | None = None,
    scale_factor: float | None = None,
    label: str = "",
):
    """
    Clip a raster to the Shanghai bounding box, reproject to UTM 51N,
    optionally extract a single band and apply a scale factor.
    Uses a two-step approach: window-based read → reproject.
    """
    print(f"\n  Processing {label or src_path.name} ...")

    if dst_path.exists() and dst_path.stat().st_size > 500:
        print(f"  [skip] {dst_path.name} already exists")
        return

    ensure_dir(dst_path.parent)

    xmin, ymin, xmax, ymax = SHANGHAI_BBOX
    buf = 0.15  # degree buffer for edge effects
    clip_xmin, clip_ymin = xmin - buf, ymin - buf
    clip_xmax, clip_ymax = xmax + buf, ymax + buf

    with rasterio.open(src_path) as src:
        # Compute window from bounds
        window = rasterio.windows.from_bounds(
            clip_xmin, clip_ymin, clip_xmax, clip_ymax,
            transform=src.transform,
        )
        # Clamp window to valid range
        window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))

        src_nodata = src.nodata
        read_band = band_index if band_index is not None else 1
        data = src.read(read_band, window=window).astype(np.float32)
        win_transform = src.window_transform(window)
        src_crs = src.crs

    print(f"    Clipped shape: {data.shape}")
    print(f"    Src nodata: {src_nodata}")

    # Mask nodata
    if src_nodata is not None and not np.isnan(src_nodata):
        data[data == src_nodata] = np.nan
    # Also mask extremely large negative values (sentinel nodata)
    data[data < -1e30] = np.nan

    # Apply scale factor
    if scale_factor is not None:
        valid = np.isfinite(data)
        data[valid] = data[valid] * scale_factor

    valid_count = np.count_nonzero(np.isfinite(data))
    print(f"    Valid pixels: {valid_count}/{data.size}")
    if valid_count > 0:
        vdata = data[np.isfinite(data)]
        print(f"    Value range: [{vdata.min():.4f}, {vdata.max():.4f}]")

    # Reproject to UTM 51N
    dst_crs = CRS_UTM51N
    transform, width, height = calculate_default_transform(
        src_crs, dst_crs,
        data.shape[1], data.shape[0],
        *rasterio.transform.array_bounds(data.shape[0], data.shape[1], win_transform),
    )

    dst_data = np.full((height, width), np.nan, dtype=np.float32)
    reproject(
        source=data,
        destination=dst_data,
        src_transform=win_transform,
        src_crs=src_crs,
        dst_transform=transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": dst_crs,
        "transform": transform,
        "nodata": np.nan,
        "compress": "lzw",
    }

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(dst_data, 1)

    sz = dst_path.stat().st_size / 1e6
    vcount = np.count_nonzero(np.isfinite(dst_data))
    print(f"    ✓ {dst_path.name}  ({sz:.1f} MB, {vcount} valid pixels, CRS={dst_crs})")


def main():
    print("=" * 60)
    print("STEP 2: Preprocessing")
    print("=" * 60)

    boundary = make_boundary()

    # --- UTCI ---
    utci_src = list(UTCI_DIR.glob("*.tif"))
    if not utci_src:
        raise FileNotFoundError(f"No UTCI TIF found in {UTCI_DIR}")
    print("\n[2/5] UTCI ...")
    clip_reproject_raster(
        utci_src[0], UTCI_PROCESSED,
        band_index=1, scale_factor=0.01,
        label="UTCI (Int16 → °C)",
    )

    # --- Population ---
    pop_src = list(POP_DIR.glob("*.tif"))
    if not pop_src:
        raise FileNotFoundError(f"No population TIF found in {POP_DIR}")
    print("\n[3/5] Population ...")
    clip_reproject_raster(
        pop_src[0], POP_PROCESSED,
        label="Population",
    )

    # --- Nightlight ---
    nl_src = list(NL_DIR.glob("*.tif"))
    if not nl_src:
        raise FileNotFoundError(f"No nightlight TIF found in {NL_DIR}")
    print("\n[4/5] Nightlight ...")
    clip_reproject_raster(
        nl_src[0], NL_PROCESSED,
        label="Nightlight (PCNL 2021)",
    )

    # --- GDP ---
    gdp_src = list(GDP_DIR.glob("*.tif"))
    if not gdp_src:
        raise FileNotFoundError(f"No GDP TIF found in {GDP_DIR}")
    with rasterio.open(gdp_src[0]) as ds:
        n_bands = ds.count
    print(f"\n[5/5] GDP ({n_bands} bands, using band {n_bands}) ...")
    clip_reproject_raster(
        gdp_src[0], GDP_PROCESSED,
        band_index=n_bands,
        label="GDP (last band = most recent year)",
    )

    # Summary
    print("\n" + "=" * 60)
    print("Preprocessing summary:")
    for p in [UTCI_PROCESSED, POP_PROCESSED, NL_PROCESSED, GDP_PROCESSED]:
        sz = p.stat().st_size / 1e6 if p.exists() else 0
        print(f"  {p.name:35s} {sz:8.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
