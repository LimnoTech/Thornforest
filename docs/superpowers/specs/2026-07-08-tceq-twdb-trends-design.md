# Round 4 — TCEQ & TWDB fetch notebooks, plus trend analysis in NB3–5

**Date:** 2026-07-08

**Status:** Draft for review

**Scope:** Three cohesive additions to the notebook series:

1. **`4_tceq_waterdata`** — new fetch notebook: TCEQ Surface Water Quality Monitoring (SWQM) data
   via the EPA Water Quality Portal (WQP).
2. **`5_twdb_waterdata`** — new fetch notebook: TWDB Groundwater Database (GWDB) well inventory +
   water-level/water-quality bulk records.
3. **Trend analysis** (Mann–Kendall + Sen's slope) added to `3_usgs_waterdata`, and to both new
   notebooks — a shared `trend_by_group` helper, applied per station × priority-parameter.

## Context & goal

Round 3 built `3_usgs_waterdata`, discovering USGS stations and fetching their daily/samples/field
records. The README's Task 2 scope also calls for TCEQ SWQM and TWDB groundwater/surface-water
data, and for trend analyses of the raw data. This round adds both.

**API research findings** (verified live against the real services, not just documentation):

- **TCEQ has no public API of its own.** SWQMIS exposes only a GUI viewer. The practical path is
  the **EPA Water Quality Portal**, via `dataretrieval.wqp` — the same `dataretrieval` package NB3
  already depends on (`wqp.what_sites`, `wqp.get_results`), so no new dependency. TCEQ's data is
  registered there (organization `TCEQMAIN`, 10,274 sites) and results *are* retrievable, but only
  when the query is **scoped** (organization + bbox + characteristic list + date range) — an
  unscoped `organization=TCEQMAIN` pull attempts to stream the state's entire multi-decade record
  and is impractically slow.
- **TCEQ's WQP characteristic names differ from the USGS/WQX names our `PRIORITY_GROUPS` substrings
  already match** — confirmed by live query: TCEQ tags dissolved oxygen as `"Oxygen"` (not
  `"Dissolved oxygen (DO)"`) and water temperature as `"Temperature, sample"` (not `"Temperature,
  water"`). `PRIORITY_GROUPS` needs broader substrings to classify both sources.
- **pH is absent from TCEQ's WQP data** in every station checked, despite being a routine field
  parameter — a real, confirmed gap (not a bug in our code), documented as a caveat rather than
  silently producing thin/zero pH results.
- **TWDB has no time-series query API at all.** The GWDB ArcGIS FeatureServer
  (`services.twdb.texas.gov/.../TWDB_Groundwater_database/FeatureServer/0`) is a single layer of
  well **inventory** (location, aquifer, well depth, and flags for whether level/quality data
  exist) — it does not carry the actual measurements. The real water-level and water-quality
  records are only published as a **nightly full-state bulk file**,
  `https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip` (~81 MB zipped, ~1.7 GB
  unzipped), containing pipe-delimited tables (`WaterLevels{Major,Minor,Combination,
  OtherUnassigned}.txt`, `WaterQuality{Major,Minor,Combination,OtherUnassigned}.txt`,
  `WellMain.txt`) keyed by `StateWellNumber`. This is a materially different fetch mechanism
  (bulk-download-and-filter) from every other source in the project (query-by-bbox).
- `mk_sen_trend`/`water_year` (in `_helpers/analysis.py`) are already generic and reusable —
  no new trend math needed, just a grouping helper.

## Decisions (resolved with user)

1. **TWDB scope:** groundwater only (GWDB). The waterdatafortexas.org Coastal API (bays/estuaries)
   is deferred — noted as a candidate for a later round given South Laguna Madre is coastal.
2. **Two new notebooks**, not one combined: `4_tceq_waterdata`, `5_twdb_waterdata` — consistent
   with the existing one-notebook-per-source convention, and justified by genuinely different fetch
   mechanisms (WQP query vs. bulk-file download).
3. **Trend analysis lives in each fetch notebook** (NB3, NB4, NB5), not deferred to a future shared
   display notebook. This supersedes NB3's current closing comment that trends live in a later
   display notebook.
4. **Trend aggregation:** resample each station × priority-parameter series to **one value per
   calendar year**, then run `mk_sen_trend` on the annual series. **Median** for irregular
   water-quality/level series (robust to non-detects and uneven sampling); **mean** for the regular
   daily discharge series (a rate, not a count).
5. **Shared `trend_by_group` helper** in `_helpers/analysis.py`, reused by all three notebooks,
   rather than copy-pasting the loop three times.
6. **Granularity: per station × priority_group** (matching the existing `coverage()` grouping) —
   the natural unit for point-station data, distinct from NB2's per-watershed grid trends (which
   aggregate a continuous raster, not discrete stations).

