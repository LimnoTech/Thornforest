# Round 3 — Notebook rename/reorder, USGS WaterData time-series fetch, home-page cards & plot display fixes

**Date:** 2026-06-30

**Status:** Draft for review

**Scope:** Four cohesive changes across the notebook site:

1. **Rename & reorder** the three notebooks (and two data folders), preserving git history.
2. **Fetch the actual USGS time-series records** (daily values, discrete samples, field
   measurements) in the renamed `3_usgs_waterdata`, saved as tidy parquet+CSV products with a
   data-availability summary.
3. **Home page:** show all three notebooks as cards in the new order (adds the climate card).
4. **Plot display fixes:** all plots single-column, fit the content column including the toolbar
   (no horizontal scroll), scroll-zoom off by default — centralized in `_helpers.py`.

## Context & goal

Rounds 1–2 produced three notebooks. Their current names/order and what this round changes:

| New pos | New name | Was | Data folder (old → new) |
|---|---|---|---|
| 1 | `1_usgs_hydrography` | `1_usgs_hydrofabric` | `data/spatial` → **`data/hydrography`** |
| 2 | `2_usgs_climate` | `3_usgs_conus404_climate` | `data/conus404` → **`data/climate`** |
| 3 | `3_usgs_waterdata` | `2_usgs_waterdata` | `data/usgs_waterdata` (unchanged) |

The reorder swaps the climate and waterdata notebooks into positions 2 and 3. This is **safe**:
both the climate and waterdata notebooks read only the HUC-8 boundaries produced by the
hydrography notebook (position 1) and are independent of each other, so neither depends on the
other's order.

The waterdata notebook so far only builds the station/parameter **inventory** (291 stations, 86
with data: 10 daily, 28 continuous, 15 field, 64 samples). What's missing is the **actual
records** — this round fetches them. The three target data types all come from the **same USGS
Water Data Services**, so the fetch is added to the (renamed) waterdata notebook, not a new one.
`dataretrieval.waterdata` provides exactly the needed functions: `get_daily`, `get_samples`,
`get_field_measurements`. Continuous/instantaneous (~15-min) data is **deferred** — 25 yrs × 28
stations is millions of rows and is typically aggregated to daily for trend work.

**Full record, not just 25 years.** We fetch the **entire available period** for each priority
parameter, not just 2000–2025. The current American Forests Task 2 deliverable analyzes the last
25 years, but we will **eventually want to analyze the full record** (longer baselines), and we
don't want that to be re-fetch-bound. Downstream analysis subsets to the study window; the saved
products keep everything.

## Decisions (resolved with user)

1. **Rename & reorder:** per the table above. **All renames use `git mv`** (notebook `.py` + `.ipynb`
   files and the tracked data files) to preserve git history.
2. **CONUS404 file names unchanged:** only the *folder* moves `data/conus404` → `data/climate`; the
   `conus404_*` file-name prefixes stay (confirmed — the data genuinely is CONUS404).
3. **Fetch placement:** extend the renamed **`3_usgs_waterdata`** — same USGS Water Data Services.
   No new notebook.
4. **Data types:** **daily values, discrete samples, field measurements**. Continuous deferred.
5. **Parameter scope:** the **11 priority parameter groups** already defined in the notebook (codes
   for daily/field; WQ characteristic patterns for samples).
6. **Time window:** **full available record** (not clipped to 2000–2025). Analysis subsets later.
7. **Storage shape:** **one tidy (long-format) file per data type**, parquet + CSV, in
   `data/usgs_waterdata/`.
8. **Display:** **availability summary + one sample time-series plot**. Heavy trend / pre-post
   analysis stays in the future display/analyze notebooks.
9. **Home page:** all three notebooks as cards in the new order (three-column row).
10. **Plot display:** all plots **single-column, fit the content column including the toolbar**
    (no side-scroll); **scroll-zoom (`wheel_zoom`) off by default**. Centralized in `_helpers.py`.

## Architecture & file layout

