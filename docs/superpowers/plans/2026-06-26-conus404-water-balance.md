# Plan — Round 2: CONUS404 monthly climate (spatial patterns + water-balance trends)

Spec: `docs/superpowers/specs/2026-06-26-conus404-water-balance-design.md`
Branch: `round2-conus404` (off `main`; user reviews/commits/merges — agent never commits).

Design pivot (after exploration): **monthly** CONUS404 (not daily), keep the **gridded datacube**
for spatial analysis, store datacubes as **zarr v3** and tabular summaries as **parquet+CSV**.

## Task 1 — deps & helpers
- `pixi add exactextract pymannkendall` (done).
- `_helpers.py` additions:
  - `save_datacube(ds, zarr_path, level=3)` — zarr **v3** + explicit `ZstdCodec` (Icechunk-ready;
    clears inherited v2 numcodecs first).
  - `conus404_monthly_grid(watersheds, zarr_path, …)` — open monthly Zarr (OSN, anon), reproject,
    bbox-slice 11 vars, collapse SMOIS layer, retain `crs`, load-if-exists → `xr.Dataset`.
  - `zonal_by_huc8(grid_ds, watersheds, …)` — `xvec`/`exactextract` area-weighted zonal mean → tidy df.
  - `water_year(dates)`, `mk_sen_trend(series)`, `pixel_trend(annual_da)` (per-cell MK/Sen).

## Task 2 — gridded datacube
- Build `data/conus404/conus404_monthly_grid.zarr` (~57 MB, 540×43×78, zarr v3 Zstd). **Git-ignored.**
- Verify: dims, time 1979-10 → 2024-09, round-trips, codec = ZstdCodec.

## Task 3 — notebook `3_usgs_conus404_climate`
- Imports + `init_session`; watershed + variable table.
- Load cube (load-if-exists) + water_year coord.
- Per-watershed: zonal → water-year balance (sum fluxes / mean states; Q, P−ET−Q, °C) →
  `conus404_wateryear_by_huc8.{parquet,csv}`; long-term means table.
- Per-watershed trends (`mk_sen_trend`) → `conus404_trends_by_huc8.{parquet,csv}`.
- Per-cell: climatology + per-cell trends → `conus404_climatology_grid.zarr`,
  `conus404_trends_grid.zarr` (datacubes).
- Maps: reproject to EPSG:4326, tiled quadmesh + watershed outlines (climatology sequential;
  trends diverging). Charts: water-year P/ET/Q, temperature, Sen's-slope bars.

## Task 4 — execute, wire into site, docs
- `jupytext --sync` + `nbconvert --execute --inplace` (loads cube → fast).  [done]
- Navbar entry "3 · CONUS404 climate" (`notebooks/*.py` already in render list).  [done]
- `pixi run render`; confirm embeds/maps + `_freeze/`.
- Update `CLAUDE.md` + `README.md` (NB3, data/conus404 products, zarr-v3/parquet convention,
  git-ignored raw cube, deps).

## Task 5 — review & handoff
- Code-review subagent on `git diff main`.
- Leave on `round2-conus404`; status summary. **No commits/merges** (user does these).

## Verification checklist
- [x] gridded cube zarr v3 + Zstd; round-trips
- [x] water-year / trends parquet+CSV; climatology/trends zarr written
- [x] notebook executes from cube without error
- [ ] site renders; maps + charts interactive; `_freeze/` committed
- [ ] docs updated; branch clean for user review