## Architecture & file layout

```text
notebooks/
  _helpers/
    analysis.py       + trend_by_group(df, group_cols, time_col, value_col, agg="median")
    config.py          PRIORITY_GROUPS characteristic substrings widened (oxygen, temperature)
    tceq.py            NEW — fetch_wqp_results (network) / tidy_wqp_results (pure)
    twdb.py            NEW — fetch_gwdb_wells, fetch_gwdb_bulk (network) /
                             tidy_gwdb_water_levels, tidy_gwdb_water_quality (pure)
    __init__.py        + re-exports for the above
  3_usgs_waterdata.py   + Step 7 — Trends (trend_by_group on daily/samples/field)
  4_tceq_waterdata.py   NEW — mirrors 3_usgs_waterdata's shape
  5_twdb_waterdata.py   NEW — well inventory (ArcGIS) + bulk water-level/quality (zip)
  tests/
    test_analysis.py    + tests for trend_by_group
    test_tceq_tidy.py   NEW — tidy_wqp_results unit tests
    test_twdb_tidy.py   NEW — tidy_gwdb_water_levels/quality unit tests
sandbox/
  explore_twdb_gwdb_bulk.py   NEW — prototype the zip-member extraction + StateWellNumber filter
                                     before porting into notebook 5 (per CLAUDE.md's sandbox-first rule)
data/
  tceq_waterdata/        NEW — tceq_monitoring_locations, tceq_results, tceq_trends (.parquet+.csv)
  twdb_waterdata/         NEW — twdb_wells, twdb_water_levels, twdb_water_quality, twdb_trends
data_temp/
  gwdb_download.zip       NEW — the cached nightly bulk file (git-ignored scratch; re-downloaded
                                 weekly, matching the HTTP cache's expiry convention)
CLAUDE.md                 helper inventory + storage sections updated with the new modules/folders
README.md                 approach section gains NB4/NB5 bullets
```

**Data flow.** Both new notebooks read `data/hydrography/huc8_watersheds.parquet` from NB1, exactly
like NB3. Neither depends on NB3's output. `data_temp/gwdb_download.zip` is scratch (never
committed); only the filtered, tidied `data/twdb_waterdata/*` products are committed, matching the
existing `cache/` (HTTP request cache) vs. `data_temp/` (scratch downloads) vs. `data/` (curated
outputs) three-way split.

## Component design

### 1. `PRIORITY_GROUPS` vocabulary widening (`_helpers/config.py`)

Broaden `characteristics` substring lists so both USGS/WQX and TCEQ naming classify correctly:

- `dissolved_oxygen`: add `"oxygen"` (currently only `"dissolved oxygen"`).
- `temperature`: add `"temperature"` broadened from the exact `"temperature, water"` (catches TCEQ's
  `"Temperature, sample"` too). Checked for false positives against the existing characteristic
  vocabulary in NB3's unmatched-characteristics audit; none expected (no unrelated "temperature"
  characteristics in the USGS or WQP samples seen so far).

