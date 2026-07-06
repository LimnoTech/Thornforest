# Round 3 — Rename/reorder, USGS time-series fetch, home cards & plot fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename/reorder the three notebooks (+ two data folders), fetch the actual USGS daily/sample/field time-series in the renamed waterdata notebook, fix the home-page cards, and make all plots single-column / content-fitting / scroll-zoom-off.

**Architecture:** Jupytext-paired notebooks (`.py` is source → `--sync` regenerates `.ipynb`) sharing `notebooks/_helpers.py`, rendered to a Quarto site (`_freeze/` cache, GitHub Pages). The renamed `3_usgs_waterdata` reads the station inventory it already builds, fetches three USGS Water Data services with `dataretrieval.waterdata`, tags rows by priority group, and saves long-format parquet+CSV via a generalized `save_outputs`. Plot display defaults are centralized in `_helpers.set_plot_defaults()` called from `init_session()`.

**Tech Stack:** Python, pixi, `dataretrieval` (waterdata APIs), geopandas/pandas, HoloViews/GeoViews/hvplot (Bokeh), Quarto, jupytext.

## Global Constraints

- **Storage convention:** tabular → parquet **+ CSV** copy; never parquet for raster/datacube (zarr). Time-series tables are plain (non-geo) DataFrames.
- **`git mv` for ALL renames** (notebook `.py`+`.ipynb`, data folders, `_freeze/` dirs) — preserve history.
- **Full available record** — do NOT clip fetches to 2000–2025.
- **Priority parameters only** — the 11 groups in `PRIORITY_GROUPS` (the dict in the waterdata notebook).
- **Notebook source is the `.py`** — edit `.py`, then `jupytext --sync`, then execute the `.ipynb`.
- **CONUS404 file names keep the `conus404_` prefix**; only the folder becomes `data/climate/`.
- Run everything via `pixi run …`. Repo root: `/Users/aaufdenkampe/Documents/git_Limno/Thornforest`.
- Work on branch `round3-usgs-timeseries` (already created).

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `notebooks/1_usgs_hydrography.{py,ipynb}` | HUC-8 boundaries → map; writes `data/hydrography/` | renamed from `1_usgs_hydrofabric`; path + plot opts |
| `notebooks/2_usgs_climate.{py,ipynb}` | CONUS404 water balance; reads `data/hydrography/`, writes `data/climate/` | renamed from `3_usgs_conus404_climate`; paths + single-col plots |
| `notebooks/3_usgs_waterdata.{py,ipynb}` | Station inventory **+ time-series fetch + availability** | renamed from `2_usgs_waterdata`; +Steps 7–10; plot opts |
| `notebooks/_helpers.py` | Shared utilities | generalize `save_outputs`; add `PLOT_WIDTH` + `set_plot_defaults()` |
| `index.qmd` | Home page | 3 cards, new order, `.html` links, 3-col grid |
| `_quarto.yml` | Site config | navbar hrefs/labels/order |
| `.gitignore` | ignore rules | `data/conus404/…zarr` → `data/climate/…zarr` |
| `CLAUDE.md`, `README.md` | Docs | names, order, data-folder references |
| `data/hydrography/`, `data/climate/` | Saved products | renamed folders |

---

## Task 1: Rename & reorder notebooks, data folders, and all references

