#!/usr/bin/env python3
"""
09_generate_qgis_project.py — Generate a QGIS 3.x project file (.qgz).

Creates a .qgs XML file and packages it into a .qgz archive.
The project includes:
  - Layer groups: Base Data / Heat Risk HRI / Shelter Resources / Intervention Priority
  - Graduated renderers with Jenks 7-class for HRI (YlOrRd), OHSPI/IHSPI (RdYlGn)
  - CartoDB Positron XYZ tile basemap
  - OSM vector layers as muted overlay (roads, water, green)
  - CRS: EPSG:32651
"""

import sys
import uuid
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    BLOCKS_FILE,
    CRS_UTM51N,
    MAPS_DIR,
    OSM_DIR,
    OSM_ROADS,
    OSM_WATER,
    OUTPUT_DIR,
    QGIS_PROJECT,
)


# ── Color ramps ───────────────────────────────────────────────────────────

YLOR_RD = [
    "#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026",
]

RDYLGN_R = [
    "#1a9850", "#91cf60", "#d9ef8b", "#ffffbf", "#fee08b", "#fc8d59", "#d73027",
]

GREENS = [
    "#edf8e9", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#005a32",
]

BLUES = [
    "#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#084594",
]


def uid():
    return str(uuid.uuid4()).replace("-", "")[:20]


def build_graduated_renderer(field: str, colors: list, breaks: list) -> Element:
    """Build a QgsGraduatedSymbolRenderer XML element."""
    renderer = Element("renderer-v2", type="graduatedSymbol", attr=field,
                       symbollevels="0", graduatedMethod="GraduatedColor")
    ranges_el = SubElement(renderer, "ranges")
    symbols_el = SubElement(renderer, "symbols")

    for i in range(len(breaks) - 1):
        lower = f"{breaks[i]:.4f}"
        upper = f"{breaks[i + 1]:.4f}"
        label = f"{breaks[i]:.2f} – {breaks[i + 1]:.2f}"
        sym_name = str(i)

        SubElement(ranges_el, "range", lower=lower, upper=upper,
                   symbol=sym_name, label=label, render="true")

        sym = SubElement(symbols_el, "symbol", type="fill", name=sym_name,
                         alpha="0.85", force_rhr="0")
        layer = SubElement(sym, "layer", locked="0", enabled="1",
                           **{"class": "SimpleFill"})
        # Fill color
        r, g, b = int(colors[i][1:3], 16), int(colors[i][3:5], 16), int(colors[i][5:7], 16)
        SubElement(layer, "prop", k="color", v=f"{r},{g},{b},217")
        SubElement(layer, "prop", k="style", v="solid")
        SubElement(layer, "prop", k="outline_color", v="128,128,128,255")
        SubElement(layer, "prop", k="outline_width", v="0.1")
        SubElement(layer, "prop", k="outline_style", v="solid")

    return renderer