This is a shared, source-agnostic fix (not TCEQ-specific code) that also makes USGS classification
marginally more robust.

### 2. `4_tceq_waterdata.py`

Same shape as `3_usgs_waterdata`:

- **Step 2 — Discover stations:** `wqp.what_sites(organization="TCEQMAIN", bBox=...)`, `sjoin`ed to
  the watersheds (identical pattern to NB3 Step 2).
- **Step 3 — Classify by priority parameter:** for each priority group, query
  `wqp.get_results(organization="TCEQMAIN", bBox=..., characteristicName="<group's ; -joined
  characteristics>", ...)` — one scoped call per group (or a combined call across all groups'
  characteristics in one pass if the response size is manageable; decided during implementation
  against real row counts). Tag with `priority_group` via `classify_parameter`.
- **Step 4 — Fetch full record:** `_helpers/tceq.py`:
  - `fetch_wqp_results(station_ids, characteristics) -> raw DataFrame` (network; wraps
    `wqp.get_results`).
  - `tidy_wqp_results(raw, huc8_by_station, groups=PRIORITY_GROUPS) -> DataFrame` (pure): rename
    WQP's `MonitoringLocationIdentifier` → `monitoring_location_id`, `ActivityStartDate`/
    `ActivityStartDateTime` → `datetime`, `CharacteristicName` → `characteristic`,
    `ResultMeasureValue` → `value`, `ResultMeasure/MeasureUnitCode` → `unit`,
    `ResultSampleFractionText` → `fraction`, `ResultDetectionConditionText` →
    `detection_condition`, `MeasureQualifierCode` → `qualifier`, `LaboratoryName` → `lab_name` —
    same column convention as `tidy_samples`, filtered to rows whose characteristic maps to a
    priority group, tagged with `priority_group`/`huc8`.
- **Step 5 — Audit + documented gap:** unmatched-characteristics audit (same as NB3), plus an
  explicit markdown note: *pH results are not currently retrievable for TCEQ stations via the Water
  Quality Portal* (confirmed by live testing) — mirrors how the Mexico binational gap is documented
  in the README, so a reader understands why pH is thin/absent rather than suspecting a bug.
- **Step 6 — Map + Step 7 — Availability:** same shape as NB3 Steps 5–6.
- **Step 8 — Trends:** see Component 4 below.

### 3. `5_twdb_waterdata.py`

- **Step 2 — Discover wells:** query the ArcGIS FeatureServer's `query` endpoint
  (`.../TWDB_Groundwater_database/FeatureServer/0/query?geometry=<bbox>&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=geojson`),
  paginated via `resultOffset`/`maxRecordCount` (1,000/page) if needed. Read directly with
  `geopandas.read_file` (GeoJSON) or `requests`+`json`, `sjoin`ed to the watersheds. Flags
  `WaterLevelObservationType`/`WaterQualityAvailable` on the inventory play the same role as NB3's
  `daily`/`continuous`/etc. columns.
- **Step 3 — Bulk download:** `_helpers/twdb.py::fetch_gwdb_bulk()` — downloads
  `GWDBDownload.zip` to `data_temp/` (skips re-download if a cached copy is under a week old,
  matching `S.cache_expire_seconds`), then uses `zipfile.ZipFile` to extract **only** the eight
  water-level/water-quality member files plus `WellMain.txt` — never the full archive.
- **Step 4 — Filter + tidy:** `tidy_gwdb_water_levels(raw, well_ids, huc8_by_well)` /
  `tidy_gwdb_water_quality(raw, well_ids, huc8_by_well, groups=PRIORITY_GROUPS)` (pure): filter the
  four Major/Minor/Combination/OtherUnassigned splits down to `StateWellNumber`s in our watershed
  wells, concatenate, rename to project conventions (`StateWellNumber` → `monitoring_location_id`,
  `MeasurementDate`/`SampleDate` → `datetime`, `WaterElevation`/`DepthFromLSD` → `value`,
  `ParameterCode`/`ParameterDescription` → classified via `classify_parameter` — TWDB's codes are
  its own analyte system, not USGS pcodes, so this reuses the **characteristic-name** matching path
  (`ParameterDescription`) rather than the parameter-code path; confirmed feasible during sandbox
  exploration).
