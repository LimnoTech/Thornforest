# TCEQ & TWDB Fetch Notebooks + Trend Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new source-fetch notebooks (TCEQ surface-water-quality via the EPA Water Quality
Portal; TWDB groundwater via the GWDB ArcGIS inventory + nightly bulk file), and add Mann–Kendall/
Sen's-slope trend analysis to notebook 3 (USGS) and both new notebooks, per
`docs/superpowers/specs/2026-07-08-tceq-twdb-trends-design.md`.

**Architecture:** Two new `_helpers` modules (`tceq.py`, `twdb.py`) follow the existing
`fetch_*` (network) / `tidy_*` (pure) split from `usgs.py`. Two new numbered notebooks
(`4_tceq_waterdata.py`, `5_twdb_waterdata.py`) mirror `3_usgs_waterdata.py`'s shape (discover →
classify → fetch → tidy → map → availability → **trend**). A new `trend_by_group` helper in
`_helpers/analysis.py` is shared by all three fetch notebooks. All facts below (API behavior,
column names, response sizes) were verified live against the real services during design — this
plan contains no speculative endpoints or guessed schemas.

**Tech Stack:** `dataretrieval.wqp` (TCEQ, no new dependency), `requests` (already a transitive
dependency of `dataretrieval`/`pygeohydro`; used directly for the TWDB ArcGIS FeatureServer and bulk
zip download), `geopandas`, `pandas`, `pymannkendall` (already a dependency, via `mk_sen_trend`).

## Global Constraints

- **Storage:** tabular results → GeoParquet + CSV via `save_dataframe` (never parquet-only).
- **Notebooks:** edit the paired `.py` (jupytext percent format), never the `.ipynb`; after any
  edit run `pixi run jupytext --sync notebooks/<name>.py` to regenerate the `.ipynb`.
- **Tests:** `pixi run test` (pytest, `notebooks/tests/`).
- **Source terminology:** carry each source's own parameter/characteristic names, codes, units
  verbatim in saved data; only genuinely new derived quantities get new names.
- **Never commit or push.** Leave all changes staged/on-disk. Per this repo's workflow, each
  task-group below is a gate: implement the group, run its tests/verification, leave the
  working-tree diff staged, and stop for the user to review and commit before the next group
  starts. (The executing skill handles actual branch creation.)
- **Heavy imports stay lazy** (inside the function that needs them) in `_helpers/` modules.
  Notebook cells stay type-hint-free (the audience is new to Python/Jupyter).
- Project-specific constants (`PRIORITY_GROUPS`, `WATERSHEDS`, endpoint URLs/schemas for a given
  source) live next to the code that uses them (`config.py` for cross-source constants, or the
  owning `_helpers/<source>.py` module for source-specific endpoint/schema constants) — never
  hardcoded inside a generic function body.
- `from _helpers import ...` — every new public helper must be re-exported from
  `notebooks/_helpers/__init__.py`.

---

## Task Group 1: Shared helpers — `trend_by_group`, vocabulary widening, `_warn_missing_huc8` relocation

This group touches only `_helpers/analysis.py`, `_helpers/config.py`, `_helpers/usgs.py`, and their
tests — no notebook changes yet. It unblocks every later group (NB3's trend step and both new
notebooks all depend on `trend_by_group`; the TCEQ/TWDB tidy functions depend on the widened
`PRIORITY_GROUPS`).

### Task 1: Relocate `_warn_missing_huc8` into `_helpers/analysis.py`

`_warn_missing_huc8` (currently private to `usgs.py`) will be needed by the new `tceq.py` and
`twdb.py` tidy functions too. It's generic (no USGS-specific logic), so move it to `analysis.py`
alongside the other generic, source-agnostic helpers.

**Files:**
- Modify: `notebooks/_helpers/analysis.py`
- Modify: `notebooks/_helpers/usgs.py:21-27` (remove the definition, add an import)

**Interfaces:**
- Produces: `_warn_missing_huc8(df: pd.DataFrame, label: str) -> pd.DataFrame` importable as
  `from .analysis import _warn_missing_huc8` (private — not re-exported from `__init__.py`, but
  every sibling module in the package may import it directly).

- [ ] **Step 1: Add the function to `analysis.py`**

Add this function to `notebooks/_helpers/analysis.py` (after the imports, before `water_year`):

```python
def _warn_missing_huc8(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Warn (don't silently drop) if the huc8 join produced NaN — signals a station-id mismatch."""
    missing = df["huc8"].isna()
    if missing.any():
        ids = sorted(df.loc[missing, "monitoring_location_id"].unique())[:10]
        print(f"WARNING: {int(missing.sum())} {label} rows had no huc8 match; unmatched ids: {ids}")
    return df
```

- [ ] **Step 2: Remove the duplicate from `usgs.py` and import it instead**

In `notebooks/_helpers/usgs.py`, delete the `_warn_missing_huc8` function definition (lines 21-27),
and change the top-level import line:

```python
from .config import PRIORITY_GROUPS
```

to:

```python
from .analysis import _warn_missing_huc8
from .config import PRIORITY_GROUPS
```

- [ ] **Step 3: Run the existing test suite to confirm nothing broke**

Run: `pixi run test`
Expected: PASS — all existing tests (including `test_usgs_tidy.py`, which exercises
`_warn_missing_huc8` indirectly through `tidy_daily`/`tidy_samples`/`tidy_field`) still pass.

- [ ] **Step 4: Commit**

```bash
git add notebooks/_helpers/analysis.py notebooks/_helpers/usgs.py
git commit -m "refactor: move _warn_missing_huc8 into analysis.py (shared by tceq/twdb helpers)"
```

### Task 2: Add `trend_by_group` to `_helpers/analysis.py`

**Files:**
- Modify: `notebooks/_helpers/analysis.py`
- Test: `notebooks/tests/test_analysis.py`

**Interfaces:**
- Consumes: `mk_sen_trend(series) -> dict` (already defined in this file, keys `trend`/`p`/`slope`/
  `intercept`/`n`).
- Produces: `trend_by_group(df: pd.DataFrame, group_cols: list[str], time_col: str, value_col: str,
  agg: str = "median") -> pd.DataFrame` — one row per unique `group_cols` combination, columns
  `[*group_cols, "trend", "p", "slope", "intercept", "n"]`. Used by NB3/NB4/NB5.

- [ ] **Step 1: Write the failing tests**

Add to `notebooks/tests/test_analysis.py` (after the existing imports, which already import from
`_helpers` — extend that import line to include `trend_by_group`):

```python
from _helpers import coverage, mk_sen_trend, trend_by_group, water_year
```

Then append these test functions to the file:

```python
def test_trend_by_group_one_row_per_group_with_correct_trend():
    df = pd.DataFrame({
        "station": ["A"] * 6 + ["B"] * 3,
        "date": pd.to_datetime(
            ["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01", "2006-01-01"]
            + ["2001-01-01", "2002-01-01", "2003-01-01"]
        ),
        "value": [1, 2, 3, 4, 5, 6, 10, 10, 10],
    })
    out = trend_by_group(df, ["station"], "date", "value")
    assert set(out.columns) == {"station", "trend", "p", "slope", "intercept", "n"}
    a = out[out["station"] == "A"].iloc[0]
    b = out[out["station"] == "B"].iloc[0]
    assert a["trend"] == "increasing"
    assert a["n"] == 6
    assert b["trend"] == "insufficient"  # only 3 points, below mk_sen_trend's minimum of 4


def test_trend_by_group_agg_choice_changes_slope():
    # Three readings in 2001 (1, 1, 100) make mean (34) and median (1) diverge sharply.
    df = pd.DataFrame({
        "station": ["A"] * 7,
        "date": pd.to_datetime([
            "2001-01-01", "2001-04-01", "2001-08-01",
            "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01",
        ]),
        "value": [1.0, 1.0, 100.0, 2.0, 3.0, 4.0, 5.0],
    })
    median_out = trend_by_group(df, ["station"], "date", "value", agg="median")
    mean_out = trend_by_group(df, ["station"], "date", "value", agg="mean")
    assert median_out.iloc[0]["slope"] != mean_out.iloc[0]["slope"]


def test_trend_by_group_coerces_non_numeric_value_column():
    df = pd.DataFrame({
        "station": ["A"] * 5,
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01"]),
        "value": ["1", "2", "3", "4", "5"],  # strings, like tidy_samples' `value` column
    })
    out = trend_by_group(df, ["station"], "date", "value")
    assert out.iloc[0]["trend"] == "increasing"


def test_trend_by_group_multiple_group_cols():
    df = pd.DataFrame({
        "station": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "priority_group": ["discharge"] * 4 + ["ph"] * 4,
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01"] * 2),
        "value": [1, 2, 3, 4, 4, 3, 2, 1],
    })
    out = trend_by_group(df, ["station", "priority_group"], "date", "value")
    assert len(out) == 2
    assert set(out.columns) == {"station", "priority_group", "trend", "p", "slope", "intercept", "n"}


def test_trend_by_group_empty_input_returns_typed_empty():
    df = pd.DataFrame(columns=["station", "date", "value"])
    out = trend_by_group(df, ["station"], "date", "value")
    assert list(out.columns) == ["station", "trend", "p", "slope", "intercept", "n"]
    assert len(out) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run test -k trend_by_group -v`
