# `_helpers` Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `notebooks/_helpers.py` into a focused, teaching-oriented `_helpers/` package; promote reusable USGS logic out of NB3; add a real pytest suite; consolidate the env manifest into `pyproject.toml`; and fold in the outstanding PR-review fixes.

**Architecture:** `notebooks/_helpers.py` becomes a `notebooks/_helpers/` package whose `__init__.py` re-exports the full public API (so `from _helpers import …` is unchanged). Concern-based modules (`session`, `io`, `viz`, `analysis`, `usgs`, `climate`) are generic and WAP-bound; a `config.py` holds Thornforest-only constants and is injected as function arguments, cutting the generic/project seam now. USGS fetching splits into thin `fetch_*` (network) + pure `tidy_*` (unit-testable) layers; notebooks keep the fetch visible and show intermediate results.

**Tech Stack:** Python 3.13, pixi (via `pyproject.toml`), pytest, ruff, `dataretrieval.waterdata`, geopandas/pandas, xarray/zarr, HoloViews/GeoViews/hvplot, Quarto, jupytext.

## Global Constraints

- **The agent never commits or merges.** Each task ends staged on-disk; the **user** reviews the working-tree diff and commits at the task-group gate (per `CLAUDE.md`). "Commit" steps below are the user's gate, not an agent action.
- **Branch:** stack this work on `round3-usgs-timeseries` (create `helpers-refactor` off it: `git checkout -b helpers-refactor round3-usgs-timeseries`). Repo root: `/Users/aaufdenkampe/Documents/git_Limno/Thornforest`.
- **Edit the notebook `.py`, never the `.ipynb`;** after editing run `pixi run jupytext --sync <name>.py`, then execute headlessly with `pixi run jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb`, then `pixi run render`.
- **Storage formats fixed:** tabular → GeoParquet + CSV (`save_outputs`); datacubes → zarr v3 (`save_datacube`).
- **Source-term fidelity:** carry source parameter/variable names, descriptions, units verbatim in data; new names only for derived/blended quantities, labeled as such; link to primary docs in prose.
- **Underscore keeps Quarto ignoring the helpers** — the package dir must stay `notebooks/_helpers/`.
- Run everything via `pixi run …`. After the pyproject migration (Task 1), the test command is `pixi run test`.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `pyproject.toml` | Single env + tool manifest (`[tool.pixi.*]`, pytest, ruff) | **create** (replaces `pixi.toml`) |
| `pixi.toml` | — | **delete** |
| `notebooks/_helpers/__init__.py` | Re-export public API (back-compat shim) | create |
| `notebooks/_helpers/config.py` | Thornforest constants: `PRIORITY_GROUPS`, `PLOT_WIDTH`, `WATERSHEDS`, `CONUS404_VARIABLES` | create |
| `notebooks/_helpers/session.py` | `find_repo_root`, `Session`, `init_session` | create (from `_helpers.py`) |
| `notebooks/_helpers/io.py` | `save_outputs`, `save_datacube` | create (from `_helpers.py`) |
| `notebooks/_helpers/viz.py` | `show`, `set_plot_defaults`, `CATEGORICAL`, `categorical_colors`, `make_legend_clickable` | create (from `_helpers.py`) |
| `notebooks/_helpers/analysis.py` | `water_year`, `mk_sen_trend`, `coverage` | create (from `_helpers.py` + NB3) |
| `notebooks/_helpers/usgs.py` | `classify_parameter`, `build_parameter_name_lookup`, `station_parameters`, `fetch_*`, `tidy_*` | create (from NB3) |
| `notebooks/_helpers/climate.py` | CONUS404 constants + `conus404_monthly_grid`, `zonal_by_huc8`, `pixel_trend` | create (from `_helpers.py`) |
| `notebooks/_helpers.py` | — | **delete** (replaced by the package) |
| `notebooks/tests/test_*.py` | pytest unit tests | create/expand |
| `notebooks/{1,2,3}_usgs_*.py` | Notebook edits (promotion, titles, warnings, steps) | modify |
| `.gitignore`, `CLAUDE.md` | Doc/comment fixes + directive updates | modify |

---

## Task 1: Migrate `pixi.toml` → `pyproject.toml` (+ ruff, pytest config)

**Files:**
- Create: `pyproject.toml`
- Delete: `pixi.toml`
- Modify: `notebooks/_helpers.py:21` (`find_repo_root` marker)

**Interfaces:**
- Consumes: nothing.
- Produces: a working pixi env from `pyproject.toml`; `pixi run test`/`render`/`preview`; `find_repo_root(marker="pyproject.toml")`.

- [ ] **Step 1: Create the branch**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git checkout -b helpers-refactor round3-usgs-timeseries
```

- [ ] **Step 2: Write `pyproject.toml`**

Create `pyproject.toml` with exactly:

```toml
[tool.pixi.workspace]
authors = ["Anthony Aufdenkampe <aaufdenkampe@limno.com>"]
channels = ["conda-forge"]
name = "Thornforest"
platforms = ["osx-arm64", "win-64", "linux-64"]
version = "0.1.0"

[tool.pixi.tasks]
# Render the Quarto website into _site/ (executes notebooks as needed, refreshes _freeze/).
render = "quarto render"
preview = "quarto preview"
# Run the unit test suite.
test = "pytest"

[tool.pixi.dependencies]
python = "3.13.*"

# Data processing
geopandas = "*"
pyarrow = "*"
rioxarray = "*"
xarray = "*"
xvec = "*"
zarr = ">=3"

# Other Geospatial
gdal = "*"
libgdal-arrow-parquet = "*"
libgdal-xls = "*"
python-libarchive-c = "*"

# Remote Access
fsspec = "*"
python-dotenv = ">=1.2.2,<2"
s3fs = "*"
universal_pathlib = "*"

# USGS packages for data fetching
dataretrieval = "*"

# HyRiver packages for data fetching
hydrosignatures = ">=0.19"
pygeohydro = ">=0.19"
pygeoogc = ">=0.19"
pynhd = ">=0.19"

# Visualization
colorcet = ">=3.2.1,<4"
hvplot = "*"
geoviews = "*"

# Interactivity via Jupyter Notebooks
jupyter_bokeh = "*"
jupyterlab = "*"
jupytext = "*"

# Testing & linting
pytest = "*"
ruff = "*"

