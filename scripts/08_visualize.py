#!/usr/bin/env python3
"""
08_visualize.py — Generate thematic maps for Shanghai heat-risk analysis.

Produces 5 maps:
  1. HRI Heat Risk Map (7-class Jenks, YlOrRd)
  2. OHSPI Outdoor Priority Map (RdYlGn_r diverging)
  3. IHSPI Indoor Priority Map (RdYlGn_r diverging)
  4. Priority Composite — dual-panel with Top-10 annotation
  5. Supply-Demand Dashboard — 6-subplot overview
"""

import sys
import warnings
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import mapclassify
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.lines import Line2D
from matplotlib_scalebar.scalebar import ScaleBar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BLOCKS_FILE, MAPS_DIR, JENKS_CLASSES

warnings.filterwarnings("ignore")

# Try importing scalebar; if unavailable, we'll skip it
try:
    from matplotlib_scalebar.scalebar import ScaleBar
    HAS_SCALEBAR = True
except ImportError:
    HAS_SCALEBAR = False

# Basemap tile source — CartoDB Positron
TILE_SRC = ctx.providers.CartoDB.Positron


def add_basemap(ax, crs):
    """Add CartoDB Positron basemap tiles."""
    try:
        ctx.add_basemap(ax, crs=crs, source=TILE_SRC, zoom=11, alpha=0.5)
    except Exception as e:
        print(f"    [warn] Basemap failed: {e}")


def add_north_arrow(ax, x=0.95, y=0.95):
    """Add a simple north arrow."""
    ax.annotate(
        "N", xy=(x, y), xycoords="axes fraction",
        fontsize=14, fontweight="bold", ha="center", va="center",
    )
    ax.annotate(
        "", xy=(x, y - 0.01), xytext=(x, y - 0.06),
        xycoords="axes fraction",
        arrowprops=dict(arrowstyle="->", lw=2, color="black"),
    )


def add_scale_bar(ax):
    """Add a scale bar if matplotlib_scalebar is available."""
    if HAS_SCALEBAR:
        sb = ScaleBar(1, "m", location="lower left", length_fraction=0.2)
        ax.add_artist(sb)


def plot_classified_map(
    gdf: gpd.GeoDataFrame,
    column: str,
    cmap: str,
    title: str,
    filename: str,
    legend_title: str = "",
    k: int = JENKS_CLASSES,
):
    """Plot a single thematic map with Jenks classification."""
    print(f"\n  Generating {filename} ...")

    fig, ax = plt.subplots(1, 1, figsize=(12, 14))

    # Classification
    values = gdf[column].dropna()
    n_unique = len(np.unique(values))
    actual_k = min(k, n_unique) if n_unique >= 2 else 2

    gdf.plot(
        column=column,
        cmap=cmap,
        scheme="natural_breaks",
        k=actual_k,
        ax=ax,
        edgecolor="gray",
        linewidth=0.2,
        alpha=0.8,
        legend=True,
        legend_kwds={
            "title": legend_title or column,
            "loc": "lower right",
            "fontsize": 8,
            "title_fontsize": 10,
        },
    )

    add_basemap(ax, gdf.crs)
    add_north_arrow(ax)
    add_scale_bar(ax)

    ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
    ax.set_axis_off()

    plt.tight_layout()

    # Save PNG + SVG
    png_path = MAPS_DIR / f"{filename}.png"
    svg_path = MAPS_DIR / f"{filename}.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"    ✓ {png_path.name} ({png_path.stat().st_size / 1e6:.1f} MB)")
    print(f"    ✓ {svg_path.name}")


