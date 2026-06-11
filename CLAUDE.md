# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A data-compilation and analysis project for **American Forests' Thornforest project, Task 2**:
gather, organize, and analyze **25 years (2000–2025)** of publicly available precipitation,
streamflow, and water-quality data for three South Texas HUC-8 watersheds, then test whether
measurable changes in water quantity/quality correlate with the timing and location of restoration
activity. See [README.md](README.md) for the full scope.

**Publication goal:** the notebooks are published with **interactive HoloViews/GeoViews visuals**
as a static **website built with Quarto** — the same toolchain and patterns as the sibling
**`soil-health-hydraulics`** repo. The local render is set up (see **Website (Quarto)** below);
deploying to `*.github.io` is deferred until the (private) repo gets publish permission.

**Current status.** Notebook 1 (`notebooks/1_usgs_hydrography_waterdata`) is built: it fetches the
three HUC-8 boundaries, maps them, discovers the USGS monitoring stations within them, flags which of
four data types each station offers, and **saves each result to `data/` (GeoParquet + CSV)** with
on-disk request caching. Data-source exploration that doesn't belong in the polished notebooks lives in
`sandbox/` (e.g. `sandbox/explore_nhdplus_vpu13`). The **stream network is deferred** (see the coverage
note below).

## Planned structure (agreed approach)

A series of Jupyter notebooks in a **hybrid** organization:

- **Fetch notebooks, one per source** — each discovers what data exists within the three watersheds,
  fetches the 2000–2025 record, and saves it under `data/`. Source-prefixed, numbered names
  (e.g. `1_usgs_hydrography_waterdata`, then further `waterdata`-based notebooks).
- **Display / analyze notebooks, shared** — read the saved data and work across sources by data type or
  watershed (maps, trends, pre/post-restoration comparisons). The Excel/structured deliverable is
  exported from the harmonized data at the end.

**Data directory layout** — each saved dataframe is written in **two formats**: GeoParquet
(compact, typed — what notebooks read) **and** a CSV copy (geometry as WKT) for transparency.

- `data/spatial/` — geometries from **HyRiver/`pygeohydro`** (e.g. `huc8_watersheds`).
- `data/usgs_waterdata/` — products from **`dataretrieval.waterdata`** (e.g.
  `usgs_monitoring_locations`, `usgs_monitoring_locations_data_types`).
- `data/<source>/` — one folder per other source as they're added (TCEQ, NCEI, …).

**Caching (two distinct layers — keep them separate):**

- **`cache/` (git-ignored)** — persistent **HTTP request cache** (sqlite). HyRiver caches its
  requests here by default (set `HYRIVER_CACHE_NAME`); the per-station samples requests are
  cached here too via `async_retriever` (`cache_name=`, `expire_after=` 1 week). This is what
  makes re-runs fast — it is *not* committed.
- **`data/` (committed)** — curated GeoParquet/CSV **outputs**, the shareable products other
  notebooks read. Written every run; not a freshness-gated cache.
- The plain `dataretrieval.waterdata` discovery calls (stations, time-series/field metadata) use
  their own client and are **not** in the HTTP cache, but they're few and cheap (and the API key
  removes the rate limit). Only HyRiver + `async_retriever` requests are cached in `cache/`.

**Notebook 1 (`notebooks/1_usgs_hydrography_waterdata`)** — built. Steps: (1) imports; (1b) setup —
`load_dotenv()` for the API key, the `cache/` HTTP cache, and a `save_outputs(gdf, path)` helper that
writes GeoParquet **+** CSV; (3) fetch the three HUC-8 boundaries with `pygeohydro.WBD` → save to
`data/spatial/`; (4) map them on an Esri World Topo basemap; (5) discover monitoring stations via
`dataretrieval.waterdata.get_monitoring_locations(bbox=…)`, clip to the polygons with `geopandas.sjoin`
→ save to `data/usgs_waterdata/`; (6) flag which of four data endpoints each station offers (samples
fetched concurrently via `async_retriever`) → save to `data/usgs_waterdata/`; (7) map stations by data
type with a click-to-toggle legend. **The stream network was removed** from NB1 and is deferred pending
a Mexico-capable source (see coverage note).

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
  see the warning above), **not** the legacy `nwis` module. Plus the **HyRiver** suite (`pygeohydro`
  for WBD boundaries; `pynhd`, `pygeoogc`, `hydrosignatures`). **`async_retriever`** (HyRiver's async
  HTTP layer) fires many small requests concurrently and caches them — used for the per-station samples
  lookups in NB1.
- **Geospatial:** `geopandas`, `gdal` + `libgdal-arrow-parquet`, `rioxarray`, `xarray`, `xvec`,
  `cfunits` — for station locations, raster/precip data, and unit handling. Station-to-restoration-
  site mapping (spatial relevance) is an explicit project goal.
- **Storage / remote access:** `pyarrow`, `zarr>=3`, `fsspec`/`s3fs`/`universal_pathlib` — Parquet/
  Zarr outputs and cloud-path access.