# Website rendering & analysis
quarto = ">=1.9.38,<2"
exactextract = ">=0.3.0,<0.4"
pymannkendall = ">=1.4.3,<2"

[tool.pixi.pypi-dependencies]
# Put pip-only requirements here if needed

[tool.pytest.ini_options]
testpaths = ["notebooks/tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 3: Delete `pixi.toml`**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && git rm pixi.toml
```

- [ ] **Step 4: Update the `find_repo_root` marker default**

In `notebooks/_helpers.py`, change the signature on line 21 from:

```python
def find_repo_root(marker="pixi.toml", start=None):
```
to:
```python
def find_repo_root(marker="pyproject.toml", start=None):
```
Also update the following line's docstring reference from `pixi.toml` to `pyproject.toml`.

- [ ] **Step 5: Verify the env solves and tasks work**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
pixi install 2>&1 | tail -3
pixi run test 2>&1 | tail -15
```
Expected: env solves from `pyproject.toml`; `pixi run test` runs pytest and the existing `notebooks/tests/test_save_outputs.py` passes. (`pixi.lock` regenerates — that is expected.)

- [ ] **Step 6: User review + commit gate**

Stage everything (`git add -A`) and STOP. The user reviews the working-tree diff and commits (suggested message: `Migrate pixi.toml to pyproject.toml; add ruff + pytest config`).

---

## Task 2: Split `_helpers.py` into the `_helpers/` package

Moves existing code verbatim into concern-based modules, applies the two `_helpers`-level PR-review fixes, and keeps `from _helpers import …` working via a re-export `__init__.py`. Behavior-preserving.

**Files:**
- Create: `notebooks/_helpers/{__init__,config,session,io,viz,analysis,climate}.py`
- Delete: `notebooks/_helpers.py`
- Modify: `notebooks/tests/test_save_outputs.py`

**Interfaces:**
- Consumes: `find_repo_root` (Task 1).
- Produces (public API re-exported by `__init__.py`): `find_repo_root`, `Session`, `init_session`, `save_outputs`, `save_datacube`, `show`, `set_plot_defaults`, `PLOT_WIDTH`, `CATEGORICAL`, `categorical_colors`, `make_legend_clickable`, `water_year`, `mk_sen_trend`, `conus404_monthly_grid`, `zonal_by_huc8`, `pixel_trend`. New: `config` constants.

- [ ] **Step 1: Create `config.py`**

Create `notebooks/_helpers/config.py`:

```python
"""Thornforest-specific constants. Kept separate from the generic helper modules so those
modules stay project-agnostic (they take these as arguments) and can later move to the shared
watershed-analysis-planning package unchanged.

PRIORITY_GROUPS is the project's grouping of USGS parameters/characteristics into the 11 target
variables — an explicitly-new blend, distinct from the verbatim source parameter names.
"""

# group -> {"parameter_codes": set[str], "characteristics": list[str] (lowercase substrings)}
PRIORITY_GROUPS = {
    "conductivity": {"parameter_codes": {"00095", "90095"}, "characteristics": ["specific conductance", "conductivity"]},
    "temperature": {"parameter_codes": {"00010"}, "characteristics": ["temperature, water"]},
    "dissolved_oxygen": {"parameter_codes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
    "dissolved_solids": {"parameter_codes": {"70300", "00515"}, "characteristics": ["total dissolved solids"]},
    "chlorophyll": {"parameter_codes": {"32209", "32210", "32211", "70953"}, "characteristics": ["chlorophyll", "algae"]},
    "pH": {"parameter_codes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classify_parameter)
    "nitrogen": {
        "parameter_codes": {"00600", "00605", "00608", "00613", "00615", "00618", "00620", "00625", "00630"},
        "characteristics": ["nitrogen", "nitrate", "nitrite", "ammonia", "kjeldahl"],
    },
    "phosphorus": {"parameter_codes": {"00650", "00665", "00666", "00671"}, "characteristics": ["phosphorus", "orthophosphate"]},
    "turbidity": {"parameter_codes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
    # Water quantity (flow & level)
    "discharge": {
        "parameter_codes": {"00060", "00061", "00055", "70232", "30208", "30209"},  # discharge + velocity
        "characteristics": ["discharge", "stream flow", "streamflow"],
    },
    "water_level": {
        "parameter_codes": {"00065", "00062", "00054", "62611", "62614", "62615", "63160", "72019", "72020", "72148", "72150", "72170"},
        "characteristics": ["gage height", "stream stage", "water level", "water-surface elevation"],
    },
}
PRIORITY_NAMES = list(PRIORITY_GROUPS)

# The three study watersheds (HUC-8 code -> name).
WATERSHEDS = {
    "12110208": "South Laguna Madre",
    "13090001": "Los Olmos",
    "13090002": "Lower Rio Grande",
}

# Plot frame width (px), tuned to fit the Quarto cosmo content column incl. toolbar.
# Lower it (or widen body-width) if any page side-scrolls.
PLOT_WIDTH = 600

# CONUS404 variables (Task 5 populates the derived-label mapping).
CONUS404_VARIABLES = {}
```

- [ ] **Step 2: Create `session.py`**

Create `notebooks/_helpers/session.py` by moving `find_repo_root` (with the Task-1 `pyproject.toml` marker), the `Session` dataclass, and `init_session` from `_helpers.py` verbatim. Add the `find_repo_root` not-found warning (PR-review #7): replace the final `return start` with:

```python
    print(f"WARNING: {marker} not found walking up from {start}; using it as repo root.")
    return start
```
`init_session` must `from .viz import set_plot_defaults` (it calls it) and keep `set_plot_defaults()` before building the `Session`. Header imports: `import os`, `from dataclasses import dataclass`, `from pathlib import Path`, `from dotenv import load_dotenv`.

- [ ] **Step 3: Create `io.py` with the `save_outputs` public-isinstance fix**

Create `notebooks/_helpers/io.py`. Move `save_datacube` verbatim. Move `save_outputs` but replace the private-attribute check (PR-review #6). Full `save_outputs`:

```python
from pathlib import Path

from .session import find_repo_root


def save_outputs(df, parquet_path):
    """Save a (Geo)DataFrame two ways for transparency: parquet (compact, typed) + a CSV copy.

    - GeoDataFrame: GeoParquet + CSV with geometry written as WKT, geometry column moved to the
      end so the table reads cleanly in any software.
    - Plain pandas DataFrame (no geometry): a standard (non-Geo) parquet + CSV, columns unchanged.

    Side-effect helper — prints a confirmation and returns nothing (so it never accidentally
    renders a table when it is the last line of a notebook cell)."""
    import geopandas as gpd

    if isinstance(df, gpd.GeoDataFrame) and df.active_geometry_name is not None:
        name = df.geometry.name
        ordered = df[[c for c in df.columns if c != name] + [name]]
    else:
        ordered = df

    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_parquet(parquet_path)
    ordered.to_csv(parquet_path.with_suffix(".csv"), index=False)  # geometry -> WKT when GeoDataFrame

    try:
        shown = parquet_path.relative_to(find_repo_root())
    except ValueError:
        shown = parquet_path
    print(f"saved {len(ordered)} rows → {shown} (+ .csv)")
```
`save_datacube` keeps its lazy `import zarr` and body unchanged.

- [ ] **Step 4: Create `viz.py`**

Create `notebooks/_helpers/viz.py`. Move `show`, `set_plot_defaults`, `CATEGORICAL`, `categorical_colors`, `make_legend_clickable` verbatim. Import `PLOT_WIDTH` from config and drop the stale "see Task 3 verification" comment:

```python
import colorcet as cc
from IPython.display import HTML

from .config import PLOT_WIDTH
```
`set_plot_defaults(width=PLOT_WIDTH)` keeps its lazy `import holoviews as hv` and body. `CATEGORICAL = cc.b_glasbey_category10` and the other functions move verbatim.

- [ ] **Step 5: Create `analysis.py`**

Create `notebooks/_helpers/analysis.py`. Move `water_year` and `mk_sen_trend` verbatim (keep their lazy imports). Leave `coverage` for Task 3 (imported from NB3 then). Add a module docstring noting these are generic, source-agnostic analysis utilities.

- [ ] **Step 6: Create `climate.py`**

Create `notebooks/_helpers/climate.py`. Move the CONUS404 block verbatim: `CONUS404_MONTHLY_ZARR`, `CONUS404_ENDPOINT`, `CONUS404_VARS`, `conus404_monthly_grid`, `zonal_by_huc8`, `pixel_trend`. `pixel_trend` calls `mk_sen_trend` — add `from .analysis import mk_sen_trend`. It calls `save_datacube` — add `from .io import save_datacube`. Keep all other imports lazy inside the functions.

- [ ] **Step 7: Create the `__init__.py` re-export shim**

Create `notebooks/_helpers/__init__.py`:

```python
"""Shared helpers for the Thornforest notebooks, organized into focused modules.

Import from the package root — the public API is re-exported here so notebooks use
`from _helpers import save_outputs, show, init_session, ...` regardless of which module
a helper lives in. The leading underscore makes Quarto ignore this package when rendering.

Generic modules (session, io, viz, analysis, usgs, climate) are project-agnostic and take
project constants as arguments; Thornforest-specific constants live in `config`.
"""

from . import config
from .analysis import coverage, mk_sen_trend, water_year
from .climate import conus404_monthly_grid, pixel_trend, zonal_by_huc8
from .config import CONUS404_VARIABLES, PLOT_WIDTH, PRIORITY_GROUPS, PRIORITY_NAMES, WATERSHEDS
from .io import save_datacube, save_outputs
from .session import Session, find_repo_root, init_session
from .usgs import (
    build_parameter_name_lookup,
    classify_parameter,
    fetch_daily,
    fetch_field,
    fetch_samples,
    station_parameters,
    tidy_daily,
    tidy_field,
    tidy_samples,
)
from .viz import (
    CATEGORICAL,
    categorical_colors,
    make_legend_clickable,
    set_plot_defaults,
    show,
)

__all__ = [
    "config", "CONUS404_VARIABLES", "PLOT_WIDTH", "PRIORITY_GROUPS", "PRIORITY_NAMES", "WATERSHEDS",
    "find_repo_root", "Session", "init_session",
    "save_outputs", "save_datacube",
    "show", "set_plot_defaults", "CATEGORICAL", "categorical_colors", "make_legend_clickable",
    "water_year", "mk_sen_trend", "coverage",
    "classify_parameter", "build_parameter_name_lookup", "station_parameters",
    "fetch_daily", "fetch_samples", "fetch_field", "tidy_daily", "tidy_samples", "tidy_field",
    "conus404_monthly_grid", "zonal_by_huc8", "pixel_trend",
]
```
Note: this imports `analysis.coverage` and the `usgs` symbols, which are created in Tasks 3–4. To keep Task 2 self-contained and importable, first create **stub** `notebooks/_helpers/usgs.py` and add `coverage` now:
  - Add `coverage` to `analysis.py` in this task (moved from NB3 lines 409-420, verbatim) so `analysis` is complete.
  - Create `notebooks/_helpers/usgs.py` with the real `classify_parameter`, `build_parameter_name_lookup`, and `station_parameters` **now** (moved from NB3 — see Task 3 for their exact bodies), plus temporary `def fetch_daily(*a, **k): raise NotImplementedError` (and `fetch_samples`, `fetch_field`, `tidy_daily`, `tidy_samples`, `tidy_field`) so imports resolve. Task 4 replaces the stubs with real implementations + tests.

(This ordering keeps every task's tree importable while still splitting the review gates: Task 2 = mechanical split + `_helpers` fixes, Task 3 = USGS classification tests, Task 4 = fetch/tidy.)

- [ ] **Step 8: Delete the old module**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && git rm notebooks/_helpers.py
```

- [ ] **Step 9: Improve the `save_outputs` GeoDataFrame test (PR-review #3)**

Replace `notebooks/tests/test_save_outputs.py` with (adds a geometry-**first** fixture so the reorder is actually exercised, and asserts WKT in the CSV):

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import _helpers from notebooks/
from _helpers import save_outputs


def test_save_outputs_plain_dataframe(tmp_path):
    df = pd.DataFrame({"station": ["A", "B"], "value": [1.0, 2.0]})
    out = tmp_path / "sub" / "table.parquet"

    assert save_outputs(df, out) is None  # side-effect helper returns nothing
    assert out.exists()
    assert out.with_suffix(".csv").exists()
    pd.testing.assert_frame_equal(pd.read_parquet(out), df)


def test_save_outputs_geodataframe_moves_geometry_last_and_writes_wkt(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Point

    # geometry FIRST so the reorder-to-last is genuinely exercised.
    gdf = gpd.GeoDataFrame(
        {"geometry": [Point(0, 0), Point(1, 1)], "id": ["a", "b"], "value": [1, 2]},
        crs="EPSG:4326",
    )
    out = tmp_path / "geo.parquet"
    save_outputs(gdf, out)

    back = gpd.read_parquet(out)
    assert list(back.columns)[-1] == "geometry"  # geometry moved last
    assert list(back.columns)[:2] == ["id", "value"]  # non-geometry order preserved

    csv = pd.read_csv(out.with_suffix(".csv"))
    assert list(csv.columns)[-1] == "geometry"
    assert str(csv["geometry"].iloc[0]).upper().startswith("POINT")  # geometry -> WKT
```

- [ ] **Step 10: Run the tests and a notebook-import smoke check**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
pixi run test 2>&1 | tail -20
pixi run python -c "import sys; sys.path.insert(0,'notebooks'); import _helpers; print('exports ok:', 'save_outputs' in dir(_helpers), 'init_session' in dir(_helpers))"
```
Expected: both `save_outputs` tests pass; the import prints `exports ok: True True`.

- [ ] **Step 11: Confirm Quarto still ignores the package**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run render 2>&1 | grep -iE "output created|error" | tail -3
ls _site/notebooks/*.html
```
Expected: `Output created`; `_site/notebooks/` has only the three notebook pages (no `_helpers` page).

- [ ] **Step 12: User review + commit gate** — stage (`git add -A`) and STOP for review/commit (suggested: `Split _helpers.py into the _helpers/ package + save_outputs fixes`).

---

## Task 3: Promote USGS classification to `usgs.py` with tests

Replaces the Task-2 real moves with test coverage and confirms the promoted classification behaves identically. (The functions were physically moved in Task 2 to keep the tree importable; this task locks them with TDD and injects `groups`.)

**Files:**
- Modify: `notebooks/_helpers/usgs.py`
- Create: `notebooks/tests/test_usgs_classify.py`, `notebooks/tests/test_analysis.py`

**Interfaces:**
- Consumes: `config.PRIORITY_GROUPS`.
- Produces: `classify_parameter(parameter_code=None, characteristic=None, groups=PRIORITY_GROUPS) -> str | None`; `build_parameter_name_lookup() -> dict[str,str]` (network); `station_parameters(sid, ts_codes_by_site, fm_codes_by_site, name_lookup, samples_summaries, groups=PRIORITY_GROUPS) -> tuple[set,list]`; `coverage(df, time_col) -> DataFrame`.

- [ ] **Step 1: Finalize `classify_parameter` with an injected `groups`**

In `notebooks/_helpers/usgs.py`, ensure the top imports and function read:

```python
import warnings

import pandas as pd

from .config import PRIORITY_GROUPS


def classify_parameter(parameter_code=None, characteristic=None, groups=PRIORITY_GROUPS):
    """Return the priority group for a USGS parameter_code or a WQ characteristic name, else None.

    `groups` maps group name -> {"parameter_codes": set[str], "characteristics": [substrings]}.
    pH is matched EXACTLY on the characteristic to avoid the 'ph' substring matching e.g. 'phosphorus'.
    USGS parameter-code reference: https://help.waterdata.usgs.gov/codes-and-parameters/parameters
    """
    if parameter_code is not None:
        parameter_code = str(parameter_code).strip().zfill(5)
        for group, spec in groups.items():
            if parameter_code in spec["parameter_codes"]:
                return group
    if characteristic is not None:
        name = str(characteristic).strip().lower()
        if name == "ph":
            return "pH"
        for group, spec in groups.items():
            if group == "pH":
                continue
            if any(pat in name for pat in spec["characteristics"]):
                return group
    return None
```

- [ ] **Step 2: Write the classifier test**

Create `notebooks/tests/test_usgs_classify.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import classify_parameter


def test_classify_by_parameter_code_zero_pads():
    assert classify_parameter(parameter_code="60") == "discharge"      # 00060, zero-padded
    assert classify_parameter(parameter_code="00010") == "temperature"


def test_classify_by_characteristic_substring():
    assert classify_parameter(characteristic="Dissolved oxygen (DO)") == "dissolved_oxygen"
    assert classify_parameter(characteristic="Turbidity, FNU") == "turbidity"


def test_ph_matches_exactly_not_as_substring():
    assert classify_parameter(characteristic="pH") == "pH"
    assert classify_parameter(characteristic="Phosphorus as P") == "phosphorus"  # not pH


def test_unknown_returns_none():
    assert classify_parameter(parameter_code="99999") is None
    assert classify_parameter(characteristic="Fecal coliform") is None
    assert classify_parameter() is None
```

- [ ] **Step 3: Run the classifier test**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run test -k classify -v 2>&1 | tail -15
```
Expected: 4 passed.

- [ ] **Step 4: Confirm `build_parameter_name_lookup` and `station_parameters` are present**

In `notebooks/_helpers/usgs.py` ensure these exist (moved from NB3), with `groups` injected and no notebook-global dependencies:

```python
def build_parameter_name_lookup():
    """parameter_code (str) -> readable name, from the USGS 'parameter-codes' reference table.
    Names are carried verbatim from the source table (source-term fidelity)."""
    from dataretrieval import waterdata

    table, _ = waterdata.get_reference_table("parameter-codes")
    return dict(zip(table["parameter_code"].astype(str), table["parameter_name"]))


def parameter_name(code, name_lookup):
    """Look up a code's verbatim source name, trying the 5-digit zero-padded form first.
    Falls back to the raw code (caller should audit codes that fall through)."""
    code = str(code)
    return name_lookup.get(code.zfill(5), name_lookup.get(code, code))


def station_parameters(sid, ts_codes_by_site, fm_codes_by_site, name_lookup,
                       samples_summaries, groups=PRIORITY_GROUPS):
    """Return (priority_groups: set[str], parameter_names: sorted list[str]) for one station,
    combining time-series/field parameter codes with discrete-sample characteristics."""
    found_groups, names = set(), set()
    for code in ts_codes_by_site.get(sid, set()) | fm_codes_by_site.get(sid, set()):
        names.add(parameter_name(code, name_lookup))
        g = classify_parameter(parameter_code=code, groups=groups)
        if g:
            found_groups.add(g)
    summary = samples_summaries.get(sid)
    if summary is not None and "characteristic" in summary.columns:
        for char in summary["characteristic"].dropna().unique():
            names.add(str(char))
            g = classify_parameter(characteristic=char, groups=groups)
            if g:
                found_groups.add(g)
    return found_groups, sorted(names)
```

- [ ] **Step 5: Write the analysis-utilities tests**

Create `notebooks/tests/test_analysis.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import coverage, mk_sen_trend, water_year


def test_water_year_october_boundary():
    wy = water_year(pd.to_datetime(["2020-09-30", "2020-10-01", "2021-01-15"]))
    assert list(wy) == [2020, 2021, 2021]


def test_mk_sen_trend_insufficient_under_four_points():
    assert mk_sen_trend([1, 2, 3])["trend"] == "insufficient"


def test_mk_sen_trend_detects_increase():
    r = mk_sen_trend([1, 2, 3, 4, 5, 6])
    assert r["trend"] == "increasing"
    assert r["slope"] > 0


def test_coverage_counts_and_span_per_group():
    df = pd.DataFrame({
        "monitoring_location_id": ["A", "A", "A"],
        "priority_group": ["discharge", "discharge", "discharge"],
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01"]),
    })
    out = coverage(df, "date")
    row = out.iloc[0]
    assert row["n"] == 3
    assert row["start"].year == 2001 and row["end"].year == 2003
```
Confirm `coverage` in `analysis.py` (moved from NB3) matches this contract: groups by `["monitoring_location_id", "priority_group"]` and aggregates `n="size", start="min", end="max"` on `pd.to_datetime(df[time_col])`.

- [ ] **Step 6: Run all tests**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run test 2>&1 | tail -20
```
Expected: all pass (save_outputs ×2, classify ×4, analysis ×4).

- [ ] **Step 7: User review + commit gate** — stage and STOP (suggested: `Promote USGS classification + analysis utils with pytest coverage`).

---

## Task 4: `fetch_*` / `tidy_*` USGS time-series functions (+ warning fixes)

Replaces the Task-2 stubs with the thin-fetch / pure-tidy split, folding in the empty-list guard, the `huc8`-NaN warning, the samples `DtypeWarning` suppression, and the `PerformanceWarning` fix.

**Files:**
- Modify: `notebooks/_helpers/usgs.py`
- Create: `notebooks/tests/test_usgs_tidy.py`

**Interfaces:**
- Consumes: `classify_parameter`, `parameter_name`, `config.PRIORITY_GROUPS`.
- Produces: `fetch_daily(station_ids, parameter_codes)`, `fetch_samples(station_ids)`, `fetch_field(station_ids, parameter_codes)` → raw DataFrame; `tidy_daily(raw, huc8_by_station, name_lookup, groups=PRIORITY_GROUPS)`, `tidy_samples(raw, huc8_by_station, groups=PRIORITY_GROUPS)`, `tidy_field(raw, huc8_by_station, name_lookup, groups=PRIORITY_GROUPS)` → tidy long-format DataFrame with fixed columns.

- [ ] **Step 1: Add the column constants and shared guards**

In `notebooks/_helpers/usgs.py` add near the top (after imports):

```python
DAILY_COLUMNS = ["monitoring_location_id", "date", "parameter_code", "parameter_name",
                 "statistic", "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
SAMPLES_COLUMNS = ["monitoring_location_id", "datetime", "characteristic", "parameter_code", "value",
                   "unit", "fraction", "detection_condition", "qualifier", "characteristic_group",
                   "lab_name", "priority_group", "huc8"]
FIELD_COLUMNS = ["monitoring_location_id", "datetime", "parameter_code", "parameter_name", "value",
                 "unit", "qualifier", "approval_status", "priority_group", "huc8"]


def _warn_missing_huc8(df, label):
    """Warn (don't silently drop) if the huc8 join produced NaN — signals a station-id mismatch."""
    missing = df["huc8"].isna()
    if missing.any():
        ids = sorted(df.loc[missing, "monitoring_location_id"].unique())[:10]
        print(f"WARNING: {int(missing.sum())} {label} rows had no huc8 match; unmatched ids: {ids}")
    return df
```

- [ ] **Step 2: Write the `fetch_*` wrappers (empty-guard + DtypeWarning suppression)**

Append to `usgs.py`:

```python
def fetch_daily(station_ids, parameter_codes):
    """Fetch the full daily-values record for the given stations & parameter codes (raw response).
    Docs: https://api.waterdata.usgs.gov/  (dataretrieval.waterdata.get_daily)"""
    from dataretrieval import waterdata

    if not station_ids:
        print("no daily stations — returning empty frame")
        return pd.DataFrame()
    raw, _ = waterdata.get_daily(
        monitoring_location_id=list(station_ids), parameter_code=list(parameter_codes), skip_geometry=True
    )
    return raw


def fetch_field(station_ids, parameter_codes):
    """Fetch the full field-measurements record (raw response)."""
    from dataretrieval import waterdata

    if not station_ids:
        print("no field-measurement stations — returning empty frame")
        return pd.DataFrame()
    raw, _ = waterdata.get_field_measurements(
        monitoring_location_id=list(station_ids), parameter_code=list(parameter_codes), skip_geometry=True
    )
    return raw


def fetch_samples(station_ids):
    """Fetch all discrete water-quality samples for the given stations (raw response).

    Suppresses the DtypeWarning raised *inside* dataretrieval's own pd.read_csv — the mixed-type
    columns it warns about (Activity_EndTime, Result_TimeBasis, DataQuality_PrecisionValue) are not
    ones we consume, and we cannot pass low_memory/dtype through the library call."""
    from dataretrieval import waterdata

    if not station_ids:
        print("no samples stations — returning empty frame")
        return pd.DataFrame()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)
        raw, _ = waterdata.get_samples(monitoring_location_id=list(station_ids))
    return raw
```

- [ ] **Step 3: Write the pure `tidy_*` transforms (single-assign, no fragmentation)**

Append to `usgs.py`:

```python
def tidy_daily(raw, huc8_by_station, name_lookup, groups=PRIORITY_GROUPS):
    """Rename → tag priority_group/parameter_name/huc8 → select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)
    renamed = raw.rename(columns={"time": "date", "statistic_id": "statistic", "unit_of_measure": "unit"})
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        parameter_name=lambda d: d["parameter_code"].map(lambda c: parameter_name(c, name_lookup)),
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[DAILY_COLUMNS].sort_values(
        ["monitoring_location_id", "parameter_code", "date"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "daily")


def tidy_field(raw, huc8_by_station, name_lookup, groups=PRIORITY_GROUPS):
    """Rename → tag → select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=FIELD_COLUMNS)
    renamed = raw.rename(columns={"time": "datetime", "unit_of_measure": "unit"})
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        parameter_name=lambda d: d["parameter_code"].map(lambda c: parameter_name(c, name_lookup)),
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[FIELD_COLUMNS].sort_values(
        ["monitoring_location_id", "parameter_code", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "field")


def tidy_samples(raw, huc8_by_station, groups=PRIORITY_GROUPS):
    """Rename → keep rows whose characteristic maps to a priority group → tag → select/sort.

    NOTE: `value` (Result_Measure) is a string (may hold non-detect/text results) — cast with
    pd.to_numeric(errors='coerce') before numeric ops. Columns are assigned in a single .assign to
    avoid the PerformanceWarning from repeatedly inserting into a wide frame. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=SAMPLES_COLUMNS)
    renamed = raw.rename(columns={
        "Location_Identifier": "monitoring_location_id", "Activity_StartDateTime": "datetime",
        "Result_Characteristic": "characteristic", "USGSpcode": "parameter_code",
        "Result_Measure": "value", "Result_MeasureUnit": "unit", "Result_SampleFraction": "fraction",
        "Result_ResultDetectionCondition": "detection_condition", "Result_MeasureQualifierCode": "qualifier",
        "Result_CharacteristicGroup": "characteristic_group", "LabInfo_Name": "lab_name",
    })
    priority = renamed["characteristic"].map(lambda c: classify_parameter(characteristic=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[SAMPLES_COLUMNS].sort_values(
        ["monitoring_location_id", "characteristic", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "samples")
```

- [ ] **Step 4: Write the tidy tests (fixtures mimic raw API columns; no network)**

Create `notebooks/tests/test_usgs_tidy.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_daily, tidy_field, tidy_samples

HUC8 = {"S1": "13090001"}
NAMES = {"00060": "Discharge, cubic feet per second"}


def test_tidy_daily_tags_and_orders():
    raw = pd.DataFrame({
        "monitoring_location_id": ["S1", "S1"],
        "time": ["2001-01-02", "2001-01-01"],
        "parameter_code": ["00060", "99999"],  # second row not a priority code -> dropped
        "statistic_id": ["00003", "00003"],
        "value": [10.0, 1.0],
        "unit_of_measure": ["ft3/s", "x"],
        "approval_status": ["Approved", "Approved"],
        "qualifier": [None, None],
    })
    out = tidy_daily(raw, HUC8, NAMES)
    assert list(out.columns) == [
        "monitoring_location_id", "date", "parameter_code", "parameter_name", "statistic",
        "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
    assert len(out) == 1  # non-priority row dropped
    assert out.iloc[0]["priority_group"] == "discharge"
    assert out.iloc[0]["parameter_name"] == "Discharge, cubic feet per second"
    assert out.iloc[0]["huc8"] == "13090001"


def test_tidy_samples_keeps_priority_characteristics_only():
    raw = pd.DataFrame({
        "Location_Identifier": ["S1", "S1"],
        "Activity_StartDateTime": ["2001-01-01", "2001-01-02"],
        "Result_Characteristic": ["Turbidity", "Fecal coliform"],  # 2nd -> no group -> dropped
        "USGSpcode": ["00076", "31625"],
        "Result_Measure": ["5", "10"],
        "Result_MeasureUnit": ["NTU", "cfu"],
        "Result_SampleFraction": [None, None],
        "Result_ResultDetectionCondition": [None, None],
        "Result_MeasureQualifierCode": [None, None],
        "Result_CharacteristicGroup": ["Physical", "Biological"],
        "LabInfo_Name": [None, None],
    })
    out = tidy_samples(raw, HUC8)
    assert len(out) == 1
    assert out.iloc[0]["priority_group"] == "turbidity"
    assert out.iloc[0]["huc8"] == "13090001"
    assert list(out.columns)[-2:] == ["priority_group", "huc8"]


def test_tidy_empty_returns_typed_empty():
    assert list(tidy_field(pd.DataFrame(), HUC8, NAMES).columns)[0] == "monitoring_location_id"
    assert len(tidy_field(pd.DataFrame(), HUC8, NAMES)) == 0
```

- [ ] **Step 5: Run the tidy tests**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run test -k tidy -v 2>&1 | tail -20
```
Expected: 3 passed.

- [ ] **Step 6: Full suite green**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run test 2>&1 | tail -8
```
Expected: all tests pass.

- [ ] **Step 7: User review + commit gate** — stage and STOP (suggested: `Add fetch_/tidy_ USGS time-series helpers with tests; fix NB3 warnings`).

---

## Task 5: CONUS404 source-term fidelity

Preserve original CONUS404 variable names + source attributes; document derived labels in `config.CONUS404_VARIABLES`; guard the fidelity with a `save_datacube` attrs test.

**Files:**
- Modify: `notebooks/_helpers/config.py`, `notebooks/_helpers/io.py` (only if attrs are not preserved)
- Create: `notebooks/tests/test_save_datacube_attrs.py`

**Interfaces:**
- Consumes: `save_datacube`.
- Produces: `config.CONUS404_VARIABLES` mapping `original_name -> {derived_label, derivation}`; a verified `save_datacube` that preserves variable `attrs`.

- [ ] **Step 1: Populate `CONUS404_VARIABLES` (derived labels only; source descriptions stay in the cube)**

In `notebooks/_helpers/config.py` replace `CONUS404_VARIABLES = {}` with:

```python
# CONUS404 source variable -> our derived presentation label + how we derive it.
# Source names, long_name descriptions, and units are carried verbatim from the dataset's own
# variable attributes (see NB2) — NOT paraphrased here. Docs:
# https://www.usgs.gov/data/conus404-40-years-daily-4-km-resolution-conus-model-simulation-output
CONUS404_VARIABLES = {
    "PREC_ACC_NC": {"derived_label": "precip_mm", "derivation": "monthly precip accumulation (mm); sum 12 → water-year total"},
    "ACETLSM":     {"derived_label": "et_mm", "derivation": "monthly ET accumulation (mm); sum 12 → water-year total"},
    "ACRUNSF":     {"derived_label": "surf_runoff_mm", "derivation": "monthly surface-runoff accumulation (mm)"},
    "ACRUNSB":     {"derived_label": "subsurf_runoff_mm", "derivation": "monthly subsurface-runoff accumulation (mm)"},
    "RECH":        {"derived_label": "recharge_mm", "derivation": "monthly recharge accumulation (mm)"},
    "SMOIS":       {"derived_label": "soil_moisture_m3m3", "derivation": "surface soil-layer volumetric moisture (m³/m³)"},
    "SNOW":        {"derived_label": "snow_kgm2", "derivation": "snow water equivalent (kg/m²)"},
    "CANWAT":      {"derived_label": "canopy_water_kgm2", "derivation": "canopy water (kg/m²)"},
    "T2":          {"derived_label": "t2_degc", "derivation": "2 m air temperature, converted K → °C"},
    "TD2":         {"derived_label": "td2_degc", "derivation": "2 m dewpoint, converted K → °C"},
    "Q2":          {"derived_label": "q2_kgkg", "derivation": "2 m water-vapor mixing ratio (kg/kg)"},
}
```
Add `CONUS404_VARIABLES` to the `__init__.py` re-export if not already present (it is, from Task 2).

- [ ] **Step 2: Write the attrs-preservation test**

Create `notebooks/tests/test_save_datacube_attrs.py`:

```python
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import save_datacube


def test_save_datacube_preserves_variable_attrs(tmp_path):
    ds = xr.Dataset(
        {"PREC_ACC_NC": (("time", "y", "x"), np.ones((2, 2, 2)))},
        coords={"time": [0, 1], "y": [0, 1], "x": [0, 1]},
    )
    ds["PREC_ACC_NC"].attrs = {"long_name": "ACCUMULATED TOTAL GRID SCALE PRECIPITATION", "units": "mm"}

    out = save_datacube(ds, tmp_path / "cube.zarr")

    back = xr.open_zarr(out)
    assert back["PREC_ACC_NC"].attrs["long_name"] == "ACCUMULATED TOTAL GRID SCALE PRECIPITATION"
    assert back["PREC_ACC_NC"].attrs["units"] == "mm"
```

- [ ] **Step 3: Run it; fix `save_datacube` only if it fails**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest && pixi run test -k datacube_attrs -v 2>&1 | tail -15
```
Expected: PASS (current `save_datacube` clears `encoding`, not `attrs`, so attrs should survive). If it FAILS, ensure `save_datacube` only clears `ds[var].encoding` and never touches `ds[var].attrs`.

- [ ] **Step 4: User review + commit gate** — stage and STOP (suggested: `Add CONUS404 source-term mapping + save_datacube attrs test`).

---

## Task 6: Update the notebooks (use helpers, show intermediates, fix titles/steps/doc-rot)

**Files:**
- Modify: `notebooks/3_usgs_waterdata.py`, `notebooks/2_usgs_climate.py`, `notebooks/1_usgs_hydrography.py`, `.gitignore`

**Interfaces:**
- Consumes: the `_helpers` package public API (Tasks 2–5).
- Produces: executed notebooks whose committed outputs + rendered site reflect the refactor.

- [ ] **Step 1: NB3 — import promoted helpers, drop local definitions**

In `notebooks/3_usgs_waterdata.py`:
- Extend the `_helpers` import to include: `PRIORITY_GROUPS, PRIORITY_NAMES, classify_parameter, build_parameter_name_lookup, station_parameters, fetch_daily, fetch_samples, fetch_field, tidy_daily, tidy_samples, tidy_field, coverage`.
- Delete the local `PRIORITY_GROUPS`/`PRIORITY_NAMES` block (old lines 100-125), the local `classify_parameter` (128-144), the local `station_parameters` (187-207), the local `_parameter_name` (274-276), and the local `coverage` (409-420).
- Replace the reference-table lookup (176-179) with `parameter_name_by_code = build_parameter_name_lookup()`.
- Update `station_parameters` call sites (211-214) to pass the now-explicit args: `station_parameters(sid, ts_parameter_codes_by_site, fm_parameter_codes_by_site, parameter_name_by_code, samples_summaries)`.

- [ ] **Step 2: NB3 — replace the three inline fetch cells with fetch/tidy + shown intermediates**

Replace the Daily/Samples/Field cells (old lines 283-368) with, for each data type, a markdown + code pair that shows the raw response then the tidy result. Daily example (mirror for samples/field using `fetch_samples`/`tidy_samples` and `fetch_field`/`tidy_field`):

```python
# %%
daily_station_ids = stations_in_area.loc[stations_in_area["daily"], "monitoring_location_id"].tolist()
daily_raw = fetch_daily(daily_station_ids, PRIORITY_CODES)
show(daily_raw.head())  # peek at the raw USGS response shape before we tidy it

# %%
# Tidy to a long-format table tagged with priority_group / parameter_name / huc8 (see _helpers/usgs.py).
daily = tidy_daily(daily_raw, huc8_by_station, parameter_name_by_code)
show(daily.head())
save_outputs(daily, S.data_dir / "usgs_waterdata" / "usgs_daily_values.parquet")
```
For samples: `samples_raw = fetch_samples(samples_station_ids)`; `samples = tidy_samples(samples_raw, huc8_by_station)`. For field: `field_raw = fetch_field(field_station_ids, PRIORITY_CODES)`; `field = tidy_field(field_raw, huc8_by_station, parameter_name_by_code)`. Keep the existing markdown intro for each, adding a sentence + link to the WaterData docs (<https://api.waterdata.usgs.gov/>).

- [ ] **Step 3: NB3 — fix the H1 title and renumber the steps sequentially**

- Line 17: `# # 2 · USGS WaterData …` → `# # 3 · USGS WaterData — Monitoring Stations, Parameters & Time-Series`.
- Renumber the `## Step N` markdown headers so they ascend without gaps (current 1, 5, 6, 7, 8, 10 → 1, 2, 3, 4, 5, 6, …). Keep the order; only the integers change.

- [ ] **Step 4: NB2 — source-term mapping + H1 title**

In `notebooks/2_usgs_climate.py`:
- Line 17: `# # 3 · CONUS404 Climate …` → `# # 2 · CONUS404 Climate — Spatial Patterns & Water-Balance Trends`.
- Import `CONUS404_VARIABLES` from `_helpers`. Where the notebook renames CONUS404 vars to friendly labels, drive the rename from `CONUS404_VARIABLES` and add a markdown cell that displays a table of `original_name`, the source `long_name`/`units` (read from the cube's `ds[var].attrs`), the `derived_label`, and the `derivation` — so the source vocabulary is shown verbatim. Link to the CONUS404 dataset page.
- Reconcile the raw-cube size text (`~80 MB`) with the actual on-disk size:
  ```bash
  du -sh data/climate/conus404_monthly_grid.zarr
  ```
  Set the notebook prose, README, and CLAUDE.md to the measured value.

- [ ] **Step 5: NB1 — fix the H1 title**

In `notebooks/1_usgs_hydrography.py` line 17: `# # 1 · USGS Hydrofabric …` → `# # 1 · USGS Hydrography — Watershed Boundaries & Context`.

- [ ] **Step 6: Fix the `.gitignore` comment**

In `.gitignore`, change the CONUS404 cube comment `… regenerated from OSN by NB3.` → `… regenerated from OSN by NB2.`

- [ ] **Step 7: Sync, execute, and render all three notebooks**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
for nb in 1_usgs_hydrography 2_usgs_climate 3_usgs_waterdata; do pixi run jupytext --sync notebooks/$nb.py; done
for nb in 1_usgs_hydrography 2_usgs_climate 3_usgs_waterdata; do \
  pixi run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/$nb.ipynb 2>&1 | grep -iE "writing|error|traceback|warning" | tail -6; done
pixi run render 2>&1 | grep -iE "output created|error" | tail -3
```
Expected: each notebook writes with no traceback; crucially **no `DtypeWarning` and no `PerformanceWarning`** in NB3's output; `Output created`.

- [ ] **Step 8: Verify page titles and data products**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
grep -oE "<title>[^<]+</title>" _site/notebooks/*.html
pixi run python -c "
import pandas as pd
for n in ['usgs_daily_values','usgs_samples','usgs_field_measurements']:
    df = pd.read_parquet(f'data/usgs_waterdata/{n}.parquet')
    assert df['priority_group'].notna().all() and df['huc8'].notna().any(), n
    print(n, len(df))
"
```
Expected: titles read "1 · … Hydrography", "2 · … Climate", "3 · … WaterData" (numbers match filenames); the three products rebuild non-empty with valid `priority_group`/`huc8`.

- [ ] **Step 9: User review + commit gate** — stage `notebooks/`, `data/usgs_waterdata/`, `.gitignore`, `_freeze/` and STOP (suggested: `Refactor notebooks onto _helpers package; fix titles, steps, warnings, doc-rot`).

---

## Task 7: Update `CLAUDE.md`

Apply the standing-directive changes now that their underlying changes exist. (The source-term-fidelity guardrail was already added.)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Flip the test-suite guardrail**

Replace the guardrail bullet:
```
- **No formal test suite** — verify by executing notebooks headlessly + rendering, not pytest. See
  [Commands](#commands) and [Workflow](#workflow).
```
with:
```
- **Tests run via `pixi run test` (pytest).** Verification is the pytest suite **plus** executing
  notebooks headlessly + `pixi run render`. See [Commands](#commands) and [Workflow](#workflow).
```

- [ ] **Step 2: Update the Commands + environment references**

In the Commands section, change the manifest reference from `pixi.toml` to `pyproject.toml` (both the prose and the `([pixi.toml](pixi.toml))` link → `([pyproject.toml](pyproject.toml))`), and add:
```
pixi run test                                                  # run the pytest unit suite
```
Update the Workflow "Verification" bullet to mention pytest alongside notebook execution + render.

- [ ] **Step 3: Update the helpers reference**

In the "Notebooks & helpers" section, change the `[`notebooks/_helpers.py`]` reference to the `notebooks/_helpers/` package, and add a short line: modules are concern-based and generic (`session`, `io`, `viz`, `analysis`, `usgs`, `climate`) with Thornforest constants in `config.py` injected as arguments; `usgs` splits fetching into `fetch_*` (network) + `tidy_*` (pure); the `__init__.py` re-exports so `from _helpers import …` is unchanged.

- [ ] **Step 4: Add the teaching directive**

Add a general bullet under "Notebooks & helpers": notebooks **show intermediate results** (e.g. `show(raw.head())` on API responses) and **link to primary documentation**, for the new-contributor audience.

- [ ] **Step 5: Verify no stale references remain**

```bash
cd /Users/aaufdenkampe/Documents/git_Limno/Thornforest
git grep -nE "pixi\.toml|No formal test suite|_helpers\.py" -- CLAUDE.md
```
Expected: no matches except intentional historical mentions (there should be none in the guardrails/commands/helpers sections).

- [ ] **Step 6: User review + commit gate** — stage `CLAUDE.md` and STOP (suggested: `Update CLAUDE.md: pytest, pyproject, _helpers package, teaching directives`).

---

## Self-Review

**Spec coverage:**
- Package split + `__init__` re-export → Task 2. ✓
- Generic/project seam (`config.py`, injected `groups`) → Tasks 2–4. ✓
- Teaching-first + fetch/tidy split + shown intermediates → Task 4 (functions), Task 6 (notebooks). ✓
- Source-term fidelity (USGS verbatim kept; CONUS404 mapping + attrs) → Tasks 3–5. ✓
- pytest adoption (config, task, TDD of pure functions) → Task 1 (config) + Tasks 2–5 (tests). ✓
- `pixi.toml` → `pyproject.toml` (+ ruff) → Task 1. ✓
- PR-review fixes: `save_outputs` isinstance (T2), `find_repo_root` warning (T2), huc8 NaN guard (T4), empty-list guards (T4), samples `DtypeWarning` (T4), `PerformanceWarning` (T4), test improvements (T2), stale H1 titles + `.gitignore` + step renumber + size reconciliation + PLOT_WIDTH comment (T2/T6). ✓
- CLAUDE.md directives → Task 7 (+ source-term guardrail already added). ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; the only intentional deferrals are the Task-2 `usgs` stubs, which Task 4 replaces (explicitly noted).

**Type consistency:** `classify_parameter(parameter_code, characteristic, groups)`, `tidy_*(raw, huc8_by_station[, name_lookup], groups)`, and the `DAILY_COLUMNS`/`SAMPLES_COLUMNS`/`FIELD_COLUMNS` orders match between the implementations (Task 4) and the tests (Task 4) and the notebook call sites (Task 6). `__init__.py` re-exports match the module symbol names.
