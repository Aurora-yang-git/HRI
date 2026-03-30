#!/usr/bin/env python3
"""
04_zonal_stats.py — Compute zonal statistics for each road-enclosed block.

Adds the following columns to the blocks GeoPackage:
  - utci_mean     : Mean UTCI value (°C) within each block
  - pop_sum       : Total population within each block
  - pop_density   : Population per km²
  - nl_mean       : Mean nighttime light intensity
  - gdp_mean      : Mean GDP value
  - green_area_m2 : Total green space area (m²) within each block
  - weighted_poi_count : Weighted count of indoor-shelter POIs
  - poi_density   : Weighted POI count per km²
  - mean_wt       : Mean operational weight of POIs in block
"""

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterstats import zonal_stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    BLOCKS_FILE,
    CRS_UTM51N,
    GDP_PROCESSED,
    GREEN_CLASSES,
    INDOOR_SHELTER_POI,
    NL_PROCESSED,
    OSM_LANDUSE,
    OSM_POIS,
    OSM_TRANSPORT,
    POP_PROCESSED,
    TRANSPORT_SHELTER,
    UTCI_PROCESSED,
)

warnings.filterwarnings("ignore", category=RuntimeWarning)


def add_raster_stats(
    blocks: gpd.GeoDataFrame,
    raster_path: Path,
    stat: str,
    col_name: str,
    label: str = "",
) -> gpd.GeoDataFrame:
    """Run zonal_stats and add result as a column."""
    print(f"\n  Computing {label or col_name} ...")
    stats = zonal_stats(
        blocks, str(raster_path),
        stats=[stat],
        nodata=np.nan,
        all_touched=True,
    )
    blocks[col_name] = [s[stat] for s in stats]

    # Fill NaN with 0 for sum stats, or column median for mean stats
    null_count = blocks[col_name].isna().sum()
    if null_count > 0:
        if stat == "sum":
            blocks[col_name] = blocks[col_name].fillna(0)
        else:
            median_val = blocks[col_name].median()
            blocks[col_name] = blocks[col_name].fillna(median_val)
        print(f"    Filled {null_count} NaN values")

    print(f"    {col_name}: min={blocks[col_name].min():.4f}, "
          f"max={blocks[col_name].max():.4f}, "
          f"mean={blocks[col_name].mean():.4f}")
    return blocks


def compute_green_space(blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute green space area within each block from OSM landuse."""
    print("\n  Computing green space area per block ...")
    landuse = gpd.read_file(OSM_LANDUSE)
    greens = landuse[landuse["fclass"].isin(GREEN_CLASSES)].copy()
    print(f"    Green space polygons: {len(greens)}")

    greens = greens.to_crs(CRS_UTM51N)

    # Spatial overlay: intersection of greens with blocks
    try:
        overlay = gpd.overlay(
            blocks[["block_id", "geometry"]],
            greens[["geometry"]],
            how="intersection",
        )
    except Exception:
        # Fallback: use sjoin + manual area calc
        overlay = gpd.sjoin(
            greens[["geometry"]],
            blocks[["block_id", "geometry"]],
            how="inner",
            predicate="intersects",
        )

    if len(overlay) > 0:
        overlay["_green_area"] = overlay.geometry.area
        green_by_block = overlay.groupby("block_id")["_green_area"].sum()
        blocks["green_area_m2"] = blocks["block_id"].map(green_by_block).fillna(0)
    else:
        blocks["green_area_m2"] = 0.0

    print(f"    Green area: min={blocks['green_area_m2'].min():.0f}, "
          f"max={blocks['green_area_m2'].max():.0f}, "
          f"mean={blocks['green_area_m2'].mean():.0f} m²")
    return blocks


def compute_poi_density(blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute weighted indoor-shelter POI density per block."""
    print("\n  Computing indoor shelter POI density ...")

    # Load POI point data
    pois = gpd.read_file(OSM_POIS)
    transport = gpd.read_file(OSM_TRANSPORT)

    # Filter to shelter categories
    poi_shelter = pois[pois["fclass"].isin(INDOOR_SHELTER_POI.keys())].copy()
    transport_shelter = transport[transport["fclass"].isin(TRANSPORT_SHELTER.keys())].copy()

    print(f"    Shelter POIs: {len(poi_shelter)}")
    print(f"    Transport shelter: {len(transport_shelter)}")

    # Assign weights
    poi_shelter["weight"] = poi_shelter["fclass"].map(INDOOR_SHELTER_POI)
    transport_shelter["weight"] = transport_shelter["fclass"].map(TRANSPORT_SHELTER)

    # Combine
    all_shelter = pd.concat([
        poi_shelter[["geometry", "fclass", "weight"]],
        transport_shelter[["geometry", "fclass", "weight"]],
    ], ignore_index=True)
    all_shelter = gpd.GeoDataFrame(all_shelter, crs=pois.crs)
    all_shelter = all_shelter.to_crs(CRS_UTM51N)
    print(f"    Total shelter features: {len(all_shelter)}")

    # Spatial join with blocks
    joined = gpd.sjoin(all_shelter, blocks[["block_id", "geometry"]], how="inner", predicate="within")

    if len(joined) > 0:
        # Weighted count per block
        wt_count = joined.groupby("block_id")["weight"].sum()
        mean_wt = joined.groupby("block_id")["weight"].mean()

        blocks["weighted_poi_count"] = blocks["block_id"].map(wt_count).fillna(0)
        blocks["mean_wt"] = blocks["block_id"].map(mean_wt).fillna(0.5)  # default weight
    else:
        blocks["weighted_poi_count"] = 0.0
        blocks["mean_wt"] = 0.5

    blocks["poi_density"] = blocks["weighted_poi_count"] / blocks["area_km2"]

    print(f"    POI density: min={blocks['poi_density'].min():.2f}, "
          f"max={blocks['poi_density'].max():.2f}, "
          f"mean={blocks['poi_density'].mean():.2f}")
    return blocks


def main():
    print("=" * 60)
    print("STEP 4: Zonal Statistics")
    print("=" * 60)

    # Load blocks
    print("\nLoading blocks ...")
    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"  {len(blocks)} blocks loaded")

    # Raster zonal stats
    blocks = add_raster_stats(blocks, UTCI_PROCESSED, "mean", "utci_mean", "UTCI mean")
    blocks = add_raster_stats(blocks, POP_PROCESSED, "sum", "pop_sum", "Population sum")
    blocks["pop_density"] = blocks["pop_sum"] / blocks["area_km2"].clip(lower=0.001)

    blocks = add_raster_stats(blocks, NL_PROCESSED, "mean", "nl_mean", "Nightlight mean")
    blocks = add_raster_stats(blocks, GDP_PROCESSED, "mean", "gdp_mean", "GDP mean")

    # Vector-based stats
    blocks = compute_green_space(blocks)
    blocks = compute_poi_density(blocks)

    # Save
    blocks.to_file(BLOCKS_FILE, driver="GPKG")
    print(f"\n  ✓ Saved enriched blocks → {BLOCKS_FILE}")
    print(f"    Columns: {list(blocks.columns)}")

    print("\n" + "=" * 60)
    print(f"Zonal statistics complete for {len(blocks)} blocks")
    print("=" * 60)


if __name__ == "__main__":
    main()
