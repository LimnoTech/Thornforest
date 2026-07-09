# Excel Workbook Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile every saved table into one downloadable `.xlsx` workbook per `data/` subfolder
(one sheet per table, frozen first row/column, autofilter on headers), generated from each
notebook's own in-memory DataFrames, committed to `data/`, and linked directly from the home page.

**Architecture:** One new generic helper (`_helpers/excel.py::save_workbook`) writes an ordered
`{sheet_name: dataframe}` dict to one `.xlsx` via `pandas.ExcelWriter(engine="openpyxl")`, applying
`freeze_panes`/`auto_filter` per sheet and converting any GeoDataFrame's geometry to WKT text
first. Each of the 5 fetch notebooks calls it once, as their final step, building the dict from
DataFrames already in scope — no new fetches, no CSV re-reads. `_quarto.yml` gains a `resources:`
entry so the committed `.xlsx` files are copied into the published site, and `index.qmd` gets a
new "Downloads" section linking to all 5.

**Tech Stack:** `openpyxl` (already a pyproject.toml dependency), `pandas.ExcelWriter`, `geopandas`.

## Global Constraints

- **Storage:** the `.xlsx` files are a third **committed** output format alongside the existing
  parquet + CSV, per this repo's "data/ outputs are committed" convention — not gitignored.
- **Notebooks:** edit the paired `.py` (jupytext percent format), never the `.ipynb`; after any
  edit run `pixi run jupytext --sync notebooks/<name>.py`.
- **Tests:** `pixi run test` (pytest, `notebooks/tests/`).
- **Never commit or push.** Leave all changes staged/on-disk. Per this repo's workflow, each task
  group below is a gate: implement the group, run its tests/verification, leave the working-tree
  diff staged, and stop for the user to review and commit before the next group starts.
- **Multi-task-group round:** this plan has more than one task group, so per this repo's
  `CLAUDE.md`, work happens on a local **integration branch** (e.g. `excel-export`) that every
  group branches off of and merges back into; `main` is only touched once, at the very end. Set
  `worktree.baseRef: "head"` in `.claude/settings.json` (already configured from the prior round)
  so parallel worktrees branch from the integration branch's local tip, not `origin/main`.
  Independent groups (Task Groups 2-5 below) may run in parallel git worktrees since none of them
  depend on each other's output — only on Task Group 1's helper.
- **No new fetches, no CSV re-reads:** every workbook must be built from DataFrames already in
  memory in that notebook (the same objects passed to `save_dataframe` elsewhere in the file), to
  preserve numeric/date dtype fidelity — never `pd.read_csv` the just-saved output back in.
- Heavy imports stay lazy (inside the function that needs them) in `_helpers/` modules, per
  existing convention (see `save_dataframe`/`load_dataframe` in `_helpers/io.py`).

---

## Task Group 1: `_helpers/excel.py` (shared helper + tests)

This is foundational — every other group depends on `save_workbook` existing and being correct.
Do this group first, alone, before any of the parallel groups start.

### Task 1: Create `_helpers/excel.py`

**Files:**
- Create: `notebooks/_helpers/excel.py`
- Modify: `notebooks/_helpers/__init__.py`
- Test: `notebooks/tests/test_save_workbook.py`

**Interfaces:**
- Produces: `save_workbook(sheets: dict[str, "pd.DataFrame"], xlsx_path: Path | str) -> None`,
  re-exported from `_helpers` (used by Task Groups 2-5).

- [ ] **Step 1: Write the failing tests**

