# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Read this first — critical guardrails

**These are the rules most easily missed and most costly to get wrong. Read this whole section — and
the [Conventions](#conventions) section near the bottom — _before_ doing any work, not just the
overview above it.**

- **Only the user commits and merges — never the agent.** Do **not** run `git commit`, `git merge`, or
  `git push`. Make and verify the file changes, leave them **staged / on-disk**, and let the user review,
  commit, and merge in GitHub Desktop. Creating a branch (`git checkout -b` / `git branch`) is fine — that
  is not a commit. _A local `.claude/` PreToolUse hook also blocks these commands, but `.claude/` is
  git-ignored, so this written rule — not the hook — is the durable, cross-machine contract._
- **Edit the notebook `.py`, never the `.ipynb` directly.** Notebooks are jupytext-paired and the `.py`
  is the source of truth; after editing run `pixi run jupytext --sync <name>.py`. The `.py` is what you
  review.
- **Storage formats are fixed:** tabular DataFrames → **GeoParquet + a CSV copy** (via `save_outputs`);
  raster / xarray datacubes → **zarr v3** (via `save_datacube`), **never parquet**.
- **USGS data comes from the new WaterData APIs — NOT the legacy NWIS / Water Quality Portal.** See
  _Use the new USGS WaterData APIs_ below.
- **Federal hydrography & monitoring data is US-only** — it stops at the Rio Grande border; capturing
  the Mexican side needs other sources. See _Stream-network data is US-only — the Mexico gap_ below.
- **Multi-step work pauses for the user at each task-group gate** (branch off `main`, agent does not
  commit, user reviews the working-tree diff and commits). See _Development workflow_ under Conventions.
- **No formal test suite:** verify by executing notebooks headlessly (`pixi run jupyter nbconvert
  --to notebook --execute --inplace <nb>.ipynb`) + `pixi run render` + small assertion snippets — not pytest.
- **A USGS API key in `.env`** (`API_USGS_PAT`) raises rate limits; without it, repeated calls **hit HTTP 429**.

Everything below expands on these. When a detail here and a detail below ever disagree, the more specific
section below wins — but the bullets above are the ones you must not skip.

## What this is

A data-compilation and analysis project for **American Forests' Thornforest project, Task 2**:
gather, organize, and analyze **25 years (2000–2025)** of publicly available precipitation,
streamflow, and water-quality data for three South Texas HUC-8 watersheds, then test whether
measurable changes in water quantity/quality correlate with the timing and location of restoration
activity. See [README.md](README.md) for the full scope.

**Publication goal:** the notebooks are published with **interactive HoloViews/GeoViews visuals**
as a static **website built with Quarto**, deployed to **GitHub Pages** via GitHub Actions — the same
toolchain and patterns as the sibling **`soil-health-hydraulics`** repo. **Live at
<https://limnotech.github.io/Thornforest/>** (see **Website (Quarto)** below).

**Current status (Round 1 complete, site live).** The work is split into two notebooks:
**`1_usgs_hydrography`** (HUC-8 boundaries → map) and **`3_usgs_waterdata`** (discover monitoring
stations → record which priority parameters each measured → maps). Shared setup/colors/utilities live in
`notebooks/_helpers.py`. Each result is saved to `data/` as **GeoParquet + CSV** with on-disk request
caching, and the site is **published to GitHub Pages** (LimnoTech-branded via `_brand.yml`).
Data-source exploration lives in `sandbox/` (e.g. `sandbox/explore_nhdplus_vpu13`). The **stream
network is deferred** (see the coverage note below).

## Planned structure (agreed approach)

A series of Jupyter notebooks in a **hybrid** organization:

- **Fetch notebooks, one per source** — each discovers what data exists within the three watersheds,
  fetches the 2000–2025 record, and saves it under `data/`. Source-prefixed, numbered names
  (e.g. `1_usgs_hydrography`, `2_usgs_climate`, `3_usgs_waterdata`, then further source notebooks).
- **Display / analyze notebooks, shared** — read the saved data and work across sources by data type or
  watershed (maps, trends, pre/post-restoration comparisons). The Excel/structured deliverable is
  exported from the harmonized data at the end.

**Storage-format convention (firm).** **Tabular** DataFrames/GeoDataFrames → **parquet** (compact,
typed — what notebooks read) **plus a CSV copy** (geometry as WKT) for transparency. **Datacubes**
(anything read natively with xarray — raster/gridded data) → **zarr, never parquet**. Write zarr as
**v3 with an explicit `ZstdCodec`** (Icechunk-ready) via the `save_datacube` helper. Parquet flattens
away dims/coords/CRS/chunking that make a cube useful; zarr preserves them.

**Data directory layout:**

- `data/hydrography/` — geometries from **HyRiver/`pygeohydro`** (e.g. `huc8_watersheds`). (parquet+CSV)
- `data/usgs_waterdata/` — products from **`dataretrieval.waterdata`** (e.g.
  `usgs_monitoring_locations`, `usgs_monitoring_locations_parameters`). (parquet+CSV)
- `data/climate/` — CONUS404 climate products (NB2): the gridded monthly **datacube**
  `conus404_monthly_grid.zarr` (**git-ignored**, ~57 MB — regenerated from the cloud), the small
  **committed** derived datacubes `conus404_climatology_grid.zarr` / `conus404_trends_grid.zarr`,
  and the tabular `conus404_wateryear_by_huc8.{parquet,csv}` / `conus404_trends_by_huc8.{parquet,csv}`.
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

**Notebook 1 (`notebooks/1_usgs_hydrography`)** — imports at top + `S = init_session()` (from
`_helpers`); fetch the three HUC-8 boundaries with `pygeohydro.WBD` → `save_outputs` to `data/hydrography/`;
map them on an Esri World Topo basemap (watershed colors via `categorical_colors`).

**Notebook 3 (`notebooks/3_usgs_waterdata`)** — reads `data/hydrography/huc8_watersheds.parquet`; discovers
stations via `dataretrieval.waterdata.get_monitoring_locations(bbox=…)` clipped with `geopandas.sjoin`;
then records, per station, the four **data-type flags** (daily/continuous/field/samples) **and** which of
eleven **priority parameters** — nine water-quality (conductivity, temperature, dissolved oxygen,
dissolved solids, chlorophyll, pH, nitrogen, phosphorus, turbidity) plus two water-quantity
(**discharge** and **water level**) — it measured — gathered from `get_time_series_metadata` +
`get_field_measurements_metadata` (parameter codes) and the per-station samples summary (characteristics, fetched
concurrently via `async_retriever`), enriched via `get_reference_table("parameter-codes")`, using
`PRIORITY_GROUPS`/`classify_parameter` defined in NB3. Saves the inventory (+ a `parameters` list column)
to `data/usgs_waterdata/usgs_monitoring_locations_parameters.{parquet,csv}` and maps stations by
parameter (click-legend toggle). **The stream network is deferred** pending a Mexico-capable source
(see coverage note).

**Notebook 2 (`notebooks/2_usgs_climate`)** — reads `data/hydrography/huc8_watersheds.parquet`;
opens **CONUS404** monthly output (`s3://hytest/conus404/conus404_monthly.zarr` on the USGS OSN pod,
anonymous; grid CRS via `pyproj.CRS.from_cf(ds['crs'].attrs)`), clips the 11 water-balance variables
to the bbox, and **saves the gridded monthly datacube to zarr** (`conus404_monthly_grid`, via the
`conus404_monthly_grid` helper, load-if-exists). From the cube it derives, **per watershed**, an
area-weighted zonal mean (`zonal_by_huc8` → `xvec`/`exactextract`) aggregated to water-year totals/means
with a simple water balance `P − ET − Q` and **Mann–Kendall/Sen's-slope** trends (`mk_sen_trend`,
tabular → parquet+CSV); and, **per grid cell**, a climatology and per-cell trends (`pixel_trend`,
datacubes → zarr) for spatial-pattern + change-over-time maps. Maps reproject the small cube to
EPSG:4326 (`rioxarray`) for tiled GeoViews quadmeshes; charts show water-year P/ET/Q, temperature, and
Sen's-slope bars. **Monthly** (not daily) keeps the gridded cube small (~57 MB vs ~2.4 GB) — the size
that makes keeping the spatial grid practical. Monthly `AC*` values are **monthly accumulations** (sum
12 → water-year total).

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
  (pass `skip_geometry=True` to drop coordinates). Parameter codes are USGS `parameter_code`s (e.g. discharge
  `00060`, mean-daily statistic `00003`); query by `monitoring_location_id`, geography, parameter, and
  date range. Specify *just enough* inputs — redundant geographic/parameter filters slow queries and can error.
