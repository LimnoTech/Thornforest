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
# # 3 · USGS WaterData — Monitoring Stations, Parameters & Time-Series
#
# Reads the watershed boundaries from notebook 1, discovers the USGS monitoring stations
# inside them via the new USGS **Water Data** API, and records **which priority parameters**
# each station measured. Primary source & API docs: <https://api.waterdata.usgs.gov/>.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
from io import StringIO
from urllib.parse import quote

import geopandas as gpd
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the availability plots)
import pandas as pd
import async_retriever as ar
from dataretrieval import waterdata

import geoviews as gv
import geoviews.tile_sources as gvts

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
)

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Discover monitoring stations
#
# We load the watershed boundaries saved by notebook 1, ask the Water Data API for every
# station in their bounding box, then keep only those that fall **within** the watershed
# polygons (a spatial join).

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
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
save_dataframe(
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

# %% [markdown]
# ## Step 3 — Which priority parameters does each station measure?
#
# The README prioritizes these water-quality parameters, plus water-quantity (flow & level). For
# each we list the USGS `parameter_code`s (used by the time-series & field-measurement services) and
# the Water Quality characteristic-name patterns (used by the discrete-samples service) — see
# `PRIORITY_GROUPS` in `_helpers/config.py`. `classify_parameter` (from `_helpers`) maps any measured
# parameter code / characteristic to its priority group (or `None`).

# %%
SAMPLES_SUMMARY_URL = "https://api.waterdata.usgs.gov/samples-data/summary"

# Time-series metadata (daily & continuous), split by computation period; carries parameter_codes.
ts_meta, _ = waterdata.get_time_series_metadata(bbox=bbox, skip_geometry=True)
period = ts_meta["computation_period_identifier"]
daily_ids = set(ts_meta.loc[period == "Daily", "monitoring_location_id"])
continuous_ids = set(ts_meta.loc[period == "Points", "monitoring_location_id"])

# Field-measurement metadata; carries parameter_codes.
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

# %%
# parameter_code -> readable name, from the USGS reference table (verbatim source names).
parameter_name_by_code = build_parameter_name_lookup()

# Build, per station: the set of measured parameter_codes/characteristics, the priority groups they
# hit, and a sorted human-readable parameter list.
ts_parameter_codes_by_site = ts_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()
fm_parameter_codes_by_site = fm_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()

groups_by_site, params_by_site = {}, {}
for sid in station_ids:
    g, names = station_parameters(
        sid, ts_parameter_codes_by_site, fm_parameter_codes_by_site, parameter_name_by_code, samples_summaries
    )
    groups_by_site[sid] = g
    params_by_site[sid] = names

# Data-type flags (kept) + one boolean column per priority group + the readable parameter list.
sid_col = stations_in_area["monitoring_location_id"]
stations_in_area["daily"] = sid_col.isin(daily_ids)
stations_in_area["continuous"] = sid_col.isin(continuous_ids)
stations_in_area["field_measurements"] = sid_col.isin(field_ids)
stations_in_area["samples"] = sid_col.isin(samples_ids)
for group in PRIORITY_NAMES:
    stations_in_area[group] = sid_col.map(lambda s, g=group: g in groups_by_site.get(s, set()))
stations_in_area["parameters"] = sid_col.map(lambda s: params_by_site.get(s, []))

save_dataframe(
    stations_in_area,
    S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations_parameters.parquet",
)

# %% [markdown]
# ### How many stations measure each priority parameter?
#
# The audit below lists any measured parameter codes / characteristics that did NOT map to a priority
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

# %% [markdown]
# ## Step 4 — Fetch the time-series records
#
# For the stations that actually have data, fetch the **full available record** of the **priority
# parameters** from three USGS Water Data services (docs: <https://api.waterdata.usgs.gov/>) and
# save one tidy (long-format) table per data type. Daily values and field measurements filter by
# USGS `parameter_code`; discrete samples are keyed by characteristic name, so we fetch all and keep
# rows whose characteristic maps to a priority group. (Analysis later subsets to the 25-year study
# window — we keep everything.) Each `fetch_*`/`tidy_*` pair (from `_helpers/usgs.py`) is shown
# below: first the **raw** API response, then the **tidy** result actually saved.

# %%
# All priority parameter codes, flattened, for the code-keyed services (daily, field).
PRIORITY_CODES = sorted({c for spec in PRIORITY_GROUPS.values() for c in spec["parameter_codes"]})

# Reusable lookup (built from the inventory in Step 3).
huc8_by_station = dict(zip(stations_in_area["monitoring_location_id"], stations_in_area["huc8"]))

# %% [markdown]
# ### Daily values
#
# Daily statistics (mostly discharge & water level) for the stations flagged `daily`.

# %%
daily_station_ids = stations_in_area.loc[stations_in_area["daily"], "monitoring_location_id"].tolist()
daily_raw = fetch_daily(daily_station_ids, PRIORITY_CODES)
show(daily_raw.head())  # peek at the raw USGS response shape before we tidy it

# %%
# Tidy to a long-format table tagged with priority_group / parameter_name / huc8 (see _helpers/usgs.py).
daily = tidy_daily(daily_raw, huc8_by_station, parameter_name_by_code)
show(daily.head())
save_dataframe(daily, S.data_dir / "usgs_waterdata" / "usgs_daily_values.parquet")

# %% [markdown]
# ### Discrete water-quality samples
#
# Lab samples for the stations flagged `samples`. The samples service is keyed by characteristic
# **name**, so we fetch all results per station and keep those whose characteristic maps to one of
# our priority groups via `classify_parameter`.

# %%
samples_station_ids = stations_in_area.loc[stations_in_area["samples"], "monitoring_location_id"].tolist()
samples_raw = fetch_samples(samples_station_ids)
show(samples_raw.head())  # peek at the raw USGS response shape before we tidy it

# %%
samples = tidy_samples(samples_raw, huc8_by_station)
show(samples.head())
save_dataframe(samples, S.data_dir / "usgs_waterdata" / "usgs_samples.parquet")

# %% [markdown]
# ### Field measurements
#
# In-situ readings (temperature, DO, pH, conductivity, turbidity, …) for the stations flagged
# `field_measurements`.

# %%
field_station_ids = stations_in_area.loc[stations_in_area["field_measurements"], "monitoring_location_id"].tolist()
field_raw = fetch_field(field_station_ids, PRIORITY_CODES)
show(field_raw.head())  # peek at the raw USGS response shape before we tidy it

# %%
field = tidy_field(field_raw, huc8_by_station, parameter_name_by_code)
show(field.head())
save_dataframe(field, S.data_dir / "usgs_waterdata" / "usgs_field_measurements.parquet")

# %% [markdown]
# ## Step 5 — Map stations by priority parameter
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
    data_aspect=1,
    title="Monitoring stations by priority parameter (click legend to toggle)",
    legend_position="right",
    hooks=[make_legend_clickable],
)
stations_param_map

