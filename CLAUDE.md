# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A data-compilation and analysis project for **American Forests' Thornforest project, Task 2**:
gather, organize, and analyze **25 years (2000–2025)** of publicly available precipitation,
streamflow, and water-quality data for three South Texas HUC-8 watersheds, then test whether
measurable changes in water quantity/quality correlate with the timing and location of restoration
activity. See [README.md](README.md) for the full scope.

**Publication goal:** the notebooks will be released with **interactive HoloViews/GeoViews visuals**
as a static **GitHub Pages (`*.github.io`) website built with Quarto** — the same toolchain and
patterns as the sibling **`soil-health-hydraulics`** repo (Quarto executes/freezes the notebooks to
preserve the interactive Bokeh embeds in static HTML). That repo is the reference for the eventual
`_quarto.yml` / freeze / deploy setup.

**Current status.** Notebook 1 (`notebooks/1_usgs_hydrography_waterdata`) is built: it fetches the
three HUC-8 boundaries, maps them, discovers the USGS monitoring stations within them, and flags which
of four data types each station offers. Data-source exploration that doesn't belong in the polished
notebooks lives in `sandbox/` (e.g. `sandbox/explore_nhdplus_vpu13`). Nothing is saved to `data/` yet,
and the **stream network is deferred** (see the coverage note below).

## Planned structure (agreed approach)

A series of Jupyter notebooks in a **hybrid** organization:

- **Fetch notebooks, one per source** — each discovers what data exists within the three watersheds,
  fetches the 2000–2025 record, and saves it under `data/`. Source-prefixed, numbered names
  (e.g. `1_usgs_hydrography_waterdata`, then further `waterdata`-based notebooks).
- **Display / analyze notebooks, shared** — read the saved data and work across sources by data type or
  watershed (maps, trends, pre/post-restoration comparisons). The Excel/structured deliverable is
  exported from the harmonized data at the end.

**Data directory layout:**

- `data/spatial/` — **GeoParquet**: HUC-8 watershed boundaries, stream network, station locations.
- `data/<source>/` — **Parquet**: tabular timeseries per source (e.g. `data/usgs/streamflow.parquet`).

**Notebook 1 (`notebooks/1_usgs_hydrography_waterdata`)** — built. Steps: (1–4) fetch the three HUC-8
boundaries with `pygeohydro.WBD` and map them on an Esri World Topo basemap; (5) discover monitoring
stations via `dataretrieval.waterdata.get_monitoring_locations(bbox=…)`, then clip to the watershed
polygons with `geopandas.sjoin`; (6) determine which of four data endpoints each station offers;
(7) map stations by data type with a click-to-toggle legend. **The stream network was removed** from
NB1 and is deferred pending a Mexico-capable source (see coverage note). Saving to `data/spatial/` is
still TODO.

**Audience:** notebooks are written for readers **new to Python/Jupyter** — explain each step in
markdown, and keep code cells small and commented.

## Watersheds & target variables

Three HUC-8 watersheds:

- South Laguna Madre — `12110208`
- Los Olmos — `13090001`
- Lower Rio Grande — `13090002`

Water-quality parameters to compile where available: conductivity, temperature, dissolved oxygen,
dissolved solids, total algae/chlorophyll, pH, nitrogen & phosphorus species, turbidity — plus
precipitation and streamflow.

## Data sources (per README)

USGS streamflow + water quality, EPA water quality, Texas Commission on Environmental Quality (TCEQ)
Surface Water Quality Monitoring, Texas Water Development Board, International Boundary and Water
Commission (Rio Grande flow/allocation), NOAA NCEI (precipitation), and local irrigation-district
records. Each compiled record must carry complete source info (hyperlinks) and metadata; the
deliverable is a structured database (Excel or a format American Forests prefers).

### ⚠️ Use the new USGS WaterData APIs — NOT legacy NWIS / Water Quality Portal