- **API key (optional):** access works unauthenticated; a free key at
  <https://api.waterdata.usgs.gov/signup/> raises rate limits. It's read from the **`API_USGS_PAT`**
  env var. Pattern: a git-ignored **`.env`** holds the real key, the committed **`.env.example`** is
  the template (`cp .env.example .env`), and notebooks call `load_dotenv()` (**`python-dotenv`** is in
  `pixi.toml`) to load it. Never hardcode the key or commit `.env`. Everything still runs with no key.

### Discovering data availability (the NB3 pattern)

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
  lookups in NB3.
- **Geospatial:** `geopandas`, `gdal` + `libgdal-arrow-parquet`, `rioxarray`, `xarray`, `xvec`,
  `exactextract`, `cfunits` — for station locations, raster/climate datacubes, area-weighted zonal
  stats (`xvec` + `exactextract`), and unit handling. Station-to-restoration-site mapping (spatial
  relevance) is an explicit project goal.
- **Analysis:** `pymannkendall` — Mann–Kendall trend test + Sen's-slope estimate (NB2 trends).
- **Storage / remote access:** `pyarrow`, `zarr>=3`, `fsspec`/`s3fs`/`universal_pathlib` — Parquet
  (tabular) / **Zarr v3** (datacubes) outputs and anonymous cloud-path access (CONUS404 on the OSN pod).
