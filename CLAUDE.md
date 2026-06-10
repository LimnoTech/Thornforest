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

**Status: greenfield.** As of this writing the repo contains only the README, LICENSE, and the
pixi environment — no notebooks, modules, or data-fetch code yet. The dependency list in
[pixi.toml](pixi.toml) is the clearest statement of the *intended* technical approach (below).
When you add the first code, also document the emerging structure here.

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

**Notebook 1 (`1_usgs_hydrography_waterdata`)** establishes the spatial foundation — HUC-8 boundaries
**and** the stream network via HyRiver `pynhd` (saved to `data/spatial/`) — then **begins data
discovery** with the new `dataretrieval.waterdata` module. (User will provide further build details.)

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

## Environment & commands

Environment is managed by **pixi** ([pixi.toml](pixi.toml)); never use bare `pip`/`conda`.

```bash
pixi install              # create/refresh the env from pixi.lock
pixi run jupyter lab      # work interactively (no custom [tasks] are defined yet)
```

There is no test suite, linter, or build step configured yet. If you add reusable tasks (fetch,
render, lint), define them under `[tasks]` in `pixi.toml` so they're discoverable here.

## Intended stack (what the dependencies imply)

The pinned deps signal the planned architecture — useful context before any code exists:

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

## Conventions

- **Commits are made manually by the user in GitHub Desktop — do not run `git commit`.** Make and
  verify the file changes; leave staging/committing to the user.
- **Paired notebooks (jupytext):** commit a diff-friendly `.py` alongside each `.ipynb`; keep them in
  sync with `pixi run jupytext --sync <name>.py`. The `.py` is the source to review/commit.
- **Saved data** goes in `data/` (Parquet timeseries per source; GeoParquet in `data/spatial/`) — see
  Planned structure above.
- `.pixi/` is git-ignored; commit `pixi.lock` so the environment is reproducible.
- The `.gitignore` is the standard GitHub Python template (plus `.pixi`); large/raw data files are
  **not** yet covered by a deliberate pattern — decide whether `data/` (or just raw pulls) is committed
  or ignored before pulling 25 years of records into the repo.