```text
notebooks/
  _helpers.py                       + PLOT_WIDTH constant, set_plot_defaults() (called by init_session);
                                      save_outputs() generalized to plain DataFrames (no geometry)
  1_usgs_hydrography.{py,ipynb}     renamed from 1_usgs_hydrofabric; writes data/hydrography/
  2_usgs_climate.{py,ipynb}         renamed from 3_usgs_conus404_climate; reads data/hydrography/, writes data/climate/
  3_usgs_waterdata.{py,ipynb}       renamed from 2_usgs_waterdata; reads data/hydrography/;
                                      + Steps 7-10: fetch daily / samples / field, then availability summary
data/
  hydrography/                      renamed from data/spatial/ (git mv huc8_watersheds.{parquet,csv})
  climate/                          renamed from data/conus404/ (git mv tracked products; keep conus404_* names)
  usgs_waterdata/                   + usgs_daily_values, usgs_samples, usgs_field_measurements (.parquet+.csv)
index.qmd                           three cards in new order (g-col-md-4)
_quarto.yml                         navbar hrefs/labels/order updated to new names
.gitignore                          /data/conus404/...zarr → /data/climate/...zarr
CLAUDE.md, README.md                prose + data-layout references updated
docs/superpowers/specs/             this spec
```

Render uses the `notebooks/*.py` glob, so renamed files are picked up automatically; only the
navbar's explicit hrefs/labels/order need editing. The historical specs/plans under
`docs/superpowers/` are records of past rounds and are **left unchanged**.

**Data flow.** The hydrography notebook writes `data/hydrography/huc8_watersheds.{parquet,csv}`. The
climate and waterdata notebooks each **read** that file (path updated to `data/hydrography/`). The
new fetch steps tag results with `priority_group` and `huc8` from the inventory and save. Requests
reuse the existing on-disk `cache/` (week-long expiry).

## Component design

### 0. Notebook rename & reorder (do this first)

`git mv` each notebook pair and the tracked data products, then update every reference:

- **Notebook files:** `git mv` `1_usgs_hydrofabric.{py,ipynb}` → `1_usgs_hydrography.*`;
  `3_usgs_conus404_climate.{py,ipynb}` → `2_usgs_climate.*`; `2_usgs_waterdata.{py,ipynb}` →
  `3_usgs_waterdata.*`. Keep the jupytext `.py`/`.ipynb` pairing intact.
- **Data folders:** `git mv data/spatial data/hydrography`; `git mv data/conus404 data/climate`
  (tracked products only — the git-ignored `conus404_monthly_grid.zarr` is regenerated).
- **In-notebook paths:** `S.data_dir / "spatial"` → `"hydrography"` (hydrography write +
  climate/waterdata reads); the five `S.data_dir / "conus404"` in the climate notebook → `"climate"`.
- **`_quarto.yml` navbar:** update the three hrefs, labels, and order →
  `1 · Hydrography`, `2 · Climate`, `3 · WaterData`.
- **`.gitignore`:** `/data/conus404/conus404_monthly_grid.zarr/` → `/data/climate/...`.
- **`CLAUDE.md` / `README.md`:** update notebook names, the new order, and the `data/spatial` →
  `data/hydrography` and `data/conus404` → `data/climate` layout references.
- **Stale freeze:** remove `_freeze/notebooks/<old-name>/` dirs; re-render regenerates them.

Do the rename/reorder **before** the fetch work so the new steps land in the already-renamed file.

### 1. Fetch steps (`3_usgs_waterdata`, Steps 7–9)

- **Step 7 — Daily values** (`waterdata.get_daily`): the ~10 daily stations, filtered to priority
  `parameter_code`s (discharge, water level, and any daily WQ). Full period.