Expected: FAIL with `ImportError: cannot import name 'trend_by_group'`

- [ ] **Step 3: Implement `trend_by_group`**

Add to `notebooks/_helpers/analysis.py` (after `mk_sen_trend`, before `coverage`):

```python
def trend_by_group(
    df: pd.DataFrame,
    group_cols: list[str],
    time_col: str,
    value_col: str,
    agg: str = "median",
) -> pd.DataFrame:
    """Resample value_col to one value per calendar year within each group_cols combo
    (coercing to numeric first), then run mk_sen_trend on the annual series. Returns
    one row per group with trend/p/slope/intercept/n alongside the group_cols."""
    empty_columns = [*group_cols, "trend", "p", "slope", "intercept", "n"]
    if df.empty:
        return pd.DataFrame(columns=empty_columns)

    rows = []
    for keys, g in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        annual = (
            g.assign(
                _year=pd.to_datetime(g[time_col]).dt.year,
                _value=pd.to_numeric(g[value_col], errors="coerce"),
            )
            .groupby("_year")["_value"]
            .agg(agg)
        )
        r = mk_sen_trend(annual.to_numpy())
        rows.append({**dict(zip(group_cols, keys)), **r})
    return pd.DataFrame(rows, columns=empty_columns)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pixi run test -k trend_by_group -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Update `_helpers/__init__.py` re-exports**

In `notebooks/_helpers/__init__.py`, change:

```python
from .analysis import coverage, mk_sen_trend, water_year
```

to:

```python
from .analysis import coverage, mk_sen_trend, trend_by_group, water_year
```

and in `__all__`, change:

```python
    "water_year", "mk_sen_trend", "coverage",
```

to:

```python
    "water_year", "mk_sen_trend", "coverage", "trend_by_group",
```

- [ ] **Step 6: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/analysis.py notebooks/_helpers/__init__.py notebooks/tests/test_analysis.py
git commit -m "feat: add trend_by_group helper for per-station/parameter Mann-Kendall trends"
```

### Task 3: Widen `PRIORITY_GROUPS` vocabulary (TCEQ naming + TWDB codes)

Verified live against real API responses during design:
- TCEQ's WQP data tags dissolved oxygen as `"Oxygen"` (not `"Dissolved oxygen (DO)"`) and water
  temperature as `"Temperature, sample"` (not `"Temperature, water"`) — the current substrings
  (`"dissolved oxygen"`, `"temperature, water"`) don't match either.