- **Visualization & notebooks:** `hvplot`, `geoviews`, `contextily`, JupyterLab, `jupyter_bokeh`,
  and `jupytext` — interactive maps/plots authored in notebooks.

## Website (Quarto) — local render; publishing deferred

The notebooks publish as a static, interactive website built with **Quarto**, modeled on the
sibling `soil-health-hydraulics` repo.

- **Config:** [`_quarto.yml`](_quarto.yml) (website; `cosmo` theme; `code-fold`; `execute-dir: file`;
  `execute: { enabled: true, freeze: auto }`) + [`index.qmd`](index.qmd) landing page.
- **Build:** `pixi run render` → `_site/` (executes notebooks, refreshes `_freeze/`);
  `pixi run preview` for a live-reload server.
- **Freeze:** Quarto **executes** the notebooks — that is what bakes the interactive
  HoloViews/GeoViews **Bokeh embeds** (`holoviews_exec`) into the static HTML — then freezes the
  results to **`_freeze/` (committed)**. **Re-render and commit `_freeze/` after editing a notebook.**
- **What renders:** the `render:` list is `index.qmd` + `notebooks/*.py`, so the **`sandbox/` is
  excluded**. Quarto resolves each paired notebook via its **`.py`** (not the `.ipynb`), so the render
  list targets `.py`; **navbar `href`s point at the output `.html`**. The `notebooks/*.py` glob is safe
  even though `notebooks/_helpers.py` matches it — Quarto ignores underscore-prefixed files.
- **Git:** `_site/`, `.quarto/`, `cache/` are ignored; **`_freeze/` is committed** (the render cache).

**Publishing is deferred** (private repo; needs permission to publish to `*.github.io`). To enable
later: add `.github/workflows/publish.yml` (same as soil-health), add **`API_USGS_PAT`** as a repo
**secret** (so a freeze-miss CI re-execution stays authenticated — NB1 hits the USGS APIs), and set
**Settings → Pages → Source → GitHub Actions**.

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
- **Scrollable tables:** display dataframes with **`show(df)`** (from `_helpers`) — a fixed-height,
  sticky-header scrollable box that emits *every* row and renders the same in JupyterLab and the static
  site. Don't end a cell on a bare dataframe (truncated, non-scrollable) or on a function that returns
  one (see the `save_outputs` note in Conventions).
- **Refreshing a notebook's committed outputs:** `jupytext --sync` only syncs *code/markdown*, and
  `pixi run render` writes `_site/`/`_freeze/` — **neither updates the `.ipynb`'s stored outputs**
  (what you view in the IDE / on GitHub). After changing code that affects displayed output, re-run
  `pixi run jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb` so the committed `.ipynb`
  matches, then `pixi run render`.

## Conventions

- **Commits are made manually by the user in GitHub Desktop — do not run `git commit`.** Make and
  verify the file changes; leave staging/committing to the user.
- **Explore new data sources in a `sandbox/` notebook first**, then port the proven approach into the
  numbered notebooks (mirrors the sibling `data-engine/sandbox/` pattern).
- **Reusable, project-agnostic helpers live in [`notebooks/_helpers.py`](notebooks/_helpers.py)**
  (`find_repo_root`, `save_outputs`, `show`); notebooks `from _helpers import …` rather than redefining
  them. The leading underscore makes Quarto ignore the module when rendering. (Candidate to grow into a
  shareable cross-project package.)
- **`save_outputs` returns nothing on purpose** — a save call is often the last line of a cell, and a
  returned (Geo)DataFrame would auto-render as a stray, non-scrollable table. Display tables explicitly
  with **`show(df)`** (fixed-height scrollable box; emits every row).
- **Paired notebooks (jupytext):** commit a diff-friendly `.py` alongside each `.ipynb`; keep them in
  sync with `pixi run jupytext --sync <name>.py`. The `.py` is the source to review/commit.
- **Saved data** goes in `data/` as **GeoParquet + a CSV copy** (via the `save_outputs` helper);
  HyRiver geometries in `data/spatial/`, `dataretrieval` products in `data/usgs_waterdata/` — see the
  data layout & caching notes above.
- **API key:** `load_dotenv()` reads `API_USGS_PAT` from the repo-root `.env`; it's attached as the
  `X-Api-Key` header (and to `async_retriever` requests via `request_kwds`). Without it, calls fall back
  to anonymous limits and **will hit HTTP 429** under repeated use.
- `.pixi/` is git-ignored; commit `pixi.lock` so the environment is reproducible.
- **Git-ignored, never committed:** `cache/` (HTTP request cache) and `data_temp/` (scratch/raw
  downloads, e.g. the EPA NHDPlus `.7z` archives). **Committed:** `data/` outputs (the shareable
  GeoParquet/CSV products).
- **Dependencies added beyond the original manifest:** `pygeohydro` (WBD boundaries), `python-dotenv`
  (API key), and `python-libarchive-c` (`.7z` extraction in the sandbox).