Create `notebooks/tests/test_save_workbook.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import save_workbook


def test_save_workbook_writes_one_sheet_per_entry_in_order(tmp_path):
    import openpyxl

    sheets = {
        "first": pd.DataFrame({"a": [1, 2]}),
        "second": pd.DataFrame({"b": [3, 4]}),
    }
    out = tmp_path / "book.xlsx"
    assert save_workbook(sheets, out) is None  # side-effect helper returns nothing

    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["first", "second"]


def test_save_workbook_freezes_panes_and_sets_autofilter(tmp_path):
    import openpyxl

    sheets = {"data": pd.DataFrame({"a": [1, 2], "b": [3, 4]})}
    out = tmp_path / "book.xlsx"
    save_workbook(sheets, out)

    ws = openpyxl.load_workbook(out)["data"]
    assert ws.freeze_panes == "B2"
    assert ws.auto_filter.ref == "A1:B3"


def test_save_workbook_converts_geodataframe_geometry_to_wkt(tmp_path):
    import geopandas as gpd
    import openpyxl
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame(
        {"id": ["a", "b"], "geometry": [Point(0, 0), Point(1, 1)]}, crs="EPSG:4326"
    )
    out = tmp_path / "book.xlsx"
    save_workbook({"points": gdf}, out)

    ws = openpyxl.load_workbook(out)["points"]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("id", "geometry")
    assert rows[1] == ("a", "POINT (0 0)")
    assert rows[2] == ("b", "POINT (1 1)")


def test_save_workbook_truncates_and_deduplicates_long_sheet_names(tmp_path):
    import openpyxl

    long_name = "usgs_monitoring_locations_parameters"  # 37 chars, exceeds Excel's 31-char limit
    sheets = {
        long_name: pd.DataFrame({"a": [1]}),
        long_name + "_2": pd.DataFrame({"a": [2]}),  # truncates to the same 31-char prefix
    }
    out = tmp_path / "book.xlsx"
    save_workbook(sheets, out)

    names = openpyxl.load_workbook(out).sheetnames
    assert len(names) == 2
    assert len(set(names)) == 2  # unique
    assert all(len(n) <= 31 for n in names)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run test -k save_workbook -v`
Expected: FAIL with `ImportError: cannot import name 'save_workbook' from '_helpers'`

- [ ] **Step 3: Implement `_helpers/excel.py`**

Create `notebooks/_helpers/excel.py`:

```python
"""Compiling saved tables into a single downloadable Excel workbook: one sheet per table,
first row + first column frozen, autofilter on the header row."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .session import find_repo_root

if TYPE_CHECKING:
    import pandas as pd


def _unique_sheet_name(name: str, used: set[str]) -> str:
    """Excel sheet names must be <=31 characters and unique within the workbook. Truncate to 31
    characters, then shrink further and append a numeric suffix on collision."""
    candidate = name[:31]
    n = 1
    while candidate in used:
        suffix = f"_{n}"
        candidate = name[: 31 - len(suffix)] + suffix
        n += 1
    return candidate


def save_workbook(sheets: dict[str, "pd.DataFrame"], xlsx_path: Path | str) -> None:
    """Compile named (Geo)DataFrames into one .xlsx workbook, one sheet per entry (dict order
    preserved), each with the first row and first column frozen and autofilter enabled on the
    header row. Written directly from the in-memory frames (not re-read from CSV) so numeric/date
    dtypes survive intact. GeoDataFrame geometry columns are converted to WKT text first (Excel
    has no native geometry type), matching save_dataframe's CSV output. Side-effect helper; prints
    a confirmation and returns nothing."""
    import geopandas as gpd
    import pandas as pd

    xlsx_path = Path(xlsx_path)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            if isinstance(df, gpd.GeoDataFrame) and df.active_geometry_name is not None:
                geometry_col = df.geometry.name
                wkt = df.geometry.to_wkt()
                df = pd.DataFrame(df)  # drop GeoDataFrame-ness so to_excel treats it plainly
                df[geometry_col] = wkt

            sheet_name = _unique_sheet_name(name, used_names)
            used_names.add(sheet_name)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "B2"
            worksheet.auto_filter.ref = worksheet.dimensions

    try:
        shown = xlsx_path.relative_to(find_repo_root())
    except ValueError:
        shown = xlsx_path
    print(f"saved {len(sheets)} sheet(s) → {shown}")
```

- [ ] **Step 4: Re-export from `_helpers/__init__.py`**

In `notebooks/_helpers/__init__.py`, add this import line (after the `.climate` import, before
`.config`, to keep the block roughly alphabetical like the rest of the file):

```python
from .excel import save_workbook
```

And in `__all__`, change:

```python
    "save_dataframe", "load_dataframe", "save_datacube",
```

to:

