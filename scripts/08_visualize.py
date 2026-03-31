#!/usr/bin/env python3
"""
08_visualize.py -- Generate thematic maps for Shanghai heat-risk analysis.

Produces 5 maps:
  1. HRI Heat Risk Map (7-class quantile, YlOrRd)
  2. OHSPI Outdoor Priority Map (RdYlGn_r diverging)
  3. IHSPI Indoor Priority Map (RdYlGn_r diverging)
  4. Priority Composite -- dual-panel with Top-10 annotation
  5. Supply-Demand Dashboard -- 5-subplot overview

Classification uses quantile breaks for even color distribution.
Zero-population blocks are rendered as a neutral gray underlay.
"""

import sys
import warnings
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BLOCKS_FILE, MAPS_DIR, JENKS_CLASSES

warnings.filterwarnings("ignore")

try:
    from matplotlib_scalebar.scalebar import ScaleBar
    HAS_SCALEBAR = True
except ImportError:
    HAS_SCALEBAR = False

TILE_SOURCES = [
    ctx.providers.CartoDB.Positron,
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    ctx.providers.Stadia.StamenTonerLite,
]


def add_basemap(ax, crs):
    for src in TILE_SOURCES:
        try:
            ctx.add_basemap(ax, crs=crs, source=src, zoom=11, alpha=0.4)
            return
        except Exception:
            continue
    ax.set_facecolor("#f5f5f5")


def add_north_arrow(ax, x=0.95, y=0.95):
    ax.annotate("N", xy=(x, y), xycoords="axes fraction",
                fontsize=14, fontweight="bold", ha="center", va="center")
    ax.annotate("", xy=(x, y - 0.01), xytext=(x, y - 0.06),
                xycoords="axes fraction",
                arrowprops=dict(arrowstyle="->", lw=2, color="black"))


def add_scale_bar(ax):
    if HAS_SCALEBAR:
        sb = ScaleBar(1, "m", location="lower left", length_fraction=0.2)
        ax.add_artist(sb)


def plot_classified_map(
    gdf_all: gpd.GeoDataFrame,
    gdf_active: gpd.GeoDataFrame,
    column: str,
    cmap: str,
    title: str,
    filename: str,
    legend_title: str = "",
    k: int = JENKS_CLASSES,
):
    """Plot a thematic map. Gray underlay for inactive blocks, quantile-classified
    colored overlay for active blocks."""
    print(f"\n  Generating {filename} ...")

    fig, ax = plt.subplots(1, 1, figsize=(12, 14))

    # Gray underlay for all blocks (including zero-pop)
    gdf_all.plot(ax=ax, color="#E8E8E8", edgecolor="#D0D0D0", linewidth=0.15)

    # Quantile-classified active blocks
    n_unique = len(gdf_active[column].dropna().unique())
    actual_k = min(k, n_unique) if n_unique >= 2 else 2

    gdf_active.plot(
        column=column,
        cmap=cmap,
        scheme="quantiles",
        k=actual_k,
        ax=ax,
        edgecolor="gray",
        linewidth=0.15,
        alpha=0.9,
        legend=True,
        legend_kwds={
            "title": legend_title or column,
            "loc": "lower right",
            "fontsize": 8,
            "title_fontsize": 10,
        },
    )

    add_basemap(ax, gdf_all.crs)
    add_north_arrow(ax)
    add_scale_bar(ax)

    ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
    ax.set_axis_off()
    plt.tight_layout()

    png_path = MAPS_DIR / f"{filename}.png"
    svg_path = MAPS_DIR / f"{filename}.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"    ? {png_path.name} ({png_path.stat().st_size / 1e6:.1f} MB)")


