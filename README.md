# Thornforest project for American Forests

## Task 2: Hydrological and Water Quality Data Compilation and Analysis

Gather, compile, organize, and analyze 25 years (2000–2025) of publicly and
digitally available precipitation, streamflow, and water quality data for the
three HUC-8 watersheds of interest:
- South Laguna Madre (12110208)
- Los Olmos (13090001)
- Lower Rio Grande (13090002)

Water quality data will include conductivity, temperature, dissolved oxygen,
dissolved solids, total algae/chlorophyll, pH, nutrient concentrations (nitrogen and
phosphorus species), and turbidity measurements, where available.

Retrieve data from multiple federal and state sources, including USGS streamflow gauge records and water
quality sampling data; EPA water quality monitoring; Texas Commission on Environmental Quality (TCEQ)
Surface Water Quality Monitoring program; Texas Water Development Board groundwater and surface water
databases; the International Boundary and Water Commission for Rio Grande flow and allocation data; NOAA
National Centers for Environmental Information (NCEI) for precipitation records; and local irrigation
district records where accessible.

> **USGS / EPA data-system migration.** USGS and EPA are retiring the legacy data systems — the National
> Water Information System (**NWIS**) and the EPA STORET / **Water Quality Portal** — and consolidating
> federal water data behind the new **USGS Water Data APIs** at <https://api.waterdata.usgs.gov>. This
> project targets the new APIs via the **`waterdata` module of the [`dataretrieval`](https://doi-usgs.github.io/dataretrieval-python/)**
> Python package (which supersedes that package's legacy `nwis` module), rather than the deprecated
> NWIS/WQP endpoints. See the [WaterData demo](https://doi-usgs.github.io/dataretrieval-python/examples/WaterData_demo.html).
> Data is also fetched from the USGS Water Services host <https://api.water.usgs.gov>, used alongside
> the WaterData APIs at <https://api.waterdata.usgs.gov>.

Compile all retrieved into a structured database format (such as Excel or other format preferred by
American Forests) that American Forests can use for ongoing analysis. We will document each data source with
complete source information (including hyperlinks) and any relevant metadata. We will map monitoring station
locations relative to existing thornscrub area and American Forests restoration sites to assess spatial relevance. We
will use the collected and organized data to assess whether measurable changes in water quantity or quality
correlate with the timing and location of 25 years of restoration activity in the region.

Apply scientific statistical methods to identify correlations, which may include trend analyses of the raw data
(how does the water quantity or quality data change over time), trend analysis of normalized data (e.g.: adjust flow
and/or water quality data based on observed rainfall or temperature to minimize external factors that may skew the
trend analysis), box and whisker plots of data collected pre- and post-restoration efforts, and similar.

## Approach

The work is organized as a series of Jupyter notebooks following a **hybrid** structure:

- **Fetch notebooks (one per source)** — discover what data exists within the three HUC-8 watersheds,
  fetch the 2000–2025 record, and save it to `data/`. So far:
  - **`1_usgs_hydrofabric`** — the spatial foundation: HUC-8 watershed boundaries via HyRiver
    `pygeohydro`, mapped on an interactive topographic basemap.
  - **`2_usgs_waterdata`** — discovers the USGS monitoring stations within the watersheds
    (`dataretrieval.waterdata`) and records, per station, both the available **data types** (daily,
    continuous, field measurements, water-quality samples) and **which priority parameters** it
    measured — water quality (conductivity, temperature, dissolved oxygen, dissolved solids,
    chlorophyll, pH, nitrogen, phosphorus, turbidity) and water quantity (**discharge** and **water
    level**).
  - **`3_usgs_conus404_climate`** — fetches **CONUS404** monthly climate output (a 4-km reanalysis,
    cloud-hosted) for the area as a gridded datacube, then derives a long-term water balance
    (precipitation, evapotranspiration, runoff, recharge) and **trends** — both **per watershed**
    (water-year time series + Mann–Kendall/Sen's-slope) and **per grid cell** (climatology and trend
    maps showing spatial patterns and how they change over 1980–2024). This reaches the **whole
    area, including the Mexican side**, since it is gridded model output rather than US-only gauges.
- **Display / analyze notebooks (shared)** — read the saved data and work across sources by data type or
  watershed (maps, trend analyses, pre/post-restoration comparisons). A structured deliverable (Excel or
  the format American Forests prefers) is exported from the harmonized data at the end.

> **Binational coverage caveat.** The watersheds straddle the Rio Grande, but the US federal
> hydrography datasets (USGS NHD / NHDPlus and the WaterData monitoring network) are **US-only** and
> stop at the international border. Capturing the Mexican side of the basin (stream network and
> stations) will require Mexico-capable sources (e.g. HydroRIVERS, INEGI, or the IBWC), which is why
> the stream network is deferred to a later round.

The notebooks render as a static, **fully interactive** website (HoloViews/GeoViews visuals) built
with **[Quarto](https://quarto.org)** — `pixi run render` builds `_site/`, `pixi run preview` serves a
live-reload preview. Quarto executes the notebooks (baking the interactive Bokeh maps into the HTML)
and freezes the results to `_freeze/` (committed). The site is **published to GitHub Pages** via GitHub
Actions on every push to `main`: **<https://limnotech.github.io/Thornforest/>**.

Saved results live in `data/`. **Tabular** results are written as **GeoParquet** (compact, typed —
what the notebooks read) **and** a **CSV** copy (human-readable, geometry as WKT) for transparency:
HyRiver geometries (e.g. watershed boundaries) under `data/spatial/`, USGS WaterData products under
`data/usgs_waterdata/`, and the CONUS404 per-watershed water-balance/trend tables under
`data/conus404/`. **Gridded datacubes** (climate rasters) are written as **Zarr** instead — the
CONUS404 climatology and trend grids under `data/conus404/` (the larger raw monthly cube is
regenerated on demand rather than committed). To keep downloads fast, web requests are
cached on disk in a git-ignored `cache/` folder (reused for a week), so re-running a notebook doesn't
re-download. A free [USGS API key](https://api.waterdata.usgs.gov/signup/) in `.env` raises the rate
limits (see below).

## Environment

We recommend using [pixi](https://pixi.prefix.dev/latest/), the next-generation reproducible package management tool built on [conda](https://docs.conda.io/projects/conda/en/stable/) tooling.

If you are new to pixi but familiar with conda, this [Switching from Conda](https://pixi.prefix.dev/latest/switching_from/conda/) documentation succinctly compares similarities and differences.

For required dependencies see [pixi.toml](pixi.toml).

### 1. Install Pixi

Follow [Pixi Installation](https://pixi.prefix.dev/latest/installation/) instructions for your platform.

### 2. Clone or Download this Repository

From these Github sites, click on the green "Code" dropdown button near the upper right. Select to either "Open in GitHub Desktop" (i.e. git clone) or "Download ZIP". 

We recommend using GitHub Desktop, to most easily manage git workflows by providing excellent visuals for stagging commits, exploring commit histories, comparing branches, and resolving merge conflicts in tight integration with Visual Studio Code.

Place your copy of these repos in any convenient location on your computer.

### 3. Create a Workspace and Python Environment

Create a project-specific Pixi workspace and Python enviornment(s) from the `pixi.toml` manifest file.

```bash
pixi install              # create/refresh the env from pixi.lock
pixi run jupyter lab      # work on notebooks interactively
```

## USGS API key (optional)

Accessing the USGS Water Data APIs works **without credentials**; a free
[API key](https://api.waterdata.usgs.gov/signup/) only raises rate limits. To add one safely:

```bash
cp .env.example .env          # then paste your key into .env (API_USGS_PAT=...)
```

`.env` is git-ignored — your key never gets committed. Notebooks load it with
[`python-dotenv`](https://pypi.org/project/python-dotenv/):

```python
from dotenv import load_dotenv
load_dotenv()                 # reads API_USGS_PAT from .env into the environment, if present
```

The `dataretrieval.waterdata` calls then pick up the key automatically. With no `.env`, everything
still runs (at lower rate limits).
