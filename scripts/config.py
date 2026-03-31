"""
Global configuration for Shanghai Heat Risk Analysis pipeline.

All paths, CRS definitions, classification parameters, and data URLs
are centralized here for easy maintenance and reproducibility.
"""

from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OSM_DIR = DATA_DIR / "shanghai-260329-free.shp"
UTCI_DIR = DATA_DIR / "utci"
POP_DIR = DATA_DIR / "population"
NL_DIR = DATA_DIR / "nightlight"
GDP_DIR = DATA_DIR / "gdp"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = ROOT / "output"
BLOCKS_DIR = OUTPUT_DIR / "blocks"
MAPS_DIR = OUTPUT_DIR / "maps"
FIGURES_DIR = OUTPUT_DIR / "figures"

# ── Coordinate Reference Systems ──────────────────────────────────────────
CRS_WGS84 = "EPSG:4326"
CRS_UTM51N = "EPSG:32651"

# ── Shanghai bounding box (WGS84: xmin, ymin, xmax, ymax) ────────────────
SHANGHAI_BBOX = (120.85, 30.68, 122.00, 31.88)

# ── Block generation thresholds ───────────────────────────────────────────
BLOCK_MIN_AREA_M2 = 5_000       # Remove fragments smaller than 5,000 m²
BLOCK_MAX_AREA_M2 = 2_000_000   # Flag blocks larger than 2 km²

# ── Normalization range [0.1, 0.9] ────────────────────────────────────────
NORM_MIN = 0.1
NORM_MAX = 0.9

# ── Road classes used for polygonize ──────────────────────────────────────
ROAD_CLASSES = [
    "motorway", "trunk", "primary", "secondary", "tertiary", "residential",
]

# ── Green space landuse classes (for OHSI) ────────────────────────────────
GREEN_CLASSES = [
    "park", "forest", "grass", "recreation_ground", "meadow", "nature_reserve",
]

# ── Indoor shelter POI classes and operational time weights (W_T) ─────────
# W_T reflects the fraction of a 24-hour day that the facility type
# is typically open and accessible to the public.
INDOOR_SHELTER_POI = {
    # Mall / Commercial — typically 10:00–22:00 → 12/24 = 0.50
    "mall": 0.50,
    "department_store": 0.50,
    "supermarket": 0.50,
    # Restaurant / Café — typically 07:00–22:00 → 15/24 ≈ 0.625
    "restaurant": 0.625,
    "cafe": 0.625,
    "fast_food": 0.625,
    "food_court": 0.625,
    "bar": 0.625,
    "bakery": 0.625,
    # Cultural / Public — typically 09:00–17:00 → 8/24 ≈ 0.33
    "museum": 0.33,
    "library": 0.33,
    "cinema": 0.33,
    "theatre": 0.33,
    "arts_centre": 0.33,
    "community_centre": 0.33,
}

# Metro / railway from transport layer — 06:00–23:00 → 17/24 ≈ 0.71
TRANSPORT_SHELTER = {
    "railway_station": 0.71,
}

# ── Data download URLs ────────────────────────────────────────────────────
# GloUTCI-M: 1 km monthly UTCI, August 2022 (Int16, divide by 100 for °C)
UTCI_URL = (
    "https://zenodo.org/api/records/8310513/files/"
    "GloUTCI-M_YEAR_2022_MONTH_08.zip/content"
)

# WorldPop 2024 China unconstrained 100 m population
POP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/"
    "R2024A/2024/CHN/v1/100m/unconstrained/"
    "chn_pop_2024_UC_100m_R2024A_v1.tif"
)

# PCNL 2021 harmonized nighttime light (500 m, China)
NL_URL = (
    "https://zenodo.org/api/records/7612389/files/"
    "PCNL2021.tif/content"
)

# Gridded GDP total, 30 arc-second (~1 km) resolution, 1990–2020 (multi-band)
GDP_URL = (
    "https://zenodo.org/api/records/13943886/files/"
    "rast_gdpTot_1990_2020_30arcsec.tif/content"
)

# ── Jenks natural-breaks classification ───────────────────────────────────
JENKS_CLASSES = 7

# ── OSM layer file paths (derived) ───────────────────────────────────────
OSM_ROADS = OSM_DIR / "gis_osm_roads_free_1.shp"
OSM_LANDUSE = OSM_DIR / "gis_osm_landuse_a_free_1.shp"
OSM_POIS = OSM_DIR / "gis_osm_pois_free_1.shp"
OSM_POIS_A = OSM_DIR / "gis_osm_pois_a_free_1.shp"
OSM_TRANSPORT = OSM_DIR / "gis_osm_transport_free_1.shp"
OSM_BUILDINGS = OSM_DIR / "gis_osm_buildings_a_free_1.shp"
OSM_WATER = OSM_DIR / "gis_osm_water_a_free_1.shp"

# ── Processed raster file paths (derived) ────────────────────────────────
UTCI_PROCESSED = PROCESSED_DIR / "utci_shanghai_utm.tif"
POP_PROCESSED = PROCESSED_DIR / "pop_shanghai_utm.tif"
NL_PROCESSED = PROCESSED_DIR / "nl_shanghai_utm.tif"
GDP_PROCESSED = PROCESSED_DIR / "gdp_shanghai_utm.tif"
BOUNDARY_FILE = PROCESSED_DIR / "shanghai_boundary.gpkg"

# ── Output file paths ────────────────────────────────────────────────────
BLOCKS_FILE = BLOCKS_DIR / "road_blocks.gpkg"
QGIS_PROJECT = OUTPUT_DIR / "shanghai_heat_risk.qgz"