def plot_priority_composite(gdf: gpd.GeoDataFrame):
    """Dual-panel OHSPI + IHSPI with Top-10 annotations."""
    print("\n  Generating priority composite map ...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 14))

    for ax, col, title_suffix in [
        (ax1, "ohspi", "Outdoor (OHSPI)"),
        (ax2, "ihspi", "Indoor (IHSPI)"),
    ]:
        gdf.plot(
            column=col, cmap="RdYlGn_r", scheme="natural_breaks",
            k=JENKS_CLASSES, ax=ax, edgecolor="gray", linewidth=0.2,
            alpha=0.8, legend=True,
            legend_kwds={"title": col.upper(), "loc": "lower right", "fontsize": 7},
        )
        add_basemap(ax, gdf.crs)
        ax.set_title(f"Heat Shelter Priority — {title_suffix}", fontsize=14, fontweight="bold")
        ax.set_axis_off()

        # Annotate top 10
        top10 = gdf.nlargest(10, col)
        for idx, row in top10.iterrows():
            centroid = row.geometry.centroid
            ax.annotate(
                f"#{row['block_id']}",
                xy=(centroid.x, centroid.y),
                fontsize=7, fontweight="bold", color="darkred",
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7, edgecolor="red"),
            )

    plt.suptitle("Intervention Priority — Shanghai 2022", fontsize=18, fontweight="bold", y=1.02)
    plt.tight_layout()

    png_path = MAPS_DIR / "map_priority_composite.png"
    svg_path = MAPS_DIR / "map_priority_composite.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"    ✓ {png_path.name}")


def plot_dashboard(gdf: gpd.GeoDataFrame):
    """6-subplot supply-demand dashboard."""
    print("\n  Generating dashboard ...")

    fig, axes = plt.subplots(2, 3, figsize=(30, 20))

    panels = [
        ("hri_norm", "YlOrRd", "Heat Risk Index (HRI)"),
        ("ohsi", "Greens", "Outdoor Heat Shelter Index (OHSI)"),
        ("ihsi", "Blues", "Indoor Heat Shelter Index (IHSI)"),
        ("ohspi", "RdYlGn_r", "Outdoor Priority (OHSPI)"),
        ("ihspi", "RdYlGn_r", "Indoor Priority (IHSPI)"),
    ]

    for ax, (col, cmap, title) in zip(axes.flat, panels):
        gdf.plot(
            column=col, cmap=cmap, scheme="natural_breaks",
            k=JENKS_CLASSES, ax=ax, edgecolor="none", linewidth=0,
            alpha=0.85, legend=True,
            legend_kwds={"fontsize": 6, "loc": "lower right"},
        )
        add_basemap(ax, gdf.crs)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_axis_off()

    # Turn off the 6th subplot
    axes[1, 2].set_visible(False)

    plt.suptitle(
        "Shanghai Heat Risk Supply-Demand Dashboard — 2022",
        fontsize=20, fontweight="bold", y=1.01,
    )
    plt.tight_layout()

    png_path = MAPS_DIR / "map_dashboard.png"
    svg_path = MAPS_DIR / "map_dashboard.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"    ✓ {png_path.name}")


def main():
    print("=" * 60)
    print("STEP 8: Visualization")
    print("=" * 60)

    # Ensure output dir
    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    # Load blocks
    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    # Map 1: HRI
    plot_classified_map(
        blocks, "hri_norm", "YlOrRd",
        "Heat Risk Index (HRI) — Shanghai 2022",
        "map_hri",
        legend_title="HRI (7-class Jenks)",
    )

    # Map 2: OHSPI
    plot_classified_map(
        blocks, "ohspi", "RdYlGn_r",
        "Outdoor Heat Shelter Priority Index (OHSPI)",
        "map_ohspi",
        legend_title="OHSPI",
    )

    # Map 3: IHSPI
    plot_classified_map(
        blocks, "ihspi", "RdYlGn_r",
        "Indoor Heat Shelter Priority Index (IHSPI)",
        "map_ihspi",
        legend_title="IHSPI",
    )

    # Map 4: Priority composite
    plot_priority_composite(blocks)

    # Map 5: Dashboard
    plot_dashboard(blocks)

    print("\n" + "=" * 60)
    print(f"Visualization complete — {len(list(MAPS_DIR.glob('*')))} files in {MAPS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