- **Step 8 — Discrete samples** (`waterdata.get_samples`): the ~64 sample stations, filtered by the
  priority **WQ characteristic** patterns (the samples service keys on characteristic names, not
  parameter codes — reuse the `characteristics` patterns already in the notebook's `PRIORITY_PARAMETERS`).
- **Step 9 — Field measurements** (`waterdata.get_field_measurements`): the ~15 field stations,
  filtered to priority `parameter_code`s.

Each fetch reuses the notebook's `classify_parameter` to tag every returned row with its
`priority_group`.

### 2. Storage layout — one tidy file per data type

All long-format, saved via the generalized `save_outputs` (parquet + CSV) to `data/usgs_waterdata/`:

| File | One row = | Key columns |
|---|---|---|
| `usgs_daily_values` | station × date × parameter | `monitoring_location_id`, `date`, `parameter_code`, `parameter_name`, `statistic`, `value`, `unit`, `approval/qualifier`, `priority_group`, `huc8` |
| `usgs_samples` | station × datetime × characteristic | `monitoring_location_id`, `datetime`, `characteristic`, `value`, `unit`, `fraction`, `detection_condition`, lab metadata, `priority_group`, `huc8` |
| `usgs_field_measurements` | station × datetime × parameter | `monitoring_location_id`, `datetime`, `parameter_code`, `parameter_name`, `value`, `unit`, `priority_group`, `huc8` |

Exact source columns are mapped to these during implementation (verified against live API
responses). `priority_group` and `huc8` are joined from the inventory so downstream analysis
filters without re-deriving.

### 3. `save_outputs` generalization (`_helpers.py`)

Today `save_outputs(gdf, parquet_path)` assumes a GeoDataFrame (`gdf.geometry.name`). Generalize it
to accept a plain **pandas `DataFrame`** too:

- **GeoDataFrame (has geometry):** unchanged — write **GeoParquet** + a CSV copy with geometry as
  WKT, geometry column moved to the end.
- **Plain DataFrame (no geometry):** save as a **pandas DataFrame** — standard `DataFrame.to_parquet`
  (a regular, non-Geo parquet) + `to_csv`, with no geometry-column reordering and no WKT.

Detect the case by checking whether the input is a GeoDataFrame / has a geometry column. One helper
serves both the spatial inventory and the new non-spatial time-series tables.

### 4. Availability display (`3_usgs_waterdata`, Step 10)

- **Coverage table** per data type: record count + first/last date per station × priority group
  (rendered with `show()`).
- **Data-availability heatmap** (HoloViews): station vs. time, marking where records exist — a
  visual check on the multi-decade span.
- **One illustrative time-series plot** (e.g. daily discharge at the main Rio Grande gauge).

### 5. Home-page cards (`index.qmd`)

Show all three notebooks as cards in the **new order** — `1 · Hydrography`, `2 · Climate`,
`3 · WaterData stations`. This updates the two existing cards (rename + reorder) and **adds the
climate card**. Change `g-col-md-6` → `g-col-md-4` so all three sit in one row.

**Link-target fix:** the existing cards link to the raw `notebooks/<name>.ipynb` files (which the
browser serves as source, not the rendered page). Change all card links to the rendered
**`.html`** pages — `notebooks/1_usgs_hydrography.html`, `notebooks/2_usgs_climate.html`,
`notebooks/3_usgs_waterdata.html` — matching the navbar.

### 6. Cross-cutting plot display fixes

Root cause: the hydrography/waterdata maps set `frame_width` 800–850 plus a side toolbar,
overflowing the cosmo content column (~700px, TOC on the right) → horizontal scroll; they also set
`active_tools=["wheel_zoom"]`, making scroll-zoom active; the climate notebook lays out maps
`.cols(2)`.

Centralize the fix in `_helpers.py`:

- Add a **`PLOT_WIDTH`** constant and a **`set_plot_defaults()`** function (called from
  `init_session()`) that applies `hv.opts.defaults(...)` across the element/overlay/layout types in
  use: a frame width tuned to **fit the content column including the toolbar** (no side-scroll), and
  an **`active_tools` list that excludes `wheel_zoom`** so scroll-zoom is off by default (the
  wheel-zoom button remains available in the toolbar, just inactive).
- Refactor the hydrography (`frame_width=850`), waterdata (`frame_width=800`), and climate
  (380/720/760) notebooks to drop hard-coded widths and inherit the shared default.
- Convert all multi-column layouts to **single column**: the climate notebook's two `.cols(2)` → `.cols(1)`.
- Remove `active_tools=["wheel_zoom"]` from the hydrography/waterdata notebooks (inherit the default).

The exact `PLOT_WIDTH` px is tuned during implementation by rendering and confirming no horizontal
scroll on the published pages (maps with right-side legends/colorbars are the binding case).

## Testing / verification

- After the rename: `pixi run render` builds with the new names; navbar shows
  `1 · Hydrography`, `2 · Climate`, `3 · WaterData`; no orphaned `_freeze` dirs leak into `_site`;
  the climate and waterdata notebooks read boundaries from `data/hydrography/` without error.
- Re-run the waterdata notebook end-to-end: the three new products appear in `data/usgs_waterdata/`
  (parquet + CSV), with non-zero rows spanning multiple decades; `priority_group`/`huc8` populated;
  row counts reconcile with the inventory's per-data-type station counts.
- **Manually confirm** no horizontal scroll on all three notebook pages, and that scrolling the
  mouse wheel over a plot does **not** zoom by default.
- Home page shows three notebook cards in one row, all links resolve.

## Out of scope (this round)

- Continuous/instantaneous data fetch.
- Trend analysis, normalized trends, pre/post-restoration comparisons, the Excel deliverable
  (the future display/analyze notebooks).
- New sources (TCEQ, NCEI, TWDB, IBWC) and the binational stream network.
- Renaming the `conus404_*` data files or the `data/usgs_waterdata/` folder.