- **Visualization & notebooks:** `hvplot`, `geoviews`, `contextily`, JupyterLab, `jupyter_bokeh`,
  and `jupytext` — interactive maps/plots authored in notebooks.

## Website (Quarto) — published to GitHub Pages

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

**Publishing (live):** [`.github/workflows/publish.yml`](.github/workflows/publish.yml) renders and
deploys to **GitHub Pages** on every push to `main` (and on `workflow_dispatch`). The render step is
given the **`API_USGS_PAT`** repo **secret** so a freeze-miss CI re-execution stays authenticated (the
notebooks hit the USGS APIs); Pages Source is set to **GitHub Actions**. Live at
<https://limnotech.github.io/Thornforest/>. After editing a notebook, re-run `pixi run render` locally
and commit `_freeze/` to keep CI fast.

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

### Development workflow (branches, commits, reviews)

- **Only the user commits and merges — never the agent.** This is the keystone rule — its full text
  lives in [⚠️ Read this first](#️-read-this-first--critical-guardrails) at the top of this file.
  (Creating a branch with `git checkout -b` / `git branch` is fine — that is not a commit.)
- **Feature work happens on a branch per coupled task-group, branched off `main` by the agent.** Group
  tightly-coupled tasks onto one branch (don't make a branch per micro-step). The user reviews the whole
  branch, commits, and merges it to `main` before the next group's branch is created off the updated
  `main`. Task-groups are dependent, so the agent **pauses after each group** for the user's
  review/commit/merge gate.
- **Multi-step plans run via subagent-driven development:** a fresh implementer subagent per task-group,
  a task review (spec compliance + code quality) before handing the group to the user. Because the agent
  doesn't commit, per-group review runs on the **working-tree diff** (`git add -N` untracked, then
  `git diff`), not on commit ranges.
- **Verification (no formal test suite):** the deliverable is executed notebooks + the rendered site.
  Verify by executing notebooks headlessly (`pixi run jupyter nbconvert --to notebook --execute
  --inplace <nb>.ipynb`), running small assertion snippets, and `pixi run render` + grep — not pytest.
- **Explore new data sources in a `sandbox/` notebook first**, then port the proven approach into the
  numbered notebooks (mirrors the sibling `data-engine/sandbox/` pattern).
- **Reusable, project-agnostic helpers live in [`notebooks/_helpers.py`](notebooks/_helpers.py)**
  (`find_repo_root`, `init_session`/`Session`, `save_outputs`, `save_datacube`, `show`,
  `categorical_colors`/`CATEGORICAL`, `make_legend_clickable`; plus the CONUS404 set
  `conus404_monthly_grid`, `zonal_by_huc8`, `water_year`, `mk_sen_trend`, `pixel_trend`); notebooks
  `from _helpers import …` rather than redefining them. The leading underscore makes Quarto ignore the
  module when rendering. Heavy imports (xarray/pyproj/xvec/pymannkendall) in the CONUS404 helpers are
  **lazy** (inside the functions) so NB1/NB3 don't pay their import cost. (Candidate to grow into a
  shareable cross-project package.)