- TWDB's GWDB water-quality file reuses USGS-style parameter codes, including two not yet in
  `PRIORITY_GROUPS`: `00403` ("PH (STANDARD UNITS) LAB") and `82079` ("TURBIDITY, LAB,
  NEPHELOMETRIC TURBIDITY UNITS, NTU").
- The broadened `"oxygen"`/`"temperature"` substrings only affect **characteristic-name** matching
  (used by USGS samples and TCEQ WQP results). TWDB's water-quality classification goes through the
  **parameter_code** path instead (added in Task Group 6), so TWDB's own oxygen-isotope analytes
  (codes `50790`/`50982`, unrelated to dissolved oxygen) are unaffected by this widening.

**Files:**
- Modify: `notebooks/_helpers/config.py:11-32`
- Test: `notebooks/tests/test_usgs_classify.py`

**Interfaces:**
- Consumes: none new.
- Produces: `PRIORITY_GROUPS` (dict, already exported) with updated `characteristics`/
  `parameter_codes` values for `dissolved_oxygen`, `temperature`, `pH`, `turbidity`.

- [ ] **Step 1: Write the failing tests**

Append to `notebooks/tests/test_usgs_classify.py`:

```python
def test_widened_oxygen_and_temperature_match_tceq_naming():
    assert classify_parameter(characteristic="Oxygen") == "dissolved_oxygen"
    assert classify_parameter(characteristic="Temperature, sample") == "temperature"
    # still match the original USGS/WQX names
    assert classify_parameter(characteristic="Dissolved oxygen (DO)") == "dissolved_oxygen"
    assert classify_parameter(characteristic="Temperature, water") == "temperature"


def test_twdb_parameter_codes_classify():
    assert classify_parameter(parameter_code="00403") == "pH"        # TWDB lab pH
    assert classify_parameter(parameter_code="82079") == "turbidity"  # TWDB lab turbidity
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run test -k "widened_oxygen or twdb_parameter_codes" -v`
Expected: FAIL — `Oxygen`/`Temperature, sample` classify as `None`; `00403`/`82079` classify as `None`.

- [ ] **Step 3: Widen `PRIORITY_GROUPS` in `config.py`**

In `notebooks/_helpers/config.py`, change these four entries within the `PRIORITY_GROUPS` dict:

```python
    "temperature": {"parameter_codes": {"00010"}, "characteristics": ["temperature, water"]},
```
to:
```python
    "temperature": {"parameter_codes": {"00010"}, "characteristics": ["temperature"]},  # broadened: matches TCEQ's "Temperature, sample" too
```

```python
    "dissolved_oxygen": {"parameter_codes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
```
to:
```python
    "dissolved_oxygen": {"parameter_codes": {"00300", "00301"}, "characteristics": ["oxygen"]},  # broadened: matches TCEQ's bare "Oxygen"
```

```python
    "pH": {"parameter_codes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classify_parameter)
```
to:
```python
    "pH": {"parameter_codes": {"00400", "00403"}, "characteristics": ["ph"]},  # 00403 = TWDB GWDB lab pH; pH matched EXACTLY (see classify_parameter)
```

```python
    "turbidity": {"parameter_codes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
```
to:
```python
    "turbidity": {"parameter_codes": {"00076", "63675", "63676", "63680", "82079"}, "characteristics": ["turbidity"]},  # 82079 = TWDB GWDB lab turbidity
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pixi run test -k "widened_oxygen or twdb_parameter_codes" -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite (confirm no regressions from the widened substrings)**

Run: `pixi run test`
Expected: PASS — including `test_classify_by_characteristic_substring` and
`test_ph_matches_exactly_not_as_substring`, which exercise the un-widened groups and must be
unaffected.

- [ ] **Step 6: Commit**

```bash
git add notebooks/_helpers/config.py notebooks/tests/test_usgs_classify.py
git commit -m "feat: widen PRIORITY_GROUPS to match TCEQ characteristic names + TWDB parameter codes"
```

---

## Task Group 2: Trend step in `3_usgs_waterdata.py`

### Task 4: Add Step 7 — Trends to notebook 3

**Files:**
- Modify: `notebooks/3_usgs_waterdata.py` (append after the existing Step 6, which ends at line 336)

**Interfaces:**
- Consumes: `trend_by_group` (Task Group 1), the notebook's existing `daily`/`samples`/`field`
  DataFrames (already tidied and in-memory from Steps 4).

- [ ] **Step 1: Update the imports**

In `notebooks/3_usgs_waterdata.py`, change the `from _helpers import (...)` block to add
`trend_by_group`:

```python
from _helpers import (
    init_session,
    save_dataframe,
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

- [ ] **Step 2: Remove the stale "trends live elsewhere" comment**

Find and remove this line from the Step 6 markdown cell (it no longer reflects the plan):

```
# analyses live in the later display notebooks.)
```

(part of the sentence `## Step 6 — Data availability & a sample series` markdown cell — reword that
cell's closing parenthetical from `(Trend and pre/post analyses live in the later display
notebooks.)` to `(Pre/post-restoration comparisons live in a later shared display notebook; trends
are Step 7, below.)`)

- [ ] **Step 3: Append the new Step 7 cells** at the end of the file (after the `sample_series`
      cell, which currently ends the notebook):

```python
# %% [markdown]
# ## Step 7 — Trends (Mann–Kendall + Sen's slope)
#
# For each station × priority-parameter series we run the **Mann–Kendall** test (is there a
# monotonic trend?) and estimate **Sen's slope** (the robust per-year rate of change), same
# granularity as the coverage table above. Discharge is aggregated to an **annual mean** (a rate);
# water-quality samples and field measurements use the **annual median** (robust to non-detects and
# uneven sampling). Trends with *p* < 0.05 are flagged significant.

# %%
daily_trends = trend_by_group(daily, ["monitoring_location_id", "priority_group"], "date", "value", agg="mean")
samples_trends = trend_by_group(samples, ["monitoring_location_id", "priority_group"], "datetime", "value", agg="median")
field_trends = trend_by_group(field, ["monitoring_location_id", "priority_group"], "datetime", "value", agg="median")

usgs_trends = pd.concat(
    [
        daily_trends.assign(data_type="daily"),
        samples_trends.assign(data_type="samples"),
        field_trends.assign(data_type="field"),
    ],
    ignore_index=True,
)
usgs_trends["significant"] = usgs_trends["p"] < 0.05
save_dataframe(usgs_trends, S.data_dir / "usgs_waterdata" / "usgs_trends.parquet")
show(usgs_trends.round({"p": 4, "slope": 4}))

# %% [markdown]
# ### Trend rates (Sen's slope) by priority parameter
#
# Each bar is one station × priority-parameter trend; hover for the Mann–Kendall direction and
# *p*-value.

# %%
trend_chart = usgs_trends.dropna(subset=["slope"]).hvplot.bar(
    x="priority_group", y="slope", by="data_type",
    hover_cols=["monitoring_location_id", "trend", "p", "significant"],
    frame_height=360, rot=40,
    ylabel="Sen's slope (per year)", xlabel="",
    title="USGS station trend rates by priority parameter (Sen's slope)", legend="top_right",
).opts(active_tools=[])
trend_chart
```

- [ ] **Step 4: Regenerate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/3_usgs_waterdata.py`
Expected: `notebooks/3_usgs_waterdata.ipynb` is updated (git diff shows cell changes matching the
new `.py` content).

- [ ] **Step 5: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/3_usgs_waterdata.ipynb`
Expected: completes without error; `data/usgs_waterdata/usgs_trends.parquet` (+ `.csv`) exists and
is non-empty; printed save confirmation shows a row count matching (daily + samples + field) unique
station×priority_group combinations.

- [ ] **Step 6: Commit**

```bash
git add notebooks/3_usgs_waterdata.py notebooks/3_usgs_waterdata.ipynb data/usgs_waterdata/usgs_trends.parquet data/usgs_waterdata/usgs_trends.csv
git commit -m "feat: add Step 7 trend analysis (Mann-Kendall/Sen's slope) to 3_usgs_waterdata"
```

---

## Task Group 3: TCEQ helpers (`_helpers/tceq.py`)

### Task 5: Create `_helpers/tceq.py`

Design decision made during planning (superseding the spec's "one scoped call per group" open
question): query the WQP **once** per notebook run, scoped only by `organization` + `bBox` (no
`characteristicName` filter) — verified live to return 93,436 rows in ~78s for the actual study-area
bbox, a perfectly manageable size. This mirrors the existing `fetch_samples`/`tidy_samples` pattern
in `usgs.py` (fetch everything for the area, classify locally) rather than pre-filtering by exact
characteristic name, which would require guessing WQP's exact case-sensitive vocabulary per
source. Also verified live: WQP's `siteid` parameter does **not** reliably OR across multiple
semicolon-joined site IDs (a multi-site query silently only returned the first site's rows), so
station scoping is by bbox, not by passing a station-id list.

Also verified live: `dataretrieval.wqp.what_sites`/`get_results` return **plain `pandas.DataFrame`s**
with `LatitudeMeasure`/`LongitudeMeasure` columns — unlike `dataretrieval.waterdata`, there is no
automatic geometry column, so the notebook must build one with `geopandas.points_from_xy`.

**Files:**
- Create: `notebooks/_helpers/tceq.py`
- Test: `notebooks/tests/test_tceq_tidy.py`

**Interfaces:**
- Consumes: `classify_parameter(characteristic=..., groups=...) -> str | None` (from `.usgs`),
  `_warn_missing_huc8(df, label) -> df` (from `.analysis`, Task Group 1), `PRIORITY_GROUPS` (from
  `.config`).
- Produces:
  - `TCEQ_COLUMNS: list[str]`
  - `fetch_wqp_results(bbox: list[float], organization: str = "TCEQMAIN") -> pd.DataFrame` (network)
  - `tidy_wqp_results(raw: pd.DataFrame, huc8_by_station: dict[str, str], groups: dict =
    PRIORITY_GROUPS) -> pd.DataFrame` (pure) — used by NB4.

- [ ] **Step 1: Write the failing tests**

Create `notebooks/tests/test_tceq_tidy.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_wqp_results

HUC8 = {"TCEQMAIN-12336": "13090002"}


def test_tidy_wqp_results_tags_and_orders():
    raw = pd.DataFrame({
        "MonitoringLocationIdentifier": ["TCEQMAIN-12336", "TCEQMAIN-12336"],
        "ActivityStartDateTime": ["2020-01-02", "2020-01-01"],
        "CharacteristicName": ["Oxygen", "Fecal coliform"],  # 2nd -> no group -> dropped
        "USGSPCode": [None, None],
        "ResultMeasureValue": ["8.1", "10"],
        "ResultMeasure/MeasureUnitCode": ["mg/L", "cfu"],
        "ResultSampleFractionText": [None, None],
        "ResultDetectionConditionText": [None, None],
        "MeasureQualifierCode": [None, None],
        "LaboratoryName": [None, None],
    })
    out = tidy_wqp_results(raw, HUC8)
    assert list(out.columns) == [
        "monitoring_location_id", "datetime", "characteristic", "parameter_code",
        "value", "unit", "fraction", "detection_condition", "qualifier", "lab_name",
        "priority_group", "huc8"]
    assert len(out) == 1  # non-priority row dropped
    assert out.iloc[0]["priority_group"] == "dissolved_oxygen"  # widened "oxygen" substring
    assert out.iloc[0]["huc8"] == "13090002"


def test_tidy_wqp_results_empty_returns_typed_empty():
    out = tidy_wqp_results(pd.DataFrame(), HUC8)
    assert len(out) == 0
    assert list(out.columns)[0] == "monitoring_location_id"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run test -k tceq -v`
Expected: FAIL with `ImportError: cannot import name 'tidy_wqp_results'`

- [ ] **Step 3: Implement `_helpers/tceq.py`**

Create `notebooks/_helpers/tceq.py`:

```python
"""TCEQ Surface Water Quality Monitoring (SWQM) helpers: fetch and tidy results from the EPA
Water Quality Portal (WQP), which TCEQ submits its SWQMIS data to under organization TCEQMAIN.
TCEQ has no public API of its own — WQP is the practical programmatic path. Docs:
https://www.waterqualitydata.us/  API reference: dataretrieval.wqp."""

from __future__ import annotations

import pandas as pd

from .analysis import _warn_missing_huc8
from .config import PRIORITY_GROUPS
from .usgs import classify_parameter

TCEQ_COLUMNS = ["monitoring_location_id", "datetime", "characteristic", "parameter_code",
                "value", "unit", "fraction", "detection_condition", "qualifier", "lab_name",
                "priority_group", "huc8"]


def fetch_wqp_results(bbox: list[float], organization: str = "TCEQMAIN") -> pd.DataFrame:
    """Fetch every WQP result for one organization within a bounding box (raw response, no
    characteristic filter — the query is already scoped tightly enough by bbox+organization that
    an unfiltered pull is a manageable size; verified ~93k rows / ~80s for this project's study
    area). Docs: https://www.waterqualitydata.us/  (dataretrieval.wqp.get_results).

    Unlike dataretrieval.waterdata, WQP's `siteid` parameter does not reliably OR across multiple
    semicolon-joined ids (verified empirically — only the first id's rows were returned), so this
    intentionally does not filter by station id; downstream tidy_wqp_results tags huc8 per row
    from the discovered station inventory instead."""
    from dataretrieval import wqp

    raw, _ = wqp.get_results(organization=organization, bBox=",".join(str(v) for v in bbox))
    return raw


def tidy_wqp_results(
    raw: pd.DataFrame,
    huc8_by_station: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename WQP's legacy result columns -> keep rows whose characteristic maps to a priority
    group -> tag priority_group/huc8 -> select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=TCEQ_COLUMNS)
    renamed = raw.rename(columns={
        "MonitoringLocationIdentifier": "monitoring_location_id",
        "ActivityStartDateTime": "datetime",
        "CharacteristicName": "characteristic",
        "USGSPCode": "parameter_code",
        "ResultMeasureValue": "value",
        "ResultMeasure/MeasureUnitCode": "unit",
        "ResultSampleFractionText": "fraction",
        "ResultDetectionConditionText": "detection_condition",
        "MeasureQualifierCode": "qualifier",
        "LaboratoryName": "lab_name",
    })
    priority = renamed["characteristic"].map(lambda c: classify_parameter(characteristic=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[TCEQ_COLUMNS].sort_values(
        ["monitoring_location_id", "characteristic", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "TCEQ WQP")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pixi run test -k tceq -v`
Expected: PASS

- [ ] **Step 5: Re-export from `_helpers/__init__.py`**

Add to `notebooks/_helpers/__init__.py`:

```python
from .tceq import TCEQ_COLUMNS, fetch_wqp_results, tidy_wqp_results
```

(place it after the `.usgs` import block) and add to `__all__`:

```python
    "TCEQ_COLUMNS", "fetch_wqp_results", "tidy_wqp_results",
```

- [ ] **Step 6: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/tceq.py notebooks/_helpers/__init__.py notebooks/tests/test_tceq_tidy.py
git commit -m "feat: add _helpers/tceq.py (fetch/tidy TCEQ SWQM data via the EPA Water Quality Portal)"
```

---

## Task Group 4: `4_tceq_waterdata.py` notebook

### Task 6: Create notebook 4

**Files:**
- Create: `notebooks/4_tceq_waterdata.py` (jupytext-paired; `.ipynb` generated by `--sync`)

**Interfaces:**
- Consumes: `init_session`, `save_dataframe`, `show`, `categorical_colors`, `make_legend_clickable`,
  `coverage`, `trend_by_group` (existing/Task Group 1), `PRIORITY_GROUPS`, `PRIORITY_NAMES`,
  `classify_parameter` (existing), `fetch_wqp_results`, `tidy_wqp_results` (Task Group 3). Reads
  `data/hydrography/huc8_watersheds.parquet` (from NB1).
- Produces: `data/tceq_waterdata/tceq_monitoring_locations.parquet` (+csv),
  `data/tceq_waterdata/tceq_results.parquet` (+csv), `data/tceq_waterdata/tceq_trends.parquet`
  (+csv).

- [ ] **Step 1: Create the notebook file**

Create `notebooks/4_tceq_waterdata.py`:

```python
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 4 · TCEQ Surface Water Quality — Monitoring Stations & Results
#
# Reads the watershed boundaries from notebook 1, discovers TCEQ **Surface Water Quality
# Monitoring (SWQM)** stations inside them, and fetches their results. TCEQ has no public API of
# its own — SWQMIS data is submitted to the EPA **Water Quality Portal (WQP)** under organization
# `TCEQMAIN`, which we query via the same `dataretrieval` package used for USGS
# (`dataretrieval.wqp`). Primary source: <https://www.tceq.texas.gov/waterquality/monitoring>.
# API docs: <https://www.waterqualitydata.us/>.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
import geopandas as gpd
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the trend chart)
import pandas as pd
from dataretrieval import wqp

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_dataframe,
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

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Discover monitoring stations
#
# `wqp.what_sites` returns a **plain DataFrame** (unlike `dataretrieval.waterdata`, WQP has no
# built-in geometry column) — we build one from its lat/long columns, then keep only stations
# **within** the watershed polygons, exactly as notebook 3 does for USGS stations.

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

sites_df, _ = wqp.what_sites(organization="TCEQMAIN", bBox=",".join(str(v) for v in bbox))
stations_gdf = gpd.GeoDataFrame(
    sites_df,
    geometry=gpd.points_from_xy(sites_df["LongitudeMeasure"], sites_df["LatitudeMeasure"]),
    crs=4326,
)
stations_in_area = gpd.sjoin(
    stations_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)
print(
    f"{len(stations_gdf)} TCEQ stations in the bounding box; "
    f"{len(stations_in_area)} within the watersheds."
)
show(stations_in_area[["MonitoringLocationIdentifier", "MonitoringLocationName", "name"]])

# %% [markdown]
# ## Step 3 — Fetch the full results record
#
# We fetch **every** WQP result for `TCEQMAIN` in the study-area bounding box — not filtered by
# characteristic up front, mirroring notebook 3's discrete-samples fetch (`fetch_samples`), since
# WQP's per-organization-plus-bbox query is already small enough to pull in full (verified: tens of
# thousands of rows, under two minutes) and its exact characteristic-name vocabulary is easier to
# filter **after** fetching than to guess before.

# %%
raw_results = fetch_wqp_results(bbox, organization="TCEQMAIN")
show(raw_results.head())  # peek at the raw WQP response shape before we tidy it

# %% [markdown]
# ## Step 4 — Tidy and classify by priority parameter
#
# `tidy_wqp_results` renames WQP's columns to the project's convention, keeps only rows whose
# `characteristic` maps to one of our priority groups (`classify_parameter`), and tags
# `priority_group`/`huc8`.

# %%
huc8_by_station = dict(zip(stations_in_area["MonitoringLocationIdentifier"], stations_in_area["huc8"]))
tceq_results = tidy_wqp_results(raw_results, huc8_by_station)
show(tceq_results.head())
save_dataframe(tceq_results, S.data_dir / "tceq_waterdata" / "tceq_results.parquet")

# %% [markdown]
# ### Which stations measure which priority parameters?
#
# Derived from the tidied results (WQP has no separate lightweight "what does this station
# measure" endpoint the way USGS WaterData does, so we classify after fetching rather than
# before).
#
# > **A note on completeness:** in testing, **pH was completely absent** from TCEQ's WQP data for
# > every station checked, despite being a routine field measurement — this looks like a gap in
# > how TCEQ's pH results are tagged for WQP submission, not a bug in this notebook. If pH shows up
# > thin or missing below, that's this known gap, not a query error.

# %%
groups_by_station = tceq_results.groupby("monitoring_location_id")["priority_group"].agg(set).to_dict()
for group in PRIORITY_NAMES:
    stations_in_area[group] = stations_in_area["MonitoringLocationIdentifier"].map(
        lambda s, g=group: g in groups_by_station.get(s, set())
    )
save_dataframe(
    stations_in_area,
    S.data_dir / "tceq_waterdata" / "tceq_monitoring_locations.parquet",
)

print(f"Stations by priority parameter (of {len(stations_in_area)}):")
print(stations_in_area[PRIORITY_NAMES].sum().to_string())

unmatched = sorted({
    str(c) for c in raw_results["CharacteristicName"].dropna().unique()
    if classify_parameter(characteristic=c) is None
})
print(f"\n{len(unmatched)} unmatched characteristics (first 25):")
print("\n".join(unmatched[:25]))

show(stations_in_area[["MonitoringLocationIdentifier", "MonitoringLocationName", *PRIORITY_NAMES]])

# %% [markdown]
# ## Step 5 — Map stations by priority parameter
#
# One colored layer per priority parameter, over the watershed outlines. Click a legend entry to
# hide/show that parameter's layer.

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
        vdims=["MonitoringLocationName", "MonitoringLocationIdentifier"],
        label=param,
    ).opts(color=PARAM_COLORS[param], size=7, line_color="white", tools=["hover"])

stations_param_map = stations_param_map.opts(
    data_aspect=1,
    title="TCEQ monitoring stations by priority parameter (click legend to toggle)",
    legend_position="right",
    hooks=[make_legend_clickable],
)
stations_param_map

# %% [markdown]
# ## Step 6 — Data availability
#
# Record count + first/last date per station × priority group.

# %%
show(coverage(tceq_results, "datetime"))

# %%
tceq_year = tceq_results.assign(year=pd.to_datetime(tceq_results["datetime"]).dt.year)
availability = tceq_year.groupby(["monitoring_location_id", "year"]).size().reset_index(name="records")
availability.hvplot.heatmap(
    x="year", y="monitoring_location_id", C="records", cmap="blues",
    title="TCEQ result availability (count per station-year)", colorbar=True, rot=45,
)

# %% [markdown]
# ## Step 7 — Trends (Mann–Kendall + Sen's slope)
#
# Per station × priority-parameter, annual **median** (robust to non-detects / uneven sampling),
# same approach as notebook 3's water-quality series.

# %%
tceq_trends = trend_by_group(
    tceq_results, ["monitoring_location_id", "priority_group"], "datetime", "value", agg="median"
)
tceq_trends["significant"] = tceq_trends["p"] < 0.05
save_dataframe(tceq_trends, S.data_dir / "tceq_waterdata" / "tceq_trends.parquet")
show(tceq_trends.round({"p": 4, "slope": 4}))

# %%
trend_chart = tceq_trends.dropna(subset=["slope"]).hvplot.bar(
    x="priority_group", y="slope",
    hover_cols=["monitoring_location_id", "trend", "p", "significant"],
    frame_height=360, rot=40,
    ylabel="Sen's slope (per year)", xlabel="",
    title="TCEQ station trend rates by priority parameter (Sen's slope)",
).opts(active_tools=[])
trend_chart

# %% [markdown]
# ## What's next
#
# TCEQ results, station inventory, and trends are saved under `data/tceq_waterdata/`. Notebook
# **`5_twdb_waterdata`** covers TWDB groundwater; a future shared display notebook can compare
# trends across USGS/TCEQ/TWDB side by side.
```

- [ ] **Step 2: Generate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/4_tceq_waterdata.py`
Expected: `notebooks/4_tceq_waterdata.ipynb` is created.

- [ ] **Step 3: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/4_tceq_waterdata.ipynb`
Expected: completes without error (the WQP fetch takes ~1-2 minutes — this is expected, not a
hang). `data/tceq_waterdata/` contains `tceq_monitoring_locations`, `tceq_results`, `tceq_trends`
(each `.parquet` + `.csv`), all non-empty. Console output shows the unmatched-characteristics audit
and station counts.

- [ ] **Step 4: Sanity-check the pH gap is visible, not silently hidden**

Open the executed `.ipynb` (or check the printed `stations_in_area[PRIORITY_NAMES].sum()` output)
and confirm the `pH` column sums to 0 or near-0 — matching the documented caveat in Step 4's
markdown. If pH shows substantial non-zero coverage, the earlier live-testing finding may have been
non-representative for this exact bbox/time — note the actual observed count in a follow-up commit
message rather than silently leaving the caveat text wrong.

- [ ] **Step 5: Commit**

```bash
git add notebooks/4_tceq_waterdata.py notebooks/4_tceq_waterdata.ipynb data/tceq_waterdata/
git commit -m "feat: add 4_tceq_waterdata notebook (TCEQ SWQM via EPA Water Quality Portal)"
```

---

## Task Group 5: TWDB sandbox exploration

### Task 7: Prototype the GWDB bulk-file approach in `sandbox/`

Per this repo's convention (new data sources get explored in `sandbox/` before being ported to a
numbered notebook), and because the GWDB bulk-file mechanism is genuinely new to this project
(nothing else here downloads-and-filters a whole-state flat file), prototype it standalone first.
This task's real facts (file member names, exact pipe-delimited columns, ArcGIS FeatureServer
pagination) were already verified live during planning — this step writes that verification into a
reviewable sandbox script rather than re-discovering it blind.

**Files:**
- Create: `notebooks/sandbox/explore_twdb_gwdb_bulk.py`

**Interfaces:** none (sandbox scripts aren't imported by anything; `_quarto.yml`'s `render:` list
only globs `notebooks/*.py`, not `notebooks/sandbox/*.py`, so this never renders to the site).

- [ ] **Step 1: Create the sandbox script**

Create `notebooks/sandbox/explore_twdb_gwdb_bulk.py`:

```python
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Sandbox: TWDB GWDB bulk-file exploration
#
# TWDB's Groundwater Database (GWDB) ArcGIS FeatureServer
# (`Public/TWDB_Groundwater_database/FeatureServer/0`) only exposes a well **inventory** layer
# (location, aquifer, flags for whether level/quality data exist) — no time-series query endpoint.
# The actual water-level and water-quality measurements are only published as a **nightly full-state
# bulk file**: <https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip> (~81 MB zipped, ~1.7 GB
# unzipped). This notebook prototypes: (1) paginated ArcGIS bbox queries for well inventory, (2)
# downloading + caching the bulk zip, (3) extracting only the needed member files without
# unpacking the whole archive, (4) filtering the huge `WaterQualityMajor.txt` (~1 GB uncompressed)
# by `StateWellNumber` without loading it entirely into memory, and (5) confirming TWDB's water-
# quality `ParameterCode` reuses USGS-style codes (so `classify_parameter(parameter_code=...)`
# works unchanged). Once proven here, the approach is ported into `5_twdb_waterdata.py`.

# %% [markdown]
# ## Step 1 — Well inventory via the ArcGIS FeatureServer (paginated)
#
# The server's `maxRecordCount` is 1,000; a South-Texas-scale bbox returns ~3,300 wells, so
# pagination via `resultOffset` is required to get them all.

# %%
import geopandas as gpd
import requests

from _helpers import init_session

S = init_session()

GWDB_FEATURESERVER_URL = (
    "https://services.twdb.texas.gov/arcgis/rest/services/Public/"
    "TWDB_Groundwater_database/FeatureServer/0/query"
)
GWDB_PAGE_SIZE = 1000

bbox = [-98.5, 25.8, -97.0, 27.5]  # rough box around the 3 study HUC-8s

features, offset = [], 0
while True:
    params = {
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "geojson",
        "resultRecordCount": GWDB_PAGE_SIZE,
        "resultOffset": offset,
    }
    page = requests.get(GWDB_FEATURESERVER_URL, params=params, timeout=60).json()
    page_features = page.get("features", [])
    features.extend(page_features)
    print(f"offset {offset}: +{len(page_features)} features")
    if len(page_features) < GWDB_PAGE_SIZE:
        break
    offset += GWDB_PAGE_SIZE

wells = gpd.GeoDataFrame.from_features(features, crs=4326)
print(f"{len(wells)} wells total in bbox")
wells[["StateWellNumber", "WaterLevelObservationType", "WaterQualityAvailable"]].head()

# %% [markdown]
# ## Step 2 — Download and cache the bulk zip

# %%
import time
from pathlib import Path

GWDB_BULK_URL = "https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip"
zip_path = S.repo_root / "data_temp" / "gwdb_download.zip"


def fetch_gwdb_zip(dest: Path, url: str = GWDB_BULK_URL, max_age_days: int = 7) -> Path:
    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_days * 86400:
        print(f"using cached {dest} (< {max_age_days} days old)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} -> {dest} ...")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


zip_path = fetch_gwdb_zip(zip_path)
print(zip_path, zip_path.stat().st_size, "bytes")

# %% [markdown]
# ## Step 3 — Inspect member files (without extracting the whole archive)

# %%
import zipfile

with zipfile.ZipFile(zip_path) as z:
    for info in z.infolist():
        if "WaterLevels" in info.filename or "WaterQuality" in info.filename or "WellMain" in info.filename:
            print(f"{info.filename}\t{info.file_size:,} bytes")

# %% [markdown]
# ## Step 4 — Chunked filter by StateWellNumber (proves the memory-bounded approach)
#
# `WaterQualityMajor.txt` alone is ~1 GB uncompressed — read it in chunks and keep only rows for
# our bbox's wells, never materializing the whole file as a DataFrame.

# %%
import pandas as pd

well_ids = set(wells["StateWellNumber"].dropna())
print(f"{len(well_ids)} candidate well ids")

matched_chunks = []
with zipfile.ZipFile(zip_path) as z:
    with z.open("GWDBDownload/WaterQualityMajor.txt") as f:
        for chunk in pd.read_csv(
            f, sep="|", dtype=str,
            usecols=["StateWellNumber", "SampleDate", "ParameterCode", "ParameterDescription",
                     "ParameterUnitOfMeasure", "ParameterValue"],
            chunksize=200_000,
        ):
            matched = chunk[chunk["StateWellNumber"].isin(well_ids)]
            if len(matched):
                matched_chunks.append(matched)

water_quality_major = pd.concat(matched_chunks, ignore_index=True) if matched_chunks else pd.DataFrame()
print(f"{len(water_quality_major)} WaterQualityMajor rows matched our wells")
water_quality_major.head()

# %% [markdown]
# ## Step 5 — Confirm parameter codes classify with the existing `classify_parameter`
#
# TWDB's `ParameterCode` values are the same 5-digit USGS-style codes already in `PRIORITY_GROUPS`
# (verified: `00010` temperature, `00300` dissolved oxygen, `00400`/`00403` pH, `00095` specific
# conductance, the `006xx`/`0066x` nitrogen/phosphorus families, plus `82079` turbidity — the last
# two required widening `PRIORITY_GROUPS`, done in a separate task group).

# %%
from _helpers import classify_parameter

water_quality_major["priority_group"] = water_quality_major["ParameterCode"].map(
    lambda c: classify_parameter(parameter_code=c)
)
print(water_quality_major["priority_group"].value_counts(dropna=False))
```

- [ ] **Step 2: Sync + execute the sandbox script**

Run: `pixi run jupytext --sync notebooks/sandbox/explore_twdb_gwdb_bulk.py`
Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/sandbox/explore_twdb_gwdb_bulk.ipynb`

Expected: completes without error (the bulk download takes a minute or two the first time,
instant on reruns within 7 days); Step 5's `value_counts()` shows non-`NaN` priority groups for
at least `dissolved_oxygen`, `temperature`, `pH`, `conductivity` (the exact counts don't matter —
confirm they're non-zero, i.e. the classification path actually works on real data).

- [ ] **Step 3: Confirm `data_temp/gwdb_download.zip` is git-ignored**

Run: `git status --short`
Expected: `data_temp/` does **not** appear (already covered by the repo's `.gitignore`).

- [ ] **Step 4: Commit**

```bash
git add notebooks/sandbox/explore_twdb_gwdb_bulk.py notebooks/sandbox/explore_twdb_gwdb_bulk.ipynb
git commit -m "sandbox: prototype TWDB GWDB bulk-file download + chunked well filtering"
```

---

## Task Group 6: TWDB helpers (`_helpers/twdb.py`)

### Task 8: Create `_helpers/twdb.py`

**Files:**
- Create: `notebooks/_helpers/twdb.py`
- Test: `notebooks/tests/test_twdb_tidy.py`

**Interfaces:**
- Consumes: `classify_parameter(parameter_code=..., groups=...) -> str | None` (from `.usgs`),
  `_warn_missing_huc8(df, label) -> df` (from `.analysis`), `PRIORITY_GROUPS` (from `.config`).
- Produces:
  - `GWDB_FEATURESERVER_URL: str`, `GWDB_BULK_URL: str`
  - `WATER_LEVEL_MEMBERS: list[str]`, `WATER_QUALITY_MEMBERS: list[str]` (the four
    Major/Minor/Combination/OtherUnassigned zip member paths for each)
  - `GWDB_COLUMNS_LEVELS: list[str]`, `GWDB_COLUMNS_QUALITY: list[str]`
  - `fetch_gwdb_wells(bbox: list[float]) -> gpd.GeoDataFrame` (network, paginated)
  - `fetch_gwdb_zip(dest: Path, url: str = GWDB_BULK_URL, max_age_days: int = 7) -> Path` (network)
  - `fetch_gwdb_members(zip_path: Path, members: list[str], usecols: list[str], well_ids: set[str])
    -> pd.DataFrame` (network/IO — reads the local zip)
  - `tidy_gwdb_water_levels(raw: pd.DataFrame, huc8_by_well: dict[str, str]) -> pd.DataFrame` (pure)
  - `tidy_gwdb_water_quality(raw: pd.DataFrame, huc8_by_well: dict[str, str], groups: dict =
    PRIORITY_GROUPS) -> pd.DataFrame` (pure) — used by NB5.

- [ ] **Step 1: Write the failing tests**

Create `notebooks/tests/test_twdb_tidy.py`:

```python
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_gwdb_water_levels, tidy_gwdb_water_quality

HUC8 = {"0140901": "13090002"}


def test_tidy_gwdb_water_levels_tags_and_orders():
    raw = pd.DataFrame({
        "StateWellNumber": ["0140901", "0140901"],
        "MeasurementDate": ["1958-04-16", "1960-01-01"],
        "DepthFromLSD": ["73", "80"],
        "WaterElevation": ["4596", "4589"],
        "MeasuringAgency": ["Other or Source of Measurement Unknown", "TWDB"],
    })
    out = tidy_gwdb_water_levels(raw, HUC8)
    assert list(out.columns) == [
        "monitoring_location_id", "datetime", "depth_from_lsd_ft", "water_elevation_ft",
        "measuring_agency", "priority_group", "huc8"]
    assert len(out) == 2
    assert (out["priority_group"] == "water_level").all()
    assert out.iloc[0]["huc8"] == "13090002"


def test_tidy_gwdb_water_quality_keeps_priority_codes_only():
    raw = pd.DataFrame({
        "StateWellNumber": ["0140901", "0140901"],
        "SampleDate": ["1992-09-18", "1992-09-18"],
        "ParameterCode": ["00300", "39086"],  # 2nd (alkalinity) -> no group -> dropped
        "ParameterDescription": ["OXYGEN, DISSOLVED (MG/L)", "ALKALINITY FIELD DISSOLVED AS CACO3"],
        "ParameterUnitOfMeasure": ["MG/L", "MG/L AS CACO3"],
        "ParameterValue": ["6.2", "186"],
    })
    out = tidy_gwdb_water_quality(raw, HUC8)
    assert len(out) == 1
    assert out.iloc[0]["priority_group"] == "dissolved_oxygen"
    assert out.iloc[0]["huc8"] == "13090002"
    assert list(out.columns)[-2:] == ["priority_group", "huc8"]


def test_tidy_gwdb_empty_returns_typed_empty():
    assert list(tidy_gwdb_water_levels(pd.DataFrame(), HUC8).columns)[0] == "monitoring_location_id"
    assert len(tidy_gwdb_water_quality(pd.DataFrame(), HUC8)) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run test -k twdb -v`
Expected: FAIL with `ImportError: cannot import name 'tidy_gwdb_water_levels'`

- [ ] **Step 3: Implement `_helpers/twdb.py`**

Create `notebooks/_helpers/twdb.py`:

```python
"""TWDB Groundwater Database (GWDB) helpers. The ArcGIS FeatureServer only exposes a well
INVENTORY layer (location, aquifer, flags) — the actual water-level and water-quality time
series only exist in a nightly full-state bulk zip (GWDBDownload.zip), keyed by
StateWellNumber. Verified live: GWDB's water-quality ParameterCode reuses USGS-style parameter
codes, so classification reuses classify_parameter(parameter_code=...) unchanged."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analysis import _warn_missing_huc8
from .config import PRIORITY_GROUPS
from .usgs import classify_parameter

GWDB_FEATURESERVER_URL = (
    "https://services.twdb.texas.gov/arcgis/rest/services/Public/"
    "TWDB_Groundwater_database/FeatureServer/0/query"
)
GWDB_BULK_URL = "https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip"
GWDB_PAGE_SIZE = 1000  # the FeatureServer's maxRecordCount

WATER_LEVEL_MEMBERS = [
    "GWDBDownload/WaterLevelsMajor.txt",
    "GWDBDownload/WaterLevelsMinor.txt",
    "GWDBDownload/WaterLevelsCombination.txt",
    "GWDBDownload/WaterLevelsOtherUnassigned.txt",
]
WATER_QUALITY_MEMBERS = [
    "GWDBDownload/WaterQualityMajor.txt",
    "GWDBDownload/WaterQualityMinor.txt",
    "GWDBDownload/WaterQualityCombination.txt",
    "GWDBDownload/WaterQualityOtherUnassigned.txt",
]
WATER_LEVEL_USECOLS = ["StateWellNumber", "MeasurementDate", "DepthFromLSD", "WaterElevation", "MeasuringAgency"]
WATER_QUALITY_USECOLS = ["StateWellNumber", "SampleDate", "ParameterCode", "ParameterDescription",
                         "ParameterUnitOfMeasure", "ParameterValue"]

GWDB_COLUMNS_LEVELS = ["monitoring_location_id", "datetime", "depth_from_lsd_ft", "water_elevation_ft",
                      "measuring_agency", "priority_group", "huc8"]
GWDB_COLUMNS_QUALITY = ["monitoring_location_id", "datetime", "parameter_code", "parameter_description",
                       "value", "unit", "priority_group", "huc8"]


def fetch_gwdb_wells(bbox: list[float]) -> "gpd.GeoDataFrame":
    """Query the TWDB GWDB well-inventory ArcGIS FeatureServer within a bounding box, paginating
    past the server's 1,000-record page limit. Docs:
    https://www.twdb.texas.gov/mapping/data-services.asp"""
    import geopandas as gpd
    import requests

    features, offset = [], 0
    while True:
        params = {
            "geometry": ",".join(str(v) for v in bbox),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": GWDB_PAGE_SIZE,
            "resultOffset": offset,
        }
        page = requests.get(GWDB_FEATURESERVER_URL, params=params, timeout=60).json()
        page_features = page.get("features", [])
        features.extend(page_features)
        if len(page_features) < GWDB_PAGE_SIZE:
            break
        offset += GWDB_PAGE_SIZE
    return gpd.GeoDataFrame.from_features(features, crs=4326)


def fetch_gwdb_zip(dest: Path, url: str = GWDB_BULK_URL, max_age_days: int = 7) -> Path:
    """Download the nightly GWDB bulk zip (~81 MB) to `dest`, skipping the download if a cached
    copy under `max_age_days` old already exists (matches this project's week-long cache
    convention). Streamed to avoid holding the whole file in memory."""
    import time
    import requests

    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_days * 86400:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def fetch_gwdb_members(
    zip_path: Path, members: list[str], usecols: list[str], well_ids: set[str]
) -> pd.DataFrame:
    """Stream-read and filter each pipe-delimited member in the GWDB bulk zip to `well_ids`,
    chunked to bound memory (WaterQualityMajor.txt alone is ~1 GB uncompressed). Never extracts
    the full archive or loads a whole member into memory at once."""
    import zipfile

    frames = []
    with zipfile.ZipFile(zip_path) as z:
        for member in members:
            with z.open(member) as f:
                for chunk in pd.read_csv(f, sep="|", usecols=usecols, dtype=str, chunksize=200_000):
                    matched = chunk[chunk["StateWellNumber"].isin(well_ids)]
                    if len(matched):
                        frames.append(matched)
    if not frames:
        return pd.DataFrame(columns=usecols)
    return pd.concat(frames, ignore_index=True)


def tidy_gwdb_water_levels(raw: pd.DataFrame, huc8_by_well: dict[str, str]) -> pd.DataFrame:
    """Rename GWDB water-level columns -> tag priority_group ('water_level' — GWDB's water-level
    file has no other analyte) + huc8 -> select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=GWDB_COLUMNS_LEVELS)
    renamed = raw.rename(columns={
        "StateWellNumber": "monitoring_location_id",
        "MeasurementDate": "datetime",
        "DepthFromLSD": "depth_from_lsd_ft",
        "WaterElevation": "water_elevation_ft",
        "MeasuringAgency": "measuring_agency",
    })
    tidy = renamed.assign(
        priority_group="water_level",
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_well),
    )
    tidy = tidy[GWDB_COLUMNS_LEVELS].sort_values(
        ["monitoring_location_id", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "GWDB water levels")


def tidy_gwdb_water_quality(
    raw: pd.DataFrame,
    huc8_by_well: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename GWDB water-quality columns -> keep rows whose ParameterCode maps to a priority group
    (GWDB reuses USGS-style parameter codes) -> tag priority_group/huc8 -> select/sort. Pure; no
    network."""
    if raw.empty:
        return pd.DataFrame(columns=GWDB_COLUMNS_QUALITY)
    renamed = raw.rename(columns={
        "StateWellNumber": "monitoring_location_id",
        "SampleDate": "datetime",
        "ParameterCode": "parameter_code",
        "ParameterDescription": "parameter_description",
        "ParameterValue": "value",
        "ParameterUnitOfMeasure": "unit",
    })
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_well),
    )
    tidy = tidy[GWDB_COLUMNS_QUALITY].sort_values(
        ["monitoring_location_id", "parameter_code", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "GWDB water quality")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pixi run test -k twdb -v`
Expected: PASS

- [ ] **Step 5: Re-export from `_helpers/__init__.py`**

Add to `notebooks/_helpers/__init__.py`:

```python
from .twdb import (
    GWDB_BULK_URL,
    GWDB_FEATURESERVER_URL,
    fetch_gwdb_members,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
)
```

and to `__all__`:

```python
    "GWDB_FEATURESERVER_URL", "GWDB_BULK_URL", "fetch_gwdb_wells", "fetch_gwdb_zip",
    "fetch_gwdb_members", "tidy_gwdb_water_levels", "tidy_gwdb_water_quality",
```

- [ ] **Step 6: Run the full test suite**

Run: `pixi run test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/twdb.py notebooks/_helpers/__init__.py notebooks/tests/test_twdb_tidy.py
git commit -m "feat: add _helpers/twdb.py (fetch/tidy TWDB GWDB well inventory + bulk water-level/quality)"
```

---

## Task Group 7: `5_twdb_waterdata.py` notebook

### Task 9: Create notebook 5

**Files:**
- Create: `notebooks/5_twdb_waterdata.py` (jupytext-paired; `.ipynb` generated by `--sync`)

**Interfaces:**
- Consumes: `init_session`, `save_dataframe`, `show`, `categorical_colors`, `make_legend_clickable`,
  `coverage`, `trend_by_group`, `PRIORITY_NAMES` (existing/Task Group 1), `fetch_gwdb_wells`,
  `fetch_gwdb_zip`, `fetch_gwdb_members`, `tidy_gwdb_water_levels`, `tidy_gwdb_water_quality`,
  `WATER_LEVEL_MEMBERS`, `WATER_QUALITY_MEMBERS`, `WATER_LEVEL_USECOLS`, `WATER_QUALITY_USECOLS`
  (Task Group 6 — note the last four are module constants in `twdb.py`, not currently re-exported;
  import them directly from `_helpers.twdb` in the notebook, matching how NB3 defines its own
  `SAMPLES_SUMMARY_URL` locally rather than exporting every endpoint constant). Reads
  `data/hydrography/huc8_watersheds.parquet` (from NB1).
- Produces: `data/twdb_waterdata/twdb_wells.parquet` (+csv),
  `data/twdb_waterdata/twdb_water_levels.parquet` (+csv),
  `data/twdb_waterdata/twdb_water_quality.parquet` (+csv),
  `data/twdb_waterdata/twdb_trends.parquet` (+csv).

- [ ] **Step 1: Create the notebook file**

Create `notebooks/5_twdb_waterdata.py`:

```python
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 5 · TWDB Groundwater — Well Inventory, Water Levels & Quality
#
# Reads the watershed boundaries from notebook 1, discovers **TWDB Groundwater Database (GWDB)**
# wells inside them via the TWDB ArcGIS FeatureServer, then fetches their water-level and
# water-quality **measurements** from TWDB's nightly full-state bulk file — the FeatureServer only
# carries well *inventory* (location, aquifer, flags), not the actual time series. Primary source:
# <https://www.twdb.texas.gov/groundwater/data/index.asp>.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
import geopandas as gpd
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the trend chart)
import pandas as pd

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_dataframe,
    show,
    categorical_colors,
    make_legend_clickable,
    PRIORITY_NAMES,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    fetch_gwdb_members,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
    coverage,
    trend_by_group,
)
from _helpers.twdb import WATER_LEVEL_MEMBERS, WATER_LEVEL_USECOLS, WATER_QUALITY_MEMBERS, WATER_QUALITY_USECOLS

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Discover wells
#
# Queries the GWDB well-inventory ArcGIS FeatureServer within the watersheds' bounding box, then
# keeps only wells **within** the watershed polygons — same bbox-then-spatial-join pattern as
# notebooks 3-4.

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

