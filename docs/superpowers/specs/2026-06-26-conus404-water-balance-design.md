# Round 2 — CONUS404 monthly climate: spatial patterns & water-balance trends per HUC-8

**Date:** 2026-06-26

**Status:** Draft for review (revised after exploration)

**Scope:** A new notebook `3_usgs_conus404_climate` that fetches **monthly** CONUS404 climate
output for the three South-Texas HUC-8 watersheds across the full model record, keeps it as a
**gridded datacube** (for spatial-pattern analysis), and derives per-HUC-8 water-balance
statistics and long-term trends — both **per cell** (spatial maps of change) and **per watershed**
(tabular time series + trends).

## Context & goal

Round 1 produced the hydrofabric (NB1 → `data/spatial/huc8_watersheds.parquet`) and the USGS
station inventory (NB2). Round 2 adds the **climate forcing & water balance** layer the American
Forests Task 2 analysis needs, with two purposes: (1) a long-term per-watershed water balance, and
(2) **spatial patterns and how they change over time** across the area.

Source: **CONUS404** (NCAR/USGS 4-km hourly WRF reanalysis) at its **monthly** aggregation,
`s3://hytest/conus404/conus404_monthly.zarr` on the USGS OSN pod (anonymous S3, endpoint
`https://usgs.osn.mghpcc.org`; grid CRS = Lambert Conformal Conic via
`pyproj.CRS.from_cf(ds['crs'].attrs)`). It provides a physically closed land-surface water budget
on a common grid covering all three HUC-8s — including the Mexican portion of the Lower Rio
Grande that US-only NHD/NWQN products miss.

## Decisions (resolved with user)

1. **Placement:** a new notebook `3_usgs_conus404_climate`.
2. **Temporal resolution:** **monthly** (not daily) — the full gridded bbox cube is ~80 MB vs
   ~2.4 GB daily, small enough to keep the spatial grid. Record: 540 months, WY1980–2024.
   Monthly `AC*` values are **monthly accumulations** (units mm) — sum 12 → water-year total.
3. **Keep the gridded datacube** for spatial analysis (do not reduce to zonal means only).
4. **Storage convention (locked):** xarray **datacubes → zarr**; tabular DataFrames →
   **parquet (+CSV)**. Never parquet for raster/datacube data.
5. **Analysis scope:** **both** — per-cell climatology + per-cell trend maps (spatial change),
   **and** per-HUC-8 water-year balance + trend tables.
6. **Raw grid storage:** **git-ignore** `conus404_monthly_grid.zarr` (~80 MB) and regenerate from
   OSN; commit only the small derived products + the Quarto `_freeze/` cache.
7. **Variables (11):** fluxes (mm) `PREC_ACC_NC`, `ACETLSM`, `ACRUNSB`, `ACRUNSF`, `RECH`;
   storage states `SMOIS` (surface soil layer, m³/m³), `SNOW` (SWE, kg/m²≈mm), `CANWAT` (mm);
   forcing `T2`, `TD2` (K→°C in summaries), `Q2` (kg/kg). `SMOIS` is 4-D → surface layer.
8. **Trends:** Mann–Kendall + Sen's slope (`pymannkendall`) on water-year series — per cell and
   per HUC-8.

## Architecture & file layout

```text
notebooks/
  3_usgs_conus404_climate.{py,ipynb}   monthly cube → spatial maps + per-HUC-8 balance/trends
  _helpers.py                          + CONUS404 datacube / zonal / trend helpers (shared)
data/conus404/
  conus404_monthly_grid.zarr               GRIDDED monthly bbox cube (datacube)  [GIT-IGNORED, ~80 MB]
  conus404_climatology_grid.zarr           per-cell mean-annual P/ET/T … (datacube)  [committed, tiny]
  conus404_trends_grid.zarr                per-cell Sen's slope + p per term (datacube) [committed, tiny]
  conus404_wateryear_by_huc8.{parquet,csv} per-HUC-8 water-year balance (tabular)  [committed]
  conus404_trends_by_huc8.{parquet,csv}    per-HUC-8 Mann–Kendall + Sen's slope (tabular) [committed]
```

