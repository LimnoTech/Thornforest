# Round 1 — USGS notebooks split, shared helpers, branding & parameter discovery

**Date:** 2026-06-11

**Status:** Draft for review

**Scope:** Refactor of the existing `1_usgs_hydrography_waterdata` notebook plus LimnoTech branding and a parameter-level reshape of the station discovery, and re-enabling the published site.

## Context & goal

`notebooks/1_usgs_hydrography_waterdata` currently does everything in one notebook: watershed boundaries → map → station discovery → data-type flags → map. This round (a) splits it into two focused notebooks, (b) moves reusable setup/colors/utilities into `_helpers.py`, (c) applies the LimnoTech brand to the Quarto site (with colorcet for data colors), (d) reshapes station discovery to record **which priority parameters** each station measured, and (e) re-enables GitHub Pages publishing now that the repo is public (the client wants site access).

## Decisions (resolved with user)

1. Parameter representation: **one boolean column per priority group + a `parameters` list column**.
2. Step 7 map: **toggle by priority parameter**; **keep** the 4 data-type flags as summary columns.
3. Session setup: **`init_session()` function** returning a config object.
4. Publishing: **include GitHub Pages this round**.
5. Data colors: **colorcet `glasbey_category10`** via a generic `categorical_colors()` helper.
6. Branding: **Quarto `_brand.yml`** (palette + Roboto), not hand-written SCSS.

## Architecture & file layout

```text
notebooks/
  _helpers.py                       shared: init_session(), colors, save_outputs, show, find_repo_root
  1_usgs_hydrofabric.{py,ipynb}     Steps 1-4: boundaries + map  -> data/spatial/
  2_usgs_waterdata.{py,ipynb}       Steps 5+: stations, parameters, maps -> data/usgs_waterdata/
_brand.yml                          LimnoTech site theme (colors + Roboto)
.github/workflows/publish.yml       GitHub Pages deploy (re-enabled)
docs/superpowers/specs/             this spec
```

**Data flow.** NB1 writes `data/spatial/huc8_watersheds.{parquet,csv}`. NB2 **reads** that file to get the bbox and run the spatial join — it does not re-fetch boundaries. Both notebooks `from _helpers import …`. The HTTP request cache (`cache/`) and the API key (`.env`) are shared.

## Component design

### 1. Notebook split (Item 7)

- **`1_usgs_hydrofabric`** — Steps 1-4 (imports, `init_session()`, name watersheds, download boundaries, map). Name leaves room to add the stream network / NHD hydrofabric later.
- **`2_usgs_waterdata`** — Steps 5+ (read boundaries → discover stations → parameter inventory → maps). Reads `data/spatial/huc8_watersheds.parquet`; if missing, prints a clear "run NB1 first".
- Rename the current `1_usgs_hydrography_waterdata.{py,ipynb}` accordingly; delete the old pair.

### 2. Imports at top (Item 1)

Each notebook has a single import block at the very top (stdlib, third-party, then `from _helpers import …`). Only *config/state* stays in the setup cell: `cfg = init_session()` and `gv.extension("bokeh")`.

### 3. Shared `_helpers.py` (Items 2, 4)

- **`init_session()`** — loads `.env` (repo-root), sets `HYRIVER_CACHE_NAME`/`HYRIVER_CACHE_EXPIRE`, and returns a small config object (a `dataclass`) with: `REPO_ROOT`, `DATA_DIR`, `CACHE_FILE`, `CACHE_EXPIRE_SECONDS`, `API_KEY`, `API_HEADERS`. Prints whether a key was found.
- **Colors** — `import colorcet as cc`; expose `CATEGORICAL = cc.glasbey_category10` and a helper `categorical_colors(keys) -> dict` mapping a list of category keys → hex colors (cycling the palette). A continuous default (e.g. `cc.CET_L*` / `cc.fire`) is reserved for future use. Notebooks call `categorical_colors([...])`; `_helpers` holds no project-specific category lists.
- **Existing** `find_repo_root`, `save_outputs`, `show` stay (used by both notebooks).
- The Bokeh `make_legend_clickable` hook moves to `_helpers` (reused by both maps).

### 4. Branding (Item 3) + figures

- **`_brand.yml`** (Quarto-native): `color.palette` = Limno Navy `#174A7C`, Limno Blue `#56A0D3`, Limno Lime `#8DC63F`, plus secondary Aqua/Sky/Yellow and the greys; map `primary` → Navy. `typography` base/headings = **Roboto** (Google font; Quarto fetches it). Keep `cosmo` as the base theme in `_quarto.yml`; `_brand.yml` overrides palette/fonts.
- **Figures color *data* with colorcet, never the brand** — watershed fills, station points, and the per-parameter layers all draw from `categorical_colors(...)`.

### 5. Parameter discovery (Items 5, 6) — reshape of Steps 6-7 in NB2