USGS and EPA are **retiring** the legacy systems — **NWIS** and the EPA STORET / **Water Quality
Portal (WQP)** — and consolidating federal water data behind the new **USGS Water Data APIs** at
<https://api.waterdata.usgs.gov>. This project targets the new APIs. We also fetch from the USGS
Water Services host <https://api.water.usgs.gov> (a separate USGS endpoint used alongside the
WaterData APIs).

- **Use `dataretrieval.waterdata`** (the new module), **not** `dataretrieval.nwis` (legacy) and **not**
  WQP endpoints. The `waterdata` module supersedes `nwis` for both streamflow and water-quality data.
- Reference: [WaterData demo](https://doi-usgs.github.io/dataretrieval-python/examples/WaterData_demo.html).
- **Discovery** (find what exists before fetching): `get_monitoring_locations()`,
  `get_time_series_metadata()`, plus lookups `get_reference_table()` / `get_codes()`.
- **Fetch:** `get_daily()` (daily min/max/mean), `get_continuous()` (instantaneous),
  `get_samples()` (water-quality samples), `get_field_measurements()`, and the `get_latest_*` helpers.
- Each function returns a `(dataframe, metadata)` tuple — a **GeoDataFrame** when geopandas is installed
  (pass `skip_geometry=True` to drop coordinates). Parameter codes are USGS pcodes (e.g. discharge
  `00060`, mean-daily statistic `00003`); query by `monitoring_location_id`, geography, parameter, and
  date range. Specify *just enough* inputs — redundant geographic/parameter filters slow queries and can error.
- **API key (optional):** access works unauthenticated; a free key at
  <https://api.waterdata.usgs.gov/signup/> raises rate limits. It's read from the **`API_USGS_PAT`**
  env var. Pattern: a git-ignored **`.env`** holds the real key, the committed **`.env.example`** is
  the template (`cp .env.example .env`), and notebooks call `load_dotenv()` (**`python-dotenv`** is in
  `pixi.toml`) to load it. Never hardcode the key or commit `.env`. Everything still runs with no key.

### Discovering data availability (the NB1 pattern)

- **Stations:** `get_monitoring_locations(bbox=[minlon,minlat,maxlon,maxlat])` → GeoDataFrame; call
  `.set_crs(4326)` (it comes back without a CRS), then `geopandas.sjoin(..., predicate="within")` to the
  watershed polygons. The `hydrologic_unit_code` filter matches only the *exact* HUC string (misses
  sites tagged with longer HUC12 codes), so use **bbox + spatial filter** instead.
- **Which of the four data endpoints a station offers:**
  - **daily** & **continuous** — both from `get_time_series_metadata(bbox=…)`; split on
    `computation_period_identifier` (`"Daily"` vs `"Points"`).
  - **field measurements** — `get_field_measurements_metadata(bbox=…)`.
  - **samples** — ⚠️ the area-wide samples *results* service **504-times-out** in data-dense regions,
    and `get_samples(service="locations")` merely mirrors the full station registry (non-discriminating).
    The reliable signal is **per-station `get_samples_summary(monitoringLocationIdentifier=<id>)`**
    (non-empty = has samples) — accurate but one request per site, so it is the slow step (cache if needed).
  - Join availability back to stations on `monitoring_location_id`.

### ⚠️ Stream-network data is US-only — the Mexico gap

The study watersheds straddle the Rio Grande, but **every NHD product is US-only** and stops at the
international border (~25.84°N at the river mouth) — verified for the HyRiver WaterData
`nhdflowline_network` service, the `pynhd.NHDPlusHR` service, **and** the EPA NHDPlus V2.1 Rio Grande
VPU 13 download (explored in `sandbox/explore_nhdplus_vpu13`). Querying flowlines within the (US-only)
HUC-8 polygons compounds this. A **binational** stream network needs a Mexico-capable source —
**HydroRIVERS** (global, has a Strahler-order field), Mexico's **INEGI** Red Hidrográfica, or **OSM**
waterways. Until that is decided, NB1 omits the stream network.

## Environment & commands

Environment is managed by **pixi** ([pixi.toml](pixi.toml)); never use bare `pip`/`conda`.

```bash
pixi install              # create/refresh the env from pixi.lock
pixi run jupyter lab      # work interactively (no custom [tasks] are defined yet)
```

There is no test suite, linter, or build step configured yet. If you add reusable tasks (fetch,
render, lint), define them under `[tasks]` in `pixi.toml` so they're discoverable here.

## Stack (what the dependencies provide)

The pinned deps map to the project's needs:

- **Water-data retrieval:** `dataretrieval` — use its **`waterdata`** module (new USGS Water Data APIs;
  see the warning above), **not** the legacy `nwis` module. Plus the **HyRiver** suite (`pynhd`,
  `pygeoogc`, `hydrosignatures`) for NHD/watershed boundaries and stream networks by HUC.
- **Geospatial:** `geopandas`, `gdal` + `libgdal-arrow-parquet`, `rioxarray`, `xarray`, `xvec`,
  `cfunits` — for station locations, raster/precip data, and unit handling. Station-to-restoration-
  site mapping (spatial relevance) is an explicit project goal.
- **Storage / remote access:** `pyarrow`, `zarr>=3`, `fsspec`/`s3fs`/`universal_pathlib` — Parquet/
  Zarr outputs and cloud-path access.
- **Visualization & notebooks:** `hvplot`, `geoviews`, `contextily`, JupyterLab, `jupyter_bokeh`,
  and `jupytext` — interactive maps/plots authored in notebooks.

## Notebook & GeoViews gotchas (learned)

- **Tile maps:** set `frame_width=…` + `data_aspect=1` (do *not* fix both width and height) so basemap
  tiles aren't stretched/blurry — let the height follow the data's true geographic aspect.
- **Don't force a tile `min_zoom`** above the initial-view zoom to shrink labels — it breaks pan/zoom
  (tiles don't exist below the forced level). Choose the basemap/extent instead. Current basemap:
  `geoviews.tile_sources.EsriWorldTopo`.
- **Toggle layers on/off:** overlay one labeled layer per category, then a Bokeh hook
  `plot.state.legend.click_policy = "hide"` — clicking a legend entry hides/shows that layer
  (static-HTML-safe; no Panel `embed` needed).
- **EPA NHDPlus file-geodatabases** (sandbox method): read via `s3fs(anon=True)` from
  `dmap-data-commons-ow/NHDPlusV21/…` → extract `.7z` with **`libarchive`** → `pyogrio.read_arrow`.
  `FType` is a **numeric code** (460 = StreamRiver), not a string; `StreamOrde` is in a separate
  `PlusFlowlineVAA` table joined by **COMID**; geometries are **3D (measured Z)** → call
  `.geometry.force_2d()` before GeoViews can draw them. (`py7zr` won't solve on conda-forge here.)

## Conventions

- **Commits are made manually by the user in GitHub Desktop — do not run `git commit`.** Make and
  verify the file changes; leave staging/committing to the user.
- **Explore new data sources in a `sandbox/` notebook first**, then port the proven approach into the
  numbered notebooks (mirrors the sibling `data-engine/sandbox/` pattern).
- **Paired notebooks (jupytext):** commit a diff-friendly `.py` alongside each `.ipynb`; keep them in
  sync with `pixi run jupytext --sync <name>.py`. The `.py` is the source to review/commit.
- **Saved data** goes in `data/` (Parquet timeseries per source; GeoParquet in `data/spatial/`) — see
  Planned structure above.
- `.pixi/` is git-ignored; commit `pixi.lock` so the environment is reproducible.
- **Scratch/raw downloads** go in git-ignored **`data_temp/`** (e.g. the EPA NHDPlus `.7z` archives);
  curated outputs go in **`data/`**. Decide per-file whether large `data/` outputs are committed before
  pulling 25 years of records into the repo.
- **Dependencies added beyond the original manifest:** `pygeohydro` (WBD boundaries), `python-dotenv`
  (API key), and `python-libarchive-c` (`.7z` extraction in the sandbox).