**Data flow.** Read NB1 watersheds → open monthly Zarr → reproject watersheds to grid CRS →
bbox-slice the 11 vars (78×43 cells) → **save gridded cube to zarr** (load-if-exists). From the
local cube: (a) `xvec` zonal mean → per-HUC-8 monthly → water-year balance (parquet); (b) per-cell
water-year aggregation → climatology + per-cell Mann–Kendall/Sen trends (zarr); (c) figures.

### Caching

The gridded cube uses **load-if-exists** on the zarr path: present → `xr.open_zarr` (fast); absent →
fetch+slice from OSN and write. Because it is git-ignored, a CI/site render on a `_freeze/` miss
re-pulls ~80 MB monthly from OSN (feasible) and re-derives; on a freeze hit, nothing re-executes.
Derived products (small zarrs + parquet/CSV) are committed.

### Spatial products (the new centerpiece)

- **Climatology grid** (`conus404_climatology_grid.zarr`): per-cell mean annual precipitation, ET,
  runoff, recharge (mm/yr) and mean temperature (°C) over the full record.
- **Trend grid** (`conus404_trends_grid.zarr`): per-cell Sen's slope (per year) + Mann–Kendall
  p-value for each water-year term — i.e. *where* the area is getting wetter/drier/warmer.
- **Maps:** reproject to EPSG:4326 for tiled GeoViews/hvplot quadmesh maps over the watershed
  outlines (diverging colormap for trends, sequential for climatology).

### Per-HUC-8 water balance & trends (tabular)

`xvec`/`exactextract` area-weighted zonal mean of the cube → monthly per-HUC-8 → water-year totals
(fluxes) / means (states); `Q = surface + subsurface runoff`; balance `P − ET − Q` (residual ≈
Δstorage + recharge); T2/TD2 → °C. Mann–Kendall + Sen's slope per term × HUC-8.

### Figures (interactive; embeds preserved by Quarto execute + `_freeze/`)

1. Spatial **climatology** maps (mean annual P, ET, T).
2. Spatial **trend** maps (Sen's slope per cell — P, T, …) with diverging colormap.
3. Per-HUC-8 **water-year P/ET/Q** time series + mean-temperature series (clickable legend).
4. Per-HUC-8 **trend bars** (Sen's slope, MK significance on hover).

Data colors via `categorical_colors(...)`; brand reserved for site chrome. Scrollable tables via `show`.

## Shared helpers added to `_helpers.py`

- `conus404_monthly_grid(watersheds, zarr_path, variables=CONUS404_VARS, verbose=True)` — open
  monthly Zarr, reproject, bbox-slice, collapse SMOIS layer, retain CRS; load-if-exists on
  `zarr_path`; returns an `xr.Dataset` (time, y, x).
- `zonal_by_huc8(grid_ds, watersheds, variables)` — `xvec` area-weighted zonal mean → tidy
  DataFrame (date, huc8, name, vars).
- `water_year(dates)` — calendar → water-year label.
- `mk_sen_trend(series)` — `pymannkendall` original test → {trend, p, slope, intercept, n}.
- `pixel_trend(annual_da, dim="water_year")` — per-cell Mann–Kendall/Sen via `apply_ufunc` →
  Dataset of `slope` + `p` grids.

## Non-goals (YAGNI)

- No daily or hourly CONUS404; no bias-correction/validation against gauges (future round).
- No full multi-layer soil-water budget (surface layer + residual closure only).

## Risks / constraints

- **Quarto embeds:** figures use `hvplot`/HoloViews/GeoViews with Quarto execution + `_freeze/`.
- **Reprojection for maps:** native grid is LCC; reproject the small bbox cube to EPSG:4326 for
  tiled maps (cheap at 78×43).
- **`exactextract` + `pymannkendall`** added to `pixi.toml` (conda-forge, all platforms).
