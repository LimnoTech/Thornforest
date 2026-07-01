# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo. This file covers **how to work
here**; for *what the project is* — scope, data sources, per-notebook narrative, environment setup,
and API-key setup — see [README.md](README.md) and its sections, referenced inline below. When the
two disagree, this file wins on process, README wins on scope.

> **Using this file as a template.** Within each section, directives that transfer to other repos
> come first; repo-specific ones follow under a **This repo:** marker. To reuse, keep the general
> bullets and swap the repo-specific ones.

## ⚠️ Critical guardrails — read before any work

- **Only the user commits and merges — never the agent.** Do **not** run `git commit`, `git merge`,
  or `git push`. Make and verify changes, leave them **staged / on-disk**, and let the user review
  and commit in GitHub Desktop. Creating a branch (`git checkout -b`) is fine. *A git-ignored
  `.claude/` hook also blocks these, but this written rule is the durable, cross-machine contract.*
- **Multi-step work pauses at each task-group gate** — branch off `main`, agent does not commit, user
  reviews the working-tree diff and commits before the next group. See [Workflow](#workflow).
- **Edit the notebook `.py`, never the `.ipynb`.** Notebooks are jupytext-paired; the `.py` is the
  source of truth and what you review. After editing: `pixi run jupytext --sync <name>.py`.
- **No formal test suite** — verify by executing notebooks headlessly + rendering, not pytest. See
  [Commands](#commands) and [Workflow](#workflow).
- **Storage formats are fixed** — tabular → GeoParquet **+ CSV** (`save_dataframe`); raster/xarray
  datacubes → **zarr v3** (`save_datacube`), never parquet. See [Storage & data](#storage--data).
- **Preserve original source terminology in the data.** Carry each source's own parameter/variable
  names, descriptions, and units **verbatim** in datasets and saved outputs; introduce new names only
  for explicitly derived or blended quantities, and label them as such (so newcomers see the raw
  vocabulary the agencies actually use). In prose (docstrings/markdown) paraphrasing is fine — but
  **link to the primary documentation, liberally.**

**This repo:**

- **USGS data comes from the new WaterData APIs — NOT legacy NWIS / Water Quality Portal.** See
  [README § migration note](README.md#task-2-hydrological-and-water-quality-data-compilation-and-analysis)
  and [USGS WaterData](#usgs-waterdata-apis--discovery) below.
- **Federal hydrography & monitoring data is US-only** — it stops at the Rio Grande border; the
  Mexican side needs other sources and the stream network is deferred. See
  [README § binational caveat](README.md#approach) and [the Mexico gap](#the-mexico-gap).
- **A USGS API key in `.env`** (`API_USGS_PAT`) raises rate limits; without it, repeated calls **hit
  HTTP 429**. Setup in [README § USGS API key](README.md#usgs-api-key-optional).

## Commands

Environment is managed by **pixi** ([pixi.toml](pixi.toml)); **never** use bare `pip`/`conda`.
Install and interactive use are in [README § Environment](README.md#environment). Working commands:

```bash
pixi run jupytext --sync notebooks/<name>.py                    # regenerate the paired .ipynb after editing .py
pixi run jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb   # refresh committed .ipynb outputs
pixi run render      # build _site/ (executes notebooks, refreshes _freeze/)
pixi run preview     # live-reload preview server
```

Define any new reusable task under `[tasks]` in `pixi.toml` so it's discoverable.

## Workflow

- **Branch per coupled task-group, off `main`.** Group tightly-coupled tasks onto one branch (not one
  per micro-step). The user reviews, commits, and merges each group before the next branches off the
  updated `main`. Task-groups are dependent, so **pause after each group** for that gate.
- **Multi-step plans run via subagent-driven development** — a fresh implementer subagent per
  task-group, then a task review (spec + code quality) before handing to the user. Since the agent
  doesn't commit, per-group review runs on the **working-tree diff** (`git add -N` untracked, then
  `git diff`), not commit ranges.
- **Typical cadence — pause at each task-group gate.** The agent implements a task-group, reviews it
  (and applies fixes), then **stops and leaves the work staged for the user to commit** before the
  next group starts; the user's commit becomes the next group's clean baseline. The agent runs
  *within* a group autonomously (no check-ins between steps) — the gates are only *between* groups.
  To maximize autonomy, **group more tasks per gate** (fewer, larger task-groups → fewer pauses);
  to keep tighter checkpoints, split them.
- **Verification (no test suite):** the deliverable is executed notebooks + the rendered site.
  Execute notebooks headlessly, run small assertion snippets, and `pixi run render` + grep.
- **Explore new data sources in a `sandbox/` notebook first**, then port the proven approach into the
  numbered notebooks. (`sandbox/` is excluded from the site render.)

## Notebooks & helpers

- **`.py` is the source of truth** (jupytext-paired) — edit it, then `--sync`. Notebooks are written
  for readers **new to Python/Jupyter**: explain each step in markdown, keep code cells small.
- **Reusable helpers live in [`notebooks/_helpers.py`](notebooks/_helpers.py)** — `import` them, don't
  redefine. The leading underscore makes Quarto ignore the module when rendering. Keep heavy imports
  **lazy** (inside the functions that need them) so light notebooks don't pay the cost.
- **Set up each notebook with `S = init_session()`** once near the top — it loads `.env`, configures
  the HTTP cache, and returns paths/headers (`S.data_dir`, `S.cache_file`, `S.api_headers`, …). Don't
  scatter that config across cells.
- **`save_dataframe` returns nothing on purpose** (a save is often a cell's last line; a returned frame
  would auto-render as a stray, non-scrollable table). Display tables with **`show(df)`** — a
  fixed-height, sticky-header scrollable box that emits every row.
- **Color data with colorcet, never the brand palette** — `categorical_colors(keys)` (colorcet
  `b_glasbey_category10`) for figure data; the brand palette + Roboto (`_brand.yml`) are site chrome.

**This repo:**

- Helper inventory: `find_repo_root`, `init_session`/`Session`, `save_dataframe`, `save_datacube`,
  `show`, `categorical_colors`/`CATEGORICAL`, `make_legend_clickable`, plus the CONUS404 set
  (`conus404_monthly_grid`, `zonal_by_huc8`, `water_year`, `mk_sen_trend`, `pixel_trend`). Candidate
  to grow into a shareable cross-project package.
- Per-notebook responsibilities and methods are described in [README § Approach](README.md#approach).

## Storage & data

- **Tabular** (Geo)DataFrames → **GeoParquet + a CSV copy** via `save_dataframe` (parquet is compact and
  typed — what notebooks read; the CSV, geometry as WKT, is for transparency).
- **Datacubes** (anything read natively with xarray) → **zarr v3 with an explicit `ZstdCodec`**
  (Icechunk-ready) via `save_datacube`, **never parquet** (parquet flattens away dims/coords/CRS/chunking).
- **Two cache layers, kept separate:** `cache/` (git-ignored) is the persistent **HTTP request
  cache** (sqlite; HyRiver + `async_retriever`) that makes re-runs fast; `data/` (committed) holds the
  curated **outputs** other notebooks read (written every run, not freshness-gated).
- **Git-ignored:** `cache/`, `data_temp/` (scratch/raw downloads), `.pixi/`, `_site/`, `.quarto/`.
  **Committed:** `data/` outputs, `pixi.lock`, and `_freeze/` (the render cache).

**This repo:**

- `data/hydrography/` — HyRiver/`pygeohydro` geometries (e.g. `huc8_watersheds`).
- `data/usgs_waterdata/` — `dataretrieval.waterdata` products (station inventory + time-series).
- `data/climate/` — CONUS404: the raw `conus404_monthly_grid.zarr` cube is **git-ignored** (~57 MB,
  regenerated from the cloud); the derived climatology/trend grids and water-year/trend tables are committed.
- `data/<source>/` — one folder per new source (TCEQ, NCEI, …).
- Plain `dataretrieval.waterdata` discovery calls use their own client and are **not** in `cache/`.

## Website (Quarto → GitHub Pages)

- **Config:** [`_quarto.yml`](_quarto.yml) (`cosmo` theme, `code-fold`, `execute-dir: file`,
  `freeze: auto`) + [`index.qmd`](index.qmd) landing page.
- **Freeze:** `pixi run render` **executes** the notebooks — that bakes the interactive
  HoloViews/GeoViews Bokeh embeds (`holoviews_exec`) into the static HTML — then freezes to
  **`_freeze/` (committed)**. **Re-render and leave `_freeze/` staged after editing a notebook.**
- **Render resolves paired notebooks via their `.py`** (the `render:` list targets `.py`;
  underscore-prefixed files like `_helpers.py` are ignored); **navbar `href`s point at the output
  `.html`**. `sandbox/` is excluded.
- **Refreshing committed `.ipynb` outputs:** neither `jupytext --sync` nor `pixi run render` updates
  the `.ipynb`'s stored outputs (what you see in the IDE / on GitHub). After changing code that
  affects displayed output, run the `nbconvert` command in [Commands](#commands), then render.

**This repo:** [`.github/workflows/publish.yml`](.github/workflows/publish.yml) renders and deploys on
every push to `main`; the render step gets the **`API_USGS_PAT`** repo secret so a freeze-miss CI
re-execution stays authenticated. Live at <https://limnotech.github.io/Thornforest/>.

## USGS WaterData APIs & discovery

Background and the migration rationale are in
[README § migration note](README.md#task-2-hydrological-and-water-quality-data-compilation-and-analysis).
Working notes for this repo:

- **Use `dataretrieval.waterdata`**, not `dataretrieval.nwis` (legacy) or WQP endpoints.
  Reference: [WaterData demo](https://doi-usgs.github.io/dataretrieval-python/examples/WaterData_demo.html).
- **Discovery:** `get_monitoring_locations()`, `get_time_series_metadata()`,
  `get_field_measurements_metadata()`, lookups `get_reference_table()`/`get_codes()`.
  **Fetch:** `get_daily()`, `get_continuous()`, `get_samples()`, `get_field_measurements()`.
- Each returns a `(dataframe, metadata)` tuple — a GeoDataFrame when geopandas is installed
  (`skip_geometry=True` drops coordinates). Query by `monitoring_location_id`, geography, USGS
  `parameter_code` (e.g. discharge `00060`), and date range. Specify **just enough** inputs —
  redundant geographic/parameter filters slow queries and can error.
- **The availability pattern (NB3):**
  - **Stations:** `get_monitoring_locations(bbox=[minlon,minlat,maxlon,maxlat])`, then `.set_crs(4326)`
    (it returns without one) and `geopandas.sjoin(predicate="within")` to the polygons. Use bbox +
    spatial filter, **not** `hydrologic_unit_code` (matches only the exact HUC, missing HUC12-tagged sites).
  - **daily / continuous** — both from `get_time_series_metadata(bbox=…)`, split on
    `computation_period_identifier` (`"Daily"` vs `"Points"`). **field** — `get_field_measurements_metadata(bbox=…)`.
  - **samples** — ⚠️ the area-wide samples *results* service **504-times-out** in dense regions and
    `get_samples(service="locations")` just mirrors the registry. The reliable signal is per-station
    `get_samples_summary(monitoringLocationIdentifier=<id>)` (non-empty = has samples) — one request per
    site, so it's the slow step (cache it).
  - Join availability back to stations on `monitoring_location_id`.

### The Mexico gap

The watersheds straddle the Rio Grande, but **every NHD product is US-only** and stops at the border
(~25.84°N at the river mouth) — verified for the HyRiver `nhdflowline_network` service, `pynhd.NHDPlusHR`,
and the EPA NHDPlus V2.1 VPU 13 download (`sandbox/explore_nhdplus_vpu13`). A **binational** stream
network needs a Mexico-capable source — **HydroRIVERS**, Mexico's **INEGI** Red Hidrográfica, or **OSM**
waterways. Until decided, the stream network is omitted. (CONUS404 climate in NB2 *does* cover the whole
area, since it's gridded model output rather than US-only gauges.)

## Gotchas (learned)

- **Tile maps:** set `frame_width` + `data_aspect=1` (don't also fix height) so basemap tiles aren't
  stretched — let height follow the data's true aspect.
- **Don't force a tile `min_zoom`** above the initial view to shrink labels — it breaks pan/zoom (tiles
  don't exist below the forced level). Choose the basemap/extent instead.
- **Toggle layers:** overlay one labeled layer per category, then a Bokeh hook
  `plot.state.legend.click_policy = "hide"` — static-HTML-safe, no Panel `embed` needed.

**This repo:**

- Basemap is `geoviews.tile_sources.EsriWorldTopo`.
- **EPA NHDPlus file-geodatabases** (sandbox): read via `s3fs(anon=True)` from
  `dmap-data-commons-ow/NHDPlusV21/…` → extract `.7z` with **`libarchive`** → `pyogrio.read_arrow`.
  `FType` is a numeric code (460 = StreamRiver); `StreamOrde` lives in `PlusFlowlineVAA` joined by
  **COMID**; geometries are 3D → `.geometry.force_2d()` before GeoViews can draw them.