```python
    "save_dataframe", "load_dataframe", "save_datacube", "save_workbook",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pixi run test -k save_workbook -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full test suite**

Run: `pixi run test`
Expected: PASS (36 tests: 32 existing + 4 new)

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/excel.py notebooks/_helpers/__init__.py notebooks/tests/test_save_workbook.py
git commit -m "feat: add save_workbook helper (Excel export with frozen panes + autofilter)"
```

---

## Task Group 2: NB1 + NB2 export steps

Depends only on Task Group 1. Independent of Task Groups 3-5 — may run in a parallel worktree.

### Task 2: Add the Export step to `1_usgs_hydrography.py` and `2_usgs_climate.py`

**Files:**
- Modify: `notebooks/1_usgs_hydrography.py`
- Modify: `notebooks/2_usgs_climate.py`

**Interfaces:**
- Consumes: `save_workbook(sheets, xlsx_path)` (Task Group 1, already merged).

- [ ] **Step 1: Update NB1's imports**

In `notebooks/1_usgs_hydrography.py`, change:

```python
from _helpers import init_session, save_dataframe, show, categorical_colors
```

to:

```python
from _helpers import init_session, save_dataframe, save_workbook, show, categorical_colors
```

- [ ] **Step 2: Append NB1's Export step**

At the end of `notebooks/1_usgs_hydrography.py` (after the final `watersheds_map` cell, before
the closing `## What's next` markdown cell), insert:

```python
# %% [markdown]
# ## Step 5 — Export to Excel
#
# Compiles the one saved table into a single downloadable workbook — one sheet, frozen header
# row + first column, with autofilter enabled on the header.

# %%
save_workbook({"huc8_watersheds": watersheds_gdf}, S.data_dir / "hydrography" / "hydrography.xlsx")
```

- [ ] **Step 3: Update NB2's imports**

In `notebooks/2_usgs_climate.py`, change:

```python
from _helpers import (
    init_session,
    show,
    save_datacube,
    categorical_colors,
    make_legend_clickable,
    conus404_monthly_grid,
    zonal_by_huc8,
    water_year,
    mk_sen_trend,
    pixel_trend,
    CONUS404_VARIABLES,
)
```

to:

```python
from _helpers import (
    init_session,
    show,
    save_datacube,
    save_workbook,
    categorical_colors,
    make_legend_clickable,
    conus404_monthly_grid,
    zonal_by_huc8,
    water_year,
    mk_sen_trend,
    pixel_trend,
    CONUS404_VARIABLES,
)
```

- [ ] **Step 4: Append NB2's Export step**

At the end of `notebooks/2_usgs_climate.py` (after the final `trend_fig` cell, before the closing
`## What's next` markdown cell), insert:

```python
# %% [markdown]
# ## Step 9 — Export to Excel
#
# Compiles the two saved tables into a single downloadable workbook — one sheet each, frozen
# header row + first column, with autofilter enabled on the header.

# %%
save_workbook(
    {"conus404_wateryear_by_huc8": wy, "conus404_trends_by_huc8": trends},
    S.data_dir / "climate" / "climate.xlsx",
)
```

- [ ] **Step 5: Regenerate the paired `.ipynb`s**

Run:
```bash
pixi run jupytext --sync notebooks/1_usgs_hydrography.py
pixi run jupytext --sync notebooks/2_usgs_climate.py
```

- [ ] **Step 6: Execute both notebooks headlessly**

Run:
```bash
pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/1_usgs_hydrography.ipynb
pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/2_usgs_climate.ipynb
```
Expected: both complete without error. `data/hydrography/hydrography.xlsx` and
`data/climate/climate.xlsx` exist. Confirm sheet counts match:

```bash
pixi run python -c "
import openpyxl
print('hydrography:', openpyxl.load_workbook('data/hydrography/hydrography.xlsx').sheetnames)
print('climate:', openpyxl.load_workbook('data/climate/climate.xlsx').sheetnames)
"
```
Expected output: `hydrography: ['huc8_watersheds']` and
`climate: ['conus404_wateryear_by_huc8', 'conus404_trends_by_huc8']`

