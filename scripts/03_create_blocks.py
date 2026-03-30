#!/usr/bin/env python3
"""
03_create_blocks.py — Generate road-enclosed urban blocks.

Workflow:
  1. Load OSM roads and filter by major road classes.
  2. Reproject to UTM 51N.
  3. Merge all linestrings (unary_union) + Shanghai boundary ring.
  4. Polygonize to create enclosed blocks.
  5. Filter by area thresholds and assign block IDs.
  6. Save to GeoPackage.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    BLOCK_MAX_AREA_M2,
    BLOCK_MIN_AREA_M2,
    BLOCKS_FILE,
    BOUNDARY_FILE,
    CRS_UTM51N,
    OSM_ROADS,
    ROAD_CLASSES,
)


def main():
    print("=" * 60)
    print("STEP 3: Create Road-Enclosed Blocks")
    print("=" * 60)

    if BLOCKS_FILE.exists():
        gdf = gpd.read_file(BLOCKS_FILE)
        print(f"  [skip] Blocks file already exists with {len(gdf)} blocks")
        print(f"  → {BLOCKS_FILE}")
        return

    # 1. Load and filter roads
    print("\n[1/5] Loading OSM roads ...")
    roads = gpd.read_file(OSM_ROADS)
    print(f"  Total roads: {len(roads)}")

    roads = roads[roads["fclass"].isin(ROAD_CLASSES)].copy()
    print(f"  Filtered to {len(roads)} major roads ({', '.join(ROAD_CLASSES)})")

    # 2. Reproject
    print("\n[2/5] Reprojecting to UTM 51N ...")
    roads = roads.to_crs(CRS_UTM51N)

    # 3. Load boundary and convert to UTM
    print("\n[3/5] Loading Shanghai boundary ...")
    boundary = gpd.read_file(BOUNDARY_FILE).to_crs(CRS_UTM51N)
    boundary_geom = boundary.geometry.unary_union
    boundary_ring = boundary_geom.boundary

    # 4. Merge lines and polygonize
    print("\n[4/5] Merging roads and polygonizing ...")
    all_lines = list(roads.geometry)
    # Add boundary ring so blocks at city edge are properly enclosed
    if boundary_ring.geom_type == "MultiLineString":
        all_lines.extend(boundary_ring.geoms)
    else:
        all_lines.append(boundary_ring)

    merged = unary_union(all_lines)
    print(f"  Merged geometry type: {merged.geom_type}")

    polygons = list(polygonize(merged))
    print(f"  Raw polygons from polygonize: {len(polygons)}")

    # 5. Filter: inside boundary, area thresholds
    print("\n[5/5] Filtering blocks ...")
    valid_polys = []
    areas = []
    for poly in polygons:
        # Check if polygon centroid is within boundary
        if not boundary_geom.contains(poly.centroid):
            continue
        area = poly.area
        if area < BLOCK_MIN_AREA_M2:
            continue
        if area > BLOCK_MAX_AREA_M2:
            continue
        valid_polys.append(poly)
        areas.append(area)

    print(f"  Blocks after filtering: {len(valid_polys)}")
    print(f"  Area range: {min(areas):.0f} — {max(areas):.0f} m²")
    print(f"  Median area: {np.median(areas):.0f} m²")

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        {
            "block_id": range(1, len(valid_polys) + 1),
            "area_m2": areas,
            "area_km2": [a / 1e6 for a in areas],
        },
        geometry=valid_polys,
        crs=CRS_UTM51N,
    )

    # Save
    BLOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(BLOCKS_FILE, driver="GPKG")
    print(f"\n  ✓ Saved {len(gdf)} blocks → {BLOCKS_FILE}")
    print(f"    File size: {BLOCKS_FILE.stat().st_size / 1e6:.1f} MB")

    print("\n" + "=" * 60)
    print(f"Block generation complete: {len(gdf)} blocks")
    print("=" * 60)


if __name__ == "__main__":
    main()
