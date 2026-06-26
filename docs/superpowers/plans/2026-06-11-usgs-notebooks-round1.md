# USGS Notebooks Round 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the USGS notebook into `1_usgs_hydrofabric` (boundaries) + `2_usgs_waterdata` (stations & parameter inventory), centralize setup/colors in `_helpers.py`, brand the Quarto site (LimnoTech `_brand.yml` + colorcet data colors), and re-enable GitHub Pages publishing.

**Architecture:** Two paired jupytext notebooks share `notebooks/_helpers.py`. NB1 fetches HUC-8 boundaries → `data/spatial/`. NB2 reads those, discovers USGS monitoring stations, and records which README-priority water-quality parameters each station measured → `data/usgs_waterdata/`. The site is built with Quarto (executes + freezes notebooks) and deployed by GitHub Actions.

**Tech Stack:** Python 3.13, pixi; geopandas, pygeohydro/pynhd (HyRiver), dataretrieval (USGS WaterData API), async_retriever, geoviews/holoviews (Bokeh), colorcet, Quarto 1.9, jupytext.

## Global Constraints

- **No pytest / formal test suite.** The deliverable is executed notebooks + the rendered site. Each task is verified by running a Python snippet, executing the notebook headlessly (`pixi run jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb`), and/or `pixi run render` + grep checks — not by a unit-test framework.
- **Never run `git commit`, `git merge`, or push — only the user does.** The agent creates branches (`git checkout -b` is fine — not a commit) and leaves verified changes staged/on-disk; the user reviews, commits, and merges in GitHub Desktop.
- **Branch per task-group (see Execution model below).** One branch off `main` per coupled task-group; implement + verify all its tasks, run the task review on the working-tree diff, then **pause for the user's review/commit/merge gate**. The next group branches off the updated `main`.
- **Paired notebooks:** edit the `.py`; sync with `pixi run jupytext --sync notebooks/<name>.py`; then execute the `.ipynb` so its stored outputs match.
- **Audience:** notebooks are for readers new to Python/Jupyter — explanatory markdown per step, small commented cells.
- **Notebooks self-locate the repo root** via `_helpers.find_repo_root()`; all repo paths (`data/`, `cache/`, `.env`) are absolute off that.
- **API key:** `init_session()` loads `API_USGS_PAT` from `.env`; pass `api_headers` to `async_retriever` requests. Runs without a key at anonymous rate limits.
- **Data colors come from colorcet** (`categorical_colors`), never the LimnoTech brand palette. Brand colors are for site chrome only.
- **pixi env:** `pixi list` to check a package; `pixi add <pkg>` to add one (updates `pixi.toml` + `pixi.lock`). Do not use bare pip/conda.

---

## Execution model — task-groups, branches, gates

The 8 tasks below are executed in **3 coupled groups**, one branch each. The agent implements +
reviews a whole group, then **pauses** for the user to review, commit, and merge that branch to `main`
in GitHub Desktop; the next group branches off the updated `main`. (Groups are dependent — G2 needs G1's
helpers + boundaries output on `main`; G3 needs both notebooks.)

| Group | Branch | Tasks | Deliverable |
| --- | --- | --- | --- |
| **A** | `round1-a-helpers-hydrofabric` | Task 1, Task 2 | Shared `_helpers` (init_session, colors) + working `1_usgs_hydrofabric`; old notebook removed |
| **B** | `round1-b-waterdata` | Task 3, Task 4, Task 5 | Complete `2_usgs_waterdata` (stations + priority-parameter inventory + map) |
| **C** | `round1-c-site` | Task 6, Task 7, Task 8 | LimnoTech `_brand.yml` + navbar, publishing workflow, updated docs, full render |

Within a group the agent may dispatch one implementer subagent per task (sequential, same branch) or a
single implementer for the whole group when the plan text is complete transcription; either way the
**user gate is once per group**, not per task.

## File structure

| File | Action | Responsibility |
| --- | --- | --- |
| `notebooks/_helpers.py` | modify | Shared: `find_repo_root`, `init_session`+`Session`, `save_outputs`, `show`, `categorical_colors`+`CATEGORICAL`, `make_legend_clickable` |
| `notebooks/1_usgs_hydrofabric.py` / `.ipynb` | create | Steps 1–4: HUC-8 boundaries → map → `data/spatial/` |
| `notebooks/2_usgs_waterdata.py` / `.ipynb` | create | Steps 5+: stations + parameter inventory → `data/usgs_waterdata/` |
| `notebooks/1_usgs_hydrography_waterdata.py` / `.ipynb` | delete | replaced by the two above |
| `pixi.toml` | modify | add explicit `colorcet` dependency |
| `_brand.yml` | create | LimnoTech palette + Roboto for the site |
| `_quarto.yml` | modify | navbar: NB1 + NB2; site title |
| `.github/workflows/publish.yml` | create | GitHub Pages deploy (with `API_USGS_PAT` secret) |
| `CLAUDE.md`, `README.md` | modify | document the split, helpers, branding, publishing |

