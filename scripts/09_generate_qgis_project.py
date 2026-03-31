#!/usr/bin/env python3
"""
09_generate_qgis_project.py — Generate a QGIS 3.x project file (.qgz).

Creates a .qgs XML file and packages it into a .qgz archive.
The project includes:
  - Analysis layers: HRI, OHSI, IHSI, OHSPI, IHSPI (graduated renderers)
  - Processed rasters: UTCI, Population, Nightlight, GDP (pseudocolor)
  - OSM vector layers: Roads, Green spaces, POIs, Water, Buildings (muted style)
  - CartoDB Positron + OSM XYZ tile basemaps
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
    CRS_WGS84,
    OSM_BUILDINGS,
    OSM_LANDUSE,
    OSM_POIS,
    OSM_ROADS,
    OSM_TRANSPORT,
    OSM_WATER,
    OUTPUT_DIR,
    QGIS_PROJECT,
    UTCI_PROCESSED,
    POP_PROCESSED,
    NL_PROCESSED,
    GDP_PROCESSED,
)


# -- Color ramps -----------------------------------------------------------

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


def _hex_to_rgba(hex_color, alpha=255):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"{r},{g},{b},{alpha}"


# -- Graduated vector renderer (for analysis layers) -----------------------

def build_graduated_renderer(field, colors, breaks):
    renderer = Element("renderer-v2", type="graduatedSymbol", attr=field,
                       symbollevels="0", graduatedMethod="GraduatedColor")
    ranges_el = SubElement(renderer, "ranges")
    symbols_el = SubElement(renderer, "symbols")

    for i in range(len(breaks) - 1):
        lower = f"{breaks[i]:.4f}"
        upper = f"{breaks[i + 1]:.4f}"
        label = f"{breaks[i]:.2f} - {breaks[i + 1]:.2f}"
        sym_name = str(i)

        SubElement(ranges_el, "range", lower=lower, upper=upper,
                   symbol=sym_name, label=label, render="true")

        sym = SubElement(symbols_el, "symbol", type="fill", name=sym_name,
                         alpha="0.85", force_rhr="0")
        layer = SubElement(sym, "layer", locked="0", enabled="1",
                           **{"class": "SimpleFill"})
        SubElement(layer, "prop", k="color", v=_hex_to_rgba(colors[i], 217))
        SubElement(layer, "prop", k="style", v="solid")
        SubElement(layer, "prop", k="outline_color", v="128,128,128,255")
        SubElement(layer, "prop", k="outline_width", v="0.1")
        SubElement(layer, "prop", k="outline_style", v="solid")

    return renderer


# -- Simple vector renderer (for OSM context layers) -----------------------

def build_simple_fill_renderer(fill_rgba, outline_rgba="128,128,128,100",
                                outline_width="0.1"):
    renderer = Element("renderer-v2", type="singleSymbol", symbollevels="0")
    symbols_el = SubElement(renderer, "symbols")
    sym = SubElement(symbols_el, "symbol", type="fill", name="0",
                     alpha="1", force_rhr="0")
    layer = SubElement(sym, "layer", locked="0", enabled="1",
                       **{"class": "SimpleFill"})
    SubElement(layer, "prop", k="color", v=fill_rgba)
    SubElement(layer, "prop", k="style", v="solid")
    SubElement(layer, "prop", k="outline_color", v=outline_rgba)
    SubElement(layer, "prop", k="outline_width", v=outline_width)
    SubElement(layer, "prop", k="outline_style", v="solid")
    return renderer


def build_simple_line_renderer(color_rgba, width="0.3"):
    renderer = Element("renderer-v2", type="singleSymbol", symbollevels="0")
    symbols_el = SubElement(renderer, "symbols")
    sym = SubElement(symbols_el, "symbol", type="line", name="0",
                     alpha="1", force_rhr="0")
    layer = SubElement(sym, "layer", locked="0", enabled="1",
                       **{"class": "SimpleLine"})
    SubElement(layer, "prop", k="line_color", v=color_rgba)
    SubElement(layer, "prop", k="line_width", v=width)
    SubElement(layer, "prop", k="line_style", v="solid")
    SubElement(layer, "prop", k="capstyle", v="round")
    SubElement(layer, "prop", k="joinstyle", v="round")
    return renderer


def build_simple_marker_renderer(color_rgba, size="1.5"):
    renderer = Element("renderer-v2", type="singleSymbol", symbollevels="0")
    symbols_el = SubElement(renderer, "symbols")
    sym = SubElement(symbols_el, "symbol", type="marker", name="0",
                     alpha="1", force_rhr="0")
    layer = SubElement(sym, "layer", locked="0", enabled="1",
                       **{"class": "SimpleMarker"})
    SubElement(layer, "prop", k="color", v=color_rgba)
    SubElement(layer, "prop", k="size", v=size)
    SubElement(layer, "prop", k="name", v="circle")
    SubElement(layer, "prop", k="outline_style", v="no")
    return renderer


# -- Layer element builders ------------------------------------------------

def gpkg_layer_element(display_name, gpkg_path, field, colors, breaks):
    lid = uid()
    ml = Element("maplayer", type="vector", geometry="Polygon",
                 hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = lid
    SubElement(ml, "layername").text = display_name
    SubElement(ml, "datasource").text = f"{gpkg_path}|layername=road_blocks"
    SubElement(ml, "provider").text = "ogr"
    srs = SubElement(ml, "srs")
    sr = SubElement(srs, "spatialrefsys")
    SubElement(sr, "authid").text = CRS_UTM51N
    ml.append(build_graduated_renderer(field, colors, breaks))
    return ml


def build_pseudocolor_pipe(color_stops, band=1, nodata_val="nan"):
    """Build a <pipe> with singlebandpseudocolor renderer.
    color_stops: list of (value, r, g, b, alpha, label) tuples.
    """
    pipe = Element("pipe")
    renderer = SubElement(pipe, "rasterrenderer", type="singlebandpseudocolor",
                          band=str(band), opacity="0.85",
                          classificationMin=str(color_stops[0][0]),
                          classificationMax=str(color_stops[-1][0]))
    SubElement(renderer, "rasterTransparency")
    shader = SubElement(renderer, "rastershader")
    fn = SubElement(shader, "colorrampshader",
                    colorRampType="INTERPOLATED",
                    classificationMode="2",
                    clip="0")
    for val, r, g, b, a, label in color_stops:
        SubElement(fn, "item", value=str(val),
                   color=f"#{r:02x}{g:02x}{b:02x}",
                   alpha=str(a), label=label)
    return pipe


# Predefined color ramps for each raster type
RASTER_STYLES = {
    "utci": [
        (0,   49, 54, 149, 255, "0 C (cool)"),
        (20,  120, 180, 210, 255, "20 C"),
        (28,  255, 255, 191, 255, "28 C"),
        (33,  253, 174, 97,  255, "33 C"),
        (36,  244, 109, 67,  255, "36 C"),
        (39,  215, 48,  39,  255, "39 C"),
        (41,  165, 0,   38,  255, "41 C (extreme)"),
    ],
    "population": [
        (0,   255, 255, 229, 255, "0"),
        (5,   247, 252, 185, 255, "5"),
        (30,  217, 240, 163, 255, "30"),
        (100, 173, 221, 142, 255, "100"),
        (250, 49,  163, 84,  255, "250"),
        (500, 0,   109, 44,  255, "500"),
        (1500, 0,  68,  27,  255, "1500+"),
    ],
    "nightlight": [
        (0,   4,   4,   4,   255, "0 (dark)"),
        (10,  30,  30,  60,  255, "10"),
        (25,  70,  50,  100, 255, "25"),
        (40,  180, 120, 40,  255, "40"),
        (55,  255, 200, 50,  255, "55"),
        (70,  255, 255, 150, 255, "70"),
        (81,  255, 255, 255, 255, "80+ (bright)"),
    ],
    "gdp": [
        (0,        247, 252, 253, 255, "0"),
        (1e6,      229, 245, 249, 255, "1M"),
        (1e7,      178, 226, 226, 255, "10M"),
        (5e7,      102, 194, 164, 255, "50M"),
        (2e8,      44,  162, 95,  255, "200M"),
        (6e8,      0,   109, 44,  255, "600M"),
        (3.4e9,    0,   68,  27,  255, "3.4B+"),
    ],
}


def raster_layer_element(display_name, tif_path, style_key=None):
    lid = uid()
    ml = Element("maplayer", type="raster", hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = lid
    SubElement(ml, "layername").text = display_name
    SubElement(ml, "datasource").text = str(tif_path)
    SubElement(ml, "provider").text = "gdal"
    srs = SubElement(ml, "srs")
    sr = SubElement(srs, "spatialrefsys")
    SubElement(sr, "authid").text = CRS_UTM51N

    if style_key and style_key in RASTER_STYLES:
        pipe = build_pseudocolor_pipe(RASTER_STYLES[style_key])
        ml.append(pipe)

    return ml


def shp_layer_element(display_name, shp_path, geom_type, renderer):
    lid = uid()
    ml = Element("maplayer", type="vector", geometry=geom_type,
                 hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = lid
    SubElement(ml, "layername").text = display_name
    SubElement(ml, "datasource").text = str(shp_path)
    SubElement(ml, "provider").text = "ogr"
    srs = SubElement(ml, "srs")
    sr = SubElement(srs, "spatialrefsys")
    SubElement(sr, "authid").text = CRS_WGS84
    ml.append(renderer)
    return ml


def xyz_basemap_element(name, url):
    ml = Element("maplayer", type="raster", hasScaleBasedVisibilityFlag="0")
    SubElement(ml, "id").text = uid()
    SubElement(ml, "layername").text = name
    SubElement(ml, "datasource").text = (
        f"type=xyz&url={url}&zmax=19&zmin=0"
    )
    SubElement(ml, "provider").text = "wms"
    return ml


def add_tree_group(parent, name, layers, checked=True, expanded=True, visible=True):
    ck = "Qt::Checked" if checked else "Qt::Unchecked"
    grp = SubElement(parent, "layer-tree-group", name=name,
                     checked=ck, expanded="1" if expanded else "0")
    for le in layers:
        lid = le.find("id").text
        lname = le.find("layername").text
        lck = "Qt::Checked" if visible else "Qt::Unchecked"
        SubElement(grp, "layer-tree-layer", id=lid, name=lname,
                   checked=lck, expanded="0")
    return grp


# -- Main project builder --------------------------------------------------

def build_project(blocks_gdf, gpkg_rel_path):
    import mapclassify
    import numpy as np

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
    qgis = Element("qgis", version="3.34.0",
                    projectname="Shanghai Heat Risk Analysis")
    SubElement(qgis, "title").text = "Shanghai Heat Risk Analysis 2022"
    proj_crs = SubElement(qgis, "projectCrs")
    sr = SubElement(proj_crs, "spatialrefsys")
    SubElement(sr, "authid").text = CRS_UTM51N

    project_layers = SubElement(qgis, "projectlayers")

    # ── 1. Analysis layers (graduated) ────────────────────────────────
    hri_layer = gpkg_layer_element(
        "Heat Risk Index (HRI)", gpkg_rel_path, "hri_norm", YLOR_RD, hri_breaks)
    ohsi_layer = gpkg_layer_element(
        "Outdoor Heat Shelter Index (OHSI)", gpkg_rel_path, "ohsi", GREENS, ohsi_breaks)
    ihsi_layer = gpkg_layer_element(
        "Indoor Heat Shelter Index (IHSI)", gpkg_rel_path, "ihsi", BLUES, ihsi_breaks)
    ohspi_layer = gpkg_layer_element(
        "Outdoor HS Priority (OHSPI)", gpkg_rel_path, "ohspi", RDYLGN_R, ohspi_breaks)
    ihspi_layer = gpkg_layer_element(
        "Indoor HS Priority (IHSPI)", gpkg_rel_path, "ihspi", RDYLGN_R, ihspi_breaks)

    analysis_layers = [hri_layer, ohsi_layer, ihsi_layer, ohspi_layer, ihspi_layer]

    # ── 2. Processed raster layers (with pseudocolor symbology) ─────
    raster_layers = []
    raster_defs = [
        ("UTCI Aug 2022 (degrees C)", UTCI_PROCESSED, "utci"),
        ("Population Density (proxy)", POP_PROCESSED, "population"),
        ("Nightlight PCNL 2021", NL_PROCESSED, "nightlight"),
        ("GDP Gridded 2020 (~1km)", GDP_PROCESSED, "gdp"),
    ]
    for name, path, style in raster_defs:
        if path.exists():
            rl = raster_layer_element(name, path, style_key=style)
            raster_layers.append(rl)

    # ── 3. OSM vector layers (muted styling) ──────────────────────────
    osm_layers = []

    if OSM_ROADS.exists():
        roads = shp_layer_element(
            "OSM Roads", OSM_ROADS, "Line",
            build_simple_line_renderer("180,180,180,180", "0.3"))
        osm_layers.append(roads)

    if OSM_WATER.exists():
        water = shp_layer_element(
            "OSM Water Bodies", OSM_WATER, "Polygon",
            build_simple_fill_renderer("190,220,240,160", "150,190,210,120", "0.2"))
        osm_layers.append(water)

    if OSM_LANDUSE.exists():
        green = shp_layer_element(
            "OSM Landuse (Green Spaces)", OSM_LANDUSE, "Polygon",
            build_simple_fill_renderer("200,230,200,140", "170,210,170,100", "0.2"))
        osm_layers.append(green)

    if OSM_BUILDINGS.exists():
        buildings = shp_layer_element(
            "OSM Buildings", OSM_BUILDINGS, "Polygon",
            build_simple_fill_renderer("220,220,220,120", "200,200,200,80", "0.05"))
        osm_layers.append(buildings)

    if OSM_POIS.exists():
        pois = shp_layer_element(
            "OSM POIs (Shelter candidates)", OSM_POIS, "Point",
            build_simple_marker_renderer("70,130,180,200", "1.5"))
        osm_layers.append(pois)

    if OSM_TRANSPORT.exists():
        transport = shp_layer_element(
            "OSM Transport (Metro/Rail)", OSM_TRANSPORT, "Point",
            build_simple_marker_renderer("200,80,80,200", "2.0"))
        osm_layers.append(transport)

    # ── 4. Basemap tiles ──────────────────────────────────────────────
    basemap_carto = xyz_basemap_element(
        "CartoDB Positron",
        "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png")
    basemap_osm = xyz_basemap_element(
        "OpenStreetMap",
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png")

    basemap_layers = [basemap_carto, basemap_osm]

    # ── Add all layers to project ─────────────────────────────────────
    all_layers = analysis_layers + raster_layers + osm_layers + basemap_layers
    for layer in all_layers:
        project_layers.append(layer)

    # ── Layer tree (controls visibility and grouping) ─────────────────
    layer_tree = SubElement(qgis, "layer-tree-group")
    SubElement(layer_tree, "customproperties")

    add_tree_group(layer_tree, "Intervention Priority",
                   [ohspi_layer, ihspi_layer], checked=True, visible=True)
    add_tree_group(layer_tree, "Shelter Resources",
                   [ohsi_layer, ihsi_layer], checked=True, visible=True)
    add_tree_group(layer_tree, "Heat Risk",
                   [hri_layer], checked=True, visible=True)
    add_tree_group(layer_tree, "Raster Data (Processed)",
                   raster_layers, checked=True, visible=True)
    add_tree_group(layer_tree, "OSM Context Layers",
                   osm_layers, checked=True, visible=True)
    add_tree_group(layer_tree, "Basemap Tiles",
                   basemap_layers, checked=True, visible=True)

    raw_xml = tostring(qgis, encoding="unicode")
    dom = minidom.parseString(raw_xml)
    return dom.toprettyxml(indent="  ", encoding=None)


def main():
    print("=" * 60)
    print("STEP 9: Generate QGIS Project")
    print("=" * 60)

    blocks = gpd.read_file(BLOCKS_FILE)
    print(f"\n  Loaded {len(blocks)} blocks")

    gpkg_rel = str(BLOCKS_FILE)

    qgs_xml = build_project(blocks, gpkg_rel)

    qgs_path = OUTPUT_DIR / "shanghai_heat_risk.qgs"
    with open(qgs_path, "w", encoding="utf-8") as f:
        f.write(qgs_xml)
    print(f"\n  [OK] QGS XML written -> {qgs_path}")

    # Layer summary
    layer_groups = {
        "Analysis layers": ["HRI", "OHSI", "IHSI", "OHSPI", "IHSPI"],
        "Raster data": ["UTCI", "Population", "Nightlight", "GDP"],
        "OSM context": ["Roads", "Water", "Landuse", "Buildings", "POIs", "Transport"],
        "Basemaps": ["CartoDB Positron", "OpenStreetMap"],
    }
    for group, items in layer_groups.items():
        print(f"    {group}: {', '.join(items)}")

    with zipfile.ZipFile(QGIS_PROJECT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(qgs_path, "shanghai_heat_risk.qgs")
    print(f"\n  [OK] QGZ packaged -> {QGIS_PROJECT}")
    print(f"    Size: {QGIS_PROJECT.stat().st_size / 1024:.1f} KB")

    qgs_path.unlink()

    print("\n" + "=" * 60)
    print("QGIS project generation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