wells_gdf = fetch_gwdb_wells(bbox)
wells_in_area = gpd.sjoin(
    wells_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)
print(f"{len(wells_gdf)} GWDB wells in the bounding box; {len(wells_in_area)} within the watersheds.")
save_dataframe(wells_in_area, S.data_dir / "twdb_waterdata" / "twdb_wells.parquet")
show(wells_in_area[["StateWellNumber", "CountyName", "WaterLevelObservationType", "WaterQualityAvailable", "name"]])

# %% [markdown]
# ## Step 3 — Download the nightly GWDB bulk file
#
# The ArcGIS layer above is inventory-only; the actual water-level/quality measurements live in a
# nightly full-state zip, cached locally for a week (like this project's other request caches) so
# re-running the notebook doesn't re-download ~81 MB every time.

# %%
zip_path = fetch_gwdb_zip(S.repo_root / "data_temp" / "gwdb_download.zip")
well_ids = set(wells_in_area["StateWellNumber"].dropna())
huc8_by_well = dict(zip(wells_in_area["StateWellNumber"], wells_in_area["huc8"]))
print(f"{zip_path} ({zip_path.stat().st_size:,} bytes); {len(well_ids)} wells to filter for")

# %% [markdown]
# ## Step 4 — Water levels
#
# Filters the four Major/Minor/Combination/OtherUnassigned water-level files down to our wells,
# streamed in chunks (the files are large statewide extracts).