---

## Task 1: Dependencies + shared `_helpers.py`

**Files:**
- Modify: `pixi.toml` (add `colorcet`)
- Modify: `notebooks/_helpers.py`

**Interfaces:**
- Produces:
  - `find_repo_root(marker="pixi.toml", start=None) -> pathlib.Path` (already exists)
  - `Session` dataclass with fields `repo_root: Path, data_dir: Path, cache_file: str, cache_expire_seconds: int, api_key: str | None, api_headers: dict`
  - `init_session(cache_expire_seconds: int = 604800) -> Session`
  - `save_outputs(gdf, parquet_path) -> None` (already exists)
  - `show(df, height: int = 360) -> IPython.display.HTML` (already exists)
  - `CATEGORICAL: list[str]` (colorcet glasbey hex list)
  - `categorical_colors(keys, palette=CATEGORICAL) -> dict` (category → hex)
  - `make_legend_clickable(plot, element) -> None` (Bokeh hook)

- [ ] **Step 1: Add the colorcet dependency**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi add colorcet
```
Expected: `✔ Added colorcet …` (it resolves; it was already present transitively).

- [ ] **Step 2: Write a verification snippet that fails (helpers not yet extended)**

Run:
```bash
pixi run python -c "from notebooks._helpers import init_session, categorical_colors, make_legend_clickable" 2>&1 | tail -2
```
Expected: FAIL — `ImportError: cannot import name 'init_session' …` (these don't exist yet).

- [ ] **Step 3: Extend `notebooks/_helpers.py`**

Replace the import block at the top of `notebooks/_helpers.py` so it reads exactly:
```python
import os
from dataclasses import dataclass
from pathlib import Path

import colorcet as cc
from dotenv import load_dotenv
from IPython.display import HTML
```

Keep the existing `find_repo_root`, `save_outputs`, and `show` functions as they are. Then append the following to the end of the file:
```python
# --- Session setup (shared by every notebook) ---------------------------------

@dataclass(frozen=True)
class Session:
    """Resolved per-notebook configuration returned by init_session()."""
    repo_root: Path
    data_dir: Path
    cache_file: str
    cache_expire_seconds: int
    api_key: str | None
    api_headers: dict


def init_session(cache_expire_seconds: int = 7 * 24 * 3600) -> Session:
    """Load the optional USGS API key from .env, point HyRiver's request cache at the
    git-ignored cache/ folder, and return the resolved paths/headers as a Session.
    Safe to call without a .env (falls back to anonymous rate limits)."""
    repo_root = find_repo_root()
    load_dotenv(repo_root / ".env")
    api_key = os.getenv("API_USGS_PAT")
    api_headers = {"X-Api-Key": api_key} if api_key else {}
    cache_file = str(repo_root / "cache" / "aiohttp_cache.sqlite")
    os.environ.setdefault("HYRIVER_CACHE_NAME", cache_file)
    os.environ.setdefault("HYRIVER_CACHE_EXPIRE", str(cache_expire_seconds))
    print(
        "USGS API key loaded."
        if api_key
        else "No API key — using anonymous (lower) rate limits."
    )
    return Session(
        repo_root=repo_root,
        data_dir=repo_root / "data",
        cache_file=cache_file,
        cache_expire_seconds=cache_expire_seconds,
        api_key=api_key,
        api_headers=api_headers,
    )


# --- Colors for *data* in figures (colorcet, NOT the LimnoTech brand) ----------

CATEGORICAL = cc.glasbey_category10  # distinct, colorblind-aware categorical hex list


def categorical_colors(keys, palette=CATEGORICAL):
    """Map an ordered list of category keys -> hex colors, cycling the palette.
    Returns a dict {key: hex} for use as per-category colors in GeoViews layers."""
    keys = list(keys)
    return {key: palette[i % len(palette)] for i, key in enumerate(keys)}


# --- GeoViews/Bokeh helpers ---------------------------------------------------

def make_legend_clickable(plot, element):
    """Bokeh hook: clicking a legend entry hides/shows that layer (click_policy='hide')."""
    plot.state.legend.click_policy = "hide"
