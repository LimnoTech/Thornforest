# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A data-compilation and analysis project for **American Forests' Thornforest project, Task 2**:
gather, organize, and analyze **25 years (2000–2025)** of publicly available precipitation,
streamflow, and water-quality data for three South Texas HUC-8 watersheds, then test whether
measurable changes in water quantity/quality correlate with the timing and location of restoration
activity. See [README.md](README.md) for the full scope.

**Status: greenfield.** As of this writing the repo contains only the README, LICENSE, and the
pixi environment — no notebooks, modules, or data-fetch code yet. The dependency list in
[pixi.toml](pixi.toml) is the clearest statement of the *intended* technical approach (below).
When you add the first code, also document the emerging structure here.

## Watersheds & target variables

Three HUC-8 watersheds:
- South Laguna Madre — `12110208`
- Los Olmos — `13090001`
- Lower Rio Grande — `13090002`

Water-quality parameters to compile where available: conductivity, temperature, dissolved oxygen,
dissolved solids, total algae/chlorophyll, pH, nitrogen & phosphorus species, turbidity — plus
precipitation and streamflow.

## Data sources (per README)

USGS NWIS (streamflow + WQ), EPA Water Quality Portal / STORET, Texas Commission on Environmental
Quality (TCEQ) Surface Water Quality Monitoring, Texas Water Development Board, International
Boundary and Water Commission (Rio Grande flow/allocation), NOAA NCEI (precipitation), and local
irrigation-district records. Each compiled record must carry complete source info (hyperlinks) and
metadata; the deliverable is a structured database (Excel or a format American Forests prefers).

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

- **Water-data retrieval:** `dataretrieval` (USGS NWIS) and the **HyRiver** suite (`pynhd`,
  `pygeoogc`, `hydrosignatures`) — fetch streamflow/WQ records and NHD/watershed geometries by HUC.
- **Geospatial:** `geopandas`, `gdal` + `libgdal-arrow-parquet`, `rioxarray`, `xarray`, `xvec`,
  `cfunits` — for station locations, raster/precip data, and unit handling. Station-to-restoration-
  site mapping (spatial relevance) is an explicit project goal.
- **Storage / remote access:** `pyarrow`, `zarr>=3`, `fsspec`/`s3fs`/`universal_pathlib` — Parquet/
  Zarr outputs and cloud-path access.
- **Visualization & notebooks:** `hvplot`, `geoviews`, `contextily`, JupyterLab, `jupyter_bokeh`,
  and `jupytext` — interactive maps/plots authored in notebooks.

## Conventions

- **Jupytext is installed** — if you adopt the paired-notebook workflow (commit a diff-friendly
  `.py` alongside each `.ipynb`), keep the pair in sync with `pixi run jupytext --sync <name>.py`.
- `.pixi/` is git-ignored; commit `pixi.lock` so the environment is reproducible.
- The `.gitignore` is the standard GitHub Python template (plus `.pixi`); large/raw data files are
  **not** yet covered by a deliberate pattern — decide on a data-directory convention (and whether
  raw data is committed) before pulling 25 years of records into the repo.