# %%
water_levels_raw = fetch_gwdb_members(zip_path, WATER_LEVEL_MEMBERS, WATER_LEVEL_USECOLS, well_ids)
show(water_levels_raw.head())  # peek at the raw GWDB file shape before we tidy it

# %%
twdb_water_levels = tidy_gwdb_water_levels(water_levels_raw, huc8_by_well)
show(twdb_water_levels.head())
save_dataframe(twdb_water_levels, S.data_dir / "twdb_waterdata" / "twdb_water_levels.parquet")

# %% [markdown]
# ## Step 5 — Water quality
#
# Same filtering approach for the water-quality files; classification reuses `classify_parameter`
# on GWDB's `ParameterCode` (confirmed in the sandbox exploration to reuse USGS-style codes).

# %%
water_quality_raw = fetch_gwdb_members(zip_path, WATER_QUALITY_MEMBERS, WATER_QUALITY_USECOLS, well_ids)
show(water_quality_raw.head())  # peek at the raw GWDB file shape before we tidy it

# %%
twdb_water_quality = tidy_gwdb_water_quality(water_quality_raw, huc8_by_well)
show(twdb_water_quality.head())
save_dataframe(twdb_water_quality, S.data_dir / "twdb_waterdata" / "twdb_water_quality.parquet")