- [ ] **Step 7: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add notebooks/1_usgs_hydrography.py notebooks/1_usgs_hydrography.ipynb \
        notebooks/2_usgs_climate.py notebooks/2_usgs_climate.ipynb \
        data/hydrography/hydrography.xlsx data/climate/climate.xlsx
git commit -m "feat: export hydrography and climate tables to Excel workbooks"
```

---

## Task Group 3: NB3 export step

Depends only on Task Group 1. Independent of Task Groups 2, 4, 5 — may run in a parallel worktree.

### Task 3: Add the Export step to `3_usgs_waterdata.py`

**Files:**
- Modify: `notebooks/3_usgs_waterdata.py`

**Interfaces:**
- Consumes: `save_workbook(sheets, xlsx_path)` (Task Group 1, already merged).

**Note on the two station tables:** `usgs_monitoring_locations.csv` (pre-classification) and
`usgs_monitoring_locations_parameters.csv` (post-classification, with `daily`/`continuous`/
`field_measurements`/`samples`/priority-group/`parameters` columns added) both need a sheet, but
by the end of the notebook only the *enriched* `stations_in_area` object still exists (the
enrichment mutates it in place, and the parquet-cache-hit path skips the raw fetch entirely, so
there is no reliable earlier snapshot to reuse). Reconstruct the "basic" table by **dropping** the
columns Step 3 is known to add — this works identically whether `stations_in_area` came from a
fresh fetch or the cache, with no CSV re-read.

- [ ] **Step 1: Update NB3's imports**

In `notebooks/3_usgs_waterdata.py`, change:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    show,
    categorical_colors,
    make_legend_clickable,
    PRIORITY_GROUPS,
    PRIORITY_NAMES,
    classify_parameter,
    build_parameter_name_lookup,
    station_parameters,
    fetch_daily,
    fetch_samples,
    fetch_field,
    tidy_daily,
    tidy_samples,
    tidy_field,
    coverage,
    trend_by_group,
)
```

to:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    save_workbook,
    show,
    categorical_colors,
    make_legend_clickable,
    PRIORITY_GROUPS,
    PRIORITY_NAMES,
    classify_parameter,
    build_parameter_name_lookup,
    station_parameters,
    fetch_daily,
    fetch_samples,
    fetch_field,
    tidy_daily,
    tidy_samples,
    tidy_field,
    coverage,
    trend_by_group,
)
```

- [ ] **Step 2: Append NB3's Export step**

At the very end of `notebooks/3_usgs_waterdata.py` (after the final `trend_chart` cell), insert:

```python
# %% [markdown]
# ## Step 8 — Export to Excel
#
# Compiles all six saved tables into a single downloadable workbook — one sheet each, frozen
# header row + first column, with autofilter enabled on the header. `usgs_monitoring_locations`
# (the pre-classification station table) is reconstructed by dropping the columns Step 3 added,
# since by this point only the enriched station table still exists in memory — this works the
# same whether the station data came from a fresh fetch or the cache above.

# %%
station_enrichment_columns = [*DATA_TYPES, *PRIORITY_NAMES, "parameters"]
stations_basic = stations_in_area.drop(columns=station_enrichment_columns)

save_workbook(
    {
        "usgs_monitoring_locations": stations_basic,
        "usgs_monitoring_locations_parameters": stations_in_area,
        "usgs_daily_values": daily,
        "usgs_field_measurements": field,
        "usgs_samples": samples,
        "usgs_trends": usgs_trends,
    },
    S.data_dir / "usgs_waterdata" / "usgs_waterdata.xlsx",
)
```

- [ ] **Step 3: Regenerate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/3_usgs_waterdata.py`

- [ ] **Step 4: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/3_usgs_waterdata.ipynb`
Expected: completes without error (uses the parquet-backup-cache from the prior round, so this
should take under two minutes, not re-fetch live data unless the cache has expired).
`data/usgs_waterdata/usgs_waterdata.xlsx` exists. Confirm:

```bash
pixi run python -c "
import openpyxl
wb = openpyxl.load_workbook('data/usgs_waterdata/usgs_waterdata.xlsx')
print(wb.sheetnames)
"
```
Expected output (note the truncated 5th sheet name, 37 chars → 31):
`['usgs_monitoring_locations', 'usgs_monitoring_locations_param', 'usgs_daily_values', 'usgs_field_measurements', 'usgs_samples', 'usgs_trends']`

- [ ] **Step 5: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add notebooks/3_usgs_waterdata.py notebooks/3_usgs_waterdata.ipynb data/usgs_waterdata/usgs_waterdata.xlsx
git commit -m "feat: export USGS waterdata tables to an Excel workbook"
```