**Files:**
- Rename (git mv): `notebooks/1_usgs_hydrofabric.{py,ipynb}` → `1_usgs_hydrography.*`; `notebooks/3_usgs_conus404_climate.{py,ipynb}` → `2_usgs_climate.*`; `notebooks/2_usgs_waterdata.{py,ipynb}` → `3_usgs_waterdata.*`
- Rename (git mv): `data/spatial/` → `data/hydrography/`; `data/conus404/` → `data/climate/`; `_freeze/notebooks/<old>/` → `<new>/`
- Modify: the three notebook `.py` data-path strings; `_quarto.yml`; `.gitignore`; `CLAUDE.md`; `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: notebooks at their new paths reading `data/hydrography/huc8_watersheds.parquet` and (climate) writing `data/climate/`. Later tasks edit `3_usgs_waterdata.py` and `_helpers.py`.

- [ ] **Step 1: `git mv` the six notebook files**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git mv notebooks/1_usgs_hydrofabric.py   notebooks/1_usgs_hydrography.py
git mv notebooks/1_usgs_hydrofabric.ipynb notebooks/1_usgs_hydrography.ipynb
git mv notebooks/3_usgs_conus404_climate.py   notebooks/2_usgs_climate.py
git mv notebooks/3_usgs_conus404_climate.ipynb notebooks/2_usgs_climate.ipynb
git mv notebooks/2_usgs_waterdata.py   notebooks/3_usgs_waterdata.py
git mv notebooks/2_usgs_waterdata.ipynb notebooks/3_usgs_waterdata.ipynb
```

- [ ] **Step 2: `git mv` the data folders and freeze dirs**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git mv data/spatial data/hydrography
git mv data/conus404 data/climate
git mv _freeze/notebooks/1_usgs_hydrofabric      _freeze/notebooks/1_usgs_hydrography
git mv _freeze/notebooks/3_usgs_conus404_climate _freeze/notebooks/2_usgs_climate
git mv _freeze/notebooks/2_usgs_waterdata        _freeze/notebooks/3_usgs_waterdata
```

Note: `git mv` of a directory renames it on disk, so the git-ignored `data/climate/conus404_monthly_grid.zarr` cube moves along with it.

- [ ] **Step 3: Update data-path strings in the three notebook `.py` files**

In `notebooks/1_usgs_hydrography.py` — the save line:

```python
save_outputs(watersheds_gdf, S.data_dir / "hydrography" / "huc8_watersheds.parquet")
```

In `notebooks/2_usgs_climate.py` — the boundaries read + the five `conus404` writes. Change `"spatial"` → `"hydrography"` and every `"conus404"` → `"climate"`:

```python
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
grid_path = S.data_dir / "climate" / "conus404_monthly_grid.zarr"
wy_path = S.data_dir / "climate" / "conus404_wateryear_by_huc8.parquet"
trends_path = S.data_dir / "climate" / "conus404_trends_by_huc8.parquet"
save_datacube(climatology, S.data_dir / "climate" / "conus404_climatology_grid.zarr")
save_datacube(trend_grid, S.data_dir / "climate" / "conus404_trends_grid.zarr")
```

In `notebooks/3_usgs_waterdata.py` — the boundaries read (line ~57):

```python
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
```

Also update the "run notebook 1 first" message in `3_usgs_waterdata.py` to reference `1_usgs_hydrography`.

- [ ] **Step 4: Update `_quarto.yml` navbar (hrefs, labels, order)**

Replace the three `left:` notebook entries (keep `Home` first) with, in this order:

```yaml
      - href: notebooks/1_usgs_hydrography.html
        text: "1 · Hydrography"
      - href: notebooks/2_usgs_climate.html
        text: "2 · Climate"
      - href: notebooks/3_usgs_waterdata.html
        text: "3 · WaterData stations"
```

- [ ] **Step 5: Update `.gitignore`**

Change the CONUS404 cube ignore line:

```
/data/climate/conus404_monthly_grid.zarr/
```

- [ ] **Step 6: Update `CLAUDE.md` and `README.md` references**

Update all occurrences: `1_usgs_hydrofabric` → `1_usgs_hydrography`; `3_usgs_conus404_climate` → `2_usgs_climate`; `2_usgs_waterdata` → `3_usgs_waterdata`; `data/spatial` → `data/hydrography`; `data/conus404` → `data/climate`. Reflect the **new order** (1 Hydrography, 2 Climate, 3 WaterData) where the docs describe the notebook sequence. Leave the historical files under `docs/superpowers/plans/` and `docs/superpowers/specs/` unchanged. Verify none remain:

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git grep -nE "usgs_hydrofabric|usgs_conus404_climate|2_usgs_waterdata|data/spatial|data/conus404" -- CLAUDE.md README.md _quarto.yml .gitignore notebooks/
```
Expected: **no output** (all references updated).