def plot_priority_composite(gdf_all, gdf_active):
    """Dual-panel OHSPI + IHSPI with Top-10 annotations."""
    print("\n  Generating priority composite map ...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 14))

    for ax, col, title_suffix in [
        (ax1, "ohspi", "Outdoor (OHSPI)"),
        (ax2, "ihspi", "Indoor (IHSPI)"),
    ]:
        gdf_all.plot(ax=ax, color="#E8E8E8", edgecolor="#D0D0D0", linewidth=0.1)
        gdf_active.plot(
            column=col, cmap="RdYlGn_r", scheme="quantiles",
            k=JENKS_CLASSES, ax=ax, edgecolor="gray", linewidth=0.1,
            alpha=0.9, legend=True,
            legend_kwds={"title": col.upper(), "loc": "lower right", "fontsize": 7},
        )
        add_basemap(ax, gdf_all.crs)
        ax.set_title(f"Heat Shelter Priority -- {title_suffix}",
                      fontsize=14, fontweight="bold")
        ax.set_axis_off()

        top10 = gdf_active.nlargest(10, col)
        for _, row in top10.iterrows():
            c = row.geometry.centroid
            ax.annotate(
                f"#{row['block_id']}", xy=(c.x, c.y),
                fontsize=7, fontweight="bold", color="darkred", ha="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="red"),
            )

    plt.suptitle("Intervention Priority -- Shanghai 2022",
                  fontsize=18, fontweight="bold", y=1.02)
    plt.tight_layout()

    for ext in ("png", "svg"):
        p = MAPS_DIR / f"map_priority_composite.{ext}"
        fig.savefig(p, dpi=300 if ext == "png" else None,
                    format=ext, bbox_inches="tight")
    plt.close(fig)
    print("    ? map_priority_composite.png")


def plot_dashboard(gdf_all, gdf_active):
    """5-subplot supply-demand dashboard."""
    print("\n  Generating dashboard ...")

    fig, axes = plt.subplots(2, 3, figsize=(30, 20))

    panels = [
        ("hri_norm", "YlOrRd", "Heat Risk Index (HRI)"),
        ("ohsi", "Greens", "Outdoor Heat Shelter (OHSI)"),
        ("ihsi", "Blues", "Indoor Heat Shelter (IHSI)"),
        ("ohspi", "RdYlGn_r", "Outdoor Priority (OHSPI)"),
        ("ihspi", "RdYlGn_r", "Indoor Priority (IHSPI)"),
    ]

    for ax, (col, cmap, title) in zip(axes.flat, panels):
        gdf_all.plot(ax=ax, color="#E8E8E8", edgecolor="none", linewidth=0)
        gdf_active.plot(
            column=col, cmap=cmap, scheme="quantiles",
            k=JENKS_CLASSES, ax=ax, edgecolor="none", linewidth=0,
            alpha=0.9, legend=True,
            legend_kwds={"fontsize": 6, "loc": "lower right"},
        )
        add_basemap(ax, gdf_all.crs)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_axis_off()

    axes[1, 2].set_visible(False)

    plt.suptitle("Shanghai Heat Risk Supply-Demand Dashboard -- 2022",
                  fontsize=20, fontweight="bold", y=1.01)
    plt.tight_layout()

    for ext in ("png", "svg"):
        p = MAPS_DIR / f"map_dashboard.{ext}"
        fig.savefig(p, dpi=300 if ext == "png" else None,
                    format=ext, bbox_inches="tight")
    plt.close(fig)
    print("    ? map_dashboard.png")


def main():
    print("=" * 60)
    print("STEP 8: Visualization")
    print("=" * 60)

    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    # Split into active (has population) and inactive (no population)
    active = blocks[blocks["pop_sum"] > 0].copy()
    print(f"  Active blocks (pop > 0): {len(active)}")
    print(f"  Inactive blocks (pop = 0): {len(blocks) - len(active)}  ? rendered gray")

    # Map 1: HRI
    plot_classified_map(
        blocks, active, "hri_norm", "YlOrRd",
        "Heat Risk Index (HRI) -- Shanghai 2022",
        "map_hri", legend_title="HRI (7-class quantile)",
    )

    # Map 2: OHSPI
    plot_classified_map(
        blocks, active, "ohspi", "RdYlGn_r",
        "Outdoor Heat Shelter Priority Index (OHSPI)",
        "map_ohspi", legend_title="OHSPI",
    )

    # Map 3: IHSPI
    plot_classified_map(
        blocks, active, "ihspi", "RdYlGn_r",
        "Indoor Heat Shelter Priority Index (IHSPI)",
        "map_ihspi", legend_title="IHSPI",
    )

    # Map 4: Priority composite
    plot_priority_composite(blocks, active)

    # Map 5: Dashboard
    plot_dashboard(blocks, active)

    print("\n" + "=" * 60)
    print(f"Visualization complete -- {len(list(MAPS_DIR.glob('*.png')))} PNG files")
    print("=" * 60)


if __name__ == "__main__":
    main()