print(f"Wells by data type (of {len(wells_in_area)}):")
print(pd.Series({
    "water_level": twdb_water_levels["monitoring_location_id"].nunique(),
    "water_quality": twdb_water_quality["monitoring_location_id"].nunique(),
}).to_string())

# %% [markdown]
# ## Step 6 — Map wells by data availability
#
# Wells with water-level records, water-quality records, or both, over the watershed outlines.

# %%
level_ids = set(twdb_water_levels["monitoring_location_id"])
quality_ids = set(twdb_water_quality["monitoring_location_id"])
DATA_TYPE_COLORS = categorical_colors(["water_level", "water_quality"])
watershed_outlines = gv.Path(watersheds_gdf).opts(color="black", line_width=1.5)

wells_map = gvts.EsriWorldTopo * watershed_outlines
for label, ids in [("water_level", level_ids), ("water_quality", quality_ids)]:
    subset = wells_in_area[wells_in_area["StateWellNumber"].isin(ids)]
    if len(subset) == 0:
        continue
    wells_map = wells_map * gv.Points(
        subset, vdims=["StateWellNumber", "CountyName"], label=label,
    ).opts(color=DATA_TYPE_COLORS[label], size=7, line_color="white", tools=["hover"])

wells_map = wells_map.opts(
    data_aspect=1,
    title="TWDB GWDB wells by data type (click legend to toggle)",
    legend_position="right",
    hooks=[make_legend_clickable],
)
wells_map