- [ ] **Step 7: Re-render the site to verify**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run render 2>&1 | grep -iE "output created|error" | tail -5
ls _site/notebooks/*.html
```
Expected: `Output created`; `_site/notebooks/` contains `1_usgs_hydrography.html`, `2_usgs_climate.html`, `3_usgs_waterdata.html` (no old names). (The climate notebook may re-execute and re-download the CONUS404 cube — allow several minutes.)

- [ ] **Step 8: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add -A
git commit -m "Rename/reorder notebooks (hydrography, climate, waterdata) and data folders"
```

---

## Task 2: Generalize `save_outputs` for plain (non-geo) DataFrames

**Files:**
- Modify: `notebooks/_helpers.py` (the `save_outputs` function, ~line 32)
- Test: `notebooks/tests/test_save_outputs.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `save_outputs(df_or_gdf, parquet_path)` — accepts a `GeoDataFrame` (writes GeoParquet + WKT CSV, geometry last, as before) **or** a plain `pandas.DataFrame` (writes standard parquet + CSV, no geometry handling). Used by Task 4.

- [ ] **Step 1: Write the failing test**

Create `notebooks/tests/test_save_outputs.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import _helpers from notebooks/
from _helpers import save_outputs


def test_save_outputs_plain_dataframe(tmp_path):
    df = pd.DataFrame({"station": ["A", "B"], "value": [1.0, 2.0]})
    out = tmp_path / "sub" / "table.parquet"

    save_outputs(df, out)

    assert out.exists()
    assert out.with_suffix(".csv").exists()
    back = pd.read_parquet(out)
    pd.testing.assert_frame_equal(back, df)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -m pytest notebooks/tests/test_save_outputs.py -v
```
Expected: FAIL — `save_outputs` calls `gdf.geometry.name`, raising `AttributeError` on a plain DataFrame.

- [ ] **Step 3: Generalize the implementation**

Replace the body of `save_outputs` in `notebooks/_helpers.py` with:

```python
def save_outputs(df, parquet_path):
    """Save a (Geo)DataFrame two ways for transparency: parquet (compact, typed) + a CSV copy.

    - GeoDataFrame: GeoParquet + CSV with geometry written as WKT, geometry column moved to the
      end so the table reads cleanly in any software.
    - Plain pandas DataFrame (no geometry): a standard (non-Geo) parquet + CSV, columns unchanged.

    Side-effect helper — prints a confirmation and returns nothing (so it never accidentally
    renders a table when it is the last line of a notebook cell)."""
    has_geometry = getattr(df, "_geometry_column_name", None) is not None
    if has_geometry:
        name = df.geometry.name
        ordered = df[[c for c in df.columns if c != name] + [name]]
    else:
        ordered = df

    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_parquet(parquet_path)
    ordered.to_csv(parquet_path.with_suffix(".csv"), index=False)  # geometry -> WKT for GeoDataFrames

    try:
        shown = parquet_path.relative_to(find_repo_root())
    except ValueError:
        shown = parquet_path
    print(f"saved {len(ordered)} rows → {shown} (+ .csv)")
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -m pytest notebooks/tests/test_save_outputs.py -v
```
Expected: PASS.

- [ ] **Step 5: Confirm the GeoDataFrame path still works**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
import geopandas as gpd
import sys; sys.path.insert(0, 'notebooks')
from _helpers import save_outputs
g = gpd.read_parquet('data/hydrography/huc8_watersheds.parquet')
save_outputs(g, '/tmp/thorn_geo_check/huc8.parquet')
back = gpd.read_parquet('/tmp/thorn_geo_check/huc8.parquet')
assert back.geometry.name == g.geometry.name and len(back) == len(g)
print('geo OK', len(back))
"
```
Expected: `geo OK 3`.

- [ ] **Step 6: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add notebooks/_helpers.py notebooks/tests/test_save_outputs.py
git commit -m "Generalize save_outputs to plain (non-geo) DataFrames + test"
```

---

## Task 3: Centralize plot display defaults (single-column, content-fit, scroll-zoom off)

**Files:**
- Modify: `notebooks/_helpers.py` (add `PLOT_WIDTH` + `set_plot_defaults()`; call from `init_session()`)
- Modify: `notebooks/1_usgs_hydrography.py`, `notebooks/2_usgs_climate.py`, `notebooks/3_usgs_waterdata.py` (drop hard-coded widths / wheel_zoom; `.cols(2)` → `.cols(1)`)

**Interfaces:**
- Consumes: `init_session()` (Task 1 paths).
- Produces: `PLOT_WIDTH` (int) and `set_plot_defaults(width=PLOT_WIDTH)` in `_helpers`; `init_session()` calls it. After this task every plot inherits a content-fitting `frame_width` and `active_tools=["pan"]` (no `wheel_zoom`).

- [ ] **Step 1: Add `PLOT_WIDTH` and `set_plot_defaults()` to `_helpers.py`**

Add near the GeoViews/Bokeh helpers section:

```python
# --- Plot display defaults (shared by every notebook) -------------------------

PLOT_WIDTH = 600  # frame width (px) tuned to fit the Quarto cosmo content column incl. toolbar;
                  # see Task 3 verification — lower it (or widen body-width) if any page side-scrolls.


def set_plot_defaults(width=PLOT_WIDTH):
    """Project-wide HoloViews/Bokeh display defaults: a content-fitting frame width (so pages do
    not scroll sideways) and **scroll-zoom OFF by default** — pan is the active drag tool and
    wheel_zoom stays in the toolbar but inactive. Call AFTER the bokeh extension is loaded
    (e.g. gv.extension('bokeh'))."""
    import holoviews as hv

    hv.opts.defaults(
        hv.opts.Overlay(frame_width=width, active_tools=["pan"]),
        hv.opts.Points(frame_width=width, active_tools=["pan"]),
        hv.opts.Path(frame_width=width, active_tools=["pan"]),
        hv.opts.Polygons(frame_width=width, active_tools=["pan"]),
        hv.opts.Curve(frame_width=width, active_tools=["pan"]),
        hv.opts.QuadMesh(frame_width=width, active_tools=["pan"]),
        hv.opts.Image(frame_width=width, active_tools=["pan"]),
        hv.opts.HeatMap(frame_width=width, active_tools=["pan"]),
    )
```

- [ ] **Step 2: Call `set_plot_defaults()` from `init_session()`**

At the very end of `init_session()` in `_helpers.py`, immediately before `return Session(...)`, add:

```python
    set_plot_defaults()
```

- [ ] **Step 3: Strip per-plot overrides in `1_usgs_hydrography.py`**

In the `watersheds_map = watersheds_map.opts(...)` call, **remove** the `frame_width=850,` line and the `active_tools=["wheel_zoom"],` line (keep `data_aspect`, `title`, `legend_position`, `hooks`, etc.). The map now inherits `frame_width=PLOT_WIDTH` and pan-only tools.

- [ ] **Step 4: Strip per-plot overrides in `3_usgs_waterdata.py`**

In the `stations_param_map = stations_param_map.opts(...)` call (Step 7 map), **remove** the `frame_width=800,` line and the `active_tools=["wheel_zoom"],` line (keep `data_aspect`, `title`, `legend_position="right"`, `hooks`).

- [ ] **Step 5: Single-column layouts + strip widths in `2_usgs_climate.py`**

- Change `climatology_maps` `.cols(2)` → `.cols(1)` and `trend_maps` `.cols(2)` → `.cols(1)`.
- In `spatial_map()`, remove `frame_width=380,` from the `hvplot.quadmesh(...)` call (keep `data_aspect=1`, `clabel`, `title`, etc.) — maps inherit `PLOT_WIDTH`.
- In the `balance_fig` overlay opts, remove `frame_width=720,` (keep `frame_height=210`, `legend_position`, `hooks`). The `.cols(1)` there is already correct.
- In the seasonal/other figure opts, remove the `frame_width=720,` / `frame_width=760,` lines (keep their `frame_height` and other opts).

- [ ] **Step 6: Sync and re-render**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
pixi run jupytext --sync notebooks/1_usgs_hydrography.py
pixi run jupytext --sync notebooks/2_usgs_climate.py
pixi run jupytext --sync notebooks/3_usgs_waterdata.py
pixi run render 2>&1 | grep -iE "output created|error" | tail -5
```
Expected: `Output created`.

- [ ] **Step 7: Verify no horizontal scroll and scroll-zoom off**

Open each page and confirm visually:

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run preview
```
Check `1_usgs_hydrography`, `2_usgs_climate`, `3_usgs_waterdata`: (a) the page body does **not** scroll sideways (plots + toolbar fit the column); (b) the climate maps are stacked **one per row**; (c) scrolling the mouse wheel over a plot does **not** zoom (pan-drag works, wheel_zoom button is present but inactive). If any page still side-scrolls, lower `PLOT_WIDTH` in `_helpers.py` (e.g. 560/520) and re-render; if maps with right legends are the cause, that legend width adds to the column — reduce `PLOT_WIDTH` accordingly.

- [ ] **Step 8: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add notebooks/_helpers.py notebooks/*.py notebooks/*.ipynb _freeze/
git commit -m "Centralize plot defaults: single-column, content-fit width, scroll-zoom off"
```

---

## Task 4: Fetch the time-series (daily, samples, field) in `3_usgs_waterdata`

**Files:**
- Modify: `notebooks/3_usgs_waterdata.py` (imports; append Steps 7–9 **after** the existing Step 6 cells, before the Step-7 *map*; renumber the existing map/“What’s next” sections if needed so step labels stay monotonic)
- Produces: `data/usgs_waterdata/usgs_daily_values.{parquet,csv}`, `usgs_samples.{parquet,csv}`, `usgs_field_measurements.{parquet,csv}`

**Interfaces:**
- Consumes: `waterdata` (already imported), `save_outputs` (Task 2), `classify_parameter`, `PRIORITY_GROUPS`, `stations_in_area` (has boolean `daily`/`samples`/`field_measurements` flags + `huc8`), `parameter_name_by_code` — all already defined earlier in this notebook.
- Produces: DataFrames `daily`, `samples`, `field` and the three saved products consumed by Task 5.

> **Note on existing step numbers:** the notebook’s discovery map is currently labeled “Step 7”. Insert the fetch as Steps 7–9 *before* that map and relabel the map to **Step 11** (and availability becomes **Step 10**), or keep the map where it is and label fetch/availability as Steps 8–11 — pick whichever keeps the markdown headers in ascending order. The exact integers are cosmetic; the cells below are what matters.

- [ ] **Step 1: Add the availability/plot imports**

In the imports cell of `notebooks/3_usgs_waterdata.py`, add (next to the existing `import pandas as pd`):

```python
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the availability plots)
```

- [ ] **Step 2: Append the shared fetch setup cell**

After the Step 6 cells, append:

```python
# %% [markdown]
# ## Step 7 — Fetch the time-series records
#
# For the stations that actually have data, fetch the **full available record** of the **priority
# parameters** from three USGS Water Data services and save one tidy (long-format) table per data
# type. Daily values and field measurements filter by USGS `parameter_code`; discrete samples are
# keyed by characteristic name, so we fetch all and keep rows whose characteristic maps to a
# priority group. (Analysis later subsets to the 25-year study window — we keep everything.)

# %%
# All priority parameter codes, flattened, for the code-keyed services (daily, field).
PRIORITY_CODES = sorted({c for spec in PRIORITY_GROUPS.values() for c in spec["parameter_codes"]})

# Reusable lookups (built from the inventory in Step 6).
huc8_by_station = dict(zip(stations_in_area["monitoring_location_id"], stations_in_area["huc8"]))


def _parameter_name(code):
    code = str(code)
    return parameter_name_by_code.get(code.zfill(5), parameter_name_by_code.get(code, code))
```

- [ ] **Step 3: Append the daily-values fetch cell**

```python
# %% [markdown]
# ### Daily values
#
# Daily statistics (mostly discharge & water level) for the stations flagged `daily`.

# %%
daily_station_ids = stations_in_area.loc[stations_in_area["daily"], "monitoring_location_id"].tolist()
daily_raw, _ = waterdata.get_daily(
    monitoring_location_id=daily_station_ids,
    parameter_code=PRIORITY_CODES,
    skip_geometry=True,
)
daily = daily_raw.rename(columns={"time": "date", "statistic_id": "statistic", "unit_of_measure": "unit"})
daily["parameter_name"] = daily["parameter_code"].map(_parameter_name)
daily["priority_group"] = daily["parameter_code"].map(lambda c: classify_parameter(parameter_code=c))
daily["huc8"] = daily["monitoring_location_id"].map(huc8_by_station)
daily = (
    daily[
        ["monitoring_location_id", "date", "parameter_code", "parameter_name", "statistic",
         "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "parameter_code", "date"])
    .reset_index(drop=True)
)
save_outputs(daily, S.data_dir / "usgs_waterdata" / "usgs_daily_values.parquet")
```

- [ ] **Step 4: Append the discrete-samples fetch cell**

```python
# %% [markdown]
# ### Discrete water-quality samples
#
# Lab samples for the stations flagged `samples`. The samples service is keyed by characteristic
# **name**, so we fetch all results per station and keep those whose characteristic maps to one of
# our priority groups via `classify_parameter`.

# %%
samples_station_ids = stations_in_area.loc[stations_in_area["samples"], "monitoring_location_id"].tolist()
samples_raw, _ = waterdata.get_samples(monitoring_location_id=samples_station_ids)
samples = samples_raw.rename(columns={
    "Location_Identifier": "monitoring_location_id",
    "Activity_StartDateTime": "datetime",
    "Result_Characteristic": "characteristic",
    "USGSpcode": "parameter_code",
    "Result_Measure": "value",
    "Result_MeasureUnit": "unit",
    "Result_SampleFraction": "fraction",
    "Result_ResultDetectionCondition": "detection_condition",
    "Result_MeasureQualifierCode": "qualifier",
    "Result_CharacteristicGroup": "characteristic_group",
    "LabInfo_Name": "lab_name",
})
samples["priority_group"] = samples["characteristic"].map(lambda c: classify_parameter(characteristic=c))
samples = samples[samples["priority_group"].notna()].copy()
samples["huc8"] = samples["monitoring_location_id"].map(huc8_by_station)
samples = (
    samples[
        ["monitoring_location_id", "datetime", "characteristic", "parameter_code", "value", "unit",
         "fraction", "detection_condition", "qualifier", "characteristic_group", "lab_name",
         "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "characteristic", "datetime"])
    .reset_index(drop=True)
)
save_outputs(samples, S.data_dir / "usgs_waterdata" / "usgs_samples.parquet")
```

- [ ] **Step 5: Append the field-measurements fetch cell**

```python
# %% [markdown]
# ### Field measurements
#
# In-situ readings (temperature, DO, pH, conductivity, turbidity, …) for the stations flagged
# `field_measurements`.

# %%
field_station_ids = stations_in_area.loc[stations_in_area["field_measurements"], "monitoring_location_id"].tolist()
field_raw, _ = waterdata.get_field_measurements(
    monitoring_location_id=field_station_ids,
    parameter_code=PRIORITY_CODES,
    skip_geometry=True,
)
field = field_raw.rename(columns={"time": "datetime", "unit_of_measure": "unit"})
field["parameter_name"] = field["parameter_code"].map(_parameter_name)
field["priority_group"] = field["parameter_code"].map(lambda c: classify_parameter(parameter_code=c))
field["huc8"] = field["monitoring_location_id"].map(huc8_by_station)
field = (
    field[
        ["monitoring_location_id", "datetime", "parameter_code", "parameter_name", "value", "unit",
         "qualifier", "approval_status", "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "parameter_code", "datetime"])
    .reset_index(drop=True)
)
save_outputs(field, S.data_dir / "usgs_waterdata" / "usgs_field_measurements.parquet")
```

- [ ] **Step 6: Sync and execute the notebook**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 3_usgs_waterdata.py && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 3_usgs_waterdata.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5
```
Expected: `Writing 3_usgs_waterdata.ipynb`, no traceback. (The samples fetch over ~64 stations can take a few minutes; the on-disk cache speeds re-runs.)

- [ ] **Step 7: Verify the three products**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
import pandas as pd
for name in ['usgs_daily_values','usgs_samples','usgs_field_measurements']:
    df = pd.read_parquet(f'data/usgs_waterdata/{name}.parquet')
    yrs = pd.to_datetime(df['date' if 'date' in df else 'datetime']).dt.year
    assert len(df) > 0, name
    assert df['priority_group'].notna().all(), name
    assert df['huc8'].notna().any(), name
    print(f'{name}: {len(df):>7} rows | years {int(yrs.min())}-{int(yrs.max())} | groups {sorted(df.priority_group.unique())}')
"
```
Expected: three non-empty tables, multi-decade year spans, every row carrying a `priority_group`.

- [ ] **Step 8: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add notebooks/3_usgs_waterdata.py notebooks/3_usgs_waterdata.ipynb data/usgs_waterdata/ _freeze/
git commit -m "Fetch USGS daily/sample/field time-series in 3_usgs_waterdata"
```

---

## Task 5: Availability summary + sample plot in `3_usgs_waterdata`

**Files:**
- Modify: `notebooks/3_usgs_waterdata.py` (append the availability step after the fetch cells)

**Interfaces:**
- Consumes: `daily`, `samples`, `field` (Task 4), `show` (helper), `hvplot` (Task 4 import).
- Produces: rendered coverage tables, an availability heatmap, and one sample time-series plot.

- [ ] **Step 1: Append the coverage-table cell**

```python
# %% [markdown]
# ## Step 10 — Data availability & a sample series
#
# Confirm the fetch: per data type, how many records and what date span each station × priority
# group has, a quick availability heatmap, and one illustrative series. (Trend and pre/post
# analyses live in the later display notebooks.)

# %%
def coverage(df, time_col):
    """Record count + first/last date per station × priority group."""
    t = pd.to_datetime(df[time_col])
    out = (
        df.assign(_t=t)
        .groupby(["monitoring_location_id", "priority_group"])["_t"]
        .agg(n="size", start="min", end="max")
        .reset_index()
        .sort_values(["priority_group", "monitoring_location_id"])
    )
    return out


show(coverage(daily, "date"))
```

- [ ] **Step 2: Append the samples + field coverage cells**

```python
# %%
show(coverage(samples, "datetime"))

# %%
show(coverage(field, "datetime"))
```

- [ ] **Step 3: Append the availability heatmap cell**

```python
# %%
# Daily-value availability: record count per station per year.
daily_year = daily.assign(year=pd.to_datetime(daily["date"]).dt.year)
availability = daily_year.groupby(["monitoring_location_id", "year"]).size().reset_index(name="records")
availability.hvplot.heatmap(
    x="year", y="monitoring_location_id", C="records", cmap="blues",
    title="Daily-value record availability (count per station-year)", colorbar=True, rot=45,
)
```

- [ ] **Step 4: Append the sample time-series cell**

```python
# %%
# Illustrative series: daily discharge at the station with the most discharge records.
discharge = daily[daily["priority_group"] == "discharge"].copy()
gauge = discharge.groupby("monitoring_location_id").size().idxmax()
discharge[discharge["monitoring_location_id"] == gauge].hvplot.line(
    x="date", y="value", title=f"Daily mean discharge — {gauge}", ylabel="ft³/s", xlabel="",
)
```

- [ ] **Step 5: Sync, execute, and verify it renders**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 3_usgs_waterdata.py && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 3_usgs_waterdata.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5 && grep -c "holoviews_exec\|Bokeh.embed" 3_usgs_waterdata.ipynb
```
Expected: `Writing 3_usgs_waterdata.ipynb`, no traceback, non-zero embed count (the heatmap + line plot embedded).

- [ ] **Step 6: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add notebooks/3_usgs_waterdata.py notebooks/3_usgs_waterdata.ipynb _freeze/
git commit -m "Add data-availability summary + sample series to 3_usgs_waterdata"
```

---

## Task 6: Home-page cards — new order, three columns, rendered-page links

**Files:**
- Modify: `index.qmd` (the `## The notebooks` grid)

**Interfaces:**
- Consumes: the renamed `.html` pages (Task 1).
- Produces: a three-card grid linking to the rendered pages.

- [ ] **Step 1: Replace the notebook grid in `index.qmd`**

Replace the `::: {.grid}` … `:::` block under `## The notebooks` with three cards in the new order, `g-col-md-4`, linking to `.html`:

```markdown
::: {.grid}

::: {.g-col-12 .g-col-md-4}
### [1 · USGS Hydrography](notebooks/1_usgs_hydrography.html)
The **spatial foundation**: fetches the three HUC-8 **watershed boundaries** and maps them on an
interactive topographic basemap.
:::

::: {.g-col-12 .g-col-md-4}
### [2 · CONUS404 Climate](notebooks/2_usgs_climate.html)
Fetches **CONUS404** monthly climate output as a gridded datacube and derives the long-term
**water balance** (precipitation, ET, runoff, recharge) and **trends** — per watershed and per grid
cell — across the whole area, including the Mexican side.
:::

::: {.g-col-12 .g-col-md-4}
### [3 · USGS WaterData](notebooks/3_usgs_waterdata.html)
Discovers the **USGS monitoring stations**, records **which priority parameters** each measured,
and fetches the **time-series records** (daily values, discrete samples, field measurements) with a
data-availability summary.
:::

:::
```

- [ ] **Step 2: Render and verify the links**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run render 2>&1 | grep -iE "output created|error" | tail -3
grep -oE 'notebooks/[0-9]_usgs_[a-z]+\.html' _site/index.html | sort -u
```
Expected: `Output created`; the grep lists exactly `notebooks/1_usgs_hydrography.html`, `notebooks/2_usgs_climate.html`, `notebooks/3_usgs_waterdata.html` (`.html`, not `.ipynb`).

- [ ] **Step 3: Commit**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git add index.qmd _site/ _freeze/
git commit -m "Home page: three notebook cards in new order, linking rendered .html pages"
```

---

## Self-Review

**Spec coverage:**
- Rename/reorder + `git mv` + data folders + freeze + all references → Task 1. ✓
- `save_outputs` generalization → Task 2. ✓
- Plot fixes (single-column, content-fit, scroll-zoom off, centralized) → Task 3. ✓
- Time-series fetch (daily/samples/field, priority params, full record, tidy parquet+CSV) → Task 4. ✓
- Availability summary + sample plot → Task 5. ✓
- Home-page cards (new order, three columns, `.html` links) → Task 6. ✓
- CONUS404 file names kept, only folder renamed → Task 1 Step 3 (writes keep `conus404_` prefix). ✓
- Continuous data / trend analysis / new sources → out of scope (not implemented). ✓

**Type/name consistency:** `save_outputs(df, parquet_path)` signature is used identically in Tasks 4–5. `classify_parameter`, `PRIORITY_GROUPS`, `stations_in_area`, `parameter_name_by_code` are pre-existing names in the waterdata notebook (verified). `set_plot_defaults`/`PLOT_WIDTH` defined in Task 3 and only referenced within `_helpers`. Column renames in Task 4 (`date`, `datetime`, `unit`, `priority_group`, `huc8`) match the `coverage()`/plot references in Task 5.

**Placeholder scan:** no TBD/TODO; every code step shows full code; verification commands give expected output. The only intentionally-tunable value is `PLOT_WIDTH` (Task 3), with an explicit render-and-adjust verification loop, as the spec specified.
