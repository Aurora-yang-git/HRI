#!/usr/bin/env python3
"""
02_preprocess.py — Preprocess downloaded raster datasets.

Steps:
  1. Generate a Shanghai boundary polygon from OSM road extents.
  2. Clip each raster to Shanghai extent.
  3. Reproject all rasters to EPSG:32651 (UTM Zone 51N).
  4. For UTCI: convert Int16 values to °C (divide by 100).
  5. For GDP: extract the most recent band (2020 or 2022).
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.warp import (
    Resampling,
    calculate_default_transform,
    reproject,
)
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


# ── Helpers ────────────────────────────────────────────────────────────────

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def make_boundary() -> gpd.GeoDataFrame:
    """Create a Shanghai boundary polygon from the OSM roads bounding box."""
    print("\n[1/5] Generating Shanghai boundary ...")

    if BOUNDARY_FILE.exists():
        print(f"  [skip] Boundary already exists: {BOUNDARY_FILE}")
        return gpd.read_file(BOUNDARY_FILE)

    # Use the bounding box of all OSM road features, with a small buffer
    roads = gpd.read_file(OSM_ROADS, columns=[])  # geometry only
    total_bounds = roads.total_bounds  # [xmin, ymin, xmax, ymax]
    print(f"  OSM roads extent: {total_bounds}")

    # Use the tighter of OSM extent and configured bbox
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


def clip_and_reproject(
    src_path: Path,
    dst_path: Path,
    boundary_gdf: gpd.GeoDataFrame,
    band_index: int | None = None,
    scale_factor: float | None = None,
    label: str = "",
):
    """Clip a raster to boundary extent, reproject to UTM 51N, optionally
    extract a single band and apply a scale factor."""
    print(f"\n  Processing {label or src_path.name} ...")

    if dst_path.exists() and dst_path.stat().st_size > 500:
        print(f"  [skip] {dst_path.name} already exists")
        return

    # Ensure boundary is in the raster's CRS for clipping
    with rasterio.open(src_path) as src:
        src_crs = src.crs
        if band_index is not None:
            read_bands = [band_index]
        else:
            read_bands = list(range(1, src.count + 1))

    boundary_reproj = boundary_gdf.to_crs(src_crs)
    shapes = boundary_reproj.geometry.values

    # Step 1: clip
    with rasterio.open(src_path) as src:
        out_image, out_transform = rio_mask(
            src, shapes, crop=True, indexes=read_bands,
            nodata=src.nodata, filled=True,
        )
        out_meta = src.meta.copy()

    # Handle single band extraction
    if band_index is not None:
        if out_image.ndim == 3 and out_image.shape[0] == 1:
            pass  # already (1, H, W)
        out_meta["count"] = 1

    out_meta.update({
        "transform": out_transform,
        "height": out_image.shape[-2],
        "width": out_image.shape[-1],
    })

    # Apply scale factor (e.g. UTCI Int16 → °C)
    if scale_factor is not None:
        out_image = out_image.astype(np.float32)
        nodata_val = out_meta.get("nodata")
        if nodata_val is not None:
            valid = out_image != nodata_val
            out_image[valid] = out_image[valid] * scale_factor
        else:
            out_image = out_image * scale_factor
        out_meta["dtype"] = "float32"
        out_meta["nodata"] = -9999.0

    # Step 2: reproject to UTM 51N
    dst_crs = CRS_UTM51N
    transform, width, height = calculate_default_transform(
        out_meta["crs"] if "crs" in out_meta else src_crs,
        dst_crs,
        out_meta["width"],
        out_meta["height"],
        *rasterio.transform.array_bounds(
            out_meta["height"], out_meta["width"], out_transform
        ),
    )

    dst_meta = out_meta.copy()
    dst_meta.update({
        "crs": dst_crs,
        "transform": transform,
        "width": width,
        "height": height,
        "compress": "lzw",
        "driver": "GTiff",
    })

    # Remove tiling params if present to avoid issues
    for key in ["blockxsize", "blockysize", "tiled"]:
        dst_meta.pop(key, None)

    ensure_dir(dst_path.parent)

    with rasterio.open(dst_path, "w", **dst_meta) as dst:
        for i in range(1, dst_meta["count"] + 1):
            band_data = out_image[i - 1] if out_image.ndim == 3 else out_image
            dest_band = np.empty((height, width), dtype=dst_meta["dtype"])
            reproject(
                source=band_data,
                destination=dest_band,
                src_transform=out_transform,
                src_crs=out_meta.get("crs", src_crs),
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
            dst.write(dest_band, i)

    sz = dst_path.stat().st_size / 1e6
    print(f"  ✓ {dst_path.name}  ({sz:.1f} MB, CRS={dst_crs})")


# ── Main ──────────────────────────────────────────────────────────────────

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
    clip_and_reproject(
        utci_src[0], UTCI_PROCESSED, boundary,
        band_index=1, scale_factor=0.01,  # Int16 / 100 → °C
        label="UTCI",
    )

    # --- Population ---
    pop_src = list(POP_DIR.glob("*.tif"))
    if not pop_src:
        raise FileNotFoundError(f"No population TIF found in {POP_DIR}")
    print("\n[3/5] Population ...")
    clip_and_reproject(
        pop_src[0], POP_PROCESSED, boundary,
        label="Population",
    )

    # --- Nightlight ---
    nl_src = list(NL_DIR.glob("*.tif"))
    if not nl_src:
        raise FileNotFoundError(f"No nightlight TIF found in {NL_DIR}")
    print("\n[4/5] Nightlight ...")
    clip_and_reproject(
        nl_src[0], NL_PROCESSED, boundary,
        label="Nightlight",
    )

    # --- GDP ---
    gdp_src = list(GDP_DIR.glob("*.tif"))
    if not gdp_src:
        raise FileNotFoundError(f"No GDP TIF found in {GDP_DIR}")
    # Determine band count → pick last band (most recent year)
    with rasterio.open(gdp_src[0]) as ds:
        n_bands = ds.count
        print(f"\n[5/5] GDP ({n_bands} bands, using band {n_bands} = most recent year) ...")
    clip_and_reproject(
        gdp_src[0], GDP_PROCESSED, boundary,
        band_index=n_bands,
        label="GDP",
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