# %% [markdown]
# ## Step 7 — Data availability

# %%
show(coverage(twdb_water_levels, "datetime"))

# %%
show(coverage(twdb_water_quality, "datetime"))

# %% [markdown]
# ## Step 8 — Trends (Mann–Kendall + Sen's slope)
#
# Per well × priority-parameter, annual **median** — water levels and quality samples are both
# irregular series, same treatment as notebooks 3-4's water-quality trends.

# %%
level_trends = trend_by_group(
    twdb_water_levels, ["monitoring_location_id", "priority_group"], "datetime", "water_elevation_ft", agg="median"
)
quality_trends = trend_by_group(
    twdb_water_quality, ["monitoring_location_id", "priority_group"], "datetime", "value", agg="median"
)
twdb_trends = pd.concat(
    [level_trends.assign(data_type="water_level"), quality_trends.assign(data_type="water_quality")],
    ignore_index=True,
)
twdb_trends["significant"] = twdb_trends["p"] < 0.05
save_dataframe(twdb_trends, S.data_dir / "twdb_waterdata" / "twdb_trends.parquet")
show(twdb_trends.round({"p": 4, "slope": 4}))

# %%
trend_chart = twdb_trends.dropna(subset=["slope"]).hvplot.bar(
    x="priority_group", y="slope", by="data_type",
    hover_cols=["monitoring_location_id", "trend", "p", "significant"],
    frame_height=360, rot=40,
    ylabel="Sen's slope (per year)", xlabel="",
    title="TWDB well trend rates by priority parameter (Sen's slope)", legend="top_right",
).opts(active_tools=[])
trend_chart

