# Heat Risk Index and Shelter Priority Model — Technical Specification

> Shanghai Block-Level Extreme Heat Risk Assessment and Shelter Supply-Demand Matching
>
> Reference implementation: Yang, A. (2025). *Mapping priority zones for urban heat mitigation in Shanghai: Heat risk vs. shelter provision.* Computers, Environment and Urban Systems, 117, 102283. [doi:10.1016/j.compenvurbsys.2025.102283](https://www.sciencedirect.com/science/article/abs/pii/S0198971525000833)

---

## 1. Problem Statement

Extreme heat events in Shanghai (24.9 M residents, subtropical monsoon climate) are intensifying under climate change and rapid urbanisation. Conventional heat-risk maps based on Land Surface Temperature (LST) fail on two counts:

1. **LST ≠ human thermal stress.** Rooftop radiative temperature diverges from pedestrian-level physiological heat load.
2. **Risk maps without resource context are not actionable.** Knowing *where it is hot* is insufficient — planners need to know *where it is hot AND cooling resources are missing*.

This model addresses both gaps by computing a multiplicative Heat Risk Index ($\text{HRI}$) from human-biometeorology data, then subtracting spatially explicit shelter supply indices to identify **intervention priority zones**.

---

## 2. Notation

| Symbol | Definition | Unit |
|--------|-----------|------|
| $H_i$ | Heat Hazard index for block $i$ | dimensionless [0.1, 0.9] |
| $E_i$ | Heat Exposure index for block $i$ | dimensionless [0.1, 0.9] |
| $V_i$ | Heat Vulnerability index for block $i$ | dimensionless [0.1, 0.9] |
| $\text{HRI}_i$ | Heat Risk Index for block $i$ | dimensionless |
| $T_i$ | UTCI mean value for block $i$ | °C |
| $PD_i$ | Population density for block $i$ | persons/km² |
| $POP_i$ | Total population within block $i$ | persons |
| $NL_i$ | Nighttime light intensity for block $i$ | DN |
| $GDP_i$ | Gridded GDP for block $i$ | USD PPP |
| $GSA_i$ | Green space area within block $i$ | m² |
| $POID_i$ | Weighted POI density for block $i$ | weighted count/km² |
| $W_T^{(k)}$ | Operating-time weight for shelter type $k$ | dimensionless [0, 1] |
| $\text{OHSI}_i$ | Outdoor Heat Shelter Index for block $i$ | dimensionless [0.1, 0.9] |
| $\text{IHSI}_i$ | Indoor Heat Shelter Index for block $i$ | dimensionless [0.1, 0.9] |
| $\text{OHSPI}_i$ | Outdoor Heat Shelter Priority Index for block $i$ | dimensionless |
| $\text{IHSPI}_i$ | Indoor Heat Shelter Priority Index for block $i$ | dimensionless |
| $\mathcal{N}^{+}(\cdot)$ | Positive normalisation (higher → higher) | — |
| $\mathcal{N}^{-}(\cdot)$ | Negative normalisation (higher → lower) | — |

---

## 3. Assumptions and Justifications

| # | Assumption | Justification |
|---|-----------|---------------|
| **A1** | Heat risk is a **multiplicative** interaction of Hazard ($H$), Exposure ($E$), and Vulnerability ($V$). A block with zero population has near-zero $\text{HRI}$ regardless of thermal intensity. | Follows the IPCC AR6 risk framework. An additive model ($H + E + V$) would assign moderate risk to uninhabited blocks with high UTCI, which is epidemiologically meaningless — heat mortality requires people. The multiplicative form $H \times E \times V$ ensures risk is only high when all three dimensions co-occur (Yang, 2025). |
| **A2** | Universal Thermal Climate Index (UTCI, °C) adequately represents pedestrian-level thermal stress. Monthly-mean GloUTCI-M (August 2022) serves as the static Hazard ($H$) proxy. | UTCI integrates air temperature, humidity, wind speed, and mean radiant temperature via a multi-node thermoregulation model, directly modelling human physiological response. LST only measures rooftop radiative temperature, which diverges from street-level thermal load by up to 10–15°C in urban canyon environments. August is Shanghai's peak heat month (climatological mean $T_{\max}$ > 35°C). |
| **A3** | OSM building footprint area is proportional to residential population. Total footprint is scaled to Shanghai's 24.9 M registered population to derive a Population Density ($PD_i$) surface for Exposure ($E$). | Building footprint area correlates with floor area and occupancy. This proxy is widely used when census-calibrated gridded data (e.g., WorldPop) is inaccessible. Limitation: industrial and commercial buildings inflate estimates in non-residential zones. |
| **A4** | Nighttime light intensity ($NL_i$) and gridded GDP ($GDP_i$) are **negative** proxies for Vulnerability ($V$) — higher values indicate greater adaptive capacity. | Brighter nightlight implies denser infrastructure, higher AC penetration, and better-maintained housing (Chen et al., 2021). Higher GDP correlates with purchasing power for cooling appliances, healthcare access, and housing insulation quality (Kummu et al., 2024). Both are established socio-economic resilience proxies in urban heat vulnerability literature. |
| **A5** | Public cooling shelters split into outdoor (green space → $\text{OHSI}$) and indoor (commercial/cultural/transit POIs → $\text{IHSI}$) types, each weighted by operating-time availability ($W_T$). | In Shanghai, indoor air-conditioned spaces (malls, metro stations, cafés) are the primary refuge during extreme heat — distinct from cities where parks dominate cooling strategy. Separating the two types enables targeted policy: green space investment vs. extended public building opening hours. $W_T$ reflects that a metro station open 17 h/day provides more shelter-hours than a library open 8 h/day. |
| **A6** | Road-enclosed blocks (from `shapely.polygonize`) reflect urban morphology better than regular grids. A 500 m fishnet fills gaps where road networks are sparse. | Road-enclosed blocks naturally vary in size with urban density — small blocks (100–200 m) in the city centre match the "15-minute community life circle" scale, while suburban blocks are larger. A uniform 500 m grid would over-segment dense areas and under-segment sparse areas. The fishnet backfill ensures 100% spatial coverage without sacrificing morphological fidelity in urban cores. |

---

## 4. Data Preparation

### 4.1 Data Sources

| Dataset | Source | Native resolution | Download |
|---------|--------|-------------------|----------|
| GloUTCI-M (Aug 2022) | Yao et al. (2023), CatBoost-downscaled global monthly UTCI | ~930 m | [zenodo.org/records/8310513](https://zenodo.org/records/8310513) |
| Population proxy | OSM Geofabrik Shanghai (2026-03-29), 148,117 building footprints rasterised, scaled to 24.9 M | ~100 m | [geofabrik.de](https://download.geofabrik.de/asia/china/shanghai-latest-free.shp.zip) |
| PCNL Nightlight 2021 | Chen et al. (2021), DMSP-OLS / NPP-VIIRS harmonised | ~860 m (500 m nominal) | [zenodo.org/records/7612389](https://zenodo.org/records/7612389) |
| Gridded GDP (2020) | Kummu et al. (2024), sub-national downscaled GDP PPP, 30 arc-second | ~860 m | [zenodo.org/records/13943886](https://zenodo.org/records/13943886) |
| OSM roads, landuse, POIs, transport | OpenStreetMap via Geofabrik Shanghai extract (2026-03-29) | Vector (street-level) | [geofabrik.de](https://download.geofabrik.de/asia/china/shanghai-latest-free.shp.zip) |

### 4.2 Preprocessing

All rasters are clipped to the Shanghai bounding box (120.85°E–122.00°E, 30.68°N–31.88°N) and reprojected to EPSG:32651 (UTM Zone 51N) for metric-unit area calculations. UTCI raw values (Int16) are divided by 100 to obtain °C. GDP uses the last band (year 2020) of the multi-temporal stack. NoData pixels are set to NaN and excluded from zonal statistics.

### 4.3 Spatial Unit Construction

```mermaid
flowchart LR
    A["OSM Roads\n205,444 segments"] --> B["Filter 6 classes\nmotorway, trunk, primary,\nsecondary, tertiary, residential"]
    B --> C["unary_union()\n+ Shanghai boundary ring"]
    C --> D["shapely.polygonize()"]
    D --> E["24,214 road-enclosed blocks\n(56% area coverage)"]
    F["Shanghai boundary\n(from OSM road extents)"] --> G["Subtract road-block union"]
    G --> H["Generate 500 m × 500 m\nfishnet on uncovered area"]
    H --> I["49,056 fishnet cells"]
    E --> J["Merge → 73,270 blocks\n100% area coverage"]
    I --> J
```

Road-enclosed blocks capture urban morphology: dense city-centre blocks have 100–200 m equivalent side lengths; suburban blocks reach 500–1400 m. The fishnet infill covers the remaining 44% (rural areas, water margins, Chongming Island) where road networks do not form closed polygons.

### 4.4 Resolution Matching

| Dataset | Pixel size (UTM) | Shanghai coverage | Adequacy for block-level analysis |
|---------|-----------------|-------------------|-----------------------------------|
| GloUTCI-M (UTCI) | ~930 m | 27,150 px | ⚠️ Multiple urban blocks share one pixel — spatial smoothing in city centre |
| Population proxy | ~100 m | 1,396,425 px | ✅ Finer than most blocks; multiple pixels per block |
| PCNL Nightlight | ~860 m | 31,785 px | ⚠️ Comparable to block scale; adequate for mean statistics |
| Gridded GDP | ~860 m | 31,785 px | ✅ Upgraded from 5-arcmin (8.6 km, only 304 px) to 30-arcsec; now matches NL and UTCI |

### 4.5 Zonal Statistics

Each of the 73,270 blocks receives aggregated values from the four rasters and two vector layers:

| Zonal operation | Source | Output variable | Statistic |
|----------------|--------|-----------------|-----------|
| Raster mean | UTCI | $T_i$ (UTCI, °C) | mean of all pixels whose centre falls within block $i$ |
| Raster sum | Population | $POP_i$ (persons) | sum of population pixels; $PD_i = POP_i / \text{area}_{km^2}$ |
| Raster mean | Nightlight | $NL_i$ (DN) | mean nightlight intensity |
| Raster mean | GDP | $GDP_i$ (USD PPP) | mean gridded GDP |
| Vector intersection | OSM landuse (green classes) | $GSA_i$ (m²) | total green polygon area clipped to block $i$ |
| Vector spatial join | OSM POIs + transport (shelter classes) | $POID_i$ (weighted count/km²) | $\sum W_T^{(k)} \cdot n_k$ for each shelter type $k$ within block $i$, divided by block area |

---

## 5. Model Architecture

```mermaid
flowchart TD
    subgraph DATA["📦 Data (Section 4)"]
        UTCI["GloUTCI-M\n~930 m"]
        POP["Population Proxy\n~100 m"]
        NL["PCNL Nightlight\n~860 m"]
        GDP["Gridded GDP\n~860 m"]
        LU["OSM landuse\n(green space)"]
        POI["OSM POIs + transport\n(indoor shelters)"]
    end

    subgraph ZONAL["📊 Zonal Stats → per block i"]
        UTCI --> Z_T["T_i"]
        POP --> Z_PD["POP_i, PD_i"]
        NL --> Z_NL["NL_i"]
        GDP --> Z_GDP["GDP_i"]
        LU --> Z_GSA["GSA_i"]
        POI --> Z_POI["POID_i, W̄_T"]
    end

    subgraph HRI["🔥 Heat Risk Index — HRI (Section 6)"]
        Z_T --> HAZ["Hazard H_i = 𝒩⁺(T_i)"]
        Z_PD --> EXP["Exposure E_i = 𝒩⁺(PD_i)"]
        Z_NL --> VUL["Vulnerability V_i =\n⅓[𝒩⁻(NL_i) + 𝒩⁻(GDP_i) + 𝒩⁺(PD_i)]"]
        Z_GDP --> VUL
        Z_PD --> VUL
        HAZ --> MULT["HRI_i = H_i × E_i × V_i"]
        EXP --> MULT
        VUL --> MULT
        MULT --> NORM_HRI["HRI_norm = 𝒩⁺(HRI_i)"]
    end

    subgraph SHELTER["🏠 Shelter Supply (Section 7)"]
        Z_GSA --> OHSI["Outdoor Heat Shelter Index\nOHSI_i = 𝒩⁺(GSA_i / POP_i)"]
        Z_PD --> OHSI
        Z_POI --> IHSI["Indoor Heat Shelter Index\nIHSI_i = 𝒩⁺(POID_i / PD_i × W̄_T)"]
        Z_PD --> IHSI
    end

    subgraph PRIORITY["⚡ Priority (Section 8)"]
        NORM_HRI --> OHSPI["OHSPI_i = HRI_norm − OHSI_i"]
        OHSI --> OHSPI
        NORM_HRI --> IHSPI["IHSPI_i = HRI_norm − IHSI_i"]
        IHSI --> IHSPI
    end
```

### Data → Indicator Mapping

| Raw dataset | Zonal stat | Feeds into | Formula | $\mathcal{N}$ direction |
|-------------|-----------|------------|---------|------------------------|
| GloUTCI-M (°C) | mean → $T_i$ | Hazard $H_i$ | $\mathcal{N}^{+}(T_i)$ | + : hotter → riskier |
| Population (buildings) | sum → $POP_i$, density → $PD_i$ | Exposure $E_i$ | $\mathcal{N}^{+}(PD_i)$ | + : denser → more exposed |
| PCNL Nightlight (DN) | mean → $NL_i$ | Vulnerability $V_i$ (1/3) | $\mathcal{N}^{-}(NL_i)$ | − : brighter → less vulnerable |
| Gridded GDP (USD PPP) | mean → $GDP_i$ | Vulnerability $V_i$ (1/3) | $\mathcal{N}^{-}(GDP_i)$ | − : richer → less vulnerable |
| Population | density → $PD_i$ | Vulnerability $V_i$ (1/3) | $\mathcal{N}^{+}(PD_i)$ | + : denser → age-sensitive proxy |
| OSM landuse (green) | area → $GSA_i$ | Outdoor Heat Shelter Index $\text{OHSI}_i$ | $\mathcal{N}^{+}(GSA_i / POP_i)$ | + : more green/capita → more shelter |
| OSM POIs + transport | weighted count → $POID_i$ | Indoor Heat Shelter Index $\text{IHSI}_i$ | $\mathcal{N}^{+}(POID_i / PD_i \times \bar{W}_T)$ | + : more POI/capita → more shelter |

---

## 6. Normalisation

All indicators are mapped to $[0.1, 0.9]$ to prevent multiplication-by-zero:

$$
\mathcal{N}^{+}(I) = 0.1 + 0.8 \cdot \frac{I - I_{\min}}{I_{\max} - I_{\min}}
$$

$$
\mathcal{N}^{-}(I) = 0.1 + 0.8 \cdot \frac{I_{\max} - I}{I_{\max} - I_{\min}}
$$

where $I_{\min}$ and $I_{\max}$ are the global minimum and maximum across all 73,270 blocks.

---

## 7. Heat Risk Index ($\text{HRI}$)

### 7.1 Hazard ($H_i$)

$$
H_i = \mathcal{N}^{+}(T_i)
$$

$T_i$ is the mean UTCI (°C) for block $i$, derived from GloUTCI-M August 2022 (Yao et al., 2023). UTCI integrates air temperature, humidity, wind speed, and mean radiant temperature through a multi-node human thermoregulation model.

### 7.2 Exposure ($E_i$)

$$
E_i = \mathcal{N}^{+}(PD_i)
$$

Population density ($PD_i$, persons/km²) serves as both a direct exposure measure and an indirect proxy for anthropogenic heat emission intensity.

### 7.3 Vulnerability ($V_i$)

$$
V_i = \frac{1}{3}\Big[\mathcal{N}^{-}(NL_i) + \mathcal{N}^{-}(GDP_i) + \mathcal{N}^{+}(PD_i)\Big]
$$

| Sub-indicator | $\mathcal{N}$ | Rationale |
|--------------|---------------|-----------|
| Nightlight $NL_i$ | $\mathcal{N}^{-}$ | Higher luminosity → better infrastructure, AC penetration |
| GDP $GDP_i$ | $\mathcal{N}^{-}$ | Higher GDP → greater adaptive capacity |
| Pop. density $PD_i$ | $\mathcal{N}^{+}$ | Proxy for age-sensitive population concentration |

The full model (Yang, 2025) uses 5 sub-indicators: $NL$, $GDP$, house prices, elderly density ($PD_{>65}$), child density ($PD_{<14}$). We use 3 due to data constraints (age-sex data: 51 GB; house prices: manual scraping required).

### 7.4 Multiplicative Aggregation

$$
\text{HRI}_i = H_i \times E_i \times V_i
$$

**Why multiplicative, not additive?** An additive model ($H + E + V$) would assign moderate risk to uninhabited blocks with extreme UTCI. The multiplicative form ensures risk is only high when **all three dimensions co-occur**, consistent with epidemiological evidence on heat mortality.

Re-normalised for mapping:

$$
\text{HRI}_i^{\text{norm}} = \mathcal{N}^{+}(\text{HRI}_i)
$$

---

## 8. Shelter Supply Indices

### 8.1 Outdoor Heat Shelter Index ($\text{OHSI}$)

Green spaces provide cooling through canopy shading and evapotranspiration.

$$
\text{OHSI}_i = \mathcal{N}^{+}\!\left(\frac{GSA_i}{\max(POP_i,\; 1)}\right)
$$

Green space classes from OSM `landuse_a`: `park`, `forest`, `grass`, `recreation_ground`, `meadow`, `nature_reserve`.

### 8.2 Indoor Heat Shelter Index ($\text{IHSI}$)

Air-conditioned public spaces serve as last-resort refuges during extreme heat.

$$
\text{IHSI}_i = \mathcal{N}^{+}\!\left(\frac{POID_i}{\max(PD_i,\; 0.001)} \cdot \bar{W}_T^{(i)}\right)
$$

| Shelter category | OSM fclass | $W_T$ | Hours |
|-----------------|-----------|-------|-------|
| Mall / Commercial | `mall`, `department_store`, `supermarket` | 0.50 | 10:00–22:00 |
| Restaurant / Café | `restaurant`, `cafe`, `fast_food`, `food_court`, `bar`, `bakery` | 0.625 | 07:00–22:00 |
| Cultural / Public | `museum`, `library`, `cinema`, `theatre`, `arts_centre`, `community_centre` | 0.33 | 09:00–17:00 |
| Metro / Transit | `railway_station` | 0.71 | 06:00–23:00 |

---

## 9. Intervention Priority Indices

$$
\text{OHSPI}_i = \text{HRI}_i^{\text{norm}} - \text{OHSI}_i
$$

$$
\text{IHSPI}_i = \text{HRI}_i^{\text{norm}} - \text{IHSI}_i
$$

- $> 0$: block has **more risk than shelter supply** → priority intervention zone
- $< 0$: block has **surplus** cooling capacity relative to its risk level

```mermaid
quadrantChart
    title Shelter Priority Interpretation
    x-axis Low Heat Risk Index --> High Heat Risk Index
    y-axis Low Shelter Supply --> High Shelter Supply
    quadrant-1 "Adequate:\nHigh risk, high shelter"
    quadrant-2 "Safe:\nLow risk, high shelter"
    quadrant-3 "Watch:\nLow risk, low shelter"
    quadrant-4 "PRIORITY:\nHigh risk, low shelter"
```

---

## 10. Sensitivity Analysis

We examine how $\text{HRI}$ responds to perturbations in each input dimension.

```python
"""
sensitivity_analysis.py — One-at-a-time (OAT) sensitivity of HRI
to ±20% perturbations in Hazard, Exposure, and Vulnerability.
"""
import numpy as np
import matplotlib.pyplot as plt

H0, E0, V0 = 0.65, 0.15, 0.42   # median-block baseline
hri_base = H0 * E0 * V0

perturbations = np.linspace(-0.20, 0.20, 41)
results = {"Hazard": [], "Exposure": [], "Vulnerability": []}
for dp in perturbations:
    results["Hazard"].append((H0 * (1 + dp)) * E0 * V0)
    results["Exposure"].append(H0 * (E0 * (1 + dp)) * V0)
    results["Vulnerability"].append(H0 * E0 * (V0 * (1 + dp)))

fig, ax = plt.subplots(figsize=(8, 5))
for label, values in results.items():
    pct = [(v - hri_base) / hri_base * 100 for v in values]
    ax.plot(perturbations * 100, pct, label=label, linewidth=2)
ax.set_xlabel("Input perturbation (%)")
ax.set_ylabel("HRI change (%)")
ax.set_title("OAT Sensitivity: HRI = H × E × V")
ax.legend(); ax.grid(True, alpha=0.3)
plt.savefig("docs/sensitivity_oat.png", dpi=200)
```

In a multiplicative model $\text{HRI} = H \times E \times V$, each component has **unit elasticity** — a 1% increase in any input produces exactly a 1% increase in $\text{HRI}$. No single dimension dominates *mathematically*.

However, the **empirical variance** across Shanghai blocks differs:

| Dimension | CV (coeff. of variation) | Interpretation |
|-----------|------------------------|----------------|
| Hazard $H$ | 0.200 | UTCI is spatially smooth at ~1 km |
| Exposure $E$ | 0.413 | Population density has highest spatial variance |
| Vulnerability $V$ | 0.155 | GDP and nightlight provide modest differentiation |

![Sensitivity Analysis](sensitivity_oat.png)

Despite equal theoretical elasticity, **Exposure ($E$, population density) is the dominant empirical driver** of spatial $\text{HRI}$ variation in Shanghai, because its variance far exceeds that of Hazard or Vulnerability.

---

## 11. Classification

We apply **quantile classification** (7 classes) rather than Jenks natural breaks.

The $\text{HRI}$ distribution is heavily right-skewed (most blocks have low $\text{HRI}$ due to low population). Jenks placed 89% of blocks into the two lightest classes, producing a visually uninformative map. Quantile classification assigns equal block counts per class, ensuring the full colour ramp is utilised.

| Class | Quantile range | Interpretation |
|-------|---------------|----------------|
| 1 | 0–14th percentile | Minimal risk |
| 2 | 14–29th | Low risk |
| 3 | 29–43rd | Below average |
| 4 | 43–57th | Average |
| 5 | 57–71st | Above average |
| 6 | 71–86th | High risk |
| 7 | 86–100th | Critical — priority intervention |

---

## 12. Results

### Heat Risk Index ($\text{HRI}$) Spatial Distribution

![HRI Map](https://raw.githubusercontent.com/Aurora-yang-git/HRI/refs/heads/cursor/shanghai-heat-risk-analysis-8327/output/maps/map_hri.png)

Central Shanghai (Huangpu, Jing'an, old Pudong) shows highest $\text{HRI}$ — the co-occurrence of extreme UTCI, high population density, and relatively lower GDP per capita. Suburban new towns (Songjiang, Jiading) show moderate risk. Rural and island areas (Chongming) are gray (zero-population blocks).

### Shelter Priority ($\text{OHSPI}$ and $\text{IHSPI}$)

![OHSPI](https://raw.githubusercontent.com/Aurora-yang-git/HRI/refs/heads/cursor/shanghai-heat-risk-analysis-8327/output/maps/map_ohspi.png)

![IHSPI](https://raw.githubusercontent.com/Aurora-yang-git/HRI/refs/heads/cursor/shanghai-heat-risk-analysis-8327/output/maps/map_ihspi.png)

![Priority Composite](https://github.com/Aurora-yang-git/HRI/blob/cursor/shanghai-heat-risk-analysis-8327/output/maps/map_priority_composite.png?raw=true)

$\text{OHSPI}$ reveals the inner-city green space deficit — old urban cores have the highest risk-to-shelter gap. $\text{IHSPI}$ shows a more dispersed pattern: some suburban residential areas with rapid population growth but lagging commercial development also score high.

### Dashboard

![Dashboard](https://raw.githubusercontent.com/Aurora-yang-git/HRI/refs/heads/cursor/shanghai-heat-risk-analysis-8327/output/maps/map_dashboard.png)

---

## 13. Limitations

1. **Population proxy.** OSM building footprints ≠ census-calibrated population. Industrial buildings inflate $PD_i$ in non-residential zones.

2. **Simplified Vulnerability ($V$).** Dropping age structure and house prices reduces the model from 5 to 3 sub-indicators. $PD_i$ as an age proxy lacks directional validity — dense areas may have *younger* populations (worker dormitories) rather than elderly concentrations.

3. **Static Hazard ($H$).** Monthly-mean UTCI from 2022 does not capture intra-day or event-scale variability. A heat-wave peak (e.g., July 2022, 40.9°C) would produce different spatial patterns.

4. **MAUP at block boundaries.** Hybrid spatial units (road polygons + fishnet grid) introduce a boundary artefact where unit type changes.

5. **Shelter capacity vs. presence.** POI count ≠ cooling capacity. A 200,000 m² mall and a 50 m² café both count as one POI.

---

## 14. Conclusion

This model operationalises the IPCC risk framework ($\text{Hazard} \times \text{Exposure} \times \text{Vulnerability}$) at the urban-block scale, using UTCI as a human-centred hazard metric instead of LST. By subtracting spatially explicit shelter indices ($\text{OHSI}$, $\text{IHSI}$) from normalised risk ($\text{HRI}^{\text{norm}}$), it produces **actionable priority maps** ($\text{OHSPI}$, $\text{IHSPI}$) that identify not just *where it is hot*, but *where it is hot and under-served by cooling resources*.

The multiplicative $\text{HRI}$ structure, while theoretically sound, is empirically dominated by Exposure ($E$, population density) due to its extreme spatial variance. Future work should incorporate real-time meteorological feeds and age-disaggregated population data to improve Hazard temporal resolution and Vulnerability specificity.

---

## References

- Yang, A. (2025). Mapping priority zones for urban heat mitigation in Shanghai: Heat risk vs. shelter provision. *Computers, Environment and Urban Systems*, 117, 102283. [doi:10.1016/j.compenvurbsys.2025.102283](https://www.sciencedirect.com/science/article/abs/pii/S0198971525000833)
- Yao, Y. et al. (2023). A 1-km global monthly UTCI dataset (GloUTCI-M). *Zenodo*. [doi:10.5281/zenodo.8310513](https://zenodo.org/records/8310513)
- Chen, Z. et al. (2021). An extended time series of harmonised nighttime light data (PCNL). *Zenodo*. [doi:10.5281/zenodo.7612389](https://zenodo.org/records/7612389)
- Kummu, M. et al. (2024). Gridded global datasets for GDP and HDI. *Zenodo*. [doi:10.5281/zenodo.13943886](https://zenodo.org/records/13943886)
- IPCC (2022). Climate Change 2022: Impacts, Adaptation and Vulnerability. AR6 WGII.