- **Step 5 — Map + Step 6 — Availability:** same shape as NB3.
- **Step 7 — Trends:** see Component 4.

**Sandbox-first:** prototype the zip member extraction, `StateWellNumber` filtering, and
`ParameterDescription` → `priority_group` classification in `sandbox/explore_twdb_gwdb_bulk.py`
before writing notebook 5's real steps — this bulk-file pattern is unproven in this repo and the
file is large enough that debugging it inside the numbered notebook would be slow to iterate on.

### 4. Trend analysis (`_helpers/analysis.py` + NB3/4/5)

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
    one row per group with trend/p/slope/n_years alongside the group_cols."""
```

- Coerces `value_col` via `pd.to_numeric(errors="coerce")` before aggregating (mirrors the existing
  `tidy_samples` docstring note that `value` may hold non-numeric text).
- Applied per notebook:
  - **NB3:** `trend_by_group(daily, ["monitoring_location_id", "priority_group"], "date", "value",
    agg="mean")`; same call on `samples`/`field` with `agg="median"`. Saved as
    `data/usgs_waterdata/usgs_trends.parquet`. **Removes** NB3's existing closing comment that
    trends live in a later display notebook.
  - **NB4:** same pattern on the tidied WQP results → `data/tceq_waterdata/tceq_trends.parquet`.
  - **NB5:** same pattern on water levels + water quality →
    `data/twdb_waterdata/twdb_trends.parquet`.
- Each notebook adds an `hvplot.bar` trend chart (Sen's slope per priority parameter, colored by
  station or faceted), consistent with NB2's Step 8 trend chart style.
- Unit tests in `test_analysis.py`: insufficient-data passthrough, a known increasing/decreasing
  synthetic series, mean vs. median aggregation producing different slopes on the same input.

## Testing / verification

- `pixi run test` passes, including new tests for `trend_by_group`, `tidy_wqp_results`,
  `tidy_gwdb_water_levels`/`tidy_gwdb_water_quality`.
- Execute all three notebooks (3, 4, 5) headlessly end-to-end:
  - NB4 produces non-empty `tceq_monitoring_locations`/`tceq_results` with plausible station counts
    within the three watersheds, and `tceq_trends` with at least some non-`"insufficient"` trends.
  - NB5 produces non-empty `twdb_wells` and at least one of `twdb_water_levels`/`twdb_water_quality`
    non-empty (groundwater coverage may be sparse in this coastal area — report actual counts,
    don't assume).
  - NB3's new trend step produces `usgs_trends` and its chart renders.
- `pixi run render` builds cleanly with the two new notebook pages; `_freeze/` updated and staged.
- Manually confirm the pH-gap caveat text in NB4 reads clearly and the unmatched-characteristics
  audit still runs.
- Confirm `data_temp/gwdb_download.zip` is git-ignored (not staged) and only the filtered
  `data/twdb_waterdata/*` products are.

## Out of scope (this round)

- TWDB's coastal surface-water data (waterdatafortexas.org Coastal API) — deferred, noted as a
  candidate for a later round.
- Continuous/instantaneous USGS data (already deferred from Round 3).
- Cross-source trend comparison, normalized/de-weathered trends, pre/post-restoration comparisons,
  the Excel deliverable — remain for a future shared display/analyze notebook.
- IBWC (Rio Grande flow/allocation) and NOAA NCEI precipitation sources.
- Resolving the TCEQ pH gap by going around WQP (e.g. scraping SWQMIS's own viewer) — documented as
  a known gap, not solved this round.
