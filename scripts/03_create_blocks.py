#!/usr/bin/env python3
"""
03_create_blocks.py — Generate road-enclosed urban blocks + fishnet infill.

Workflow:
  1. Load OSM roads and filter by major road classes.
  2. Reproject to UTM 51N.
  3. Merge all linestrings (unary_union) + Shanghai boundary ring.
  4. Polygonize to create enclosed blocks.
  5. Filter by area thresholds.
  6. For uncovered areas inside Shanghai boundary, generate a 500 m fishnet
     grid so that every part of the city has spatial coverage.
  7. Save combined blocks to GeoPackage.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

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

# Only use major roads for polygonize (fast), not service/unclassified
POLYGONIZE_ROAD_CLASSES = [
    "motorway", "trunk", "primary", "secondary", "tertiary", "residential",
]

FISHNET_CELL_M = 500


def fast_fishnet(boundary_geom, covered_geom, cell_size: float):
    """Generate fishnet cells for the uncovered area, vectorized."""
    uncovered = boundary_geom.difference(covered_geom)
    if uncovered.is_empty or uncovered.area < cell_size * cell_size:
        return []

    xmin, ymin, xmax, ymax = boundary_geom.bounds
    xs = np.arange(xmin, xmax, cell_size)
    ys = np.arange(ymin, ymax, cell_size)

    print(f"    Grid dimensions: {len(xs)} × {len(ys)} = {len(xs)*len(ys)} potential cells")

    # Build all cell boxes
    cells = []
    for x in xs:
        for y in ys:
            cell = box(x, y, x + cell_size, y + cell_size)
            intersection = uncovered.intersection(cell)
            if not intersection.is_empty and intersection.area >= BLOCK_MIN_AREA_M2:
                cells.append(intersection)

    return cells


def main():
    print("=" * 60)
    print("STEP 3: Create Road-Enclosed Blocks + Fishnet Infill")
    print("=" * 60)

    if BLOCKS_FILE.exists():
        gdf = gpd.read_file(BLOCKS_FILE)
        print(f"  [skip] Blocks file already exists with {len(gdf)} blocks")
        return

    # 1. Load and filter roads
    print("\n[1/7] Loading OSM roads ...")
    roads = gpd.read_file(OSM_ROADS)
    print(f"  Total roads: {len(roads)}")

    roads = roads[roads["fclass"].isin(POLYGONIZE_ROAD_CLASSES)].copy()
    print(f"  Filtered to {len(roads)} major roads")

    # 2. Reproject
    print("\n[2/7] Reprojecting to UTM 51N ...")
    roads = roads.to_crs(CRS_UTM51N)

    # 3. Load boundary
    print("\n[3/7] Loading Shanghai boundary ...")
    boundary = gpd.read_file(BOUNDARY_FILE).to_crs(CRS_UTM51N)
    boundary_geom = boundary.geometry.union_all()
    boundary_ring = boundary_geom.boundary

    # 4. Polygonize
    print("\n[4/7] Merging roads and polygonizing ...")
    all_lines = list(roads.geometry)
    if boundary_ring.geom_type == "MultiLineString":
        all_lines.extend(boundary_ring.geoms)
    else:
        all_lines.append(boundary_ring)

    merged = unary_union(all_lines)
    print(f"  Merged geometry type: {merged.geom_type}")

    polygons = list(polygonize(merged))
    print(f"  Raw polygons: {len(polygons)}")

    # 5. Filter road blocks
    print("\n[5/7] Filtering road-enclosed blocks ...")
    valid_polys = []
    for poly in polygons:
        if not boundary_geom.contains(poly.centroid):
            continue
        area = poly.area
        if area < BLOCK_MIN_AREA_M2 or area > BLOCK_MAX_AREA_M2:
            continue
        valid_polys.append(poly)

    areas_road = [p.area for p in valid_polys]
    print(f"  Road blocks: {len(valid_polys)}")
    if areas_road:
        print(f"  Area range: {min(areas_road):.0f} — {max(areas_road):.0f} m²")
        print(f"  Median: {np.median(areas_road):.0f} m²")

    # 6. Fishnet for uncovered areas
    print("\n[6/7] Generating 500 m fishnet for uncovered areas ...")
    road_blocks_union = unary_union(valid_polys)
    uncovered_area = boundary_geom.difference(road_blocks_union).area / 1e6
    print(f"  Uncovered area: {uncovered_area:.1f} km²")

    fishnet_polys = fast_fishnet(boundary_geom, road_blocks_union, FISHNET_CELL_M)
    print(f"  Fishnet cells: {len(fishnet_polys)}")

    # 7. Combine and save
    print("\n[7/7] Combining and saving ...")
    all_polys = valid_polys + fishnet_polys
    block_types = ["road"] * len(valid_polys) + ["grid"] * len(fishnet_polys)
    all_areas = [p.area for p in all_polys]

    gdf = gpd.GeoDataFrame(
        {
            "block_id": range(1, len(all_polys) + 1),
            "area_m2": all_areas,
            "area_km2": [a / 1e6 for a in all_areas],
            "block_type": block_types,
        },
        geometry=all_polys,
        crs=CRS_UTM51N,
    )

    BLOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(BLOCKS_FILE, driver="GPKG")

    n_road = len(valid_polys)
    n_grid = len(fishnet_polys)
    total_km2 = gdf["area_km2"].sum()
    boundary_km2 = boundary_geom.area / 1e6
    print(f"\n  ✓ Saved {len(gdf)} blocks → {BLOCKS_FILE}")
    print(f"    Road-enclosed: {n_road}")
    print(f"    Fishnet infill: {n_grid}")
    print(f"    Total area: {total_km2:.0f} km² / {boundary_km2:.0f} km² ({total_km2/boundary_km2*100:.0f}%)")
    print(f"    File size: {BLOCKS_FILE.stat().st_size / 1e6:.1f} MB")

    print("\n" + "=" * 60)
    print(f"Block generation complete: {len(gdf)} blocks")
    print("=" * 60)


if __name__ == "__main__":
    main()