# %% [markdown]
# ## Step 6 — Data availability & a sample series
#
# Confirm the fetch: per data type, how many records and what date span each station × priority
# group has, a quick availability heatmap, and one illustrative series. (Trend and pre/post
# analyses live in the later display notebooks.)

# %%
show(coverage(daily, "date"))

# %%
show(coverage(samples, "datetime"))

# %%
show(coverage(field, "datetime"))

# %%
# Daily-value availability: record count per station per year.
daily_year = daily.assign(year=pd.to_datetime(daily["date"]).dt.year)
availability = daily_year.groupby(["monitoring_location_id", "year"]).size().reset_index(name="records")
availability.hvplot.heatmap(
    x="year", y="monitoring_location_id", C="records", cmap="blues",
    title="Daily-value record availability (count per station-year)", colorbar=True, rot=45,
)

# %%
# Illustrative series: daily discharge at the station with the most discharge records.
discharge = daily[daily["priority_group"] == "discharge"].copy()
if discharge.empty:
    sample_series = None
    print("No discharge records found — skipping sample series.")
else:
    gauge = discharge.groupby("monitoring_location_id").size().idxmax()
    series = discharge[discharge["monitoring_location_id"] == gauge].assign(
        value=lambda d: pd.to_numeric(d["value"], errors="coerce")
    )
    sample_series = series.hvplot.line(
        x="date", y="value", title=f"Daily mean discharge — {gauge}", ylabel="ft³/s", xlabel="",
    )
sample_series