- **Session setup via `init_session()`** — call once near the top of each notebook (`S = init_session()`);
  it loads `.env`, configures the `cache/` HTTP cache, and returns paths/headers (`S.data_dir`,
  `S.cache_file`, `S.api_headers`, …). Avoid scattering that config across cells.
- **Data colors come from colorcet, never the LimnoTech brand.** Color figure *data* with
  `categorical_colors(keys)` (colorcet `b_glasbey_category10`); the brand palette + Roboto (`_brand.yml`)
  are for the *site chrome* only.
- **`save_outputs` returns nothing on purpose** — a save call is often the last line of a cell, and a
  returned (Geo)DataFrame would auto-render as a stray, non-scrollable table. Display tables explicitly
  with **`show(df)`** (fixed-height scrollable box; emits every row).
- **Paired notebooks (jupytext):** commit a diff-friendly `.py` alongside each `.ipynb`; keep them in
  sync with `pixi run jupytext --sync <name>.py`. The `.py` is the source to review/commit.
- **Saved data** follows the storage-format convention above: **tabular** → GeoParquet + a CSV copy
  (via `save_outputs`); **datacubes** → zarr v3 (via `save_datacube`). HyRiver geometries in
  `data/hydrography/`, `dataretrieval` products in `data/usgs_waterdata/`, CONUS404 climate in
  `data/climate/` (raw monthly cube git-ignored; derived products committed) — see the data layout
  & caching notes above.
- **API key:** `load_dotenv()` reads `API_USGS_PAT` from the repo-root `.env`; it's attached as the
  `X-Api-Key` header (and to `async_retriever` requests via `request_kwds`). Without it, calls fall back
  to anonymous limits and **will hit HTTP 429** under repeated use.
- `.pixi/` is git-ignored; commit `pixi.lock` so the environment is reproducible.
- **Git-ignored, never committed:** `cache/` (HTTP request cache) and `data_temp/` (scratch/raw
  downloads, e.g. the EPA NHDPlus `.7z` archives). **Committed:** `data/` outputs (the shareable
  GeoParquet/CSV products).
- **Dependencies added beyond the original manifest:** `pygeohydro` (WBD boundaries), `python-dotenv`
  (API key), `python-libarchive-c` (`.7z` extraction in the sandbox), `colorcet` (data color palettes),
  and `quarto` (site rendering).