```

- [ ] **Step 4: Run the verification snippet — now passes and behaves correctly**

Run:
```bash
pixi run python -c "
from notebooks._helpers import init_session, categorical_colors, make_legend_clickable, CATEGORICAL
s = init_session()
print('data_dir ok:', s.data_dir.name == 'data')
print('headers is dict:', isinstance(s.api_headers, dict))
cm = categorical_colors(['a','b','c'])
print('colors:', cm, '| distinct:', len(set(cm.values())) == 3)
print('palette len:', len(CATEGORICAL))
" 2>&1 | tail -6
```
Expected: PASS — prints `data_dir ok: True`, `headers is dict: True`, a 3-key color dict with 3 distinct hex values, and a palette length > 10.

- [ ] **Step 5: Checkpoint**

Leave the changes (`pixi.toml`, `pixi.lock`, `notebooks/_helpers.py`) staged for the user to commit in GitHub Desktop. Do not run `git commit`.

---

## Task 2: Create `1_usgs_hydrofabric` (Steps 1–4) and remove the old notebook

**Files:**
- Create: `notebooks/1_usgs_hydrofabric.py` (+ generated `.ipynb`)
- Delete: `notebooks/1_usgs_hydrography_waterdata.py` and `.ipynb`

**Interfaces:**
- Consumes: `init_session`, `save_outputs`, `show`, `categorical_colors` from `_helpers`
- Produces: `data/spatial/huc8_watersheds.{parquet,csv}` (columns include `huc8`, `name`, `areasqkm`, `states`, `geometry`)

- [ ] **Step 1: Write `notebooks/1_usgs_hydrofabric.py`**

Create the file with exactly this content:
```python
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 1 · USGS Hydrofabric — Watershed Boundaries
#
# First notebook in the Thornforest hydrology series. It builds the **spatial foundation**
# (the three HUC-8 watershed boundaries) that the other notebooks rely on, and maps it.
#
# Our study area is **three HUC-8 subbasins** in South Texas:
# - South Laguna Madre (12110208)
# - Los Olmos (13090001)
# - Lower Rio Grande (13090002)
#
# > **New to Python notebooks?** Run each cell in order with **Shift + Enter**.

# %% [markdown]
# ## Step 1 — Imports and setup
#
# All imports are at the top. `init_session()` (from our shared `_helpers` module) loads the
# optional USGS API key, configures the on-disk request cache, and returns the paths we use.

# %%
from pygeohydro import WBD

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import init_session, save_outputs, show, categorical_colors

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Name our three watersheds
#
# A dictionary maps each HUC-8 code to a friendly name. Colors come from a **colorcet**
# categorical palette (via `categorical_colors`) so the figure data colors are perceptually
# distinct and consistent across the project.

# %%
HUC8_WATERSHEDS = {
    "12110208": "South Laguna Madre",
    "13090001": "Los Olmos",
    "13090002": "Lower Rio Grande",
}
HUC8_COLORS = categorical_colors(HUC8_WATERSHEDS)  # huc8 code -> hex

# %% [markdown]
# ## Step 3 — Download the watershed boundaries
#
# `WBD("huc8").byids(...)` fetches the three boundaries from the USGS Watershed Boundary
# Dataset. The request is cached on disk; the result is also saved to `data/spatial/`.

# %%
watersheds_gdf = WBD("huc8").byids("huc8", list(HUC8_WATERSHEDS))
save_outputs(watersheds_gdf, S.data_dir / "spatial" / "huc8_watersheds.parquet")
print(f"{len(watersheds_gdf)} watershed boundaries.")

# %% [markdown]
# ### What did we get back?
#
# A **GeoDataFrame** (one row per watershed, with a `geometry` shape). The coordinates are
# longitude/latitude (EPSG:4326).

# %%
print("Coordinate system:", watersheds_gdf.crs)
show(watersheds_gdf[["huc8", "name", "areasqkm", "states"]])

# %% [markdown]
# ## Step 4 — Map the watersheds
#
# We layer the boundaries over an Esri World Topo basemap; `*` stacks layers. `data_aspect=1`
# keeps map pixels square so the basemap tiles aren't stretched.
#
# > **Explore:** hover for name/area; zoom/pan with the toolbar; click legend entries.

# %%
watershed_layers = []
for code, name in HUC8_WATERSHEDS.items():
    one = watersheds_gdf[watersheds_gdf["huc8"] == code]
    watershed_layers.append(
        gv.Polygons(one, vdims=["name", "huc8", "areasqkm"], label=name).opts(
            color=HUC8_COLORS[code],
            line_color=HUC8_COLORS[code],
            alpha=0.45,
            line_width=2,
            tools=["hover"],
        )
    )

watersheds_map = gvts.EsriWorldTopo
for layer in watershed_layers:
    watersheds_map = watersheds_map * layer

watersheds_map = watersheds_map.opts(
    frame_width=850,
    data_aspect=1,
    title="Three HUC-8 Watersheds — Thornforest Study Area (South Texas)",
    legend_position="top_left",
    active_tools=["wheel_zoom"],
)
watersheds_map

# %% [markdown]
# ## What's next
#
# The boundaries are saved to `data/spatial/`. Notebook **`2_usgs_waterdata`** reads them to
# discover the USGS monitoring stations inside the watersheds and the parameters they measure.
```

- [ ] **Step 2: Sync to a notebook**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 1_usgs_hydrofabric.py
```
Expected: creates `1_usgs_hydrofabric.ipynb`.

