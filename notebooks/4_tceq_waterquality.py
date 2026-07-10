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
# Reads the watershed boundaries from notebook 1, discovers **Texas Commission on Environmental
# Quality (TCEQ)** **Surface Water Quality Monitoring (SWQM)** stations inside them, and fetches
# their results. TCEQ has no public API of its own — SWQMIS data is submitted to the **U.S.
# Environmental Protection Agency (EPA)** **Water Quality Portal (WQP)** under organization
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

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Discover monitoring stations
#
# `wqp.what_sites` returns a **plain DataFrame** (unlike `dataretrieval.waterdata`, WQP has no
# built-in geometry column) — we build one from its lat/long columns, then keep only stations
# **within** the watershed polygons, exactly as notebook 3 does for USGS stations.
#
# > **Caching note:** `dataretrieval.wqp` makes its own HTTP requests, bypassing the on-disk
# > request cache (`cache/`) HyRiver calls use — so instead we treat the saved
# > `tceq_monitoring_locations.parquet` itself as a **backup cache** (`load_dataframe`, one-week
# > freshness window): if it's still fresh, we load it and skip the network call entirely.

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

stations_path = S.data_dir / "tceq_waterquality" / "tceq_monitoring_locations.parquet"
stations_in_area = load_dataframe(stations_path, max_age_days=7)
stations_were_cached = stations_in_area is not None
if not stations_were_cached:
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
# filter **after** fetching than to guess before. This is the slow step (~1-2 minutes), so it's the
# one most worth caching — same `load_dataframe`-as-backup-cache approach as Step 2.

# %%
results_path = S.data_dir / "tceq_waterquality" / "tceq_results.parquet"
raw_results = None
tceq_results = load_dataframe(results_path, max_age_days=7)
if tceq_results is None:
    raw_results = fetch_wqp_results(bbox, organization="TCEQMAIN")
    show(raw_results.head())  # peek at the raw WQP response shape before we tidy it

# %% [markdown]
# ## Step 4 — Tidy and classify by priority parameter
#
# `tidy_wqp_results` renames WQP's columns to the project's convention, keeps only rows whose
# `characteristic` maps to one of our priority groups (`classify_parameter`), and tags
# `priority_group`/`huc8`. Skipped when `tceq_results` already came from the cache above.

# %%
huc8_by_station = dict(zip(stations_in_area["MonitoringLocationIdentifier"], stations_in_area["huc8"]))
if tceq_results is None:
    tceq_results = tidy_wqp_results(raw_results, huc8_by_station)
    show(tceq_results.head())
    save_dataframe(tceq_results, results_path)

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
# Only re-save if something was actually fetched fresh above (stations or results) — otherwise
# both came straight from cache and touching the file would reset its own freshness clock for
# nothing.
if not stations_were_cached or raw_results is not None:
    save_dataframe(stations_in_area, stations_path)

print(f"Stations by priority parameter (of {len(stations_in_area)}):")
print(stations_in_area[PRIORITY_NAMES].sum().to_string())

if raw_results is not None:
    unmatched = sorted({
        str(c) for c in raw_results["CharacteristicName"].dropna().unique()
        if classify_parameter(characteristic=c) is None
    })
    print(f"\n{len(unmatched)} unmatched characteristics (first 25):")
    print("\n".join(unmatched[:25]))
else:
    print("\n(unmatched-characteristics audit skipped — tceq_results came from the cache, not a fresh fetch)")

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
save_dataframe(tceq_trends, S.data_dir / "tceq_waterquality" / "tceq_trends.parquet")
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

# %% [markdown]
# ## What's next
#
# TCEQ results, station inventory, and trends are saved under `data/tceq_waterquality/`. Notebook
# **`5_twdb_waterdata`** covers TWDB groundwater; a future shared display notebook can compare
# trends across USGS/TCEQ/TWDB side by side.