def gpkg_layer_element(
    layer_name: str,
    display_name: str,
    gpkg_path: str,
    field: str,
    colors: list,
    breaks: list,
    layer_id: str = "",
) -> Element:
    """Create a <maplayer> element for a GeoPackage vector layer."""
    lid = layer_id or uid()
    ml = Element("maplayer", type="vector", geometry="Polygon",
                 hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = lid
    SubElement(ml, "layername").text = display_name
    SubElement(ml, "datasource").text = f"{gpkg_path}|layername=road_blocks"
    SubElement(ml, "provider").text = "ogr"
    srs = SubElement(ml, "srs")
    SubElement(srs, "spatialrefsys")
    SubElement(SubElement(srs, "spatialrefsys"), "authid").text = CRS_UTM51N

    renderer = build_graduated_renderer(field, colors, breaks)
    ml.append(renderer)
    return ml


def xyz_basemap_element() -> Element:
    """Create a CartoDB Positron XYZ tile maplayer element."""
    ml = Element("maplayer", type="raster", hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = uid()
    SubElement(ml, "layername").text = "CartoDB Positron"
    SubElement(ml, "datasource").text = (
        "type=xyz&url=https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
        "&zmax=19&zmin=0"
    )
    SubElement(ml, "provider").text = "wms"
    return ml


def build_project(blocks_gdf: gpd.GeoDataFrame, gpkg_rel_path: str) -> str:
    """Build the full QGIS .qgs XML document."""
    import mapclassify
    import numpy as np

    # Compute breaks for each field
    def get_breaks(series, k=7):
        values = series.dropna().values
        n_unique = len(np.unique(values))
        actual_k = min(k, n_unique) if n_unique >= 2 else 2
        cls = mapclassify.NaturalBreaks(values, k=actual_k)
        return [float(series.min())] + [float(b) for b in cls.bins]

    hri_breaks = get_breaks(blocks_gdf["hri_norm"])
    ohspi_breaks = get_breaks(blocks_gdf["ohspi"])
    ihspi_breaks = get_breaks(blocks_gdf["ihspi"])
    ohsi_breaks = get_breaks(blocks_gdf["ohsi"])
    ihsi_breaks = get_breaks(blocks_gdf["ihsi"])

    # Root
    qgis = Element("qgis", version="3.34.0", projectname="Shanghai Heat Risk Analysis")
    SubElement(qgis, "title").text = "Shanghai Heat Risk Analysis 2022"

    # Project CRS
    proj_crs = SubElement(qgis, "projectCrs")
    SubElement(proj_crs, "spatialrefsys")

    # Map layers
    project_layers = SubElement(qgis, "projectlayers")

    # --- Basemap ---
    basemap = xyz_basemap_element()
    project_layers.append(basemap)

    # --- HRI layer ---
    hri_layer = gpkg_layer_element(
        "hri", "Heat Risk Index (HRI)", gpkg_rel_path,
        "hri_norm", YLOR_RD, hri_breaks,
    )
    project_layers.append(hri_layer)

    # --- OHSI layer ---
    ohsi_layer = gpkg_layer_element(
        "ohsi", "Outdoor Heat Shelter Index (OHSI)", gpkg_rel_path,
        "ohsi", GREENS, ohsi_breaks,
    )
    project_layers.append(ohsi_layer)

    # --- IHSI layer ---
    ihsi_layer = gpkg_layer_element(
        "ihsi", "Indoor Heat Shelter Index (IHSI)", gpkg_rel_path,
        "ihsi", BLUES, ihsi_breaks,
    )
    project_layers.append(ihsi_layer)

    # --- OHSPI layer ---
    ohspi_layer = gpkg_layer_element(
        "ohspi", "Outdoor HS Priority (OHSPI)", gpkg_rel_path,
        "ohspi", RDYLGN_R, ohspi_breaks,
    )
    project_layers.append(ohspi_layer)

    # --- IHSPI layer ---
    ihspi_layer = gpkg_layer_element(
        "ihspi", "Indoor HS Priority (IHSPI)", gpkg_rel_path,
        "ihspi", RDYLGN_R, ihspi_breaks,
    )
    project_layers.append(ihspi_layer)

    # Layer tree (visible order)
    layer_tree = SubElement(qgis, "layer-tree-group")
    SubElement(layer_tree, "customproperties")

    # Groups
    for group_name, layer_els in [
        ("Intervention Priority", [ohspi_layer, ihspi_layer]),
        ("Shelter Resources", [ohsi_layer, ihsi_layer]),
        ("Heat Risk HRI", [hri_layer]),
        ("Base Data", [basemap]),
    ]:
        grp = SubElement(layer_tree, "layer-tree-group", name=group_name,
                         checked="Qt::Checked", expanded="1")
        for le in layer_els:
            lid = le.find("id").text
            name = le.find("layername").text
            SubElement(grp, "layer-tree-layer", id=lid, name=name,
                       checked="Qt::Checked", expanded="0")

    # Pretty print
    raw_xml = tostring(qgis, encoding="unicode")
    dom = minidom.parseString(raw_xml)
    return dom.toprettyxml(indent="  ", encoding=None)


def main():
    print("=" * 60)
    print("STEP 9: Generate QGIS Project")
    print("=" * 60)

    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    # Relative path from output/ to blocks file
    gpkg_rel = "../output/blocks/road_blocks.gpkg"

    qgs_xml = build_project(blocks, gpkg_rel)

    # Write .qgs
    qgs_path = OUTPUT_DIR / "shanghai_heat_risk.qgs"
    with open(qgs_path, "w", encoding="utf-8") as f:
        f.write(qgs_xml)
    print(f"\n  ✓ QGS XML written → {qgs_path}")

    # Package as .qgz
    with zipfile.ZipFile(QGIS_PROJECT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(qgs_path, "shanghai_heat_risk.qgs")
    print(f"  ✓ QGZ packaged  → {QGIS_PROJECT}")
    print(f"    Size: {QGIS_PROJECT.stat().st_size / 1024:.1f} KB")

    # Clean up standalone .qgs
    qgs_path.unlink()

    print("\n" + "=" * 60)
    print("QGIS project generation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