- **Priority groups** (from README): `conductivity, temperature, dissolved_oxygen, dissolved_solids, chlorophyll, pH, nitrogen, phosphorus, turbidity`.
- **Priority map** defined in **NB2** (project-specific config — `_helpers` stays generic/cross-project; a generic code→group *mapping function* may live in `_helpers`, but the priority list itself does not): each group → {USGS pcodes, WQX characteristic-name patterns}. Starting map (validated during implementation against `get_reference_table("parameter-codes")` and the characteristics actually present locally):

  | Group | Representative pcodes | WQX characteristic patterns |
  | --- | --- | --- |
  | conductivity | 00095, 90095 | "Specific conductance", "Conductivity" |
  | temperature | 00010 | "Temperature, water" |
  | dissolved_oxygen | 00300, 00301 | "Dissolved oxygen" |
  | dissolved_solids | 70300, 00515 | "Total dissolved solids" |
  | chlorophyll | 32209, 32210, 32211, 70953 | "Chlorophyll", "algae" |
  | pH | 00400 | "pH" |
  | nitrogen | 00600, 00605, 00608, 00613, 00615, 00618, 00620, 00625, 00630 | "Nitrogen", "Nitrate", "Nitrite", "Ammonia", "Kjeldahl" |
  | phosphorus | 00650, 00665, 00666, 00671 | "Phosphorus", "Orthophosphate" |
  | turbidity | 00076, 63675, 63676, 63680 | "Turbidity" |

- **Gather measured parameters per station** from three sources, then map each to a priority group:
  - `get_time_series_metadata(bbox)` → `parameter_code` per `monitoring_location_id` (daily & continuous).
  - `get_field_measurements_metadata(bbox)` → `parameter_code` per station.
  - `get_samples_summary(<id>)` per station (concurrent via `async_retriever`) → `characteristic` rows.
- **Enrich** pcodes via `get_reference_table("parameter-codes")` (`parameter_name`, `parameter_group_code`, `unit_of_measure`) so the `parameters` list column is human-readable and N/P roll-ups can lean on `parameter_group_code`.
- **Summary dataframe** (saved to `data/usgs_waterdata/`): the station attributes + the 4 data-type boolean flags (kept) + **one boolean column per priority group** + a **`parameters`** list column of all measured parameter names. Geometry last (per `save_outputs`).

### 6. Maps in NB2 (Item 6 / Step 7)

- **Stations-by-parameter map:** one `gv.Points` layer per priority group (colors from `categorical_colors`), legend `click_policy="hide"` to toggle each parameter on/off. Watershed outlines + Esri World Topo basemap underneath, `data_aspect=1`.
- The data-type flags remain as columns (useful for the later fetch notebooks) but are not the map.

### 7. Publishing (re-enabled)

- Add `.github/workflows/publish.yml` (mirrors `soil-health-hydraulics`): pixi setup → `pixi run render` → non-fatal freeze-staleness warning → upload → deploy. The render step gets `env: API_USGS_PAT: ${{ secrets.API_USGS_PAT }}` so a freeze-miss re-execution stays authenticated.
- Add NB2 to the `_quarto.yml` navbar; the `notebooks/*.py` render glob already covers both notebooks (and ignores `_helpers.py`).
- **Manual steps (user, in GitHub):** add the `API_USGS_PAT` repository secret; set Settings → Pages → Source → GitHub Actions.

## Outputs written

- `data/spatial/huc8_watersheds.{parquet,csv}` (NB1)
- `data/usgs_waterdata/usgs_monitoring_locations.{parquet,csv}` (NB2, stations within watersheds)
- `data/usgs_waterdata/usgs_monitoring_locations_parameters.{parquet,csv}` (NB2, stations + data-type flags + per-priority-group booleans + `parameters` list)

## Verification

- Both notebooks execute clean via `nbconvert --execute`; `pixi run render` builds `_site/` with live interactive embeds and scrollable tables; `_freeze/` refreshed and committed.
- Spot-check the parameter mapping: confirm known stations (e.g. a Rio Grande gauge) light up the expected priority groups; confirm counts are non-trivial for conductivity/temperature/DO.
- Confirm `_brand.yml` applies Roboto + LimnoTech palette to the site chrome while figures stay colorcet.

## Out of scope (future rounds)

- Fetching the actual records (daily/continuous/samples time series) — later notebooks.
- Precipitation (NOAA NCEI) and the Mexico-side / binational hydrography.
- TCEQ / TWDB / IBWC sources and the final Excel deliverable.

## Conventions

- Commits are made manually by the user in GitHub Desktop — this spec is written but **not** committed by the agent.
- Both `.py` and `.ipynb` stay in sync via jupytext; re-execute notebooks after code changes so the committed `.ipynb` outputs match (then `pixi run render`).