---

## Task Group 4: NB4 export step

Depends only on Task Group 1. Independent of Task Groups 2, 3, 5 — may run in a parallel worktree.

### Task 4: Add the Export step to `4_tceq_waterquality.py`

**Files:**
- Modify: `notebooks/4_tceq_waterquality.py`

**Interfaces:**
- Consumes: `save_workbook(sheets, xlsx_path)` (Task Group 1, already merged).

- [ ] **Step 1: Update NB4's imports**

In `notebooks/4_tceq_waterquality.py`, change:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    show,
    categorical_colors,
    make_legend_clickable,
    PRIORITY_NAMES,
    classify_parameter,
    fetch_wqp_results,
    tidy_wqp_results,
    coverage,
    trend_by_group,
)
```

to:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    save_workbook,
    show,
    categorical_colors,
    make_legend_clickable,
    PRIORITY_NAMES,
    classify_parameter,
    fetch_wqp_results,
    tidy_wqp_results,
    coverage,
    trend_by_group,
)
```

- [ ] **Step 2: Append NB4's Export step**

At the very end of `notebooks/4_tceq_waterquality.py` (after the final `trend_chart` cell,
replacing the closing `## What's next` markdown cell's position — add the new step *before* it),
insert:

```python
# %% [markdown]
# ## Step 8 — Export to Excel
#
# Compiles all three saved tables into a single downloadable workbook — one sheet each, frozen
# header row + first column, with autofilter enabled on the header.

# %%
save_workbook(
    {
        "tceq_monitoring_locations": stations_in_area,
        "tceq_results": tceq_results,
        "tceq_trends": tceq_trends,
    },
    S.data_dir / "tceq_waterquality" / "tceq_waterquality.xlsx",
)
```

- [ ] **Step 3: Regenerate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/4_tceq_waterquality.py`

- [ ] **Step 4: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/4_tceq_waterquality.ipynb`
Expected: completes without error (uses the parquet-backup-cache, so under a minute unless the
cache has expired). `data/tceq_waterquality/tceq_waterquality.xlsx` exists. Confirm:

```bash
pixi run python -c "
import openpyxl
print(openpyxl.load_workbook('data/tceq_waterquality/tceq_waterquality.xlsx').sheetnames)
"
```
Expected output: `['tceq_monitoring_locations', 'tceq_results', 'tceq_trends']`

- [ ] **Step 5: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add notebooks/4_tceq_waterquality.py notebooks/4_tceq_waterquality.ipynb data/tceq_waterquality/tceq_waterquality.xlsx
git commit -m "feat: export TCEQ water-quality tables to an Excel workbook"
```

---

## Task Group 5: NB5 export step

Depends only on Task Group 1. Independent of Task Groups 2, 3, 4 — may run in a parallel worktree.

### Task 5: Add the Export step to `5_twdb_groundwater.py`

**Files:**
- Modify: `notebooks/5_twdb_groundwater.py`

**Interfaces:**
- Consumes: `save_workbook(sheets, xlsx_path)` (Task Group 1, already merged).

- [ ] **Step 1: Update NB5's imports**

In `notebooks/5_twdb_groundwater.py`, change:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    show,
    categorical_colors,
    make_legend_clickable,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    fetch_gwdb_members,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
    coverage,
    trend_by_group,
)
```

to:

```python
from _helpers import (
    init_session,
    save_dataframe,
    load_dataframe,
    save_workbook,
    show,
    categorical_colors,
    make_legend_clickable,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    fetch_gwdb_members,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
    coverage,
    trend_by_group,
)
```

- [ ] **Step 2: Append NB5's Export step**

At the very end of `notebooks/5_twdb_groundwater.py` (after the final `trend_chart` cell, before
the closing `## What's next` markdown cell), insert:

```python
# %% [markdown]
# ## Step 9 — Export to Excel
#
# Compiles all four saved tables into a single downloadable workbook — one sheet each, frozen
# header row + first column, with autofilter enabled on the header.

# %%
save_workbook(
    {
        "twdb_wells": wells_in_area,
        "twdb_water_levels": twdb_water_levels,
        "twdb_water_quality": twdb_water_quality,
        "twdb_trends": twdb_trends,
    },
    S.data_dir / "twdb_groundwater" / "twdb_groundwater.xlsx",
)
```

- [ ] **Step 3: Regenerate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/5_twdb_groundwater.py`

- [ ] **Step 4: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/5_twdb_groundwater.ipynb`
Expected: completes without error (uses the parquet-backup-cache, so under a minute unless the
cache has expired). `data/twdb_groundwater/twdb_groundwater.xlsx` exists. Confirm:

```bash
pixi run python -c "
import openpyxl
print(openpyxl.load_workbook('data/twdb_groundwater/twdb_groundwater.xlsx').sheetnames)
"
```
Expected output: `['twdb_wells', 'twdb_water_levels', 'twdb_water_quality', 'twdb_trends']`

- [ ] **Step 5: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add notebooks/5_twdb_groundwater.py notebooks/5_twdb_groundwater.ipynb data/twdb_groundwater/twdb_groundwater.xlsx
git commit -m "feat: export TWDB groundwater tables to an Excel workbook"
```

---

## Task Group 6: Quarto wiring, home page links, docs, and final render

Depends on Task Groups 2, 3, 4, and 5 all being merged into the integration branch (needs the
actual `.xlsx` files present in `data/` to verify the `resources:` copy and the home page links).
Not parallelizable with anything — run this last, sequentially.

### Task 6: Update `_quarto.yml`, `index.qmd`, `CLAUDE.md`, `README.md`

**Files:**
- Modify: `_quarto.yml`
- Modify: `index.qmd`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Add `resources:` to `_quarto.yml`**

In `_quarto.yml`, change:

```yaml
project:
  type: website
  output-dir: _site
  # Execute each notebook in its OWN directory (notebooks/) so any relative reads resolve;
  # the notebooks also self-locate the repo root, so absolute paths (data/, cache/, .env) work.
  execute-dir: file
  # Render the landing page and the numbered notebooks (Quarto resolves each paired
  # .py/.ipynb notebook via its .py source) — but NOT the scratch sandbox/ notebooks.
  render:
    - index.qmd
    - notebooks/*.py
```

to:

```yaml
project:
  type: website
  output-dir: _site
  # Execute each notebook in its OWN directory (notebooks/) so any relative reads resolve;
  # the notebooks also self-locate the repo root, so absolute paths (data/, cache/, .env) work.
  execute-dir: file
  # Render the landing page and the numbered notebooks (Quarto resolves each paired
  # .py/.ipynb notebook via its .py source) — but NOT the scratch sandbox/ notebooks.
  render:
    - index.qmd
    - notebooks/*.py
  # Quarto does not copy data/ into _site/ by default — the committed Excel workbooks need an
  # explicit resources: entry so the home page's download links resolve on the published site.
  resources:
    - "data/**/*.xlsx"
```

- [ ] **Step 2: Add a "Downloads" section to `index.qmd`**

In `index.qmd`, after the `::: {.grid}` block's closing `:::` (i.e. right after the five notebook
cards) and before the closing `---` + "Built with Quarto" footer line, insert:

```markdown
## Downloads

Every saved table is also compiled into a single Excel workbook per source — one sheet per
table, with the header row and first column frozen and autofilter enabled on the headers:

- [Hydrography](data/hydrography/hydrography.xlsx)
- [Climate](data/climate/climate.xlsx)
- [USGS WaterData](data/usgs_waterdata/usgs_waterdata.xlsx)
- [TCEQ Water Quality](data/tceq_waterquality/tceq_waterquality.xlsx)
- [TWDB Groundwater](data/twdb_groundwater/twdb_groundwater.xlsx)
```

- [ ] **Step 3: Update `CLAUDE.md`'s helper inventory**

In `CLAUDE.md`, under **This repo:** → "Helper inventory", change:

```
  - `io` — `save_dataframe`, `load_dataframe` (parquet-as-backup-cache read side), `save_datacube`.
```

to add a new bullet right after it:

```
  - `io` — `save_dataframe`, `load_dataframe` (parquet-as-backup-cache read side), `save_datacube`.
  - `excel` — `save_workbook` (compiles a notebook's saved tables into one downloadable .xlsx,
    one sheet each, frozen panes + autofilter).
```

- [ ] **Step 4: Update `README.md`'s Approach section**

In `README.md`, after the existing bullet list of the five source notebooks and before the
"Display / analyze notebooks (shared)" bullet, add:

```markdown
  - Each source notebook's final step also compiles its saved tables into a single downloadable
    **Excel workbook** (`data/<source>/<source>.xlsx`, one sheet per table, frozen header row +
    first column, autofilter on the headers) — linked directly from the [home page's Downloads
    section](https://limnotech.github.io/Thornforest/#downloads).
```

- [ ] **Step 5: Stage the doc changes**

```bash
git add _quarto.yml index.qmd CLAUDE.md README.md
```

(No commit yet — Task 7 verifies the full render before the final commit for this group.)

### Task 7: Render and final verification

**Files:** none new — this task only runs commands and inspects output.

- [ ] **Step 1: Run the full test suite one more time**

Run: `pixi run test`
Expected: PASS (36 tests total)

- [ ] **Step 2: Render the site**

Run: `pixi run render`
Expected: builds `_site/` including all five notebook pages; no errors.

- [ ] **Step 3: Confirm the workbooks were copied into `_site/`**

Run:
```bash
ls _site/data/hydrography/hydrography.xlsx \
   _site/data/climate/climate.xlsx \
   _site/data/usgs_waterdata/usgs_waterdata.xlsx \
   _site/data/tceq_waterquality/tceq_waterquality.xlsx \
   _site/data/twdb_groundwater/twdb_groundwater.xlsx
```
Expected: all five paths exist (confirms the `resources:` entry from Task 6 actually copies them
— before that change, `_site/data/` does not exist at all).

- [ ] **Step 4: Confirm the home page links resolve**

Run:
```bash
grep -o 'data/[a-z_]*/[a-z_]*\.xlsx' _site/index.html | sort -u
```
Expected output (5 lines, one per workbook):
```
data/climate/climate.xlsx
data/hydrography/hydrography.xlsx
data/tceq_waterquality/tceq_waterquality.xlsx
data/twdb_groundwater/twdb_groundwater.xlsx
data/usgs_waterdata/usgs_waterdata.xlsx
```

- [ ] **Step 5: Manually spot-check one workbook's formatting**

Run:
```bash
pixi run python -c "
import openpyxl
wb = openpyxl.load_workbook('data/usgs_waterdata/usgs_waterdata.xlsx')
for name in wb.sheetnames:
    ws = wb[name]
    print(name, '| freeze_panes:', ws.freeze_panes, '| auto_filter.ref:', ws.auto_filter.ref)
"
```
Expected: every sheet shows `freeze_panes: B2` and a non-`None` `auto_filter.ref` matching that
sheet's dimensions.

- [ ] **Step 6: Confirm `_freeze/` is staged for the five notebook pages**

Run: `git status --short -- _freeze/`
Expected: `_freeze/notebooks/{1_usgs_hydrography,2_usgs_climate,3_usgs_waterdata,4_tceq_waterquality,5_twdb_groundwater}/` all show modified/staged (or already staged from `git add -A` below).

- [ ] **Step 7: Stage the render output and commit this group**

```bash
git add _freeze/notebooks _site
git status --short
```
(`_site/` is git-ignored per this repo's `.gitignore` — confirm it does *not* appear in the
`git status` output; if it does, stop and investigate before committing anything.)

```bash
git add -A -- _freeze
git commit -m "docs: wire Excel downloads into Quarto resources + home page, refresh _freeze/"
```

## Out of scope (unchanged from the spec)

A single combined cross-source workbook; any Excel formatting beyond frozen panes + autofilter
(colors, conditional formatting, charts); automatic workbook regeneration outside of re-running the
notebooks themselves.
