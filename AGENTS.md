# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

This is a GIS/geospatial research data repository for **Shanghai Block-Scale Extreme Heat Risk Spatial Assessment and Heat Shelter Supply-Demand Matching Analysis (2024–2025)**. It is NOT a traditional software application — there are no build systems, package managers, or runnable services.

### Key Data Files

- `QGIS.qgz` — QGIS project file (opens with `qgis /workspace/QGIS.qgz`)
- `上海路网.shp` — Shanghai road network shapefile (missing `.shx`; set `SHAPE_RESTORE_SHX=YES` env var when loading with Python)
- `区级数据.shp.xml` — District-level administrative boundary metadata (WGS 1984 / EPSG:4326)
- `data/shanghai-260329-free.shp/` — 18 complete OpenStreetMap shapefiles (roads, buildings, POIs, water, transport, etc.)

### Development Environment

- **Python 3.12** with GIS packages: `geopandas`, `fiona`, `pyproj`, `shapely`, `matplotlib`, `numpy`, `pandas`, `folium`, `contextily`
- **QGIS 3.34** installed via apt for desktop GIS work
- CRS: All OSM data uses EPSG:4326; for metric operations project to EPSG:32651 (UTM zone 51N for Shanghai)

### Gotchas

- `上海路网.shp` is missing its `.shx` index file. Set `os.environ['SHAPE_RESTORE_SHX'] = 'YES'` before loading with geopandas/fiona.
- QGIS project was saved with v3.40.15; the installed v3.34 shows a version warning but loads successfully.
- matplotlib may warn about duplicate installations (system vs pip); use `matplotlib.use('Agg')` for headless rendering.
- The methodology uses a 500m grid (matching Shanghai's "15-minute community life circle") with formulas: `HRI = Hazard × Exposure × Vulnerability`, `OHSPI = HRI - OHSI`, `IHSPI = HRI - IHSI`.

### Running Analysis

Refer to the two markdown reports in the repo root for full methodology:
- `模型分析.md` — Model comparison (English)
- `2024-2025 年上海市街区尺度极端热风险空间评估与避难所供需匹配分析报告.md` — Full technical report (Chinese)