- [ ] **Step 3: Execute the notebook (this is the test)**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 1_usgs_hydrofabric.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5
```
Expected: `[NbConvertApp] Writing … bytes …`, no error/traceback.

- [ ] **Step 4: Verify outputs and the interactive map embed**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
import geopandas as gpd
g = gpd.read_parquet('data/spatial/huc8_watersheds.parquet')
print('rows:', len(g), '| has geometry last:', list(g.columns)[-1] == 'geometry')
" && grep -c "holoviews_exec\|Bokeh.embed" notebooks/1_usgs_hydrofabric.ipynb
```
Expected: `rows: 3 | has geometry last: True`, and a non-zero count of embed markers.

- [ ] **Step 5: Delete the old notebook pair**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && git rm notebooks/1_usgs_hydrography_waterdata.py notebooks/1_usgs_hydrography_waterdata.ipynb
```
Expected: both removed (staged deletion). (Old `data/usgs_waterdata/*` outputs are regenerated by NB2 in later tasks; leave them.)

- [ ] **Step 6: Group A gate**

This completes branch `round1-a-helpers-hydrofabric` (Tasks 1–2). After the task review passes, **hand the branch to the user** to review, commit, and merge to `main` in GitHub Desktop. **Wait** for confirmation that it's merged before creating the Group B branch (Task 3 needs the merged `_helpers` and the committed `data/spatial/huc8_watersheds.parquet`).

---

## Task 3: Create `2_usgs_waterdata` Step 5 (station discovery)

**Files:**
- Create: `notebooks/2_usgs_waterdata.py` (+ generated `.ipynb`)

**Interfaces:**
- Consumes: `init_session`, `save_outputs`, `show`, `categorical_colors`, `make_legend_clickable`; reads `data/spatial/huc8_watersheds.parquet`
- Produces: `stations_in_area` GeoDataFrame in-notebook; `data/usgs_waterdata/usgs_monitoring_locations.{parquet,csv}` (later extended in Task 4)

- [ ] **Step 1: Write `notebooks/2_usgs_waterdata.py` (header + Step 5)**

Create the file with this content (Tasks 4 and 5 append more cells to the same file):
```python
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 2 · USGS WaterData — Monitoring Stations & Parameters
#
# Reads the watershed boundaries from notebook 1, discovers the USGS monitoring stations
# inside them via the new USGS **Water Data** API, and records **which priority parameters**
# each station measured.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
from io import StringIO
from urllib.parse import quote

import geopandas as gpd
import pandas as pd
import async_retriever as ar
from dataretrieval import waterdata

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_outputs,
    show,
    categorical_colors,
    make_legend_clickable,
)

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 5 — Discover monitoring stations
#
# We load the watershed boundaries saved by notebook 1, ask the Water Data API for every
# station in their bounding box, then keep only those that fall **within** the watershed
# polygons (a spatial join).

# %%
boundaries_path = S.data_dir / "spatial" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrofabric) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

stations_gdf, _ = waterdata.get_monitoring_locations(bbox=bbox)
stations_gdf = stations_gdf.set_crs(4326)
stations_in_area = gpd.sjoin(
    stations_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)
print(
    f"{len(stations_gdf)} stations in the bounding box; "
    f"{len(stations_in_area)} within the watersheds."
)
save_outputs(
    stations_in_area, S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations.parquet"
)

# %% [markdown]
# ### What kinds of stations are there?

# %%
print("By site type:")
print(stations_in_area["site_type"].value_counts().to_string())
print("\nBy watershed:")
print(stations_in_area["name"].value_counts().to_string())
show(stations_in_area[["monitoring_location_id", "monitoring_location_name", "site_type", "name"]])
```

- [ ] **Step 2: Sync and execute**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 2_usgs_waterdata.py && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 2_usgs_waterdata.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5
```
Expected: writes the notebook, no error/traceback.

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
import geopandas as gpd
g = gpd.read_parquet('data/usgs_waterdata/usgs_monitoring_locations.parquet')
print('stations:', len(g), '| has monitoring_location_id:', 'monitoring_location_id' in g.columns)
"
```
Expected: a non-zero station count (≈291) and `True`.

- [ ] **Step 4: Checkpoint** — leave `2_usgs_waterdata.{py,ipynb}` for the user.

---

## Task 4: NB2 Step 6 — priority-parameter inventory

**Files:**
- Modify: `notebooks/2_usgs_waterdata.py` (append Step 6 cells)

**Interfaces:**
- Consumes: `stations_in_area`, `bbox`, `S` (from Task 3); `waterdata.get_time_series_metadata`, `get_field_measurements_metadata`, `get_reference_table`, the samples summary endpoint
- Produces: `stations_in_area` extended with boolean columns `daily, continuous, field_measurements, samples` + one boolean per priority group in `PRIORITY_GROUPS` + a `parameters` list column; saved to `data/usgs_waterdata/usgs_monitoring_locations_parameters.{parquet,csv}`. Also `PRIORITY_GROUPS: dict[str, dict]` and `classify_parameter(pcode=None, characteristic=None) -> str | None`.

- [ ] **Step 1: Append the priority-map + classifier cell to `notebooks/2_usgs_waterdata.py`**

Append:
```python
# %% [markdown]
# ## Step 6 — Which priority parameters does each station measure?
#
# The README prioritizes these water-quality parameters. For each we list the USGS parameter
# codes (`pcodes`, used by the time-series & field-measurement services) and the Water Quality
# characteristic-name patterns (used by the discrete-samples service). `classify_parameter`
# maps any measured pcode/characteristic to its priority group (or `None`).

# %%
# group -> {"pcodes": set[str], "characteristics": list[str] (lowercase substrings)}
PRIORITY_GROUPS = {
    "conductivity": {"pcodes": {"00095", "90095"}, "characteristics": ["specific conductance", "conductivity"]},
    "temperature": {"pcodes": {"00010"}, "characteristics": ["temperature, water"]},
    "dissolved_oxygen": {"pcodes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
    "dissolved_solids": {"pcodes": {"70300", "00515"}, "characteristics": ["total dissolved solids"]},
    "chlorophyll": {"pcodes": {"32209", "32210", "32211", "70953"}, "characteristics": ["chlorophyll", "algae"]},
    "pH": {"pcodes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classifier)
    "nitrogen": {
        "pcodes": {"00600", "00605", "00608", "00613", "00615", "00618", "00620", "00625", "00630"},
        "characteristics": ["nitrogen", "nitrate", "nitrite", "ammonia", "kjeldahl"],
    },
    "phosphorus": {"pcodes": {"00650", "00665", "00666", "00671"}, "characteristics": ["phosphorus", "orthophosphate"]},
    "turbidity": {"pcodes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
}
PRIORITY_NAMES = list(PRIORITY_GROUPS)


def classify_parameter(pcode=None, characteristic=None):
    """Return the priority group for a USGS pcode or a WQ characteristic name, else None."""
    if pcode is not None:
        code = str(pcode).strip().zfill(5)
        for group, spec in PRIORITY_GROUPS.items():
            if code in spec["pcodes"]:
                return group
    if characteristic is not None:
        name = str(characteristic).strip().lower()
        if name == "ph":
            return "pH"
        for group, spec in PRIORITY_GROUPS.items():
            if group == "pH":
                continue  # pH only via exact match above (avoid 'ph' substring false positives)
            if any(pat in name for pat in spec["characteristics"]):
                return group
    return None
```

- [ ] **Step 2: Append the metadata-gathering cell**

Append:
```python
# %%
SAMPLES_SUMMARY_URL = "https://api.waterdata.usgs.gov/samples-data/summary"

# Time-series metadata (daily & continuous), split by computation period; carries pcodes.
ts_meta, _ = waterdata.get_time_series_metadata(bbox=bbox, skip_geometry=True)
period = ts_meta["computation_period_identifier"]
daily_ids = set(ts_meta.loc[period == "Daily", "monitoring_location_id"])
continuous_ids = set(ts_meta.loc[period == "Points", "monitoring_location_id"])

# Field-measurement metadata; carries pcodes.
fm_meta, _ = waterdata.get_field_measurements_metadata(bbox=bbox, skip_geometry=True)
field_ids = set(fm_meta["monitoring_location_id"])

# Per-station discrete-samples summaries, fetched concurrently (and cached) via async-retriever.
station_ids = stations_in_area["monitoring_location_id"].tolist()
summary_urls = [f"{SAMPLES_SUMMARY_URL}/{quote(sid, safe='')}?mimeType=text/csv" for sid in station_ids]
summary_texts = ar.retrieve_text(
    summary_urls,
    request_kwds=[{"headers": S.api_headers}] * len(summary_urls) if S.api_headers else None,
    cache_name=S.cache_file,
    expire_after=S.cache_expire_seconds,
    limit_per_host=8,
)
samples_summaries = {  # station_id -> summary DataFrame (may be empty)
    sid: pd.read_csv(StringIO(txt)) for sid, txt in zip(station_ids, summary_texts) if txt
}
samples_ids = {sid for sid, df in samples_summaries.items() if len(df) > 0}
```

- [ ] **Step 3: Append the per-station parameter aggregation cell**

Append:
```python
# %%
# Pcode -> readable name, from the USGS reference table (for the human-readable `parameters` list).
param_codes, _ = waterdata.get_reference_table("parameter-codes")
pcode_name = dict(zip(param_codes["parameter_code"].astype(str), param_codes["parameter_name"]))

# Build, per station: the set of measured pcodes/characteristics, the priority groups they hit,
# and a sorted human-readable parameter list.
ts_codes_by_site = ts_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()
fm_codes_by_site = fm_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()


def station_parameters(sid):
    """Return (priority_groups: set[str], parameter_names: sorted list[str]) for one station."""
    groups, names = set(), set()
    for code in ts_codes_by_site.get(sid, set()) | fm_codes_by_site.get(sid, set()):
        code = str(code)
        names.add(pcode_name.get(code.zfill(5), pcode_name.get(code, code)))
        g = classify_parameter(pcode=code)
        if g:
            groups.add(g)
    summary = samples_summaries.get(sid)
    if summary is not None and "characteristic" in summary.columns:
        for char in summary["characteristic"].dropna().unique():
            names.add(str(char))
            g = classify_parameter(characteristic=char)
            if g:
                groups.add(g)
    return groups, sorted(names)


groups_by_site, params_by_site = {}, {}
for sid in station_ids:
    g, names = station_parameters(sid)
    groups_by_site[sid] = g
    params_by_site[sid] = names

# Data-type flags (kept) + one boolean column per priority group + the readable parameter list.
sid_col = stations_in_area["monitoring_location_id"]
stations_in_area["daily"] = sid_col.isin(daily_ids)
stations_in_area["continuous"] = sid_col.isin(continuous_ids)
stations_in_area["field_measurements"] = sid_col.isin(field_ids)
stations_in_area["samples"] = sid_col.isin(samples_ids)
for group in PRIORITY_NAMES:
    stations_in_area[group] = sid_col.map(lambda s: group in groups_by_site.get(s, set()))
stations_in_area["parameters"] = sid_col.map(lambda s: params_by_site.get(s, []))

save_outputs(
    stations_in_area,
    S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations_parameters.parquet",
)
```

- [ ] **Step 4: Append the summary + unmatched-parameter audit cell**

Append:
```python
# %% [markdown]
# ### How many stations measure each priority parameter?
#
# The audit below lists any measured pcodes/characteristics that did NOT map to a priority
# group — useful for sanity-checking and refining `PRIORITY_GROUPS`.

# %%
DATA_TYPES = ["daily", "continuous", "field_measurements", "samples"]
print("Stations by data type:")
print(stations_in_area[DATA_TYPES].sum().to_string())
print(f"\nStations by priority parameter (of {len(stations_in_area)}):")
print(stations_in_area[PRIORITY_NAMES].sum().to_string())

# Audit: characteristics seen in samples that mapped to no priority group.
unmatched = sorted({
    str(c)
    for df in samples_summaries.values()
    if "characteristic" in df.columns
    for c in df["characteristic"].dropna().unique()
    if classify_parameter(characteristic=c) is None
})
print(f"\n{len(unmatched)} unmatched sample characteristics (first 25):")
print("\n".join(unmatched[:25]))

show(stations_in_area[["monitoring_location_id", "monitoring_location_name", *PRIORITY_NAMES]])
```

- [ ] **Step 5: Sync and execute**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 2_usgs_waterdata.py && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 2_usgs_waterdata.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5
```
Expected: writes the notebook, no error/traceback. (The samples loop is cached from earlier runs, so it is fast.)

- [ ] **Step 6: Verify the parameter columns + spot-check**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
import geopandas as gpd
g = gpd.read_parquet('data/usgs_waterdata/usgs_monitoring_locations_parameters.parquet')
prio = ['conductivity','temperature','dissolved_oxygen','dissolved_solids','chlorophyll','pH','nitrogen','phosphorus','turbidity']
print('rows:', len(g))
print('all priority cols present:', all(c in g.columns for c in prio))
print('has parameters list col:', 'parameters' in g.columns)
print('per-parameter station counts:')
print(g[prio].sum().to_string())
print('stations with >=1 priority param:', int(g[prio].any(axis=1).sum()))
"
```
Expected: all priority columns present, a `parameters` column, and non-trivial counts for at least temperature / dissolved_oxygen / conductivity. If a priority parameter you expect shows 0, review the audit output from Step 4 and adjust that group's `pcodes`/`characteristics`, then re-run Steps 5–6.

- [ ] **Step 7: Checkpoint** — leave the updated NB2 + new parquet/csv for the user.

---

## Task 5: NB2 Step 7 — map stations by priority parameter

**Files:**
- Modify: `notebooks/2_usgs_waterdata.py` (append Step 7)

**Interfaces:**
- Consumes: `stations_in_area`, `watersheds_gdf`, `PRIORITY_NAMES`, `categorical_colors`, `make_legend_clickable`
- Produces: an interactive `stations_param_map` (one toggle layer per priority parameter)

- [ ] **Step 1: Append the Step 7 map cell to `notebooks/2_usgs_waterdata.py`**

Append:
```python
# %% [markdown]
# ## Step 7 — Map stations by priority parameter
#
# One colored layer per priority parameter, over the watershed outlines on the topo basemap.
# A station that measures several parameters appears in several layers.
#
# > **Interactive selector:** **click a legend entry to hide/show** that parameter's layer.

# %%
PARAM_COLORS = categorical_colors(PRIORITY_NAMES)
watershed_outlines = gv.Path(watersheds_gdf).opts(color="black", line_width=1.5)

stations_param_map = gvts.EsriWorldTopo * watershed_outlines
for param in PRIORITY_NAMES:
    subset = stations_in_area[stations_in_area[param]]
    if len(subset) == 0:
        continue
    stations_param_map = stations_param_map * gv.Points(
        subset,
        vdims=["monitoring_location_name", "monitoring_location_id", "site_type"],
        label=param,
    ).opts(color=PARAM_COLORS[param], size=7, line_color="white", tools=["hover"])

stations_param_map = stations_param_map.opts(
    frame_width=800,
    data_aspect=1,
    title="Monitoring stations by priority parameter (click legend to toggle)",
    legend_position="right",
    active_tools=["wheel_zoom"],
    hooks=[make_legend_clickable],
)
stations_param_map

# %% [markdown]
# ## What's next
#
# The station inventory — with data-type flags and per-parameter columns — is saved to
# `data/usgs_waterdata/`. Later notebooks will **fetch the actual records** (daily, continuous,
# field measurements, samples) for these stations and parameters.
```

- [ ] **Step 2: Sync, execute, verify the map embed**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest/notebooks && pixi run jupytext --sync 2_usgs_waterdata.py && pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 2_usgs_waterdata.ipynb 2>&1 | grep -iE "writing|error|traceback" | tail -5 && grep -c "holoviews_exec\|Bokeh.embed" 2_usgs_waterdata.ipynb
```
Expected: writes the notebook, no error/traceback, non-zero embed-marker count.

- [ ] **Step 3: Group B gate** — this completes branch `round1-b-waterdata` (Tasks 3–5). After the task review passes, **hand the branch to the user** to review, commit, and merge to `main`. **Wait** for confirmation before creating the Group C branch (Task 6+ render both notebooks).

---

## Task 6: LimnoTech branding — `_brand.yml` + navbar

**Files:**
- Create: `_brand.yml`
- Modify: `_quarto.yml` (navbar entries for both notebooks)

**Interfaces:**
- Produces: site-wide LimnoTech palette + Roboto typography; navbar links to both rendered notebooks.

- [ ] **Step 1: Create `_brand.yml`**

Create the file with exactly:
```yaml
color:
  palette:
    limno-navy: "#174A7C"
    limno-blue: "#56A0D3"
    limno-lime: "#8DC63F"
    limno-aqua: "#5B9B98"
    limno-sky: "#88CBDF"
    limno-yellow: "#F2D17E"
    almost-black: "#313131"
  foreground: almost-black
  primary: limno-navy
  secondary: limno-blue
  tertiary: limno-lime

typography:
  fonts:
    - family: Roboto
      source: google
  base: Roboto
  headings:
    family: Roboto
    weight: 600
    color: limno-navy
```

- [ ] **Step 2: Update the navbar in `_quarto.yml`**

In `_quarto.yml`, replace the `navbar.left` list entry for the old notebook with two entries:
```yaml
    left:
      - href: index.qmd
        text: Home
      - href: notebooks/1_usgs_hydrofabric.html
        text: "1 · Hydrofabric"
      - href: notebooks/2_usgs_waterdata.html
        text: "2 · WaterData stations"
```
Leave the rest of `_quarto.yml` (theme `cosmo`, `execute`, `render` glob `notebooks/*.py`) unchanged — `_brand.yml` is picked up automatically and layers over `cosmo`.

- [ ] **Step 3: Render and verify branding applied**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && rm -rf _site && pixi run render 2>&1 | grep -iE "output created|error" | tail -3 && grep -ric "roboto" _site/index.html && grep -rc "174A7C\|174a7c" _site/*.html _site/site_libs 2>/dev/null | grep -v ":0" | head
```
Expected: `Output created: _site/index.html`; a non-zero count of "roboto"; and the Navy hex present in the generated CSS/HTML.

- [ ] **Step 4: Verify figure data colors are colorcet, not brand**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "
from notebooks._helpers import categorical_colors
print('sample data colors:', list(categorical_colors(['a','b','c']).values()))
"
```
Expected: hex values from the glasbey palette (e.g. starting `#1f77b3`-ish), confirming data colors are independent of the brand palette.

- [ ] **Step 5: Checkpoint** — leave `_brand.yml`, `_quarto.yml`, `_freeze/` for the user.

---

## Task 7: Re-enable GitHub Pages publishing

**Files:**
- Create: `.github/workflows/publish.yml`

**Interfaces:**
- Produces: a CI workflow that renders from the committed `_freeze/` (re-executing on a freeze miss, authenticated via the `API_USGS_PAT` secret) and deploys `_site/` to GitHub Pages.

- [ ] **Step 1: Create `.github/workflows/publish.yml`**

Create the file with exactly:
```yaml
name: Publish site

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up pixi
        uses: prefix-dev/setup-pixi@v0.9.6
        with:
          environments: default
          cache: true

      - name: Render site (Quarto)
        # Renders from committed _freeze/; on a freeze miss it re-executes the notebooks,
        # which hit the USGS APIs — the key avoids the anonymous-rate-limit (HTTP 429).
        env:
          API_USGS_PAT: ${{ secrets.API_USGS_PAT }}
        run: pixi run render

      - name: Warn if _freeze/ was stale (non-blocking)
        run: |
          if [ -n "$(git status --porcelain -- _freeze/)" ]; then
            echo "::warning::_freeze/ was out of date — CI re-executed the notebooks. Run 'pixi run render' locally and commit _freeze/ to keep CI fast."
            git --no-pager diff --stat -- _freeze/
          else
            echo "_freeze/ is up to date."
          fi

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: _site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Verify the workflow is valid YAML**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml')); print('publish.yml: valid YAML')"
```
Expected: `publish.yml: valid YAML`.

- [ ] **Step 3: Record the user's manual GitHub steps**

These cannot be automated; surface them at the checkpoint:
1. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**: name `API_USGS_PAT`, value = the USGS key.
2. GitHub → **Settings → Pages → Build and deployment → Source = GitHub Actions**.

- [ ] **Step 4: Checkpoint** — leave `.github/workflows/publish.yml` for the user; remind them of the two manual steps above.

---

## Task 8: Documentation + final full-site verification

**Files:**
- Modify: `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Update `CLAUDE.md`**

Update these spots:
- "Current status" / "Planned structure": the notebook is now split into `1_usgs_hydrofabric` (boundaries) and `2_usgs_waterdata` (stations + **priority-parameter inventory**).
- "Stack"/Conventions: add `colorcet` (data colors via `categorical_colors`) and note `init_session()` returns the shared config; the LimnoTech `_brand.yml` themes the site (Roboto + palette) while figure data uses colorcet.
- "Website (Quarto)": publishing is **re-enabled** (repo public) — `.github/workflows/publish.yml` + the `API_USGS_PAT` secret + Pages→Actions.
- Outputs: `data/usgs_waterdata/usgs_monitoring_locations_parameters.{parquet,csv}` now carries the priority-parameter columns + `parameters` list.

- [ ] **Step 2: Update `README.md`**

- Reflect the two-notebook split and that NB2 records which priority parameters each station measured.
- Note the site is published to GitHub Pages (link `https://limnotech.github.io/Thornforest/`).

- [ ] **Step 3: Full render + end-to-end verification**

Run:
```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && rm -rf _site && pixi run render 2>&1 | grep -iE "output created|error" | tail -3 && echo "=== pages ===" && find _site -name "*.html" | sort && echo "=== sandbox excluded? ===" && (find _site -iname "*nhdplus*" -o -iname "*helper*" | grep -q . && echo LEAK || echo "clean ✓") && echo "=== embeds + scroll tables in NB2 ===" && grep -c "holoviews_exec" _site/notebooks/2_usgs_waterdata.html && grep -oc 'class="scroll-df"' _site/notebooks/2_usgs_waterdata.html
```
Expected: `Output created`; `_site` has `index.html`, `notebooks/1_usgs_hydrofabric.html`, `notebooks/2_usgs_waterdata.html`; no `_helpers`/sandbox leak; non-zero embed + scroll-table counts.

- [ ] **Step 4: Group C gate** — this completes branch `round1-c-site` (Tasks 6–8). After the task review passes, run the **final whole-branch review** (superpowers:requesting-code-review) over the group, then **hand the branch to the user** to review, commit, and merge to `main`. Remind them of the Task 7 manual GitHub steps (add the `API_USGS_PAT` secret; Pages → GitHub Actions) before the first deploy. (`_site/` is git-ignored; `_freeze/` is committed.)

---

## Self-Review

**Spec coverage:** Item 1 (imports at top) → Tasks 2–3 notebook headers. Item 2 (setup → helpers) → Task 1 `init_session`. Item 3 (branding + colorcet) → Task 1 colors, Task 6 `_brand.yml`. Item 4 (colors in helpers) → Task 1 `categorical_colors`. Items 5–6 (parameter inventory + reference table) → Task 4. Item 7 (split) → Tasks 2–5 + `_quarto.yml`/old-file deletion. Publishing → Task 7. Docs → Task 8. ✅ all covered.

**Placeholders:** none — every code step has complete code; the parameter map is concrete (with an audit step to refine it against live data).

**Type consistency:** `Session` fields (`data_dir`, `cache_file`, `cache_expire_seconds`, `api_headers`) used consistently in NB1/NB2; `PRIORITY_GROUPS`/`PRIORITY_NAMES`/`classify_parameter` defined in Task 4 and reused in Task 5; `categorical_colors`/`make_legend_clickable` defined in Task 1 and consumed by both notebooks.