# %% [markdown]
# ## What's next
#
# Well inventory, water levels, water quality, and trends are saved under `data/twdb_waterdata/`.
# A future shared display notebook can compare USGS/TCEQ/TWDB trends side by side, and TWDB's
# coastal surface-water data (waterdatafortexas.org, relevant to the South Laguna Madre watershed)
# remains a candidate for a later round.
```

- [ ] **Step 2: Generate the paired `.ipynb`**

Run: `pixi run jupytext --sync notebooks/5_twdb_waterdata.py`
Expected: `notebooks/5_twdb_waterdata.ipynb` is created.

- [ ] **Step 3: Execute the notebook headlessly**

Run: `pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/5_twdb_waterdata.ipynb`
Expected: completes without error (the bulk zip download/filter takes a few minutes on a cold
cache, seconds if `sandbox/explore_twdb_gwdb_bulk` already populated `data_temp/gwdb_download.zip`
within the last week). `data/twdb_waterdata/` contains `twdb_wells`, and **at least one** of
`twdb_water_levels`/`twdb_water_quality` non-empty (report actual row counts — groundwater coverage
in this coastal area may genuinely be sparse; don't assume both are populous).

- [ ] **Step 4: Commit**

```bash
git add notebooks/5_twdb_waterdata.py notebooks/5_twdb_waterdata.ipynb data/twdb_waterdata/
git commit -m "feat: add 5_twdb_waterdata notebook (TWDB GWDB well inventory + bulk water-level/quality)"
```

---

## Task Group 8: Docs & site integration

### Task 10: Update `CLAUDE.md`, `README.md`, `_quarto.yml`, `index.qmd`

**Files:**
- Modify: `CLAUDE.md` (helper inventory list, storage-and-data bullets)
- Modify: `README.md` (Approach section)
- Modify: `_quarto.yml` (navbar)
- Modify: `index.qmd` (notebook cards)

- [ ] **Step 1: Update `CLAUDE.md`'s helper inventory**

In `CLAUDE.md`, under **This repo:** → "Helper inventory", change:

```
  - `usgs` — `classify_parameter`, `build_parameter_name_lookup`, `station_parameters`,
    `fetch_daily`/`fetch_samples`/`fetch_field`, `tidy_daily`/`tidy_samples`/`tidy_field`.
```

to add two new bullets right after it:

```
  - `usgs` — `classify_parameter`, `build_parameter_name_lookup`, `station_parameters`,
    `fetch_daily`/`fetch_samples`/`fetch_field`, `tidy_daily`/`tidy_samples`/`tidy_field`.
  - `tceq` — `fetch_wqp_results`/`tidy_wqp_results` (EPA Water Quality Portal, organization
    `TCEQMAIN` — TCEQ has no API of its own).
  - `twdb` — `fetch_gwdb_wells` (ArcGIS FeatureServer inventory), `fetch_gwdb_zip`/
    `fetch_gwdb_members` (nightly bulk file — the FeatureServer has no time-series endpoint),
    `tidy_gwdb_water_levels`/`tidy_gwdb_water_quality`.
```

and change:

```
  - `analysis` — `water_year`, `mk_sen_trend`, `coverage`.
```

to:

```
  - `analysis` — `water_year`, `mk_sen_trend`, `coverage`, `trend_by_group`.
```

- [ ] **Step 2: Add a `data_temp/` bullet under Storage & data → This repo**

In `CLAUDE.md`'s `## Storage & data` → **This repo:** section, add:

```
- `data/tceq_waterdata/` — TCEQ Surface Water Quality Monitoring results via the EPA Water
  Quality Portal (`dataretrieval.wqp`, organization `TCEQMAIN`).
- `data/twdb_waterdata/` — TWDB GWDB well inventory (ArcGIS FeatureServer) + water levels/quality
  (TWDB's nightly bulk file, filtered to the study wells).
```

right after the existing `data/usgs_waterdata/` bullet, and add a note near the top-level
`## Storage & data` general bullets:

```
- **`data_temp/gwdb_download.zip`** (git-ignored scratch) caches TWDB's nightly full-state bulk
  file for a week — much larger than the HTTP request cache, so it's kept separate rather than
  routed through `cache/`.
```

- [ ] **Step 3: Update `README.md`'s Approach section**

In `README.md`, after the existing `**3_usgs_waterdata**` bullet (ends `...**discharge** and
**water level**).`), add two new bullets:

```markdown
  - **`4_tceq_waterdata`** — discovers TCEQ Surface Water Quality Monitoring stations within the
    watersheds via the EPA Water Quality Portal (TCEQ has no public API of its own) and fetches
    their results, classified into the same priority parameter groups.
  - **`5_twdb_waterdata`** — discovers TWDB Groundwater Database wells within the watersheds via
    TWDB's ArcGIS FeatureServer, then fetches water-level and water-quality measurements from
    TWDB's nightly bulk file (the FeatureServer itself carries only well inventory, not time
    series).
```

- [ ] **Step 4: Add the two new notebooks to `_quarto.yml`'s navbar**

In `_quarto.yml`, under `website: navbar: left:`, after the `3 · WaterData stations` entry, add:

```yaml
      - href: notebooks/4_tceq_waterdata.html
        text: "4 · TCEQ WaterData"
      - href: notebooks/5_twdb_waterdata.html
        text: "5 · TWDB WaterData"
```

- [ ] **Step 5: Add cards for the two new notebooks to `index.qmd`**

In `index.qmd`, inside the `::: {.grid}` block, after the existing `3 · USGS WaterData` card, add:

```markdown
::: {.g-col-12 .g-col-md-4}
### [4 · TCEQ WaterData](notebooks/4_tceq_waterdata.html)
Discovers **TCEQ Surface Water Quality Monitoring** stations via the EPA Water Quality Portal and
fetches their results, classified into the same priority parameters.
:::

::: {.g-col-12 .g-col-md-4}
### [5 · TWDB WaterData](notebooks/5_twdb_waterdata.html)
Discovers **TWDB Groundwater Database** wells and fetches water-level and water-quality
measurements from TWDB's nightly bulk file.
:::
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md _quarto.yml index.qmd
git commit -m "docs: document TCEQ/TWDB notebooks, new helpers, and data_temp/ convention"
```

### Task 11: Render and final verification

**Files:** none new — this task only runs commands and inspects output.

- [ ] **Step 1: Run the full test suite one more time**

Run: `pixi run test`
Expected: PASS (all tests across `test_analysis.py`, `test_usgs_classify.py`, `test_usgs_tidy.py`,
`test_tceq_tidy.py`, `test_twdb_tidy.py`, `test_save_dataframe.py`, `test_save_datacube_attrs.py`).

- [ ] **Step 2: Render the site**

Run: `pixi run render`
Expected: builds `_site/` including `4_tceq_waterdata.html` and `5_twdb_waterdata.html`; no errors;
`_freeze/notebooks/4_tceq_waterdata/` and `_freeze/notebooks/5_twdb_waterdata/` are created.

- [ ] **Step 3: Manually confirm the home page and navbar**

Open `_site/index.html` (or `pixi run preview`) and confirm: five notebook cards in the new order,
all links resolve; navbar shows `4 · TCEQ WaterData` and `5 · TWDB WaterData` in order.

- [ ] **Step 4: Confirm `data_temp/` is not staged**

Run: `git status --short`
Expected: no `data_temp/` entries; `_freeze/notebooks/4_tceq_waterdata/` and
`_freeze/notebooks/5_twdb_waterdata/` **are** staged (this repo commits `_freeze/`).

- [ ] **Step 5: Commit**

```bash
git add _freeze/notebooks/4_tceq_waterdata _freeze/notebooks/5_twdb_waterdata
git commit -m "chore: render TCEQ/TWDB notebooks into the Quarto site (_freeze/)"
```

## Out of scope (unchanged from the spec)

TWDB's coastal surface-water Coastal API, continuous/instantaneous USGS data, cross-source trend
comparison, normalized/de-weathered trends, pre/post-restoration comparisons, the Excel
deliverable, IBWC and NOAA NCEI sources, and resolving the TCEQ pH gap upstream of WQP.
